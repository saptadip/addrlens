# Production Readiness Review — Berlin Address Intelligence

**Date:** 2026-08-14
**Scope:** `v0.1/` tree (live) plus `micro-service/` mirror
**Author:** Review conducted with Claude Code

---

## TL;DR

The application is **soft-launch ready with four hard blockers resolved**. Feature
completeness for a v1 is genuinely there — three lenses (Young Family, Newcomer,
Bureaucracy), a raw-view Amenities strip, an Environment tab, per-tile AI insight
paragraphs, and provenance strings on every dataset. The engineering shape is
right: two-service split (per-city app + shared inference service), background
model load with a `/ready` gate, honest per-module selfchecks.

However, several items must land before any public URL goes live in Germany,
and several more should land before a public announcement (Product Hunt / HN /
`r/berlin`).

The user's plan — "run on a live server for a few weeks, then announce" — is
the right shape. Beta is only useful if you are measuring the right things
during it.

---

## What is already solid

- **Feature scope:** 3 lenses, ~27 tiles, raw-view amenities across 11
  categories including the newly added EV charging, environment tab covering
  noise / air / heat / street trees / quiet zones.
- **Data model + provenance:** Every tile carries a `sources` field pulled
  from `cfg.attribution`. Provenance strings preserve dl-de, ODbL, CC-BY
  licences correctly.
- **Two-service architecture:** App (per-city image, one instance per city
  via `CITY` env var) plus inference (city-agnostic, `mlx` or `llama`
  backend). Correct production shape.
- **Cold-start discipline:** Index build is blocking at boot; `/ready`
  returns 503 until Index is loaded. Inference `/ready` is 503 until the
  model warms in a background thread. Orchestrators can gate traffic
  correctly.
- **Selfcheck hygiene:** Every module has a `__main__` pure-assert block;
  each service has a `selfcheck.py` orchestrator that exercises live paths.
  Better test discipline than most side projects at this stage.
- **Config-as-data city model:** Adding a new city is one file in
  `app/cities/`, no cross-cutting changes.
- **Recent additions (this session):** Newcomer lens gained language school,
  library, packstation, wochenmarkt (labelled "Open market"), and
  nightlife density (numeric-only, no verdict). EV charging in the raw
  Amenities strip. Neighbourhood profile now carries a quintile-based
  tier verdict on both lenses. All shipped with matching selfchecks.

---

## Hard blockers before any public URL goes live

These are non-negotiable for a soft launch in Germany.

### 1. Impressum + Datenschutzerklärung

Legally required in Germany under §5 TMG (Impressum) and DSGVO (privacy
policy) even for a private beta on a public URL. Without them, a single
Abmahnung from a compliance troll costs €500-2000 and forces takedown.

**Action:** either use an Impressum generator (`e-recht24.de` /
`impressum-generator.de`) with the user's real name and postal address,
or engage a German lawyer for a one-shot review (~€200).

Both docs must be linked from the site footer.

### 2. HTTPS + basic monitoring

There is no TLS story documented and no monitoring in place. Under real
traffic, silent failures become invisible.

**Minimum:**
- Reverse proxy: Caddy or nginx with Let's Encrypt (Caddy is one file).
- Error tracking: Sentry free tier is enough for 5k events/month.
- Uptime pinger: UptimeRobot free tier, one check per service (`/ready`
  on both app and inference).

### 3. Rate limiting on `/api/card_insight`

LLM inference is the expensive path. A single scraper, botnet, or one
enthusiastic user pointed at a for-loop can burn thousands of tokens
per hour. Currently there is no protection.

**Action:** per-IP token bucket, ~10 requests per minute. Implementable
with `slowapi` or a Redis-backed limiter. Apply on `/api/card_insight`
only; leave `/api/lookup` and `/api/amenities` more permissive (they
are cheap).

### 4. Weekly OSM refresh cron + boot resilience

`scripts/refresh_osm_amenities.py` currently runs manually. It needs
to be a scheduled task (systemd timer, cron, or GitHub Actions
producing an artifact).

**More critical:** `Index` build at boot fails hard if a single Berlin
Geoportal WFS layer returns 5xx. That means one bad day at
`gdi.berlin.de` = pod will not boot at all until Berlin fixes their
end. This is not acceptable for production.

**Action:** wrap each WFS loader in per-layer try/except; on failure,
mark the layer as `degraded` in a `/api/config` diagnostic response
and boot with a partial Index rather than crashing. Users see specific
tiles missing rather than a 503 across the whole product.

---

## Should-fix before public announcement

These do not block the soft-launch but should land during the beta window
before broader marketing.

### 5. Analytics

Without analytics you cannot make v2 priorities on evidence. Which tiles
get their modal opened? Which addresses get looked up? Which Bezirke are
we useful for?

**Recommended:** Plausible or Umami. Both are GDPR-friendly (no cookie
banner needed with the right config).

### 6. Inference response cache

Currently every hit to `/api/card_insight` calls the model. Cache by
`(card_key, hash(tile_json_context))` with a 24h TTL. This saves 90%+
of inference cost for repeat viewers and cuts p50 latency for cached
requests from ~3s to ~50ms.

**Simplest implementation:** Redis or an in-process LRU keyed on a
stable hash of the context payload.

### 7. Inference concurrency

`inference/main.py` serialises generation with a `threading.Lock`
because MLX and llama-cpp-python are not thread-safe. This means one
user's 3s call blocks every other user waiting for insight.

**Options:**
- Accept the queue behaviour and cap it hard via rate limit.
- Run 2-3 backend workers behind a queue (each with its own model in
  memory — expensive but scales).
- Switch to a hosted inference provider (OpenAI, Anthropic, Groq)
  and let their infrastructure handle concurrency. Cost tradeoff
  depending on volume.

Under low real traffic (beta, single-digit RPS), the current serial
model is fine. Consider this before public announcement, not before
soft launch.

### 8. Structured logging

Currently `print()` for selfcheck output. Under real traffic you will
need to correlate a specific bad tile response with a specific
address lookup. JSON log lines with request id, address, tile key,
and tier make that trivial. Without it, debugging beta feedback is
grep-hell.

**Recommended:** `structlog` or Python's built-in `logging` with a
JSON formatter. Route to stdout; the reverse proxy or a sidecar can
ship them somewhere.

### 9. Feedback loop

Beta is worthless without user feedback. Add a footer link ("Feedback"
→ mailto or Formspree endpoint). Consider a lightweight in-app "was
this useful?" widget per tile — you will learn which tiles carry real
signal for which audience.

### 10. Mobile responsiveness verified

Not confirmed in this session. Berlin residents will hit this on
phones. Playwright (available via MCP) can verify layout at common
mobile breakpoints (375×667, 414×896) before soft launch.

---

## Genuine feature gaps worth naming — not blocking beta, worth v1.1

- **Map view.** Every tile has coordinates but nothing is rendered
  spatially. Berlin residents are spatially literate; a single map
  with tile pins would give an at-a-glance moment of understanding
  that no card grid can match. Leaflet + OSM tiles or MapLibre would
  fit the existing stack (stdlib + FastAPI + no build step).

- **Shareable URL.** Currently `?street=X&hnr=Y&plz=Z` is the form
  contract but there is no "copy link" affordance and no auto-run on
  page load. Critical for word-of-mouth spread ("check out my new
  address"). One-line frontend change.

- **German UI (i18n).** English-only doubles the addressable audience
  the moment we translate. String extraction not started; not v1, but
  the audience wants it. Framing effect: many Newcomer tiles reference
  German admin terms already (Bürgeramt, Wochenmarkt, Aufenthaltstitel),
  so partial German UI is actually less jarring than fully English.

- **Compare drawer regression check.** History mentions "save up to
  five and compare". Not verified in this session with all 27+ tile
  keys including the newer additions. Regression risk from lens
  additions; needs a visual QA pass.

- **Per-tile error UX.** Currently a partial failure surfaces as
  `lens.<slug>.error`. Frontend rendering of that state is not
  confirmed graceful. When Berlin BOD is down, tiles should degrade
  visibly rather than disappear.

- **SEO / discoverability.** SPA-only means Google will not index
  address pages. Server-side rendering or a static per-address
  pre-render (for high-traffic postal codes) would open organic search
  as an acquisition channel. Not v1, but worth planning.

---

## On the launch strategy

The user's plan of "run on a live server for a few weeks before announcement"
is exactly right. Two comments:

### Measure the right things during the beta window

Uptime alone is trivial. What you actually want to learn:

- **Which tiles get modal-opened.** Proxy for "user cared enough to read
  the AI insight". Signals which tiles carry real decision value.
- **Which addresses get looked up.** Signals which Bezirke you are
  actually useful for. May reveal that outer-district users find nothing
  green (data thin) or that inner-district users all cluster around a
  few postal codes.
- **How many `_error` responses per tile per day.** Signals data-source
  degradation before users complain.
- **`/api/card_insight` latency distribution.** Signals whether the
  inference serial-lock is actually hurting anyone.

Analytics and structured logs must be in place on day 1 of soft
launch, not added after complaints start.

### Invite 5-10 real users personally before broadcasting

Non-technical friends relocating to Berlin, family with kids, expat
groups (Girls Gone International, Toytown, `r/berlin` DMs). Fix what
they tell you. The public post can wait until you have run the loop
2-3 times.

Reasons this matters more than most beta strategies:

- Berlin address decisions are high-stakes and emotional. Users will
  give real feedback because they actually care about the answer.
- Data problems will be revealed by real edge cases (weird Bezirk
  boundaries, streets that got renamed, addresses that BOD does not
  geocode cleanly) that you cannot generate by testing yourself.
- A first impression matters. One clunky tile at launch is much more
  memorable than the 25 that work perfectly.

---

## Recommended order of operations

1. **Legal:** add Impressum + Datenschutzerklärung. Link from footer.
2. **Infra:** €5 Hetzner box + Caddy with Let's Encrypt + Sentry +
   UptimeRobot. Point a domain at it.
3. **Safety:** rate limit `/api/card_insight`. Weekly OSM refresh cron.
   Boot-resilience wrap on Index loaders.
4. **Signal:** add Plausible (or Umami) + structured JSON logging.
5. **Soft launch:** invite 5-10 personal beta testers. Post nowhere
   public.
6. **Iterate:** fix what they complain about. Repeat.
7. **Public:** Product Hunt / HN / `r/berlin` / expat Slacks. Only
   after 2-3 iterations with beta testers.

Under-a-day items with the highest leverage in this session were:

- Inference rate limit + Index boot resilience (blocker #3, #4).
- Inference response cache (should-fix #6).
- Shareable URL affordance (feature gap #1).

---

## What was reviewed to produce this document

Everything shipped in `v0.1/` as of commit `e1bde50`, including:

- `app/main.py`, `app/deps.py`, `app/config.py`
- `app/cities/berlin.py`, `app/cities/base.py`
- `app/core/index.py`, `app/core/scorer.py`, `app/core/amenities.py`,
  `app/core/gloss.py`, `app/core/osm_local.py`, `app/core/wfs.py`
- `app/routes/lookup.py`, `app/routes/card_insight.py`,
  `app/routes/amenities.py`
- `inference/main.py`, `inference/runtime/*`, `inference/templates/*`
- `scripts/refresh_osm_amenities.py`, `scripts/refresh_vbb.py`
- `web/index.html`, `web/static/app.js`, `web/static/app.css`
- `data/osm/berlin-amenities.json` (rebuilt: 31,084 features, 16 buckets)

Plus the governing documents:
- `berlin-family-address-intelligence-product-doc.md`
- `microservice-refactor-plan.md`
- `micro-service/CLAUDE.md`
