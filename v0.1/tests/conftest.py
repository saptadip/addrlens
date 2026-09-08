"""Shared pytest fixtures.

Environment defaults are set at import time (before any `app.*` import
during collection) so pytest never triggers a real WFS boot or LLM call
just by importing modules.

The `fake_index` fixture is a duck-typed stub that exposes only the
surface the `/api/*` routes read — no real WFS calls, no shapely trees.
Extend as new contract tests require.
"""
import os

# Set defaults BEFORE any `from app...` import runs. Pytest collection
# imports every conftest first, so this beats route/module imports.
os.environ.setdefault("CITY", "berlin")
os.environ.setdefault("INFERENCE_URL", "http://localhost:9999")

import pytest


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Wipe slowapi's in-memory rate-limit storage between tests.

    Without this, several `/api/suggest` tests in the same file bump
    against the `5/second` per-IP limit (TestClient always uses
    127.0.0.1). Production wants the limit; tests want deterministic
    counts. Reset touches the module-level `limiter` object; no route
    code path is patched.

    Guarded against a future prod switch to `RedisStorage` — the
    assertion below turns the fixture into a loud failure rather than
    silently wiping a live Redis if the test env is ever pointed at a
    real backing store.
    """
    from limits.storage.memory import MemoryStorage
    from app.core.rate_limit import limiter
    storage = getattr(limiter, "_storage", None)
    assert isinstance(storage, MemoryStorage), (
        "Rate-limit reset fixture is only safe against MemoryStorage. "
        "If production has been switched to RedisStorage, this fixture "
        "must be gated on an env var or removed."
    )
    storage.reset()
    yield


@pytest.fixture(scope="session")
def berlin_config():
    """Session-scoped Berlin CityConfig (frozen dataclass)."""
    from app.cities.berlin import BERLIN
    return BERLIN


class _FakeOSMLocal:
    """Minimal osm_local snapshot stub used by lookup + amenities paths."""
    def near(self, *_a, **_kw):
        return []


class _FakeIndex:
    """Duck-typed Index stub — only attributes the routes actually read.

    Add fields as new contract tests exercise more of the /api/lookup
    surface. Everything defaults to empty so the aggregating endpoint
    walks all branches without touching the network.
    """

    def __init__(self, cfg):
        self.cfg = cfg
        # Preloaded point layers routes iterate over.
        self.sbahn = []
        self.ubahn = []
        self.tram = []
        self.regional_rail = []
        self.fountains = []
        self.hospitals = []
        self.kitas = []
        self.esbs = []
        self.esb_to_gs = {}
        self.fire_stations = []
        self.fire_zones = []
        self.quiet_zones = []
        self.protection_em = []
        self.protection_es = []
        self.pools = []
        self.natural_swim = []
        self.gesix = []
        self.buergeramts = []
        self.tempolimits = []
        self.arterials = []
        self.bezirksgrenzen = []
        # OSM local snapshot the bus / commuter tiles walk over.
        self.osm_local = _FakeOSMLocal()

    # ---- geocoder ----------------------------------------------------
    def geocode(self, street, hnr, plz):
        """Deterministic fake — returns Alexanderplatz coords for any query."""
        return {"lon": 13.4132, "lat": 52.5219,
                "props": {"str_name": street, "hnr": hnr, "plz": plz}}

    # ---- catchment / schools -----------------------------------------
    def catchment(self, lon, lat):
        return None, None, []

    def nearest_gs_public(self, lon, lat, k=2):
        return []

    def nearest_intl(self, lon, lat):
        return None

    def sesb_strand(self, name):
        return None

    # ---- amenities / kitas / hospitals / fountains -------------------
    def kitas_near_bod(self, lon, lat, radius_m=800):
        return []

    def fountains_near_bod(self, lon, lat, radius_m=800):
        return []

    def hospitals_near_bod(self, lon, lat, radius_m=None):
        return []

    # ---- connectivity ------------------------------------------------
    def nearest_station(self, points, lon, lat):
        return None

    # ---- Phase 1 killer cards ----------------------------------------
    def fire_rescue(self, lon, lat):
        return None

    def neighborhood_protection(self, lon, lat):
        return {
            "milieuschutz": {"inside": False, "area_name": None},
            "erhaltung":    {"inside": False, "area_name": None},
        }

    def nearest_quiet_zone(self, lon, lat):
        return None

    def pools_within(self, lon, lat, radius_m=3000):
        return []

    def natural_swim_within(self, lon, lat, radius_m=15000):
        return []

    def trees_bbox(self, lon, lat, radius_m=None):
        return None

    # ---- GESIx + Others admin ----------------------------------------
    def gesix_at(self, lon, lat):
        return None

    def bezirk_for(self, lon, lat):
        return None

    def buergeramt_near(self, lon, lat, radius_m=3000):
        return []

    def arbeitsagentur_near(self, lon, lat, radius_m=5000):
        return []

    def finanzamt_nearest(self, lon, lat):
        return None

    def standesamt_for(self, lon, lat):
        return None

    # ---- Quiet Living lens data -------------------------------------
    def tempolimit_at(self, lon, lat, radius_m=100):
        return None

    def nearest_arterial(self, lon, lat, radius_m=500):
        return None

    def rail_track_proximity(self, lon, lat):
        return None


@pytest.fixture
def fake_index(berlin_config):
    """Function-scoped fake Index — cheap to build, empty state everywhere."""
    return _FakeIndex(berlin_config)


@pytest.fixture
def client(berlin_config, fake_index, monkeypatch):
    """TestClient with `get_index` / `get_city` overridden.

    Also patches network-touching WFS helpers in `app.core.wfs` so no
    live HTTP is issued during contract tests.
    """
    # Import here so env defaults are already in place.
    from fastapi.testclient import TestClient

    from app.deps import get_city, get_index
    from app.main import app
    from app.core import wfs as _wfs_mod

    # Kill the live WFS helpers — return `unavailable` shapes.
    monkeypatch.setattr(_wfs_mod, "noise_at",
                        lambda *_a, **_kw: {"unavailable": True})
    monkeypatch.setattr(_wfs_mod, "air_quality_at",
                        lambda *_a, **_kw: {"unavailable": True})
    monkeypatch.setattr(_wfs_mod, "summer_heat_at",
                        lambda *_a, **_kw: {"unavailable": True})

    app.dependency_overrides[get_index] = lambda: fake_index
    app.dependency_overrides[get_city] = lambda: berlin_config

    # /ready reads app.state.{index,city} directly (not via Depends), so
    # populate them by hand. NOTE: TestClient is NOT used as a context
    # manager — the FastAPI lifespan handler would call Index(cfg) and
    # make ~15 s of live WFS requests.
    prior_index = getattr(app.state, "index", None)
    prior_city = getattr(app.state, "city", None)
    app.state.index = fake_index
    app.state.city = berlin_config

    tc = TestClient(app)
    try:
        yield tc
    finally:
        app.dependency_overrides.clear()
        app.state.index = prior_index
        app.state.city = prior_city
