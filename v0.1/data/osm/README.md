# OSM local snapshot (Geofabrik)

Contains the weekly Berlin OSM extract + the derived amenities snapshot the
app reads at boot in place of hitting Overpass.

## Files

| File | Origin | Refresh | Size |
|---|---|---|---|
| `berlin-latest.osm.pbf` | `https://download.geofabrik.de/europe/germany/berlin-latest.osm.pbf` | weekly | ~95 MB |
| `berlin-amenities.json` | filtered from the pbf by `scripts/refresh_osm_amenities.py` | after every pbf refresh | ~4 MB |

## Manual refresh

```bash
cd v0.1/
.venv/bin/python -m scripts.refresh_osm_amenities
# --skip-download to re-parse an existing pbf without re-fetching
```

Both files are written atomically (rename over temp) — safe against a running
uvicorn holding the previous JSON in memory. The next uvicorn restart picks
up the new file.

## Cadence — Sunday 03:00 CET cron

Local host (macOS launchd or cron):

```cron
# /etc/cron.d/osm-refresh — or ~/Library/LaunchAgents equivalent on macOS
0 3 * * 0 cd /path/to/v0.1 && .venv/bin/python -m scripts.refresh_osm_amenities >> /var/log/osm-refresh.log 2>&1
```

Docker (add to your compose or k8s cronjob):

```yaml
services:
  osm-refresh:
    image: berlin-address-intel:v0.1
    entrypoint: [".venv/bin/python", "-m", "scripts.refresh_osm_amenities"]
    volumes:
      - osm-data:/data/osm
    environment:
      - OSM_DATA_DIR=/data/osm
    # Schedule via docker-compose deploy.restart_policy + external cron,
    # or use a k8s CronJob with schedule: "0 3 * * 0" (TZ: Europe/Berlin).

volumes:
  osm-data: {}
```

App reads the location from env var `OSM_LOCAL_PATH` (default `data/osm/berlin-amenities.json`).
In prod, mount a Docker volume at e.g. `/mnt/osm/` and set
`OSM_LOCAL_PATH=/mnt/osm/berlin-amenities.json`.

## Licence

OSM data © OpenStreetMap contributors, distributed under the
[Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/).
Geofabrik hosts the extract for free under the same terms
([policy](https://download.geofabrik.de/technical.html)). The
Attribution modal in `web/index.html` already carries the required notice.
