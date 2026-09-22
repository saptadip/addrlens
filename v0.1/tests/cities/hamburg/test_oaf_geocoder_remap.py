"""Regression guard for OAF geocoder property remap (Hamburg).

Hamburg's DOG OAF returns `ortsteil` as a numeric code ("117") and the
human name in `postOrtsteil` ("Hammerbrook"). The frontend's lens AI
summary chip reads `raw.ortsteil` — if the numeric code leaks through
the chip renders "117" instead of the neighbourhood name (observed on
Haakestraße 10, 21075).

Also aliases `bezirke` → `bezirk` since the frontend's fallback chain
checks the singular form.
"""
from unittest.mock import patch, MagicMock

import httpx

from app.core.loaders.oaf_geocoder import geocode_oaf


class _Cfg:
    geocoder_oaf_url = "https://example/oaf/collections/x/items"
    geocoder_oaf_field_map = {"street": "strassenname", "hnr": "hausnummer",
                              "plz": "postleitzahl"}


def _feature(props):
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "geometry": {"type": "Point", "coordinates": [10.03, 53.55]},
         "properties": props}]}


def test_oaf_geocoder_maps_postOrtsteil_over_numeric_ortsteil():
    """Hamburg case: raw.ortsteil should be the human name from
    postOrtsteil, not the numeric code."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = _feature({
        "ortsteil": "117",
        "postOrtsteil": "Hammerbrook",
        "bezirke": "Hamburg-Mitte",
    })
    mock_resp.raise_for_status = MagicMock()
    with patch("app.core.loaders.oaf_geocoder.httpx.get", return_value=mock_resp):
        r = geocode_oaf(_Cfg(), "Haakestraße", "10", "21075")
    assert r is not None
    assert r["props"]["ortsteil"] == "Hammerbrook", \
        f"expected human name, got {r['props']['ortsteil']!r}"
    assert r["props"]["bezirk"] == "Hamburg-Mitte", \
        f"bezirk alias missing: {r['props'].get('bezirk')!r}"


def test_oaf_geocoder_preserves_bezirk_when_already_present():
    """If OAF ever returns both `bezirk` and `bezirke` (unlikely but
    defensive), don't overwrite the singular form."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = _feature({
        "bezirk": "PreExisting",
        "bezirke": "Hamburg-Mitte",
    })
    mock_resp.raise_for_status = MagicMock()
    with patch("app.core.loaders.oaf_geocoder.httpx.get", return_value=mock_resp):
        r = geocode_oaf(_Cfg(), "X", "1", "20095")
    assert r["props"]["bezirk"] == "PreExisting"


def test_oaf_geocoder_leaves_props_alone_when_no_postOrtsteil():
    """Berlin-style OAF (hypothetical — Berlin uses classic WFS not OAF)
    or any city whose OAF only returns `ortsteil` as a human name must
    not be clobbered."""
    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = _feature({
        "ortsteil": "Prenzlauer Berg",  # already human
    })
    mock_resp.raise_for_status = MagicMock()
    with patch("app.core.loaders.oaf_geocoder.httpx.get", return_value=mock_resp):
        r = geocode_oaf(_Cfg(), "Kastanienallee", "12", "10435")
    assert r["props"]["ortsteil"] == "Prenzlauer Berg"
    assert "bezirk" not in r["props"]  # no alias when bezirke absent
