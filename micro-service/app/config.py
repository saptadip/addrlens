"""Env-var config. Picks CITY at startup (Ship B); INFERENCE_URL for the LLM
side-car. Deployment shape: one instance per city, CITY selects the config
(plan §0).
"""
import importlib
import os

from app.cities.base import CityConfig

INFERENCE_URL = os.environ.get("INFERENCE_URL", "http://localhost:8080")
# Timeout for the outbound call to inference-service. First request after
# boot loads the model (~10–20 s on prod CPU / ~5 s on MLX dev), so this is
# generous. Steady-state calls return in 1–3 s.
INFERENCE_TIMEOUT_S = float(os.environ.get("INFERENCE_TIMEOUT_S", "45"))

CITY = os.environ.get("CITY", "berlin").strip().lower()

# CORS allow-list (Ship D-1 item 8). Comma-separated, no wildcards. Default is
# empty — same-origin only, which is what /api/lookup + the SPA need. Deployers
# add prod origins via env (e.g. CORS_ORIGINS="https://addrlens.de").
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]


def load_city(slug: str = CITY) -> CityConfig:
    """Import `app.cities.<slug>` and return its uppercase-slug attribute
    (e.g. app.cities.berlin.BERLIN). Kept explicit so a typo in CITY fails
    fast at boot with a readable error, not deep in a request handler."""
    try:
        mod = importlib.import_module(f"app.cities.{slug}")
    except ImportError as e:
        raise RuntimeError(
            f"CITY={slug!r}: no such config module (expected app/cities/{slug}.py)"
        ) from e
    cfg = getattr(mod, slug.upper(), None)
    if not isinstance(cfg, CityConfig):
        raise RuntimeError(
            f"CITY={slug!r}: app.cities.{slug} must export {slug.upper()} : CityConfig"
        )
    return cfg
