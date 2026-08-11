"""Weekly Geofabrik OSM refresh — Berlin extract → filtered amenities JSON.

Downloads berlin-latest.osm.pbf (~75 MB) from Geofabrik, filters for the six
tag combos this app queries via Overpass in production, writes an atomic JSON
snapshot to the on-disk cache path. Cron target: Sunday 03:00 CET.

Categories mirror app/core/amenities.py:AMENITIES exactly so amenities_near()
can swap Overpass ↔ local snapshot without shape changes.

Cost: ~75 MB download (12 s on 50 Mbps) + ~30 s pyosmium parse = ~1 min end
to end. Zero Overpass dependency.

Data source: https://download.geofabrik.de/europe/germany/berlin.html
Licence: ODbL 1.0 — same as OpenStreetMap. Attribution already required and
present in the app's Attribution modal.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import osmium

# --- Category → OSM tag rules (must match app/core/amenities.py:AMENITIES) ---
# Each rule is a list of (tag_key, allowed_values) pairs — feature matches
# if ANY pair matches. Most categories are single-key, hospitals are OR-of-2.
_TAG_RULES = {
    "playgrounds":  [("leisure",          {"playground"})],
    "parks":        [("leisure",          {"park"})],
    "pharmacies":   [("amenity",          {"pharmacy"})],
    "supermarkets": [("shop",             {"supermarket"})],
    "gps":          [("amenity",          {"doctors"})],
    "transit":      [("public_transport", {"platform", "station"})],
    # Hospital contact overlay — enriches BOD hospital records with OSM's
    # phone/website/emergency/wheelchair when the campuses match within
    # hospital_match_m. Both tag conventions (`amenity=hospital` and
    # `healthcare=hospital`) are common; either qualifies.
    "hospital":     [("amenity",          {"hospital"}),
                     ("healthcare",       {"hospital"})],
}

# Categories that must have a `name` tag to survive (mirrors _DROP_UNNAMED
# in amenities.py — unnamed parks/playgrounds are noise). Others keep even
# if unnamed; a fallback label is applied at read time by amenities_near.
_DROP_UNNAMED = {"parks", "playgrounds"}

GEOFABRIK_URL = "https://download.geofabrik.de/europe/germany/berlin-latest.osm.pbf"


def _cat_for(tags) -> str | None:
    """Return the category slug this OSM feature belongs to, or None."""
    for cat, rules in _TAG_RULES.items():
        for k, vs in rules:
            v = tags.get(k)
            if v and v in vs:
                return cat
    return None


class _AmenityCollector(osmium.SimpleHandler):
    """Single-pass filter. Nodes give exact lat/lon; ways average their node
    coords (accurate enough for a search-radius amenity, no need for real
    polygon centroids). Multipolygon relations are skipped — Berlin's
    parks-as-relations count is small; we lose <2% and avoid a two-pass merge."""

    def __init__(self):
        super().__init__()
        self.buckets = {cat: [] for cat in _TAG_RULES}
        self.seen = set()   # dedup by (cat, round(lat,5), round(lon,5))

    def _add(self, cat, lat, lon, tags):
        key = (cat, round(lat, 5), round(lon, 5))
        if key in self.seen:
            return
        self.seen.add(key)
        name = (tags.get("name") or "").strip()
        if cat in _DROP_UNNAMED and not name:
            return
        # Store as a plain dict — same shape Overpass returns downstream.
        entry = {"name": name, "lat": lat, "lon": lon,
                 "tags": {k: v for k, v in tags}}
        self.buckets[cat].append(entry)

    def node(self, n):
        cat = _cat_for(n.tags)
        if not cat:
            return
        self._add(cat, n.location.lat, n.location.lon, n.tags)

    def way(self, w):
        cat = _cat_for(w.tags)
        if not cat:
            return
        # locations=True on apply_file populates w.nodes[i].location.
        # Average the node coords for a rough centroid — accurate enough
        # for "is this park within 800 m" reasoning.
        lats, lons, n = 0.0, 0.0, 0
        for nd in w.nodes:
            try:
                if not nd.location.valid():
                    continue
                lats += nd.location.lat
                lons += nd.location.lon
                n += 1
            except Exception:
                continue
        if n == 0:
            return
        self._add(cat, lats / n, lons / n, w.tags)


def download_pbf(url: str, dest: Path) -> Path:
    """Stream Geofabrik pbf to a temp path, then atomic-rename to dest.
    Returns the final path. Raises on any HTTP or IO error."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    print(f"↓ downloading {url}", flush=True)
    t0 = time.time()
    req = urllib.request.Request(url,
        headers={"User-Agent": "berlin-address-intelligence/0.1 (contact via GitHub)"})
    with urllib.request.urlopen(req, timeout=300) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, length=1 << 20)     # 1 MiB chunks
    size_mb = tmp.stat().st_size / (1024 * 1024)
    print(f"  {size_mb:.1f} MB in {time.time()-t0:.1f}s", flush=True)
    os.replace(tmp, dest)
    return dest


def parse_and_filter(pbf: Path) -> dict:
    """Filter the pbf into our 6 category buckets. Returns the bucket dict."""
    print(f"⚙  parsing {pbf.name}", flush=True)
    t0 = time.time()
    h = _AmenityCollector()
    # locations=True + idx=flex_mem builds a node→coord index so way/area
    # centres can be computed on the fly. Berlin fits comfortably in RAM.
    h.apply_file(str(pbf), locations=True, idx="flex_mem")
    total = sum(len(v) for v in h.buckets.values())
    per_cat = " · ".join(f"{k}:{len(v)}" for k, v in h.buckets.items())
    print(f"  {total} features in {time.time()-t0:.1f}s ({per_cat})", flush=True)
    return h.buckets


def write_snapshot(buckets: dict, out: Path, source: str) -> None:
    """Atomic write of the JSON snapshot with a meta header."""
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source":       source,
            "categories":   list(buckets.keys()),
            "total":        sum(len(v) for v in buckets.values()),
        },
        "buckets": buckets,
    }
    tmp = out.with_suffix(out.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, out)
    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"✓ wrote {out} ({size_mb:.1f} MB, {doc['meta']['total']} features)", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data-dir", default=os.environ.get("OSM_DATA_DIR", "data/osm"),
                    help="host filesystem dir (dev) or Docker volume mount (prod)")
    ap.add_argument("--url", default=GEOFABRIK_URL,
                    help="Geofabrik pbf URL (default: Berlin)")
    ap.add_argument("--skip-download", action="store_true",
                    help="re-parse an existing pbf without re-downloading")
    args = ap.parse_args()

    data_dir = Path(args.data_dir).resolve()
    pbf_path = data_dir / "berlin-latest.osm.pbf"
    json_path = data_dir / "berlin-amenities.json"

    if not args.skip_download:
        download_pbf(args.url, pbf_path)
    elif not pbf_path.exists():
        print(f"! --skip-download but {pbf_path} missing", file=sys.stderr)
        sys.exit(2)

    buckets = parse_and_filter(pbf_path)
    write_snapshot(buckets, json_path,
                   source=f"Geofabrik {args.url.rsplit('/', 1)[-1]} "
                          f"({datetime.fromtimestamp(pbf_path.stat().st_mtime, tz=timezone.utc).date()})")


if __name__ == "__main__":
    main()
