"""/api/config — city display strings for the frontend to inject at load
(plan §Ship B step 5). One HTTP round-trip on page-open; no per-city rebuild
of index.html required."""
from fastapi import APIRouter, Depends

from app.cities.base import CityConfig
from app.deps import get_city

router = APIRouter()


@router.get("/api/config")
def config(cfg: CityConfig = Depends(get_city)):
    return {
        "slug":            cfg.slug,
        "display_name":    cfg.display_name,
        "default_center":  list(cfg.default_center),
        "attribution":     cfg.attribution,
        "noise_year":      cfg.noise_year,
    }
