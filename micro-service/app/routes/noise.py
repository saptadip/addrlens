"""/api/noise — nearest façade point + traffic-light tier. Byte-for-byte parity."""
from fastapi import APIRouter, Depends, Query

from app.cities.base import CityConfig
from app.core.scorer import noise_tier
from app.core.wfs import noise_at
from app.deps import get_city

router = APIRouter()


@router.get("/api/noise")
def noise(
    lat: float = Query(...),
    lon: float = Query(...),
    cfg: CityConfig = Depends(get_city),
):
    n = noise_at(cfg, lon, lat)
    n["tier"] = noise_tier((n.get("l_den") or {}).get("total")) if not n.get("unavailable") else "unknown"
    return {"noise": n}
