"""Unit tests for `app.core.scoring.shape` — feature-shape helpers.

Ground truth: the selfcheck block in `app/core/scorer.py` (§ Spec D
shape helpers). Each helper returns a shaped dict or None when required
fields are missing.
"""
import pytest

from app.cities.berlin import BERLIN
from app.core.scoring.shape import (
    _int_or_none, _prune, _shape_kita, _shape_office,
    _shape_osm_feature, _shape_paediatric_gp, _shape_playground,
    _shape_refuge_quiet, _shape_refuge_trees, _shape_transit_stop,
    _tile, _valid_latlon,
)


# --- _prune -----------------------------------------------------------


def test_prune_drops_none_and_empty_string_only():
    # Keeps 0, False, [], {}. Drops None and "".
    src = {"a": "x", "b": None, "c": "", "d": 0, "e": False, "f": [], "g": {}}
    assert _prune(src) == {"a": "x", "d": 0, "e": False, "f": [], "g": {}}


def test_prune_empty_dict_returns_empty():
    assert _prune({}) == {}


# --- _int_or_none ----------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [("65", 65), (65, 65), (0, 0), ("0", 0),
     (None, None), ("", None), ("abc", None), ("1.5", None)],
)
def test_int_or_none(raw, expected):
    assert _int_or_none(raw) == expected


# --- _valid_latlon ---------------------------------------------------


@pytest.mark.parametrize(
    "d,expected",
    [
        ({"lat": 52.5, "lon": 13.4},   True),
        ({"lat": 0.0,  "lon": 0.0},    True),
        ({"lat": -89,  "lon": 179},    True),
        ({"lat": 100.0,"lon": 13.4},   False),   # lat > 90
        ({"lat": 52.5, "lon": 181},    False),   # lon > 180
        ({"lat": None, "lon": 13.4},   False),
        ({"lat": 52.5},                False),   # missing lon
        ({},                            False),
    ],
)
def test_valid_latlon(d, expected):
    assert _valid_latlon(d) is expected


# --- _tile ----------------------------------------------------------


def test_tile_defaults_features_and_sources_to_empty_list():
    t = _tile("k", "L", "i", tier="green", rule="r")
    assert t["features"] == []
    assert t["sources"] == []
    assert t["numeric"] == ""
    assert t["caveat"] == ""
    assert "metadata" not in t


def test_tile_metadata_only_added_when_provided():
    t = _tile("k", "L", "i", tier="green", rule="r", metadata={"x": 1})
    assert t["metadata"] == {"x": 1}


# --- _shape_kita ----------------------------------------------------


def test_shape_kita_shapes_bod_row():
    fm = BERLIN.kita_field_map
    raw = {
        "name": "Kita Sonnenschein",
        "lat": 52.5388, "lon": 13.3948, "distance_m": 180,
        "props": {
            fm["capacity"]:     "65",
            fm["operator_type"]: "freie Träger",
            fm["approach"]:      "Situationsansatz",
        },
    }
    r = _shape_kita(raw, fm)
    # Per-key asserts (not `assert r == {...}`) so a future additive
    # field on _shape_kita doesn't turn this into a false-positive
    # failure — every existing signal is still individually pinned.
    assert r is not None
    assert r["name"] == "Kita Sonnenschein"
    assert r["lat"] == pytest.approx(52.5388)
    assert r["lon"] == pytest.approx(13.3948)
    assert r["distance_m"] == 180
    assert r["capacity"] == 65               # stringified BOD "65" → int
    assert r["operator_type"] == "freie Träger"
    assert r["approach"] == "Situationsansatz"
    # Schema-completeness spot-check: the required-field set stays present.
    assert set(r.keys()) >= {"name", "lat", "lon", "distance_m",
                             "capacity", "operator_type", "approach"}


def test_shape_kita_rejects_missing_name():
    fm = BERLIN.kita_field_map
    raw = {"name": "", "lat": 52.5, "lon": 13.4,
           "distance_m": 100, "props": {}}
    assert _shape_kita(raw, fm) is None


def test_shape_kita_rejects_missing_latlon():
    fm = BERLIN.kita_field_map
    raw = {"name": "X", "distance_m": 100, "props": {}}
    assert _shape_kita(raw, fm) is None


# --- _shape_playground ----------------------------------------------


def test_shape_playground_with_area_and_year():
    raw = {"name": "Marheinekeplatz, Spiel",
           "lat": 52.489, "lon": 13.396, "distance_m": 75,
           "props": {"katasterfl": 446, "sanierjahr": "2018"}}
    r = _shape_playground(raw)
    # Per-key asserts so an additive field on _shape_playground stays
    # non-breaking; every existing signal is still individually pinned.
    assert r is not None
    assert r["name"] == "Marheinekeplatz, Spiel"
    assert r["lat"] == pytest.approx(52.489)
    assert r["lon"] == pytest.approx(13.396)
    assert r["distance_m"] == 75
    assert r["area_m2"] == 446
    assert r["renovated_year"] == 2018       # stringified "2018" → int
    assert set(r.keys()) >= {"name", "lat", "lon", "distance_m",
                             "area_m2", "renovated_year"}


def test_shape_playground_without_props_uses_bare_minimum():
    raw = {"name": "P2", "lat": 52.5, "lon": 13.4,
           "distance_m": 200, "props": {}}
    r = _shape_playground(raw)
    assert r is not None
    assert r["name"] == "P2"
    assert r["lat"] == pytest.approx(52.5)
    assert r["lon"] == pytest.approx(13.4)
    assert r["distance_m"] == 200
    # Optional fields must be absent when the BOD props dict has neither.
    assert "area_m2" not in r
    assert "renovated_year" not in r


# --- _shape_paediatric_gp -------------------------------------------


def test_shape_paediatric_gp_composes_address_and_carries_contact():
    raw = {
        "name": "Praxis Dr. X",
        "lat": 52.4893, "lon": 13.3889, "distance_m": 430,
        "tags": {
            "addr:street": "Bergmannstraße", "addr:housenumber": "5",
            "addr:postcode": "10961", "addr:city": "Berlin",
            "phone": "+49 30 693 80 05",
            "website": "https://example.de",
            "opening_hours": "Mo-Fr 09:00-12:00",
            "wheelchair": "yes",
        },
    }
    r = _shape_paediatric_gp(raw)
    assert r["address"] == "Bergmannstraße 5, 10961 Berlin"
    assert r["phone"].startswith("+49")
    assert r["website"].startswith("http")
    assert r["hours"].startswith("Mo-Fr")
    assert r["wheelchair"] is True


def test_shape_paediatric_gp_drops_non_yes_wheelchair():
    raw = {"name": "X", "lat": 52.5, "lon": 13.4, "distance_m": 100,
           "tags": {"wheelchair": "limited"}}
    r = _shape_paediatric_gp(raw)
    assert "wheelchair" not in r


# --- _shape_office --------------------------------------------------


def test_shape_office_computes_walk_min():
    raw = {"name": "Bürgeramt X",
           "address": "Y-Str. 1, 10000 Berlin",
           "lat": 52.5, "lon": 13.4, "distance_m": 620,
           "website": "https://x.example/"}
    r = _shape_office(raw)
    assert r["walk_min"] == 10                  # 620/62 ≈ 10 min
    assert r["website"] == "https://x.example/"


# --- _shape_transit_stop --------------------------------------------


def test_shape_transit_stop_returns_none_on_empty():
    assert _shape_transit_stop({}, "S-Bahn") is None
    assert _shape_transit_stop(None, "S-Bahn") is None


def test_shape_transit_stop_shapes_full():
    raw = {"name": "S Alexanderplatz",
           "lat": 52.5219, "lon": 13.4132, "distance_m": 250}
    r = _shape_transit_stop(raw, "S-Bahn")
    assert r["modality"] == "S-Bahn"
    assert r["walk_min"] == 4


# --- _shape_osm_feature ---------------------------------------------


def test_shape_osm_feature_uses_amenity_when_no_name():
    raw = {"lat": 52.5, "lon": 13.4, "distance_m": 200, "source": "osm",
           "tags": {"amenity": "restaurant"}}
    r = _shape_osm_feature(raw)
    assert r["name"] == "restaurant"


def test_shape_osm_feature_rejects_missing_latlon():
    assert _shape_osm_feature({"lon": 13.4, "distance_m": 100}) is None


# --- _shape_refuge_quiet --------------------------------------------


def test_shape_refuge_quiet_includes_within_range():
    q = {"name": "Volkspark", "lat": 52.53, "lon": 13.42,
         "distance_m": 350, "size_ha": 29, "kind": "Erholungsgebiet"}
    r = _shape_refuge_quiet(q, 1000)
    assert r == [{
        "name": "Volkspark", "lat": 52.53, "lon": 13.42,
        "distance_m": 350, "size_ha": 29, "kind": "Erholungsgebiet",
    }]


def test_shape_refuge_quiet_excludes_beyond_range():
    q = {"name": "Far", "lat": 52.6, "lon": 13.5, "distance_m": 5000}
    assert _shape_refuge_quiet(q, 1000) == []


def test_shape_refuge_quiet_none_returns_empty_list():
    assert _shape_refuge_quiet(None, 1000) == []


# --- _shape_refuge_trees --------------------------------------------


def test_shape_refuge_trees_filters_top_species():
    t = {"count": 42, "avg_age_yr": 35, "tallest_m": 22,
         "crown_coverage_pct": 27,
         "top_species": [{"name": "Silberlinde", "n": 12},
                         {"name": "Winterlinde", "n": 8},
                         {"name": "", "n": 0}]}
    r = _shape_refuge_trees(t)
    assert r["count"] == 42
    assert r["top_species"] == [
        {"name": "Silberlinde", "n": 12},
        {"name": "Winterlinde", "n": 8},
    ]


def test_shape_refuge_trees_returns_empty_on_error():
    assert _shape_refuge_trees({"error": "trees down"}) == {}


def test_shape_refuge_trees_returns_empty_on_none():
    assert _shape_refuge_trees(None) == {}
