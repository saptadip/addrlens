"""Ferry loader + nearest-pier lookup — pure, no live WFS."""
from types import SimpleNamespace

from app.core.index import Index


def _cfg(tmp_path):
    csv = tmp_path / "ferry.csv"
    csv.write_text("name,lat,lon,lines,peak_only\n"
                   "Landungsbrücken,53.5459,9.9683,62,0\n"
                   "Finkenwerder,53.5285,9.8571,62,0\n"
                   "Neuhof,53.5040,9.9375,61,1\n")
    return SimpleNamespace(
        slug="hamburg_test", display_name="Test",
        default_center=(53.55, 9.99), wfs_output_format="application/geo+json",
        wfs_srs_name="EPSG:4326", ferry_stations_data_path=str(csv),
        # All other CityConfig fields defaulted to None/False so no WFS calls fire.
        geocoder="oaf", geocoder_wfs_url=None, geocoder_layer=None,
        geocoder_field_map={}, geocoder_oaf_url=None, geocoder_oaf_field_map=None,
        catchment_wfs_url=None, schools_wfs_url=None, kita_wfs_url=None,
        hospital_wfs_url=None, fountains_wfs_url=None, green_wfs_url=None,
        noise_wfs_url=None, fire_wfs_url=None, trees_wfs_url=None,
        quiet_wfs_url=None, protection_wfs_url=None, pools_wfs_url=None,
        swim_natural_wfs_url=None, air_wfs_url=None, heat_wfs_url=None,
        stations_data_path=None, tram_wfs_url=None, regional_rail_stations=(),
        airport=None, bilingual_glossary=[], overpass_bbox=(53, 9, 54, 11),
        attribution={}, osm_local_path=None, address_local_path=None,
        gesix_wfs_url=None, gesix_layer=None,
        young_family_lens=None, newcomer_lens=None, quiet_living_lens=None,
        commuter_lens=None,
        bezirksgrenzen_wfs_url=None, buergeramt_wfs_url=None,
        finanzamts=(), standesamts_by_bezirk={}, arbeitsagenturs=(),
        lea_office={}, others_admin_cards=(),
        xmas_market_url=None, parking_zones_wfs_url=None,
        tempolimits_wfs_url=None, arterial_wfs_url=None,
        sozialmonitoring_wfs_url=None, sozialmonitoring_layer=None,
        sozialmonitoring_field_map=None,
        fire_zones_available=False, bezirk_id_to_name=None,
        hospital_layers=(), hospital_field_map={}, hospital_radius_m=2000,
        hospital_match_m=500, schools_field_map={}, schools_public_value="",
        schools_primary_types=frozenset(), schools_intl_keywords=(),
        bilingual_schools={}, kita_field_map={}, fountains_field_map={},
        parks_layer=None, playgrounds_layer=None, noise_layer=None,
        noise_field_map={}, noise_year=2022,
        fire_stations_layer=None, fire_zones_layer=None,
        fire_stations_field_map={}, fire_zones_field_map={},
        trees_layer=None, trees_field_map={}, trees_radius_m=200,
        quiet_layer=None, quiet_field_map={},
        protection_em_layer=None, protection_es_layer=None,
        protection_field_map={}, pools_layer=None, pools_field_map={},
        swim_natural_layer=None, swim_natural_field_map={},
        air_layer=None, air_field_map={}, heat_layer=None, heat_field_map={},
        tram_field_map={},
        tempolimits_layer=None, tempolimits_field_map={},
        arterial_layer=None, arterial_field_map={},
        bezirksgrenzen_layer=None, bezirksgrenzen_field_map={},
        buergeramt_layer=None, buergeramt_field_map={},
        catchment_layer=None, catchment_field_map={},
        parking_zones_layer=None, parking_zones_field_map=None,
        noise_model="none", air_model="none",
    )


def test_ferry_load_and_nearest(tmp_path):
    cfg = _cfg(tmp_path)
    idx = Index(cfg)
    assert len(idx.ferry) == 3
    # Landungsbrücken is at 53.5459 / 9.9683 — search from Baumwall (very close)
    hit = idx.nearest_ferry(9.9727, 53.5442)
    assert hit["name"] == "Landungsbrücken"
    assert hit["distance_m"] < 500


def test_ferry_empty_when_path_none():
    cfg = SimpleNamespace(slug="empty", ferry_stations_data_path=None,
                           # ... minimal dummy fields
                           )
    # Use the same dummy pattern — copy from _cfg without the ferry_path
    # For brevity of this test just verify the attribute exists as empty list
    from app.core.index import Index
    idx = Index.__new__(Index)          # bypass __init__ full path
    idx.cfg = cfg
    idx.ferry = []
    Index._load_ferry(idx)              # exercises the None-path guard
    assert idx.ferry == []
