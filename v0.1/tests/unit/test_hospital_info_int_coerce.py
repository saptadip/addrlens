"""Regression guard for `_hospital_info` int-vs-string field values.

Hamburg's HH_WFS_Krankenhaeuser returns `geplante_bettenzahl` and
`teilstationaere_plaetze` as JSON integers. Berlin's Krankenhäuser
returns bed counts as JSON strings. The pre-fix code called `.strip()`
on the raw value → AttributeError on Hamburg int, taking down /api/
amenities (which broke both the Amenities and Emergency tabs on
hamburg.addrlens.de).

`_s()` coerces safely and preserves the `x or ""` skip-empty semantics
so Berlin's "0 beds → skip" behaviour is byte-preservable.
"""
from app.core.index import _hospital_info, _s
import pytest

pytestmark = pytest.mark.hamburg


class _CfgHH:
    """Minimal CityConfig-shaped stub with Hamburg's hospital_field_map."""
    hospital_field_map = {
        "name_primary": "name", "name_alt1": "name", "name_alt2": "name",
        "beds": "geplante_bettenzahl", "beds_alt": "teilstationaere_plaetze",
        "traeger": "traeger", "ortsteil": "stadtteil",
        "fachabteilungen": "fachabteilungen",
    }


class _CfgBerlin:
    """Berlin's hospital_field_map — pre-existing string-typed values."""
    hospital_field_map = {
        "name_primary": "bezeichnung",
        "name_alt1": "name", "name_alt2": "beschreibung",
        "beds": "bettenzahl", "beds_alt": "bettenzahl",
        "traeger": "traeger", "ortsteil": "bezirk",
        "fachabteilungen": "fachrichtungen",
    }


def test_hospital_info_handles_hamburg_int_beds():
    """Hamburg returns `geplante_bettenzahl: 180` as int — pre-fix
    `.strip()` on int raised AttributeError. Now it coerces cleanly."""
    p = {"name": "Asklepios Barmbek", "geplante_bettenzahl": 180,
         "traeger": "Asklepios", "stadtteil": "22307 Hamburg"}
    out = _hospital_info(p, _CfgHH())
    assert "180 beds" in out, out
    assert "Asklepios" in out, out
    assert "22307 Hamburg" in out, out


def test_hospital_info_handles_hamburg_int_zero_beds_skips():
    """Hamburg tageskliniken often return `geplante_bettenzahl: 0` as
    int — the `x or ""` skip semantics must survive coercion so the
    tile doesn't render '0 beds'."""
    p = {"name": "Tagesklinik", "geplante_bettenzahl": 0,
         "traeger": "freigemeinnützig", "stadtteil": "22085 Hamburg"}
    out = _hospital_info(p, _CfgHH())
    assert "0 beds" not in out, out
    assert "freigemeinnützig" in out, out


def test_hospital_info_handles_berlin_string_beds():
    """Berlin regression guard: string bed count still renders."""
    p = {"bezeichnung": "Charité", "bettenzahl": "3000",
         "traeger": "Land Berlin", "bezirk": "Mitte"}
    out = _hospital_info(p, _CfgBerlin())
    assert "3000 beds" in out, out
    assert "Mitte" in out, out


def test_hospital_info_handles_none_and_empty():
    """Defensive: missing / None / empty fields don't crash and don't
    emit empty separators."""
    p = {"name": None, "geplante_bettenzahl": None, "traeger": "",
         "stadtteil": None}
    out = _hospital_info(p, _CfgHH())
    assert "beds" not in out
    assert out == ""


def test_hospital_info_weitere_layer_with_int_beds_alt():
    """'weitere' (specialist) layer path also coerces `beds_alt` int."""
    p = {"_layer": "weitere", "name": "Fachklinik",
         "fachabteilungen": "Kardiologie",
         "teilstationaere_plaetze": 42,
         "stadtteil": "22587 Hamburg"}
    out = _hospital_info(p, _CfgHH())
    assert "Kardiologie" in out, out
    assert "42 beds" in out, out


def test_s_helper_semantics():
    """`_s` is the coercion helper — must preserve Berlin's `x or ""`
    skip-empty behavior across None/0/empty inputs."""
    assert _s(None) == ""
    assert _s(0) == ""
    assert _s(0.0) == ""
    assert _s("") == ""
    assert _s([]) == ""
    assert _s("  Charité  ") == "Charité"
    assert _s(180) == "180"
    assert _s("180") == "180"
