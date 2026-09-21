"""Regression guard for trees_bbox geometry unpacking.

PR follow-up: prod deploy hit 500 on /api/lookup for Hamburg addresses
because Hamburg's Baumkataster returns MultiPoint geometries (each tree
wrapped as `{"type": "MultiPoint", "coordinates": [[lon, lat]]}`), and
the old code did `lo, la = g["coordinates"]` — ValueError on the outer
1-element list.

Berlin's Baumbestand uses plain Point (`{"type": "Point", "coordinates":
[lon, lat]}`), so this test asserts both shapes work without regressing
Berlin.

The full trees_bbox call path is heavy (WFS network + bbox + summary
math). Test here only the geometry-parsing branch of the loop by stubbing
wfs() with a small feature set.
"""
from unittest.mock import patch

from app.core.index import Index


class _StubCfg:
    """Minimal CityConfig-shaped stub with just the fields trees_bbox reads."""
    slug = "test"
    trees_wfs_url = "https://example/wfs"
    trees_layer = "example:trees"
    trees_radius_m = 200
    wfs_output_format = "application/json"
    wfs_srs_name = "EPSG:4326"
    trees_field_map = {
        "species_de": "art_deutsch",
        "genus_de": "gattung_deutsch",
        "group": "gattung",
        "height": "hoehe",
        "age": "alter",
        "planting_year": "pflanzjahr",
        "street": "strasse",
    }


def _stub_index() -> Index:
    """Construct Index without triggering __init__ (which does network I/O)."""
    idx = Index.__new__(Index)
    idx.cfg = _StubCfg()
    return idx


_POINT_FEATURE = {
    "geometry": {"type": "Point", "coordinates": [13.4001, 52.5001]},
    "properties": {"art_deutsch": "Linde", "gattung_deutsch": "Tilia",
                   "gattung": "Tilia", "hoehe": "12", "alter": "40",
                   "pflanzjahr": "1985", "strasse": "Musterstr."},
}

_MULTIPOINT_FEATURE = {
    "geometry": {"type": "MultiPoint", "coordinates": [[10.0319, 53.5444]]},
    "properties": {"art_deutsch": "Ahorn", "gattung_deutsch": "Acer",
                   "gattung": "Acer", "hoehe": "8", "alter": "25",
                   "pflanzjahr": "2000", "strasse": "Heidenkampsweg"},
}


def test_trees_bbox_handles_point_geometry():
    """Berlin path — Baumbestand returns Point features."""
    idx = _stub_index()
    with patch("app.core.index.wfs", return_value={"features": [_POINT_FEATURE]}):
        out = idx.trees_bbox(13.4, 52.5, radius_m=200)
    assert out is not None
    assert out["count"] == 1, f"expected 1 Point tree kept, got: {out}"


def test_trees_bbox_handles_multipoint_geometry():
    """Hamburg path — Baumkataster returns MultiPoint features wrapped
    as [[lon, lat]]. Regression guard for the ValueError observed in
    prod (`expected 2, got 1`)."""
    idx = _stub_index()
    with patch("app.core.index.wfs", return_value={"features": [_MULTIPOINT_FEATURE]}):
        out = idx.trees_bbox(10.0319, 53.5444, radius_m=200)
    assert out is not None
    assert out["count"] == 1, f"expected 1 MultiPoint tree kept, got: {out}"


def test_trees_bbox_skips_unknown_geometry_type():
    """Defensive: an unsupported geometry (LineString, Polygon, malformed)
    is skipped rather than crashing the endpoint. Berlin + Hamburg both
    ship on this codepath, so silent skip is the right degradation."""
    idx = _stub_index()
    bad = {"geometry": {"type": "LineString",
                        "coordinates": [[13.4, 52.5], [13.41, 52.51]]},
           "properties": {}}
    empty = {"geometry": None, "properties": {}}
    malformed = {"geometry": {"type": "MultiPoint", "coordinates": []},
                 "properties": {}}
    with patch("app.core.index.wfs",
               return_value={"features": [bad, empty, malformed, _POINT_FEATURE]}):
        out = idx.trees_bbox(13.4, 52.5, radius_m=200)
    assert out is not None
    assert out["count"] == 1, f"only the Point should survive, got: {out}"
