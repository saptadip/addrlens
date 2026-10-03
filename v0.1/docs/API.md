# AddrLens HTTP API

Public read-only HTTP API served by the per-city containers (`berlin.addrlens.de`, `hamburg.addrlens.de`). All endpoints are rate-limited per-IP (`X-Forwarded-For` from Cloudflare); limits noted per endpoint.

All responses are `application/json; charset=utf-8` unless noted. Error responses carry `{"detail": "..."}` with an HTTP status code.

Base URL depends on city:
- Berlin: `https://berlin.addrlens.de`
- Hamburg: `https://hamburg.addrlens.de`

The apex `addrlens.de` currently resolves to the Berlin container; a landing-page migration is planned (see `docs/superpowers/specs/2026-09-25-apex-landing-migration-design.md`).

---

## `GET /api/lookup`

Primary endpoint. Resolves an address to a lat/lon, computes catchment / schools / kitas / amenities / noise / air / heat / trees / quiet-zone / all configured life-lenses, and returns the full response payload.

**Rate limit:** 60 requests / minute / IP.

**Query parameters:**

| Name | Type | Required | Notes |
|---|---|---|---|
| `address` | string | one-of | Free-text address — e.g. `Kastanienallee 12, 10435`. Parsed into street / hnr / plz via `parse_address()`. Ignored if all three of `street`+`hnr`+`plz` are provided. Max 200 chars. **URL-encode spaces as `%20` or `+`.** |
| `street` | string | one-of | Street name — e.g. `Kastanienallee`. Max 100 chars. |
| `hnr` | string | one-of | House number — e.g. `12` or `11a`. Max 10 chars. |
| `plz` | string | one-of | 5-digit postal code — e.g. `10435`. |

Supply **either** `address` **or** all three of `street`+`hnr`+`plz`. If both are supplied, `street`/`hnr`/`plz` win.

**Examples:**

```bash
# Combined form (URL-encoded)
curl 'https://berlin.addrlens.de/api/lookup?address=Kastanienallee%2012%2C%2010435'

# Explicit form (preferred — no parse-error surface)
curl 'https://berlin.addrlens.de/api/lookup?street=Kastanienallee&hnr=12&plz=10435'

# Hamburg equivalent
curl 'https://hamburg.addrlens.de/api/lookup?street=Rathausmarkt&hnr=1&plz=20095'
```

**Response (abbreviated):**

```json
{
  "address":    {"street": "...", "hnr": "...", "plz": "...", "lon": 13.4132, "lat": 52.5219, "raw": {...}},
  "catchment":  {"esb": "...", "district": "...", "polygon": {...}, "schools_source": "esb|nearest|null"},
  "schools":    [...],
  "kitas":      [...],
  "connectivity": {"sbahn": {...}, "ubahn": {...}, "tram": {...}, "ferry": {...}, "regional_rail": {...}, "airport": {...}},
  "fire_rescue":  {...},
  "quiet_zone":   {...},
  "swim":         {"pools": [...], "natural": [...]},
  "trees":        {...},
  "air":          {"no2_ugm3": 25},
  "heat":         {"day_class": "...", "night_class": "..."},
  "lens": {
    "young_family":  {"slug": "young_family", "tiles": [...], "provenance": "..."},
    "newcomer":      {"slug": "newcomer",     "tiles": [...], "provenance": "..."},
    "quiet_living":  {...},
    "commuter":      {...}
  },
  "others":   {"bureaucracy": {...}},
  "provenance": {...}
}
```

**Errors:**

- `400 Missing street/hnr/plz.` — neither `address` nor the explicit triple was supplied with usable values.
- `400 Could not parse address. Try 'Kastanienallee 12, 10435'.` — `address` was supplied but `parse_address()` could not extract street/hnr/plz. Fall back to the explicit form.
- `404 Address '...' not found in <City>.` — geocoder returned no match. Verify the address exists in the target city.
- `404 Address '...' not recognised — check street number.` — upstream geocoder returned HTTP 400 (typically a street-type mismatch).
- `502 Geocoder unavailable, please retry.` — upstream geocoder is down or timing out.

---

## `GET /api/suggest`

Address autocomplete. Returns the top-N address matches for a partial query.

**Rate limit:** 5 requests / second / IP (debounced by the frontend, so this is for third-party integrations).

**Query parameters:**

| Name | Type | Required | Notes |
|---|---|---|---|
| `q` | string | yes | Partial address, min 2 chars, max 100 chars. |
| `limit` | int | no | Max results. Default 8. Range 1-N (see `_MAX_LIMIT` in source). |

**Example:**

```bash
curl 'https://berlin.addrlens.de/api/suggest?q=Kastanien&limit=5'
```

**Response:**

```json
{
  "hits": [
    {"label": "Kastanienallee 1, 10435", "street": "Kastanienallee", "hnr": "1", "plz": "10435", "lon": 13.4..., "lat": 52.5...},
    ...
  ]
}
```

Empty query (`q` shorter than 2 chars) returns `{"hits": []}` without error.

---

## `GET /api/noise`

Noise exposure at a specific lat/lon.

**Query parameters:**

| Name | Type | Required | Notes |
|---|---|---|---|
| `lat` | float | yes | Decimal latitude |
| `lon` | float | yes | Decimal longitude |

**Response (Berlin — point dB model):**

```json
{
  "noise": {
    "l_den":   {"total": 58, "road": 55, "rail": 49, "air": 42},
    "l_night": {"total": 52, "road": 48, "rail": 46, "air": 38},
    "tier":    "amber"
  }
}
```

**Response (Hamburg — isoline band model):**

```json
{
  "noise": {
    "bands": {"road_den_band": "55-59", "road_night_band": "<50"},
    "tier":  "amber"
  }
}
```

Note the structural difference per city — Berlin publishes per-façade dB from the Umweltatlas noise model; Hamburg publishes isoline band strings from BUKEA Lärmkarten 2022.

---

## `GET /api/amenities`

OSM-sourced amenities (gps / supermarkets / playgrounds / parks / transit / intl_food / coworking / etc.) within 800 m of the point.

**Query parameters:** `lat`, `lon` (both required floats).

**Example:**

```bash
curl 'https://berlin.addrlens.de/api/amenities?lat=52.5219&lon=13.4132'
```

**Response:**

```json
{
  "amenities": {
    "gps":          {"items": [...]},
    "supermarkets": {"items": [...]},
    "playgrounds":  {"items": [...]},
    "transit":      {"items": [...]},
    "parks":        {"items": [...]},
    ...
  },
  "provenance": "Berlin Open Data + OpenStreetMap (see per-category source)"
}
```

Each `items[]` entry carries `{name, tags, lon, lat, distance_m}`.

---

## `GET /api/config`

Per-city configuration consumed by the frontend on page load. No path params; the responding container's `CITY` env determines content.

**Example:**

```bash
curl 'https://berlin.addrlens.de/api/config'
```

**Response (abbreviated):**

```json
{
  "slug":           "berlin",
  "display_name":   "Berlin",
  "default_center": [52.52, 13.405],
  "attribution":    {"catchment": "...", "schools": "...", ...},
  ...
}
```

---

## `GET /api/history`

LLM-generated one-paragraph narrative of historic OSM points within 500 m of the address. Caches per ~100 m grid cell for 7 days.

**Rate limit:** 10 requests / minute / IP.

**Query parameters:**

| Name | Type | Required | Notes |
|---|---|---|---|
| `lat` | float | yes | Decimal latitude |
| `lon` | float | yes | Decimal longitude |
| `street` | string | no | For logging context only — NOT included in the LLM prompt (cache is per-cell, not per-address) |
| `hnr` | string | no | Same |
| `plz` | string | no | Same |
| `bezirk` | string | no | Included in the LLM prompt for borough context |
| `ortsteil` | string | no | Included in the LLM prompt for neighbourhood context |

**Example:**

```bash
curl 'https://berlin.addrlens.de/api/history?lat=52.5219&lon=13.4132&bezirk=Mitte&ortsteil=Mitte'
```

**Response:**

```json
{
  "history":        "On this block a Stolperstein commemorates ...",
  "features_count": 3,
  "model":          "llama-3.1-8b-instruct",
  "cached":         false
}
```

**Fallback responses:**

- `{"history": "No historic points on record within 500 m of this address.", "features_count": 0, "model": "none"}` — no OSM `historic=*` features in range
- `503 Location history requires the local OSM snapshot (v0.1 only). Run scripts/refresh_osm_amenities.py to seed it.` — the OSM snapshot the endpoint depends on is missing
- A degraded `{"history": "...", "degraded_reason": "..."}` payload when the inference layer is unreachable / timing out / returning malformed output (see `app/core/degraded.py`)

**Caveats:**

- The LLM can hallucinate — low temperature (0.4) + explicit anti-invention rules reduce but do not eliminate the risk. See the "Known limitations" section at the end of this document for how to verify a specific response against the raw OSM features.
- Caching is per ~100 m grid cell. Adjacent addresses return identical narratives.

---

## `POST /api/lens_insight`

LLM-generated executive summary of a specific lens' tile set at a specific address.

**Rate limit:** 10 requests / minute / IP.

**Request body (JSON):**

```json
{
  "lens":    "young_family",
  "address": {"lat": 52.5219, "lon": 13.4132},
  "tiles":   [
    {"key": "kita", "tier": "green", "rule": "...", "numeric": "..."},
    {"key": "playground", "tier": "amber", "rule": "...", "numeric": "..."},
    ...
  ]
}
```

`lens` must be one of the city's configured lens slugs. Berlin ships `young_family / newcomer / quiet_living / commuter`; Hamburg ships the same four.

**Response:**

```json
{
  "lens_insight": {
    "executive_summary": "...",
    "fit_score":  76,
    "sections": [
      {"title": "Kids & care", "verdict": "green", "paragraph": "..."},
      ...
    ],
    "highlights_green": [{"tile": "kita",     "one_line": "..."}, ...],
    "highlights_red":   [{"tile": "noise",    "one_line": "..."}, ...]
  },
  "model":  "llama-3.1-8b-instruct",
  "cached": false
}
```

**Errors:**

- `400 unknown lens '<x>' for city '<y>'; expected one of [...]` — lens slug not registered for this city.
- `400 address.lat and address.lon are required`
- `400 tiles array is required and non-empty`
- Degraded responses when the inference layer is unavailable.

---

## `GET /health`

Lightweight healthcheck used by Docker + Cloudflare Tunnel.

**Response:** `{"status": "ok"}` with HTTP 200. No parameters, no rate limit.

---

## `GET /ready`

Readiness check — returns 200 only when the index has finished loading at startup.

**Response:** `{"status": "ready", "city": "berlin"}` (or `"hamburg"`) when ready. Returns 503 during startup until the index is populated.

---

## HTML routes (not JSON)

For completeness — these serve HTML, not API data:

- `GET /` — main SPA
- `GET /impressum` — imprint
- `GET /datenschutzerklaerung` — privacy notice
- `GET /robots.txt`
- `GET /sitemap.xml`

---

## Known limitations

### History endpoint can hallucinate

The `/api/history` narrative is LLM-generated from OSM `historic=*` features within 500 m. Low temperature (0.4) + explicit "only mention facts present in the JSON" + "no invention" system-prompt rules reduce but do not eliminate hallucination risk. Known failure modes:

1. The model conflates two features into one (e.g. two Stolpersteine → one invented person)
2. The model generalises an OSM tag (`historic=memorial` becomes "a tombstone" when it's actually a plaque)
3. The model adds plausible-but-unverified context ("red-brick 19th-century" when the data didn't say that)
4. The model copies context from the few-shot exemplar (Anna Winter / Kulturbrauerei) into unrelated outputs

**To verify a specific response:**

1. Fetch the raw OSM features the endpoint reads:
   ```bash
   LAT=52.5219 LON=13.4132
   curl -sG 'https://overpass-api.de/api/interpreter' \
     --data-urlencode "data=[out:json][timeout:25];(nwr[\"historic\"](around:500,$LAT,$LON);); out tags center;" \
     | jq '.elements[] | {historic:.tags.historic, name:.tags.name, inscription:.tags.inscription}'
   ```
2. Fetch the AddrLens narrative:
   ```bash
   curl -sS "https://berlin.addrlens.de/api/history?lat=$LAT&lon=$LON" | jq .
   ```
3. Any claim in the narrative not traceable to step-1's raw tags is a hallucination.

A proper verification harness is on the roadmap (see the Prototype Fund / NLnet grant proposals under `docs/superpowers/plans/`).

### Noise comparison between road and S-Bahn

The `/api/noise` endpoint returns separate `road` / `rail` / `air` values from the official city noise model (Berlin: Umweltatlas Lärmkarten 2022; Hamburg: BUKEA Lärmkarten 2022). If the road value exceeds the rail value at an address near an S-Bahn line, this may be:

- Correct per the official model (the model treats partially-covered S-Bahn cuttings as fully attenuated)
- A loader bug — verify against the official source at [FIS-Broker](https://fbinter.stadt-berlin.de/fb/index.jsp) (Berlin) or [Transparenzportal Hamburg](https://transparenz.hamburg.de/) (Hamburg)

Open a GitHub issue with the address if the AddrLens values don't match the official source.

### Content Security Policy — Cloudflare injection

The site runs behind Cloudflare Tunnels. Cloudflare's edge injects a small inline script (`<script>(function(){...challenge-platform...})()</script>`) at the end of every HTML response for its JavaScript Detections / Bot Fight Mode feature. The injection happens AFTER FastAPI serves the HTML, so the server's `Content-Security-Policy` header doesn't cover it.

Browser consoles report:

```
Executing inline script violates the following Content Security Policy directive 'script-src 'self' https://unpkg.com https://umami.addrlens.de 'sha256-...''.
Either the 'unsafe-inline' keyword, a hash ('sha256-M3cFExag...'), or a nonce ('nonce-...') is required to enable inline execution.
```

The injected script's content includes per-request tokens (`r`, `t`) so its SHA-256 hash changes every response — a hash-based CSP whitelist is impossible.

**Fix:** disable Cloudflare JavaScript Detections / Bot Fight Mode for the AddrLens zone in the Cloudflare dashboard (`Security > Bots > Configure Bot Fight Mode`). The feature adds no value for a stateless public read-only API — see `ops/cloudflared/README.md#csp` for the full ops writeup.
