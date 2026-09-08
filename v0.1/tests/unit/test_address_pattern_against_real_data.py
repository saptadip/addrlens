"""Regression test: real Berlin street data must pass the API allow-lists.

The `/api/lookup` and `/api/suggest` character allow-lists (see
`app/routes/lookup.py` and `app/routes/suggest.py`) are meant to reject
XSS-adjacent punctuation while accepting every diacritic that appears in
real Berlin street names. An earlier iteration accepted only `ÄÖÜäöüß`
and silently 422'd streets containing é, è, á, Ś, İ, … This test loads
a sample of Geofabrik-derived Berlin data and asserts every non-empty
candidate passes the exact same Rust regex engine used by production
(`pydantic-core`'s `str_pattern`, same engine that FastAPI's
`Query(pattern=...)` uses). Any future "cleanup" of the pattern that
re-narrows it will fail here before it ships.

Sample scope
------------
The patterns validate what a user types into the search box: **street
addresses** and **address-shaped query strings**. This test therefore
walks the address-tagged POI subset (`tags["addr:street"]` /
`["addr:postcode"]`), which is exactly the shape of the AddressIndex
snapshot that feeds `/api/suggest` in production. POI display names
are *not* asserted because playground names like `Spielplatz "Elefant"`
carry double quotes that the pattern legitimately rejects — and users
never type those into the address box.

The snapshot at `v0.1/data/osm/berlin-amenities.json` is git-ignored;
when missing the test skips (rather than fails) so CI on a fresh clone
without local data still passes.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator

import pytest
from pydantic import BaseModel, Field, ValidationError

# Import the exact pattern constants used by the routes. Any drift in
# these will surface as ImportError here, which is the whole point.
from app.routes.lookup import _ADDR_CHARS, _HNR_CHARS, _PLZ_CHARS
from app.routes.suggest import _Q_CHARS

_DATA = (Path(__file__).resolve().parent.parent.parent
         / "data" / "osm" / "berlin-amenities.json")

# Cap the sample so a snapshot growth doesn't slow the suite. 5 000
# strings through the Rust regex engine runs in well under a second.
_SAMPLE_CAP = 5000


# --- Pydantic models pinned to the exact production regex engine ----------
# `Field(pattern=...)` compiles through pydantic-core → Rust `regex` crate,
# which is the same engine FastAPI uses for `Query(pattern=...)`. Testing
# via Python's `re` would not catch Rust-vs-Python regex-dialect drift
# (e.g. the anchoring differences that motivated `^...$` in the routes).

class _Addr(BaseModel):
    v: str = Field(pattern=_ADDR_CHARS, max_length=200)


class _Q(BaseModel):
    v: str = Field(pattern=_Q_CHARS, max_length=100)


class _Hnr(BaseModel):
    v: str = Field(pattern=_HNR_CHARS, max_length=10)


class _Plz(BaseModel):
    v: str = Field(pattern=_PLZ_CHARS, max_length=5)


def _load_amenities() -> dict:
    if not _DATA.exists():
        pytest.skip(f"snapshot not found: {_DATA}")
    with _DATA.open(encoding="utf-8") as f:
        return json.load(f)


def _iter_streets(payload: dict) -> Iterator[tuple[str, str]]:
    """Yield (bucket, addr:street) for every POI carrying a street tag.

    Snapshot shape: `{ "buckets": { name: [ { "tags": { "addr:street": ... } } ] } }`.
    """
    for bucket, items in (payload.get("buckets") or {}).items():
        if not isinstance(items, list):
            continue
        for item in items:
            tags = item.get("tags") or {}
            street = (tags.get("addr:street") or "").strip()
            if street:
                yield bucket, street


def _iter_plz(payload: dict) -> Iterator[str]:
    for _bucket, items in (payload.get("buckets") or {}).items():
        if not isinstance(items, list):
            continue
        for item in items:
            tags = item.get("tags") or {}
            plz = (tags.get("addr:postcode") or "").strip()
            if plz:
                yield plz


# --- Tests ----------------------------------------------------------------

def test_addr_pattern_accepts_real_berlin_streets():
    """Every real Berlin `addr:street` value must pass `_ADDR_CHARS`
    and `_Q_CHARS`. A regression here means real users typing a street
    name they saw on a map would see a 422.

    Ground truth: v0.1/data/osm/berlin-amenities.json — the weekly
    Geofabrik OSM snapshot's `addr:street` tags. This is the same
    provenance that feeds the AddressIndex snapshot backing
    /api/suggest in production.
    """
    payload = _load_amenities()
    seen = 0
    rejected: list[tuple[str, str, str]] = []
    for bucket, street in _iter_streets(payload):
        if seen >= _SAMPLE_CAP:
            break
        seen += 1
        # Route own cap is 100 (suggest) / 200 (lookup) — skip anything
        # over 200 as a max_length concern, not a pattern concern.
        if len(street) > 200:
            continue
        try:
            _Addr(v=street)
        except ValidationError as e:
            rejected.append((bucket, street, str(e).splitlines()[0]))
            continue
        # Autocomplete /api/suggest is capped at 100 — only exercise
        # `_Q_CHARS` below that length.
        if len(street) <= 100:
            try:
                _Q(v=street)
            except ValidationError as e:
                rejected.append((bucket, street, "suggest: "
                                 + str(e).splitlines()[0]))
    assert seen > 0, "sample was empty — snapshot shape may have changed"
    assert not rejected, (
        f"{len(rejected)} real Berlin streets rejected by pattern; first 5:\n"
        + "\n".join(f"  [{b}] {n!r} — {err}"
                    for b, n, err in rejected[:5])
    )


def test_plz_pattern_accepts_real_berlin_postcodes():
    """Every real Berlin `addr:postcode` value must pass `_PLZ_CHARS`
    (i.e. exactly 5 digits). Guards against `_PLZ_CHARS` regressing
    independently of `_ADDR_CHARS`.
    """
    payload = _load_amenities()
    seen = 0
    rejected: list[str] = []
    for plz in _iter_plz(payload):
        if seen >= _SAMPLE_CAP:
            break
        seen += 1
        if len(plz) > 5:
            # OSM occasionally carries "10115;10117" — production would
            # reject on max_length, not on pattern, so skip.
            continue
        try:
            _Plz(v=plz)
        except ValidationError:
            rejected.append(plz)
    if seen == 0:
        pytest.skip("no addr:postcode tags in snapshot")
    assert not rejected, (
        f"{len(rejected)} real Berlin PLZs rejected; first 5: "
        + ", ".join(repr(p) for p in rejected[:5])
    )
