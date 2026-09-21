"""Refresh the vendored HVV S/U-Bahn + HADAG ferry CSVs from HVV GTFS.

Data source: hvv Fahrplandaten (GTFS), monthly re-issue on Transparenzportal
Hamburg (dl-de/by-2-0). URL contains a UUID that changes monthly, so this
script scrapes the landing page for the current zip.

Landing page: https://suche.transparenz.hamburg.de/dataset (search)
Attribution: Hamburger Verkehrsverbund GmbH.

Run:
    python -m scripts.refresh_hvv               # scrape + fetch current issue
    python -m scripts.refresh_hvv --zip <path>  # use a pre-downloaded zip (dev)
"""
from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

TRANSPARENZPORTAL_SEARCH = ("https://suche.transparenz.hamburg.de/dataset?q="
                            "hvv+Fahrplandaten+GTFS&sort=metadata_modified+desc")

OUT_SU     = Path(__file__).resolve().parent.parent / "app" / "cities" / "data" / "vbb_hamburg_su.csv"
OUT_FERRY  = Path(__file__).resolve().parent.parent / "app" / "cities" / "data" / "hvv_hamburg_ferry.csv"

# GTFS route_type values (spec §2.1 base codes + HVV extended hierarchy codes).
# HVV GTFS Fpl_20260903 uses extended codes exclusively for metro/S-Bahn/ferry;
# the base codes (1, 2, 4) are absent in that feed. We match both sets so the
# script remains forward-compatible if HVV ever switches back to base codes.
#   base: 1=subway, 2=rail, 4=ferry
#   extended (Google Transit / NeTEx hierarchy):
#     109=S-Bahn, 402=U-Bahn/metro, 1200=water transport (HADAG ferry)
_ROUTE_TYPE_SUBWAY  = {"1",   "402"}   # U-Bahn (base + extended)
_ROUTE_TYPE_RAIL    = {"2",   "109"}   # S-Bahn + RE/RB (base + extended)
_ROUTE_TYPE_FERRY   = {"4",   "1200"}  # HADAG ferry (base + extended)


def _fetch_current_zip_url() -> str:
    """Scrape the Transparenzportal search page for the newest hvv GTFS dataset."""
    req = urllib.request.Request(TRANSPARENZPORTAL_SEARCH,
                                 headers={"User-Agent": "addrlens/refresh_hvv"})
    with urllib.request.urlopen(req, timeout=60) as r:
        html = r.read().decode("utf-8", errors="replace")
    # Landing pages match /dataset/hvv-fahrplandaten-gtfs-...
    m = re.search(r'href="(/dataset/hvv-fahrplandaten-gtfs-[a-z0-9-]+)"', html)
    if not m:
        raise RuntimeError("no HVV GTFS dataset found on Transparenzportal search")
    landing_path = m.group(1)
    landing_url = f"https://suche.transparenz.hamburg.de{landing_path}"
    req = urllib.request.Request(landing_url,
                                 headers={"User-Agent": "addrlens/refresh_hvv"})
    with urllib.request.urlopen(req, timeout=60) as r:
        page = r.read().decode("utf-8", errors="replace")
    m = re.search(r'https://daten\.transparenz\.hamburg\.de/[^"\s]+Upload__hvv_Rohdaten_GTFS_Fpl_\d+\.ZIP', page)
    if not m:
        raise RuntimeError(f"no ZIP link found on landing page {landing_url}")
    return m.group(0)


def _download_zip(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "addrlens/refresh_hvv"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def _classify_su_mode(route_short_names: set[str]) -> str:
    """Given the set of route_short_names touching a stop, classify as
    S / U / S+U / other. Copied logic mirrors refresh_vbb._mode()."""
    has_s = any(n.startswith("S") for n in route_short_names)
    has_u = any(n.startswith("U") for n in route_short_names)
    if has_s and has_u: return "S+U"
    if has_s:           return "S"
    if has_u:           return "U"
    return "other"


def _peak_only_from_calendar(calendar_csv: str, service_id: str) -> bool:
    """A service_id is peak-only if it operates Mon-Fri but neither Sat nor Sun."""
    reader = csv.DictReader(io.StringIO(calendar_csv))
    for row in reader:
        if row["service_id"] != service_id: continue
        weekday = all(row[d] == "1" for d in
                      ("monday", "tuesday", "wednesday", "thursday", "friday"))
        weekend = row["saturday"] == "1" or row["sunday"] == "1"
        return weekday and not weekend
    return False


def _extract_stops_for_route_types(*, stops_csv: str, routes_csv: str,
                                    trips_csv: str, stop_times_csv: str,
                                    route_types: set[str]) -> list[dict]:
    """Return list of {stop_id, name, lat, lon, route_short_names, service_ids}
    for stops touched by any route in route_types. Aggregates unique routes/
    services across all trips at each stop."""
    routes_by_id = {r["route_id"]: r for r in csv.DictReader(io.StringIO(routes_csv))}
    matching_route_ids = {rid for rid, r in routes_by_id.items()
                          if r["route_type"] in route_types}
    trips_by_id = {t["trip_id"]: t for t in csv.DictReader(io.StringIO(trips_csv))}
    matching_trip_ids = {tid for tid, t in trips_by_id.items()
                         if t["route_id"] in matching_route_ids}
    stops_by_id = {s["stop_id"]: s for s in csv.DictReader(io.StringIO(stops_csv))
                   if s.get("location_type", "0") in ("", "0", "1")}
    stop_routes: dict[str, set] = defaultdict(set)
    stop_services: dict[str, set] = defaultdict(set)
    for row in csv.DictReader(io.StringIO(stop_times_csv)):
        if row["trip_id"] not in matching_trip_ids: continue
        stop_id = row["stop_id"]
        if stop_id not in stops_by_id: continue
        trip = trips_by_id[row["trip_id"]]
        route = routes_by_id[trip["route_id"]]
        stop_routes[stop_id].add(route.get("route_short_name", route["route_id"]))
        stop_services[stop_id].add(trip.get("service_id", ""))
    out = []
    for stop_id, routes in stop_routes.items():
        s = stops_by_id[stop_id]
        out.append({
            "stop_id": stop_id,
            "name":    s["stop_name"],
            "lat":     float(s["stop_lat"]),
            "lon":     float(s["stop_lon"]),
            "route_short_names": routes,
            "service_ids":       stop_services[stop_id],
        })
    return out


def _write_su_csv(stops: list[dict], out_path: Path) -> int:
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "lat", "lon", "mode"])
        n = 0
        for s in stops:
            mode = _classify_su_mode(s["route_short_names"])
            if mode == "other": continue
            w.writerow([s["name"], f"{s['lat']:.6f}", f"{s['lon']:.6f}", mode])
            n += 1
    return n


def _write_ferry_csv(stops: list[dict], calendar_csv: str, out_path: Path) -> int:
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["name", "lat", "lon", "lines", "peak_only"])
        n = 0
        for s in stops:
            lines = ",".join(sorted(s["route_short_names"]))
            peak_only = all(_peak_only_from_calendar(calendar_csv, sid)
                            for sid in s["service_ids"] if sid)
            w.writerow([s["name"], f"{s['lat']:.6f}", f"{s['lon']:.6f}",
                        lines, "1" if peak_only else "0"])
            n += 1
    return n


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--zip", help="Path to a pre-downloaded HVV GTFS zip (dev)")
    args = p.parse_args()
    if args.zip:
        buf = Path(args.zip).read_bytes()
    else:
        url = _fetch_current_zip_url()
        print(f"Fetching {url}", file=sys.stderr)
        buf = _download_zip(url)
    with zipfile.ZipFile(io.BytesIO(buf)) as z:
        stops_csv      = z.read("stops.txt").decode("utf-8")
        routes_csv     = z.read("routes.txt").decode("utf-8")
        trips_csv      = z.read("trips.txt").decode("utf-8")
        stop_times_csv = z.read("stop_times.txt").decode("utf-8")
        calendar_csv   = z.read("calendar.txt").decode("utf-8")
    su_stops = _extract_stops_for_route_types(
        stops_csv=stops_csv, routes_csv=routes_csv, trips_csv=trips_csv,
        stop_times_csv=stop_times_csv,
        route_types=_ROUTE_TYPE_SUBWAY | _ROUTE_TYPE_RAIL,
    )
    ferry_stops = _extract_stops_for_route_types(
        stops_csv=stops_csv, routes_csv=routes_csv, trips_csv=trips_csv,
        stop_times_csv=stop_times_csv,
        route_types=_ROUTE_TYPE_FERRY,
    )
    n_su = _write_su_csv(su_stops, OUT_SU)
    n_ferry = _write_ferry_csv(ferry_stops, calendar_csv, OUT_FERRY)
    print(f"wrote {n_su} S/U stops to {OUT_SU}")
    print(f"wrote {n_ferry} ferry piers to {OUT_FERRY}")


if __name__ == "__main__":
    main()
