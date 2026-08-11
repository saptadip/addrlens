"""On-disk OSM amenity snapshot loader (Geofabrik-derived).

Reads the JSON produced by scripts/refresh_osm_amenities.py, keeps every
category bucket in memory, serves radius queries via haversine. Berlin's
~13k filtered points fit comfortably in RAM and a full-bucket O(n) sweep
takes <5 ms per request — no R-tree needed.

The purpose is to replace the Overpass hop in amenities.py:overpass(...).
Loader failure (file missing / stale / malformed) is non-fatal: callers
fall back to Overpass. Meant to be constructed once at Index boot.

Freshness policy: the loader reports `age_days` off the snapshot's
generated_at header. amenities.py logs a warning above 14 days and still
serves. Weekly cron target keeps age under 7 days.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.geo import haversine_m

_STALE_AFTER_DAYS = 14


class OsmLocalCache:
    """In-memory bucket store keyed by category slug. Same feature schema
    Overpass returns downstream so amenities_near() can splice results in
    without shape changes."""

    def __init__(self, path: str):
        self.path = path
        self.buckets: dict[str, list] = {}
        self.generated_at: Optional[str] = None
        self.source: Optional[str] = None
        self.total: int = 0
        self._loaded = False

    # -- Lifecycle --------------------------------------------------------

    def load(self) -> bool:
        """Load JSON snapshot from disk. Returns True on success, False if
        the file is missing / unreadable / stale-beyond-fallback."""
        p = Path(self.path)
        if not p.exists():
            print(f"osm_local: no snapshot at {self.path} — will fall back to Overpass")
            return False
        try:
            with open(p, "r", encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, ValueError) as e:
            print(f"osm_local: failed to read {self.path}: {e} — fallback to Overpass")
            return False
        meta = doc.get("meta") or {}
        self.buckets = doc.get("buckets") or {}
        self.generated_at = meta.get("generated_at")
        self.source = meta.get("source")
        self.total = meta.get("total", sum(len(v) for v in self.buckets.values()))
        self._loaded = True
        age = self.age_days()
        age_str = f"{age:.1f}d" if age is not None else "?"
        print(f"osm_local: {self.total} features, {len(self.buckets)} categories, "
              f"age {age_str}, source {self.source}")
        return True

    def loaded(self) -> bool:
        return self._loaded

    def age_days(self) -> Optional[float]:
        if not self.generated_at:
            return None
        try:
            gen = datetime.fromisoformat(self.generated_at.replace("Z", "+00:00"))
        except ValueError:
            return None
        return (datetime.now(timezone.utc) - gen).total_seconds() / 86400.0

    def is_stale(self) -> bool:
        age = self.age_days()
        return age is None or age > _STALE_AFTER_DAYS

    # -- Radius query ----------------------------------------------------

    def near(self, cat: str, lon: float, lat: float, radius_m: int) -> list[dict]:
        """Return every feature in `cat` within `radius_m` of (lon, lat).
        Each feature is augmented with `distance_m` and `source: 'osm'`.
        Sorted ascending by distance."""
        bucket = self.buckets.get(cat) or []
        hits = []
        for f in bucket:
            f_lat = f.get("lat"); f_lon = f.get("lon")
            if not isinstance(f_lat, (int, float)) or not isinstance(f_lon, (int, float)):
                continue
            d = haversine_m(lon, lat, f_lon, f_lat)
            if d <= radius_m:
                hits.append({**f, "distance_m": round(d), "source": "osm"})
        hits.sort(key=lambda x: x["distance_m"])
        return hits

    def provenance_suffix(self) -> str:
        """Short human-readable line for the amenities provenance field."""
        parts = ["© OpenStreetMap contributors (ODbL) via Geofabrik weekly snapshot"]
        age = self.age_days()
        if age is not None:
            parts.append(f"snapshot age {age:.0f} d")
        return " · ".join(parts)


def load_osm_local(path: Optional[str]) -> Optional[OsmLocalCache]:
    """Convenience factory. Returns None if the cfg didn't set a path or the
    file can't be loaded — caller then falls back to Overpass."""
    if not path:
        return None
    c = OsmLocalCache(path)
    if not c.load():
        return None
    return c
