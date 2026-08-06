"""BOD-first / OSM-supplement dedupe. Verbatim from phase3/server.py.

BOD (city open data) is authoritative; OSM fills known gaps. Dedupe drops
any OSM item whose centroid is within BOD_DEDUPE_M of a BOD centroid.
"""
from app.core.geo import haversine_m

BOD_DEDUPE_M = 50   # OSM item within this radius of a BOD centroid is a duplicate.


def _bod_area_summary(item):
    """One-liner summary for a BOD polygon feature (playground or park)."""
    parts = []
    a = item.get("area_m2")
    if a:
        try:
            a = float(a)
            parts.append(f"{a/10_000:.1f} ha" if a >= 10_000 else f"{int(a):,} m²")
        except (ValueError, TypeError): pass
    p = item.get("props") or {}
    if p.get("bezirkname"):                     parts.append(p["bezirkname"])
    if p.get("sanierjahr") and p["sanierjahr"].strip():
        parts.append(f"Renovated {p['sanierjahr'].strip()}")
    return " · ".join(parts)


def merge_bod_and_osm(bod_items, osm_items, radius_m):
    """BOD-first, OSM as supplement. Drop OSM items within BOD_DEDUPE_M of any BOD centroid.
    Returns merged list, sorted by distance, with per-item 'source' preserved."""
    merged = []
    for it in bod_items:
        if it.get("_error"): continue
        merged.append({**it, "info": it.get("info") or _bod_area_summary(it)})
    for it in osm_items:
        if any(haversine_m(it["lon"], it["lat"], b["lon"], b["lat"]) < BOD_DEDUPE_M for b in merged):
            continue
        merged.append({**it, "source": "osm"})
    merged.sort(key=lambda x: x["distance_m"])
    return merged[:radius_m and 25]     # cap same as before


if __name__ == "__main__":
    # Dedupe asserts copied verbatim from phase3/server.py:_selfcheck.
    bod = [{"name": "A", "lat": 52.5, "lon": 13.4, "distance_m": 100,
            "source": "bod", "area_m2": 1000, "props": {}}]
    osm_dup = [{"name": "A", "lat": 52.5, "lon": 13.4, "distance_m": 100, "info": ""}]
    osm_new = [{"name": "B", "lat": 52.6, "lon": 13.5, "distance_m": 200, "info": ""}]
    merged = merge_bod_and_osm(bod, osm_dup + osm_new, 800)
    assert len(merged) == 2 and {m["source"] for m in merged} == {"bod", "osm"}
    # _bod_area_summary formats sensibly.
    assert _bod_area_summary({"area_m2": 15000, "props": {}}) == "1.5 ha"
    assert _bod_area_summary({"area_m2": 900, "props": {}}) == "900 m²"
    print("merge.py selfcheck OK")
