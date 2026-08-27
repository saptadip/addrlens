"""In-memory prefix index over Berlin addresses for /api/suggest.

Loads a JSON snapshot produced by `scripts/refresh_osm_amenities.py` at boot
and answers prefix-match queries in a few microseconds. No external calls
on the hot path — the endpoint that reads this can safely be rate-limited
loose because a match costs essentially nothing.

Design notes
------------
- The source data is OSM `addr:street` + `addr:housenumber` (+ optional
  `addr:postcode`). Berlin has ~350k addressed nodes/ways; the loaded
  index takes ~30 MB in memory. Load time on a CX22 is ~200 ms.
- The primary key is `(normalised_street, hnr, plz)`. A single street name
  in OSM can appear with multiple casings and accents (e.g. "Bergmannstr.",
  "Bergmannstraße", "bergmannstrasse"). Normalisation folds all of these
  onto a single sortable string so a prefix match on "bergmann" catches
  every spelling.
- Ranking is intentionally simple for v1: (a) exact prefix on the
  normalised full label wins over prefix on street-only, (b) shorter
  matches win over longer ones, (c) alphabetic within a tie. No fuzzy
  Levenshtein, no popularity — those can layer on later without changing
  the endpoint contract.
- The query is also normalised the same way. "Bergmannstr" and "bergmann
  Str." return the same result set.
"""
from __future__ import annotations

import bisect
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class AddressHit:
    """One row returned by AddressIndex.search()."""
    street: str          # canonical display form ("Bergmannstraße")
    hnr:    str          # house number as-is ("27", "27A", "27a")
    plz:    str          # 5-digit postal code, or empty
    lat:    float
    lon:    float
    label:  str          # what the UI shows, e.g. "Bergmannstraße 27, 10961"


# --- Normalisation ---------------------------------------------------------

# German street convention: "-str.", "-straße", or "-strasse" is always a
# WORD SUFFIX inside a compound ("Bergmannstr."). Leading `\b` would break
# the common fused form because the boundary sits inside the word. Use only
# a trailing lookahead — end-of-string OR whitespace/punct — which prevents
# accidental hits inside unrelated words (e.g. "district" is followed by
# more letters, not `[\s,.-]`, so no match).
_STR_SUFFIX_RE = re.compile(
    r"(str\.?|straße|strasse|strasze)(?=$|[\s,.-])",
    flags=re.IGNORECASE,
)


def _normalise(s: str) -> str:
    """Fold umlauts, ß, and street abbreviations onto a single canonical form
    so casing / spelling differences do not fragment the prefix index.

    - Lowercase.
    - ß → ss.
    - Unicode NFKD → strip combining marks (ä → a, ö → o, ü → u, é → e).
    - "Bergmannstr." / "Bergmannstraße" / "Bergmannstrasse" all → "bergmannstrasse".
    - Collapse whitespace runs to a single space; strip.
    """
    if not s:
        return ""
    s = s.lower().replace("ß", "ss")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = _STR_SUFFIX_RE.sub("strasse", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _build_label(street: str, hnr: str, plz: str) -> str:
    """Compose the user-facing address string. Kept in the display casing —
    only the search key is normalised."""
    parts = [f"{street} {hnr}".strip()]
    if plz:
        parts.append(plz)
    return ", ".join(p for p in parts if p)


# --- Index -----------------------------------------------------------------


class AddressIndex:
    """Sorted list of (normalised_key, AddressHit). Binary-search prefix lookup."""

    def __init__(self, rows: Iterable[dict]):
        # Deduplicate on the normalised label — different OSM nodes commonly
        # tag the same building twice with slight coordinate jitter.
        seen: set[str] = set()
        entries: list[tuple[str, AddressHit]] = []
        for r in rows:
            street = (r.get("street") or "").strip()
            hnr    = (r.get("hnr")    or "").strip()
            plz    = (r.get("plz")    or "").strip()
            if not street or not hnr:
                continue
            try:
                lat = float(r["lat"])
                lon = float(r["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            label = _build_label(street, hnr, plz)
            key   = _normalise(label)
            if key in seen:
                continue
            seen.add(key)
            entries.append((key, AddressHit(
                street=street, hnr=hnr, plz=plz,
                lat=lat, lon=lon, label=label,
            )))
        entries.sort(key=lambda t: t[0])
        self._keys:    list[str]        = [k for k, _ in entries]
        self._entries: list[AddressHit] = [e for _, e in entries]

    def __len__(self) -> int:
        return len(self._entries)

    def search(self, q: str, limit: int = 8) -> list[AddressHit]:
        """Return up to `limit` addresses whose normalised label starts with
        the normalised `q`. Empty query → []."""
        if not q or limit <= 0:
            return []
        norm = _normalise(q)
        if not norm:
            return []
        # Binary search for the range of keys starting with `norm`.
        lo = bisect.bisect_left(self._keys, norm)
        # `norm + '￿'` is the exclusive upper bound of the prefix range.
        hi = bisect.bisect_left(self._keys, norm + "￿")
        # Slice + shorten. Already alphabetic thanks to the sorted list, which
        # means Bergmannstraße 27 comes before Bergmannstraße 271.
        return self._entries[lo:min(lo + limit, hi)]


def load_address_index(path: Optional[str]) -> Optional[AddressIndex]:
    """Load addresses from `path` (a JSON list of {street, hnr, plz, lat, lon})
    into an AddressIndex, or return None when the path is unset / missing.
    Missing file is not fatal — /api/suggest just returns [] until the next
    refresh."""
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    with p.open(encoding="utf-8") as f:
        rows = json.load(f)
    if not isinstance(rows, list):
        return None
    return AddressIndex(rows)


if __name__ == "__main__":
    # Pure selfcheck — no I/O.
    idx = AddressIndex([
        {"street": "Bergmannstraße", "hnr": "27",  "plz": "10961",
         "lat": 52.48864, "lon": 13.39631},
        {"street": "Bergmannstraße", "hnr": "271", "plz": "10961",
         "lat": 52.48865, "lon": 13.39632},
        {"street": "Bergmannstr.",   "hnr": "27",  "plz": "10961",
         "lat": 52.48864, "lon": 13.39631},   # dup after normalisation
        {"street": "Kastanienallee", "hnr": "12",  "plz": "10435",
         "lat": 52.53555, "lon": 13.40587},
        {"street": "Sybelstraße",    "hnr": "59",  "plz": "10629",
         "lat": 52.50632, "lon": 13.31069},
    ])

    # Dedup: "Bergmannstr. 27" folded onto "Bergmannstraße 27" as a normal
    # collision → only one entry kept.
    assert len(idx) == 4, f"expected 4 unique rows, got {len(idx)}"

    # Umlaut + street-suffix normalisation: "berg" → both Bergmannstraße rows
    hits = idx.search("berg", limit=5)
    assert len(hits) == 2, hits
    assert hits[0].label == "Bergmannstraße 27, 10961"
    assert hits[1].label == "Bergmannstraße 271, 10961"

    # Alternate spelling of the query — same results.
    assert [h.label for h in idx.search("bergmannstr", limit=5)] == \
        [h.label for h in idx.search("Bergmannstraße", limit=5)]

    # Full-label prefix wins nothing extra here but limit works.
    assert len(idx.search("bergmann", limit=1)) == 1

    # Non-matching prefix.
    assert idx.search("zzz") == []

    # Empty query short-circuits.
    assert idx.search("") == []
    assert idx.search("Kastanien")[0].label == "Kastanienallee 12, 10435"

    # Sybelstraße + variant spelling ("Sybelstrasse") → same hit.
    assert idx.search("sybelstrasse")[0].label == "Sybelstraße 59, 10629"

    # load_address_index with None / missing file is graceful.
    assert load_address_index(None) is None
    assert load_address_index("/nonexistent-path.json") is None
    print("address_index.py selfcheck OK")
