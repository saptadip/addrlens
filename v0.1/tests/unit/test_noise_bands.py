"""Isoline noise model — noise_bands_at returns per-source band strings."""
from types import SimpleNamespace
from unittest.mock import patch

from shapely.geometry import Polygon

from app.core.index import Index


def test_noise_bands_at_road_only(monkeypatch):
    cfg = SimpleNamespace(
        noise_model="isoline",
        wfs_output_format="application/geo+json",
        wfs_srs_name="EPSG:4326",
        noise_wfs_url="https://example/wfs",
        noise_isoline_road_day_layer="road_day",
        noise_isoline_road_night_layer=None,
        noise_isoline_rail_day_layer=None,
        noise_isoline_rail_night_layer=None,
        noise_isoline_air_day_layer=None,
        noise_isoline_air_night_layer=None,
    )
    idx = Index.__new__(Index)
    idx.cfg = cfg
    band_poly = Polygon([(9.99, 53.55), (10.00, 53.55), (10.00, 53.56), (9.99, 53.56)])

    def fake_load(cfg_, url, layer, count):
        return [({"band": "60-64"}, band_poly)]

    with patch("app.core.index.load_polygon_layer", side_effect=fake_load):
        out = idx.noise_bands_at(9.995, 53.555)
    assert out["road_den_band"] == "60-64"
    assert out["road_n_band"] is None
    assert out["rail_den_band"] is None
