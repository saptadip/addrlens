"""Sozialmonitoring point-in-polygon lookup — no WFS, uses shapely polygon fixture."""
from types import SimpleNamespace

from shapely.geometry import Polygon

from app.core.index import Index


def test_sozialmonitoring_at_hit():
    cfg = SimpleNamespace(sozialmonitoring_field_map={
        "statusindex": "statusindex", "gesamtindex": "gesamtindex",
        "dynamikindex": "dynamikindex", "stadtteil": "stadtteil",
        "statgeb": "statgeb", "berichtsjahr": "berichtsjahr",
    })
    idx = Index.__new__(Index)
    idx.cfg = cfg
    poly = Polygon([(9.99, 53.55), (10.00, 53.55), (10.00, 53.56), (9.99, 53.56)])
    props = {"statusindex": "hoch", "gesamtindex": "kein Handlungsbedarf",
             "dynamikindex": "stabil", "stadtteil": "Neustadt",
             "statgeb": "10101", "berichtsjahr": "2025"}
    idx.sozialmonitoring = [(props, poly)]
    hit = idx.sozialmonitoring_at(9.995, 53.555)
    assert hit["statusindex"] == "hoch"
    assert hit["stadtteil"] == "Neustadt"


def test_sozialmonitoring_at_miss():
    cfg = SimpleNamespace(sozialmonitoring_field_map={
        "statusindex": "statusindex", "gesamtindex": "gesamtindex",
        "dynamikindex": "dynamikindex", "stadtteil": "stadtteil",
        "statgeb": "statgeb", "berichtsjahr": "berichtsjahr",
    })
    idx = Index.__new__(Index)
    idx.cfg = cfg
    idx.sozialmonitoring = []
    assert idx.sozialmonitoring_at(9.995, 53.555) is None
