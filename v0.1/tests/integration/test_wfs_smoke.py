"""Live-network smoke test — hits Berlin Geoportal WFS.

Opt-in only: `pytest -m integration`. Berlin has exactly 12 Bezirke, so
counting features on the Bezirksgrenzen layer is a stable ground-truth
assertion. If the Geoportal is temporarily down this test will fail —
that is acceptable per the task brief.
"""
import pytest

pytestmark = pytest.mark.integration


def test_berlin_bezirksgrenzen_returns_twelve_features(berlin_config):
    """Berlin has 12 Bezirke — the WFS layer must report exactly that."""
    from app.core.loaders.wfs_layer import load_polygon_layer

    polys = load_polygon_layer(
        berlin_config,
        berlin_config.bezirksgrenzen_wfs_url,
        berlin_config.bezirksgrenzen_layer,
        50,
    )
    assert len(polys) == 12, f"expected 12 Bezirke, got {len(polys)}"
