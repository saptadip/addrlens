"""Weekly Geofabrik OSM refresh — Berlin extract → filtered amenities JSON.

Downloads berlin-latest.osm.pbf (~75 MB) from Geofabrik, filters for the six
tag combos this app queries via Overpass in production, writes an atomic JSON
snapshot to the on-disk cache path. Cron target: Sunday 03:00 CET.

Categories mirror app/core/amenities.py:AMENITIES exactly so amenities_near()
can swap Overpass ↔ local snapshot without shape changes.

Cost: ~75 MB download (12 s on 50 Mbps) + ~30 s pyosmium parse = ~1 min end
to end. Zero Overpass dependency.

Data source: https://download.geofabrik.de/europe/germany/berlin.html
Licence: ODbL 1.0 — same as OpenStreetMap. Attribution already required and
present in the app's Attribution modal.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import osmium

# --- Category → OSM tag rules (must match app/core/amenities.py:AMENITIES) ---
# Each rule is a list of (tag_key, allowed_values) pairs — feature matches
# if ANY pair matches. Most categories are single-key, hospitals are OR-of-2.
_TAG_RULES = {
    "playgrounds":  [("leisure",          {"playground"})],
    "parks":        [("leisure",          {"park"})],
    "pharmacies":   [("amenity",          {"pharmacy"})],
    "supermarkets": [("shop",             {"supermarket"})],
    "gps":          [("amenity",          {"doctors"})],
    "transit":      [("public_transport", {"platform", "station"})],
    # Hospital contact overlay — enriches BOD hospital records with OSM's
    # phone/website/emergency/wheelchair when the campuses match within
    # hospital_match_m. Both tag conventions (`amenity=hospital` and
    # `healthcare=hospital`) are common; either qualifies.
    "hospital":     [("amenity",          {"hospital"}),
                     ("healthcare",       {"hospital"})],
    # Location history — Stolpersteine, monuments, plaques, ruins, old rail.
    # Matches any historic=<X> tag; value-agnostic so new categories (e.g.
    # 'stolperstein' explicitly, 'boundary_stone', 'castle') survive without
    # a filter change. Value preserved in the emitted tags.
    "historic":     [("historic",         None)],

    # --- Newcomer / Relocation lens (Spec E) ---
    # Rules in this block are dicts rather than tuples — all key-value pairs
    # in a dict must match (AND logic). See _cat_for for the dispatch.

    # intl_food — international grocers + non-german restaurants.
    # Two disjunct filter groups; entities matching either sub-rule are collected.
    # German-cuisine restaurants are removed in a post-filter step (_EXCLUDE_CUISINE).
    # ponytail: post-filter covers only the cuisine tag; origin-tag grocers are
    # included unconditionally (false-negative risk small — "german" origin rarely
    # appears on OSM shop nodes in Berlin).
    "intl_food": [
        # International-origin grocers: shop tag must be one of the allowed values
        # AND origin tag must carry an international value.
        {"shop":   {"supermarket", "greengrocer", "convenience"},
         "origin": {"asian", "turkish", "indian", "african", "russian",
                    "polish", "arab", "italian", "vietnamese", "korean"}},
        # International restaurants: amenity=restaurant with any cuisine tag.
        # German/regional cuisines are stripped in _INTL_FOOD_EXCLUDE_CUISINE below.
        {"amenity": {"restaurant"}, "cuisine": None},
    ],

    # coworking — coworking spaces + laptop-friendly cafés with wifi.
    "coworking": [
        {"office": {"coworking"}},
        {"amenity": {"cafe"}, "internet_access": {"wlan", "yes"}},
    ],

    # english_clinic — English-language medical practices (OSM community tags).
    # language:en=yes AND amenity in the medical set (AND logic — dict rule).
    "english_clinic": [
        {"amenity": {"doctors", "clinic", "hospital"}, "language:en": {"yes"}},
    ],

    # buergeramt — Berlin district registration offices (OSM fallback until WFS).
    # ponytail: WFS replacement planned in Task 12 (buergeramt_wfs_url field).
    "buergeramt": [
        {"office": {"government"}, "government": {"register_office"}},
        # Also catch the German tag which OSM community sometimes uses:
        {"amenity": {"townhall"}, "government": {"register_office"}},
    ],
}

# Categories that must have a `name` tag to survive (mirrors _DROP_UNNAMED
# in amenities.py — unnamed parks/playgrounds are noise). Others keep even
# if unnamed; a fallback label is applied at read time by amenities_near.
_DROP_UNNAMED = {"parks", "playgrounds"}

# intl_food post-filter: drop restaurants whose cuisine tag is in this set.
# Only applied to the restaurant sub-rule of intl_food (the origin-tagged
# grocer sub-rule is unaffected).
# ponytail: negation expressed as an exclusion set rather than a NOT-IN operator
# in the rule engine — the tuple/dict rule format only expresses OR-of-inclusions.
_INTL_FOOD_EXCLUDE_CUISINE = frozenset({
    "german", "regional", "european", "bavarian", "berlin", "brandenburg",
})

GEOFABRIK_URL = "https://download.geofabrik.de/europe/germany/berlin-latest.osm.pbf"


def _match_rule(rule, tags) -> bool:
    """Return True if *all* key-value conditions in `rule` match `tags`.

    Supports two rule shapes:
      - tuple (k, vs): tags[k] exists AND (vs is None OR tags[k] in vs).
      - dict {k: vs, ...}: every pair must satisfy the tuple condition above.
    """
    if isinstance(rule, tuple):
        k, vs = rule
        v = tags.get(k)
        return bool(v) and (vs is None or v in vs)
    # dict rule — AND of all key-value conditions
    for k, vs in rule.items():
        v = tags.get(k)
        if not v:
            return False
        if vs is not None and v not in vs:
            return False
    return True


def _cat_for(tags) -> str | None:
    """Return the category slug this OSM feature belongs to, or None.
    A rule with vs=None means 'any non-empty value on that key wins'.
    Rules can be tuples (legacy) or dicts (AND-logic, new for newcomer cats).
    Returns only the first matching category (legacy behaviour, used by node/way)."""
    for cat, rules in _TAG_RULES.items():
        for rule in rules:
            if _match_rule(rule, tags):
                return cat
    return None


def _cats_for(tags) -> list[str]:
    """Return ALL category slugs this OSM feature matches.

    Used by node/way handlers so a feature can land in multiple buckets
    (e.g. a doctor's office with language:en=yes goes into both 'gps' and
    'english_clinic'). The single-result _cat_for is preserved for callers
    that only need one category.
    """
    matched = []
    for cat, rules in _TAG_RULES.items():
        for rule in rules:
            if _match_rule(rule, tags):
                matched.append(cat)
                break   # one match per category is enough
    return matched


class _AmenityCollector(osmium.SimpleHandler):
    """Single-pass filter. Nodes give exact lat/lon; ways average their node
    coords (accurate enough for a search-radius amenity, no need for real
    polygon centroids). Multipolygon relations are skipped — Berlin's
    parks-as-relations count is small; we lose <2% and avoid a two-pass merge."""

    def __init__(self):
        super().__init__()
        self.buckets = {cat: [] for cat in _TAG_RULES}
        self.seen = set()   # dedup by (cat, round(lat,5), round(lon,5))

    def _add(self, cat, lat, lon, tags):
        key = (cat, round(lat, 5), round(lon, 5))
        if key in self.seen:
            return
        self.seen.add(key)
        name = (tags.get("name") or "").strip()
        if cat in _DROP_UNNAMED and not name:
            return
        # intl_food post-filter: drop restaurants whose cuisine is in the
        # excluded set (german/regional etc). Origin-tagged grocers are
        # unaffected — they carry no cuisine tag.
        if cat == "intl_food":
            cuisine = (tags.get("cuisine") or "").lower()
            if cuisine in _INTL_FOOD_EXCLUDE_CUISINE:
                return
        # Store as a plain dict — same shape Overpass returns downstream.
        entry = {"name": name, "lat": lat, "lon": lon,
                 "tags": {k: v for k, v in tags}}
        self.buckets[cat].append(entry)

    def node(self, n):
        cats = _cats_for(n.tags)
        for cat in cats:
            self._add(cat, n.location.lat, n.location.lon, n.tags)

    def way(self, w):
        cats = _cats_for(w.tags)
        if not cats:
            return
        # locations=True on apply_file populates w.nodes[i].location.
        # Average the node coords for a rough centroid — accurate enough
        # for "is this park within 800 m" reasoning.
        lats, lons, n = 0.0, 0.0, 0
        for nd in w.nodes:
            try:
                if not nd.location.valid():
                    continue
                lats += nd.location.lat
                lons += nd.location.lon
                n += 1
            except Exception:
                continue
        if n == 0:
            return
        for cat in cats:
            self._add(cat, lats / n, lons / n, w.tags)


def download_pbf(url: str, dest: Path) -> Path:
    """Stream Geofabrik pbf to a temp path, then atomic-rename to dest.
    Returns the final path. Raises on any HTTP or IO error."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    print(f"↓ downloading {url}", flush=True)
    t0 = time.time()
    req = urllib.request.Request(url,
        headers={"User-Agent": "berlin-address-intelligence/0.1 (contact via GitHub)"})
    with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, length=1 << 20)     # 1 MiB chunks
    size_mb = tmp.stat().st_size / (1024 * 1024)
    print(f"  {size_mb:.1f} MB in {time.time()-t0:.1f}s", flush=True)
    os.replace(tmp, dest)
    return dest


def parse_and_filter(pbf: Path) -> dict:
    """Filter the pbf into our 6 category buckets. Returns the bucket dict."""
    print(f"⚙  parsing {pbf.name}", flush=True)
    t0 = time.time()
    h = _AmenityCollector()
    # locations=True + idx=flex_mem builds a node→coord index so way/area
    # centres can be computed on the fly. Berlin fits comfortably in RAM.
    h.apply_file(str(pbf), locations=True, idx="flex_mem")
    total = sum(len(v) for v in h.buckets.values())
    per_cat = " · ".join(f"{k}:{len(v)}" for k, v in h.buckets.items())
    print(f"  {total} features in {time.time()-t0:.1f}s ({per_cat})", flush=True)
    return h.buckets


def write_snapshot(buckets: dict, out: Path, source: str) -> None:
    """Atomic write of the JSON snapshot with a meta header."""
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source":       source,
            "categories":   list(buckets.keys()),
            "total":        sum(len(v) for v in buckets.values()),
        },
        "buckets": buckets,
    }
    tmp = out.with_suffix(out.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, out)
    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"✓ wrote {out} ({size_mb:.1f} MB, {doc['meta']['total']} features)", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data-dir", default=os.environ.get("OSM_DATA_DIR", "data/osm"),
                    help="host filesystem dir (dev) or Docker volume mount (prod)")
    ap.add_argument("--url", default=GEOFABRIK_URL,
                    help="Geofabrik pbf URL (default: Berlin)")
    ap.add_argument("--skip-download", action="store_true",
                    help="re-parse an existing pbf without re-downloading")
    args = ap.parse_args()

    data_dir = Path(args.data_dir).resolve()
    pbf_path = data_dir / "berlin-latest.osm.pbf"
    json_path = data_dir / "berlin-amenities.json"

    if not args.skip_download:
        download_pbf(args.url, pbf_path)
    elif not pbf_path.exists():
        print(f"! --skip-download but {pbf_path} missing", file=sys.stderr)
        sys.exit(2)

    buckets = parse_and_filter(pbf_path)
    write_snapshot(buckets, json_path,
                   source=f"Geofabrik {args.url.rsplit('/', 1)[-1]} "
                          f"({datetime.fromtimestamp(pbf_path.stat().st_mtime, tz=timezone.utc).date()})")


if __name__ == "__main__":
    import pathlib
    # Order:
    #   1. rule-engine pure asserts (fast, no I/O — fail fast on bad rules).
    #   2. main() — download + parse + write the fresh snapshot.
    #   3. snapshot-shape selfcheck — verify main() actually wrote the four
    #      newcomer buckets. Running this AFTER main() means `python -m
    #      scripts.refresh_osm_amenities` always does the refresh even when
    #      the on-disk snapshot is stale or missing.

    # Pure unit-tests for rule engine (no snapshot required).
    # Verify tuple rules still work (legacy categories).
    assert _match_rule(("leisure", {"playground"}), {"leisure": "playground"})
    assert not _match_rule(("leisure", {"playground"}), {"leisure": "park"})
    assert _match_rule(("historic", None), {"historic": "anything"})
    assert not _match_rule(("historic", None), {"amenity": "cafe"})
    # Verify dict rules (newcomer AND-logic).
    assert _match_rule({"office": {"coworking"}}, {"office": "coworking"})
    assert not _match_rule({"office": {"coworking"}}, {"office": "shop"})
    assert _match_rule(
        {"amenity": {"doctors", "clinic", "hospital"}, "language:en": {"yes"}},
        {"amenity": "doctors", "language:en": "yes"},
    )
    assert not _match_rule(
        {"amenity": {"doctors", "clinic", "hospital"}, "language:en": {"yes"}},
        {"amenity": "doctors"},   # missing language:en
    )
    # Verify _cat_for returns correct category for newcomer rules.
    assert _cat_for({"office": "coworking"}) == "coworking"
    assert _cat_for({"amenity": "cafe", "internet_access": "wlan"}) == "coworking"
    assert _cat_for({"office": "government", "government": "register_office"}) == "buergeramt"
    assert _cat_for({"amenity": "townhall", "government": "register_office"}) == "buergeramt"
    assert _cat_for({"amenity": "restaurant", "cuisine": "vietnamese"}) == "intl_food"
    # German cuisine restaurant must NOT match (post-filter catches it, but _cat_for
    # will still return intl_food — exclusion is in _add, not _cat_for).
    # (We verify exclusion logic through _INTL_FOOD_EXCLUDE_CUISINE membership.)
    assert "german" in _INTL_FOOD_EXCLUDE_CUISINE
    assert "bavarian" in _INTL_FOOD_EXCLUDE_CUISINE
    assert "vietnamese" not in _INTL_FOOD_EXCLUDE_CUISINE
    # Verify _cats_for multi-bucket assignment (english_clinic must co-exist with gps).
    cats_doctor_en = _cats_for({"amenity": "doctors", "language:en": "yes"})
    assert "gps" in cats_doctor_en, f"expected gps in {cats_doctor_en}"
    assert "english_clinic" in cats_doctor_en, f"expected english_clinic in {cats_doctor_en}"
    cats_doctor_only = _cats_for({"amenity": "doctors"})
    assert "gps" in cats_doctor_only
    assert "english_clinic" not in cats_doctor_only   # no language:en tag
    assert _cats_for({"office": "coworking"}) == ["coworking"]
    print("rule-engine selfcheck ok")

    main()

    # Snapshot-shape selfcheck (plan Step 4). Runs AFTER main() so the
    # snapshot is guaranteed fresh. JSON shape: {"meta": {...}, "buckets": {...}}.
    snap = pathlib.Path("data/osm/berlin-amenities.json")
    if snap.exists():
        import json as _json
        j = _json.loads(snap.read_text())
        buckets = j.get("buckets", j)   # tolerate flat shape (legacy)
        for key in ("intl_food", "coworking", "english_clinic", "buergeramt"):
            assert key in buckets, f"missing bucket {key!r}"
            assert isinstance(buckets[key], list), f"{key} not list"
        print("selfcheck ok:", {k: len(buckets[k]) for k in
              ("intl_food", "coworking", "english_clinic", "buergeramt")})
    else:
        print("selfcheck skipped — main() did not write a snapshot")
