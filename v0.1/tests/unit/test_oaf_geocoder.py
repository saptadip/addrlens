"""Unit test the OAF geocoder — mocked httpx, no network."""
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from app.core.loaders import oaf_geocoder


def _cfg():
    return SimpleNamespace(
        geocoder_oaf_url="https://example.hh/dog/items",
        geocoder_oaf_field_map={"street": "strasse", "hnr": "hausnummer", "plz": "plz"},
    )


def _feature(lon, lat, props):
    return {"features": [{"geometry": {"coordinates": [lon, lat]}, "properties": props}]}


def test_geocode_returns_lon_lat_props_on_hit():
    with patch.object(oaf_geocoder, "httpx") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.json.return_value = _feature(9.99, 53.55, {"strasse": "Reeperbahn"})
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp
        out = oaf_geocoder.geocode_oaf(_cfg(), "Reeperbahn", "1", "20359")
        assert out == {"lon": 9.99, "lat": 53.55, "props": {"strasse": "Reeperbahn"}}


def test_geocode_returns_none_on_miss():
    with patch.object(oaf_geocoder, "httpx") as mock_httpx:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"features": []}
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp
        out = oaf_geocoder.geocode_oaf(_cfg(), "Nowhere", "1", "20359")
        assert out is None


def test_geocode_ss_fold_retry():
    """When first query on 'Straße' returns empty, retry with 'Strasse' spelling."""
    call_count = {"n": 0}
    with patch.object(oaf_geocoder, "httpx") as mock_httpx:
        def _get(url, params=None, **kw):
            call_count["n"] += 1
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if call_count["n"] == 1:
                resp.json.return_value = {"features": []}
            else:
                resp.json.return_value = _feature(9.99, 53.55, {"strasse": params["strasse"]})
            return resp
        mock_httpx.get = _get
        out = oaf_geocoder.geocode_oaf(_cfg(), "Sybelstraße", "1", "20359")
        assert out is not None
        assert call_count["n"] == 2   # retry fired
