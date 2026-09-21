# Hamburg rollout verification checklist

Post-deploy smoke tests. Run against `hamburg-staging.addrlens.de` first;
promote to `hamburg.addrlens.de` after all green.

## First-boot data seed

The `app-hh` container reads HVV transit CSVs from the bind-mounted volume
`/srv/addrlens/data/hamburg-transit/`. This directory does NOT exist on a
fresh host, and the refresh-hvv.timer only runs monthly, so you must seed
it before the first `docker compose up`.

**Option A — copy committed CSVs from the repo (fastest):**
```bash
sudo mkdir -p /srv/addrlens/data/hamburg-transit
sudo cp v0.1/app/cities/data/vbb_hamburg_su.csv \
        /srv/addrlens/data/hamburg-transit/
sudo cp v0.1/app/cities/data/hvv_hamburg_ferry.csv \
        /srv/addrlens/data/hamburg-transit/
```

**Option B — run the live refresh to get current month's GTFS data:**
```bash
sudo mkdir -p /srv/addrlens/data/hamburg-transit
docker compose \
    -f docker-compose.yml \
    -f docker-compose.prod.yml \
    --env-file /srv/addrlens/.env.production \
    run --rm --entrypoint python app-hh \
    -m scripts.refresh_hvv
```
The script will write directly to `/srv/hamburg-transit/` inside the container
(which maps to `/srv/addrlens/data/hamburg-transit/` on the host) via the
`HVV_OUT_SU` / `HVV_OUT_FERRY` env vars set in docker-compose.prod.yml.

- [ ] `/srv/addrlens/data/hamburg-transit/vbb_hamburg_su.csv` exists and is non-empty before `docker compose up`
- [ ] `/srv/addrlens/data/hamburg-transit/hvv_hamburg_ferry.csv` exists and is non-empty before `docker compose up`

## Boot
- [ ] `docker compose logs app-hh` shows all Hamburg loaders completing with expected counts (calibrated to 2026-09-21 live snapshot; small drift OK, large drops warrant investigation): schools ≥ 270 public Grundschulen, kitas ≥ 1100, hospitals ≥ 35, drinking fountains ≥ 40, S-Bahn ≥ 140, U-Bahn ≥ 200, ferry piers ≥ 30, sozialmonitoring polygons ≥ 1400, Bezirke = 7, parking zones ≥ 140, tempolimits segments ≥ 30 000, arterial segments ≥ 30 000; gesix empty; fire response zones empty (Hamburg has no zone polygon)
- [ ] `curl https://hamburg-staging.addrlens.de/health` → 200 `{"status":"ok"}`
- [ ] `curl https://hamburg-staging.addrlens.de/ready` → 200 `{"status":"ready","city":"hamburg"}`
- [ ] `curl https://hamburg-staging.addrlens.de/api/config | jq .slug` → `"hamburg"`
- [ ] `curl https://hamburg-staging.addrlens.de/api/config | jq .other_cities` shows Berlin cross-link entry
- [ ] `docker compose logs app` unchanged — Berlin app still serving `addrlens.de`
- [ ] `docker compose ps` shows both `app` (port 8001) + `app-hh` (port 8002) healthy

## Sample-address suite (10 addresses across all 7 Bezirke)

For each address, fetch `/api/lookup?street=...&hnr=...&plz=...` and verify:
1. Sternschanze — Susannenstr. 34, 20357 (Altona)
2. Ottensen — Bahrenfelder Str. 156, 22765 (Altona)
3. St. Pauli — Reeperbahn 1, 20359 (Hamburg-Mitte)
4. Winterhude — Sierichstr. 42, 22301 (Hamburg-Nord)
5. Blankenese — Elbchaussee 500, 22587 (Altona)
6. Wilhelmsburg — Vogelhüttendeich 30, 21107 (Hamburg-Mitte)
7. Rahlstedt — Rahlstedter Str. 42, 22143 (Wandsbek)
8. Hoheluft — Grindelallee 100, 20146 (Eimsbüttel)
9. Bergedorf-Zentrum — Sachsentor 20, 21029 (Bergedorf)
10. Harburg-Zentrum — Harburger Rathausplatz 1, 21073 (Harburg)

Per address:
- [ ] `/api/lookup` returns 200 with populated `sozialmonitoring` block (`statusindex`, `gesamtindex`, `dynamikindex`, `stadtteil`, `statgeb`, `berichtsjahr`, `provenance`)
- [ ] `nearest_school.distance_km` is present + realistic (0.05 – 3.0 km)
- [ ] `catchment.polygon` absent OR present (Hamburg catchments are Statistikgebiet-based, not per-school)
- [ ] `schools` array (drill-down for browser) or empty for Hamburg — accept either
- [ ] `connectivity.ferry` populated if within ~2 km of the Elbe (Wilhelmsburg, St. Pauli, Blankenese should hit)
- [ ] `connectivity.sbahn` + `.ubahn` populated
- [ ] `connectivity.airport` shows HAM (Hamburg Airport Helmut Schmidt)
- [ ] `others.bureaucracy.tiles` includes exactly one `standesamt` card
- [ ] `provenance.schools` cites LGV/BSB not Berlin BOD
- [ ] Raw view: Education / Amenities / Environment / Emergency / Connectivity / Others all render honestly
- [ ] No stray "Berlin" strings anywhere on the page (footer, meta, JSON-LD)
- [ ] Ferry tile in Newcomer + Commuter lens shows real HADAG pier + distance
- [ ] Noise bands render (not numeric dB — Hamburg uses isoline classes)
- [ ] Air card absent (Hamburg has no citywide NO₂ WFS — dropped per spec Q10)
- [ ] Fire card shows nearest station only (no response zone line — Hamburg has no fire-zone polygon layer)

## LLM insights
- [ ] Newcomer lens AI Insight generates for at least 3 of the sample addresses; text references HVV / Bücherhallen / ferry / Sozialmonitoring correctly (no Berlin-tile names — no "Bürgeramt", "Tram", "GESIx", "Wochenmarkt", "Weihnachtsmarkt" leak into the summary)
- [ ] Commuter lens AI Insight generates; text references HADAG / regional rail / Bewohnerparkgebiete correctly
- [ ] Both lenses' AI Insight cache: second lookup on same address returns `cached: true` within ~50 ms
- [ ] AI Insight `fit_score` computes non-null when at least one section rolls up to green/amber/red
- [ ] Cloudflare Workers AI is the routed backend for both templates (check `_state["remote"]` in `docker compose logs inference`)

## Legal
- [ ] `curl https://hamburg-staging.addrlens.de/impressum` returns Hamburg-specific data source list (LGV / BUKEA / BSB / BSW / HVV / HADAG / Geofabrik-Hamburg / OSM cited, no Berlin sources — no BOD Berlin, no VBB, no BVG)
- [ ] `curl https://hamburg-staging.addrlens.de/datenschutzerklaerung` names HmbBfDI (Der Hamburgische Beauftragte für Datenschutz und Informationsfreiheit, Ludwig-Erhard-Str. 22, 20459 Hamburg, datenschutz-hamburg.de) as data-protection authority
- [ ] Both legal pages carry Hamburg canonical URLs (`hamburg.addrlens.de/*`)
- [ ] `/robots.txt` allows public paths, disallows `/api/*`, points at `hamburg.addrlens.de/sitemap.xml`
- [ ] `/sitemap.xml` lists 3 Hamburg URLs only

## Cross-link
- [ ] Header shows "Also live in Berlin →" pill; click routes to `addrlens.de`
- [ ] Berlin's header (`addrlens.de`) shows "Also live in Hamburg →" pill; click routes to `hamburg.addrlens.de`
- [ ] Both pill hrefs use HTTPS

## SSR + CSP
- [ ] Hamburg `<body data-city="hamburg">` — inspect HTML source
- [ ] Hamburg hero SVG uses the Hamburg silhouette (not Berlin)
- [ ] Hamburg page title / meta / JSON-LD `addressLocality` all say "Hamburg"
- [ ] Response `Content-Security-Policy: script-src ... 'sha256-<hash>'` — the hash matches Hamburg's JSON-LD content (auto-computed at boot)
- [ ] Browser console shows no CSP violations on either page

## Metrics
- [ ] Umami `hamburg.addrlens.de` site tracks pageviews (create `UMAMI_WEBSITE_ID_HAMBURG` before deploy)
- [ ] Sentry `environment=hamburg-production` filter returns Hamburg-only events

## Data refresh timers
- [ ] `systemctl status refresh-hvv.timer` shows next fire on 1st of next month 05:00
- [ ] `systemctl status refresh-osm-hamburg.timer` shows next fire on next Sunday 04:00
- [ ] Manual trigger: `sudo systemctl start refresh-osm-hamburg.service` completes without error (verifies script + Docker plumbing)
- [ ] After first refresh, `docker compose logs app-hh --tail 20` shows OsmLocalCache reload

## Rollback path (dry-run)
- [ ] `docker compose stop app-hh` succeeds without affecting Berlin app
- [ ] Removing the `hamburg.addrlens.de` hostname at Cloudflare disconnects Hamburg without affecting `addrlens.de`
- [ ] Full rollback: `git revert <T22..T27 merge commit>` restores Berlin-only behaviour cleanly (verified in a scratch worktree)

## Sign-off
- [ ] All above green
- [ ] Cloudflare `hamburg.addrlens.de` hostname flipped from staging origin to prod `app-hh:8002`
- [ ] Blog post / social announcement drafted
- [ ] Berlin's `other_cities` cfg block updated to advertise Hamburg
