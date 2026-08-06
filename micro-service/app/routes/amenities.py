"""/api/amenities — Overpass round-trip + BOD supplements. Byte-for-byte parity."""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.cities.base import CityConfig
from app.core.amenities import amenities_near
from app.core.index import Index
from app.deps import get_city, get_index

router = APIRouter()


@router.get("/api/amenities")
def amenities(
    lat: float = Query(...),
    lon: float = Query(...),
    index: Index = Depends(get_index),
    cfg: CityConfig = Depends(get_city),
):
    try:
        return {
            "amenities": amenities_near(index, cfg, lon, lat, 800),
            "provenance": f"{cfg.display_name} Open Data + OpenStreetMap (see per-category source)",
        }
    except ValueError:
        raise HTTPException(400, "lat and lon required")
