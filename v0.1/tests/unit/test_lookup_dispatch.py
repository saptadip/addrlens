"""Unit tests for Task 11: lookup.py neighbourhood + nearest-school dispatch.

Pins three invariants required by the brief:
  (a) Berlin response gains nearest_school.distance_km
  (b) Berlin schools[] array is unchanged
  (c) Hamburg predicate branches (sozialmonitoring / nearest_school km-only)
      do NOT fire for Berlin (gesix_wfs_url set, sozialmonitoring_wfs_url=None,
      slug != "hamburg")
"""
from types import SimpleNamespace

import pytest

from app.core.index import Index
from app.core.geo import haversine_m


# ---------------------------------------------------------------------------
# Helpers: minimal Index stubs
# ---------------------------------------------------------------------------

def _make_index_with_school(lon_s, lat_s, gs_public_props=None):
    """Index stub with a single public Grundschule at (lon_s, lat_s)."""
    idx = Index.__new__(Index)
    idx.cfg = SimpleNamespace(
        slug="berlin",
        gesix_wfs_url="https://example.com/gesix",
        sozialmonitoring_wfs_url=None,
        sozialmonitoring_field_map=None,
        sozialmonitoring=None,
        gesix=None,
    )
    props = gs_public_props or {"e_name": "Testschule", "bsn": "001", "type": "Grundschule"}
    idx.gs_public = [(props, (lon_s, lat_s))]
    idx.sozialmonitoring = []
    idx.gesix = []
    return idx


def _make_empty_index():
    idx = Index.__new__(Index)
    idx.cfg = SimpleNamespace(
        slug="berlin",
        gesix_wfs_url="https://example.com/gesix",
        sozialmonitoring_wfs_url=None,
        sozialmonitoring_field_map=None,
        sozialmonitoring=None,
        gesix=None,
    )
    idx.gs_public = []
    idx.sozialmonitoring = []
    idx.gesix = []
    return idx


# ---------------------------------------------------------------------------
# (a) nearest_school_km_only — Hamburg helper
# ---------------------------------------------------------------------------

def test_nearest_school_km_only_returns_distance():
    """nearest_school_km_only returns {distance_km} rounded to 2 dp."""
    idx = _make_index_with_school(10.0, 53.55)
    result = idx.nearest_school_km_only(10.001, 53.55)
    assert result is not None
    assert "distance_km" in result
    assert isinstance(result["distance_km"], float)
    # ~70 m at this latitude → well under 1 km
    assert 0 < result["distance_km"] < 1.0


def test_nearest_school_km_only_rounds_to_2dp():
    """Result is rounded to exactly 2 decimal places."""
    idx = _make_index_with_school(10.0, 53.55)
    result = idx.nearest_school_km_only(10.001, 53.55)
    assert result is not None
    # round() to 2 dp produces at most 2 significant decimal digits
    assert result["distance_km"] == round(result["distance_km"], 2)


def test_nearest_school_km_only_empty_returns_none():
    """Returns None when gs_public is empty."""
    idx = _make_empty_index()
    assert idx.nearest_school_km_only(10.0, 53.55) is None


def test_nearest_school_km_only_no_extra_keys():
    """Hamburg km-only result must not carry name or bsn."""
    idx = _make_index_with_school(10.0, 53.55)
    result = idx.nearest_school_km_only(10.001, 53.55)
    assert result is not None
    assert set(result.keys()) == {"distance_km"}


# ---------------------------------------------------------------------------
# (b) Berlin response gains nearest_school.distance_km — contract test
# ---------------------------------------------------------------------------

def test_lookup_berlin_response_has_nearest_school_distance_km(client, monkeypatch):
    """Berlin /api/lookup carries nearest_school.distance_km when schools present.

    We stub gesix_at + nearest_gs_public on the fake index to produce a
    minimal school record so the Berlin else-branch fires.
    """
    from app.deps import get_index, get_city
    from app.main import app
    from app.cities.berlin import BERLIN
    from app.core import wfs as _wfs_mod

    # Build a fake index that returns one school so out_schools is non-empty.
    class _SchoolIndex:
        """Minimal stub with one school in the catchment fallback list."""
        cfg = BERLIN
        sbahn = ubahn = tram = regional_rail = fountains = hospitals = []
        kitas = esbs = fire_stations = fire_zones = quiet_zones = []
        protection_em = protection_es = pools = natural_swim = []
        gesix = sozialmonitoring = buergeramts = tempolimits = arterials = []
        bezirksgrenzen = []
        gs_public = []

        from tests.conftest import _FakeOSMLocal
        osm_local = _FakeOSMLocal()

        def geocode(self, street, hnr, plz):
            return {"lon": 13.4132, "lat": 52.5219,
                    "props": {"str_name": street, "hnr": hnr, "plz": plz}}

        def catchment(self, lon, lat):
            # Return a props+None polygon + one school tuple so schools_source=="esb"
            esb_props = {BERLIN.catchment_field_map["id"]: "ESB001",
                         BERLIN.catchment_field_map["district"]: "Mitte"}
            s_fm = BERLIN.schools_field_map
            school_props = {
                s_fm["name"]: "Mustergrundschule",
                s_fm["id"]: "BSN123",
                s_fm["street"]: "Musterstraße",
                s_fm["hnr"]: "1",
                s_fm["plz"]: "10117",
                s_fm["phone"]: None,
                s_fm["website"]: None,
                s_fm["school_year"]: None,
            }
            # Return polygon=None to keep geometry simple (schools_source=esb via props)
            # Actually: schools_source="esb" when schools list is non-empty from catchment
            from shapely.geometry import box
            poly = box(13.4, 52.5, 13.45, 52.55)
            return esb_props, poly, [(school_props, (13.415, 52.525))]

        def nearest_gs_public(self, lon, lat, k=2): return []
        def nearest_intl(self, lon, lat): return None
        def sesb_strand(self, name): return None
        def kitas_near_bod(self, lon, lat, radius_m=800): return []
        def fountains_near_bod(self, lon, lat, radius_m=800): return []
        def hospitals_near_bod(self, lon, lat, radius_m=None): return []
        def nearest_station(self, points, lon, lat): return None
        def fire_rescue(self, lon, lat): return None
        def neighborhood_protection(self, lon, lat):
            return {"milieuschutz": {"inside": False, "area_name": None},
                    "erhaltung": {"inside": False, "area_name": None}}
        def nearest_quiet_zone(self, lon, lat): return None
        def pools_within(self, lon, lat, radius_m=3000): return []
        def natural_swim_within(self, lon, lat, radius_m=15000): return []
        def trees_bbox(self, lon, lat, radius_m=None): return None
        def gesix_at(self, lon, lat): return None
        def sozialmonitoring_at(self, lon, lat): return None
        def nearest_school_km_only(self, lon, lat): return None
        def bezirk_for(self, lon, lat): return None
        def buergeramt_near(self, lon, lat, radius_m=3000): return []
        def arbeitsagentur_near(self, lon, lat, radius_m=5000): return []
        def finanzamt_nearest(self, lon, lat): return None
        def standesamt_for(self, lon, lat): return None
        def tempolimit_at(self, lon, lat, radius_m=100): return None
        def nearest_arterial(self, lon, lat, radius_m=500): return None
        def rail_track_proximity(self, lon, lat): return None

    monkeypatch.setattr(_wfs_mod, "noise_at", lambda *_a, **_kw: {"unavailable": True})
    monkeypatch.setattr(_wfs_mod, "air_quality_at", lambda *_a, **_kw: {"unavailable": True})
    monkeypatch.setattr(_wfs_mod, "summer_heat_at", lambda *_a, **_kw: {"unavailable": True})

    school_index = _SchoolIndex()
    app.dependency_overrides[get_index] = lambda: school_index
    app.dependency_overrides[get_city] = lambda: BERLIN
    app.state.index = school_index
    app.state.city = BERLIN

    from fastapi.testclient import TestClient
    tc = TestClient(app)
    try:
        body = tc.get("/api/lookup", params={"address": "Kastanienallee 12, 10435"}).json()
    finally:
        app.dependency_overrides.clear()

    # (a) nearest_school.distance_km is present
    assert "nearest_school" in body, "Berlin response must carry nearest_school"
    ns = body["nearest_school"]
    assert "distance_km" in ns, "nearest_school must have distance_km"
    assert isinstance(ns["distance_km"], float)
    # (b) schools[] array is present and non-empty
    assert "schools" in body, "schools[] must remain in Berlin response"
    assert len(body["schools"]) > 0, "schools[] must be non-empty when catchment returned one"
    # Berlin nearest_school also carries name + bsn for drill-down
    assert "name" in ns, "Berlin nearest_school carries name for drill-down"
    assert "bsn" in ns, "Berlin nearest_school carries bsn for drill-down"
    # (c) Hamburg branches must NOT fire for Berlin
    assert "sozialmonitoring" not in body, "sozialmonitoring must not appear in Berlin response"


# ---------------------------------------------------------------------------
# (c) Hamburg slug predicate does NOT fire for Berlin
# ---------------------------------------------------------------------------

def test_berlin_lookup_has_no_sozialmonitoring_key(client):
    """The sozialmonitoring key must be absent in the Berlin /api/lookup response
    (cfg.sozialmonitoring_wfs_url is None for Berlin)."""
    body = client.get("/api/lookup",
                      params={"address": "Kastanienallee 12, 10435"}).json()
    assert "sozialmonitoring" not in body, (
        "sozialmonitoring must not appear in Berlin response "
        "(cfg.sozialmonitoring_wfs_url=None)"
    )
