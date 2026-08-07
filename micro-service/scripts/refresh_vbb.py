"""Refresh the vendored Berlin S/U-Bahn station list from VBB open data.

Data source: VBB "Koordinaten der Zugangsmöglichkeiten zu Stationen"
(CC-BY-4.0, publisher Verkehrsverbund Berlin-Brandenburg).

Run:
    python -m scripts.refresh_vbb                    # rebuild vendored CSV
    python -m scripts.refresh_vbb --find "Warschau"  # look up coord for
                                                     # a regional-rail
                                                     # station name

The vendored CSV feeds Index.sbahn / Index.ubahn (see app/core/index.py).
Re-run manually when VBB refreshes UMBW.zip (roughly annually — coord
drift for existing stations is millimetres, so a stale vendor is fine
for weeks).
"""
import argparse
import csv
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

VBB_ZIP_URL = "https://www.vbb.de/fileadmin/user_upload/VBB/Dokumente/API-Datensaetze/UMBW.zip"
OUT = Path(__file__).resolve().parent.parent / "app" / "cities" / "data" / "vbb_berlin_su.csv"


def fetch_umbw_rows():
    """Yield decoded rows from UMBW.CSV inside the VBB zip."""
    # vbb.de rejects urllib's default User-Agent (403). Any non-empty UA works.
    req = urllib.request.Request(VBB_ZIP_URL, headers={"User-Agent": "addrlens/refresh_vbb"})
    with urllib.request.urlopen(req, timeout=60) as r:
        buf = io.BytesIO(r.read())
    with zipfile.ZipFile(buf) as z:
        with z.open("UMBW.CSV") as f:
            text = f.read().decode("latin-1")
    reader = csv.reader(io.StringIO(text), delimiter=";")
    return list(reader)


def _mode(name: str) -> str:
    """S+U / S / U / other — derived from name prefix as VBB encodes it."""
    if name.startswith("S+U "): return "S+U"
    if name.startswith("S ") and not name.startswith("S+U "): return "S"
    if name.startswith("U "): return "U"
    return "other"


def _to_float(s: str) -> float:
    """VBB uses German-style comma decimal."""
    return float(s.replace(",", "."))


def build_vendor(rows) -> list[dict]:
    """Berlin S/U-Bahn stations at the station level (one row per station)."""
    header = rows[0]
    out = []
    for r in rows[1:]:
        if r[2].strip() != "Bauwerk":
            continue
        name = r[0]
        if "(Berlin)" not in name:
            continue
        mode = _mode(name)
        if mode == "other":
            continue
        out.append({
            "name": name.replace(" (Berlin)", "").strip(),
            "mode": mode,
            "lat": round(_to_float(r[6]), 6),
            "lon": round(_to_float(r[5]), 6),
        })
    out.sort(key=lambda x: (x["mode"], x["name"]))
    return out


def write_vendor(records: list[dict]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["name", "mode", "lat", "lon"])
        w.writeheader()
        w.writerows(records)


def find(rows, query: str) -> None:
    """--find helper: print every UMBW row whose Bauwerk name matches. Use
    when adding a new regional-rail station to BERLIN.regional_rail_stations
    — grep for the name here, copy the coord."""
    q = query.lower()
    hits = 0
    for r in rows[1:]:
        if r[2].strip() != "Bauwerk":
            continue
        if q in r[0].lower():
            print(f"  {r[0]!r}  → lat={_to_float(r[6]):.6f}  lon={_to_float(r[5]):.6f}")
            hits += 1
    if not hits:
        print(f"  (no matches for {query!r})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--find", metavar="QUERY",
                    help="Print UMBW rows whose station name contains QUERY. "
                         "Useful for extending BERLIN.regional_rail_stations.")
    args = ap.parse_args()

    print(f"fetching {VBB_ZIP_URL} …", flush=True)
    rows = fetch_umbw_rows()
    print(f"  {len(rows)} rows")

    if args.find:
        print(f"\nmatches for {args.find!r}:")
        find(rows, args.find)
        return 0

    recs = build_vendor(rows)
    from collections import Counter
    c = Counter(r["mode"] for r in recs)
    print(f"\nBerlin S/U stations by mode: {dict(c)}  (total {len(recs)})")
    write_vendor(recs)
    print(f"\nwrote {OUT.relative_to(Path.cwd()) if Path.cwd() in OUT.parents else OUT}")
    print(f"  {OUT.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
