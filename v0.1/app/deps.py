"""FastAPI dependencies. Kept separate from main.py to avoid the
main ↔ routes circular import."""
from fastapi import Request

from app.cities.base import CityConfig
from app.core.index import Index


def get_index(request: Request) -> Index:
    """Hands routes the singleton Index without a module-level global."""
    return request.app.state.index


def get_city(request: Request) -> CityConfig:
    """Hands routes the current CityConfig (selected by CITY at boot)."""
    return request.app.state.city
