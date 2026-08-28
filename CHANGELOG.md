# Changelog

All notable changes to this project are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html) where the *product* is versioned. The `v0.1/` tree in this repo is the current active line.

## Unreleased

Planned deliverables — see [`README.md#roadmap`](README.md#roadmap) for the full list.

- Snapshot fallback for `gdi.berlin.de` (resilience to Senate WFS outages)
- Second city: Hamburg
- Public JSON API with a documented schema
- Mietspiegel Wohnlagen integration
- WCAG 2.2 AA accessibility audit

---

## [0.1.0] — 2026-08-25 (public launch)

**AddrLens went live at `https://addrlens.de/`.**

First public build. Everything below is what a Berlin address lookup gets on day one.

### Product

- **Two Life Mode lenses.** *Young Family* (9 tiles: kita, playground, pediatrician, transit, supermarket, noise, heat, air, refuge) and *Newcomer* (13 tiles including split rail / tram / bus transit, Bürgeramt reach, coworking, English clinics, international food, language school, library, Packstation, Wochenmarkt, nightlife density, GESIx neighbourhood profile).
- **Raw view** with tabs for Education (address + assigned Grundschule + kitas), Amenities, Emergency, Environment, Connectivity, and Others (Bürgeramt / Finanzamt / Standesamt / LEA / Arbeitsagentur reach).
- **Address autocomplete** on the search input — in-memory prefix index over ~414k Berlin OSM addresses, umlaut + street-suffix normalisation (`Bergmannstr.` / `Bergmannstraße` / `bergmannstrasse` all match).
- **Neighbourhood profile "Locality" pill** on the Address card in raw view — click for a popover with rank / Planungsraum / band / source.
- **Get History** and **Get Insight** LLM narratives on tiles. Explain modals with plain-English glosses of German administrative terms.
- **Compare mode** for up to 5 addresses side by side.

### LLM stack

- **Local llama.cpp** on the same Hetzner box running Qwen 2.5 1.5B Q4_K_M for `/api/card_insight`, `/api/explain`, `/api/impression`.
- **Cloudflare Workers AI** (`@cf/meta/llama-3.1-8b-instruct-fast`) for `/api/history` — ~0.7 s wall time end-to-end vs ~35 s on the local model. Automatic local fallback on remote failure.
- **Address-agnostic prompts** — street name and house number stripped before the prompt is built, so a 7-day cache keyed on ~100 m grid cells can safely serve neighbours the same paragraph.
- **7-day TTL cache** on the history endpoint. Env-tunable via `HISTORY_CACHE_TTL_S`, `HISTORY_CACHE_SIZE`, `HISTORY_CACHE_GRID`.

### Deploy + operations

- **Deployed on Hetzner CX22** (Debian 13, Falkenstein DE) behind a **Cloudflare Tunnel** — origin never exposed to the public internet.
- **Free-tier Cloudflare WAF** — 5 custom rules covering health-probe skip, empty-UA block, country-of-origin friction, and reserved incident slot. Playbook at [`micro-service/docs/cloudflare-waf-setup.md`](micro-service/docs/cloudflare-waf-setup.md).
- **Free-tier Cloudflare Rate Limiting Rule** on `/api/history` — 5 requests / 10 seconds per IP, Block action.
- **Application-level rate limiting** via `slowapi`, keyed on `CF-Connecting-IP`: 60/min on `/api/lookup`, 10/min on `/api/history`, 30/min on `/api/card_insight`, 5/second on `/api/suggest`.
- **Weekly OSM refresh** via systemd timer (Sunday 03:00) — one osmium pass writes both `berlin-amenities.json` and `berlin-addresses.json` atomically.
- **SSH hardened** — pubkey-only, root disabled, moved off port 22, fail2ban active.

### Observability

- **Sentry** for unhandled exceptions. EU region ingest (`de.sentry.io`, Frankfurt). `send_default_pii=False` plus a `before_send` scrubber that redacts `address`, `street`, `hnr`, `plz` query parameters, `CF-Connecting-IP` / `X-Forwarded-For` / `X-Real-IP` headers, and the entire inference request body.
- **Umami analytics** self-hosted alongside the app on the same box. Cookieless, no consent banner. Eight custom events wired: `lookup`, `suggest_selected`, `chip_click`, `lens_switch`, `card_open`, `get_insight`, `get_history`, `explain_open`, `compare_open`, `gesix_click`.

### Legal / GDPR

- **Impressum** compliant with DDG §5 (bilingual DE/EN).
- **Datenschutzerklärung** aligned with the actual live stack: Sentry (Frankfurt EU region), self-hosted Umami, Cloudflare CDN + Tunnel, Cloudflare Workers AI, Hetzner. Each processor named with address, purpose, data categories, and legal basis under DSGVO Art. 6.
- **No cookies.** `localStorage` used for the lens preference and compare list; disclosed in DSE §4.

### Data sources

Berlin Senate Geoportal (Schulen, Kitas, Krankenhäuser, Feuerwehr, Milieuschutz, Umweltatlas, Baumbestand, Trinkbrunnen, Grünanlagen, Bezirksgrenzen — dl-de/by-2-0 · dl-de/zero-2-0), VBB Verkehrsverbund (S/U/Tram stations — CC-BY-4.0), BVG (bus stops — dl-de/by-2-0), Geofabrik weekly OSM extract (ODbL 1.0), Berlin Senate GESIx 2022 (Gesundheits- und Sozialstrukturatlas — dl-de/zero-2-0). Each dataset attributed per-card in the product.

---

## [0.0.5] — 2026-08-14 (soft launch prep, private)

Prep work landed before the public launch — not tagged for release but relevant history.

- Newcomer lens split into three transit tiles (Rail / Tram / Bus). Young Family transit tile got dedup and a distance cap.
- Bureaucracy lens dropped from Life Mode; the same admin-office data moved to the raw-view "Others" tab.
- Docker deploy pipeline shipped: bootstrap.sh, update.sh, rollback.sh, weekly OSM refresh systemd unit, Cloudflare Tunnel + Cloudflare Workers AI wiring, env-guarded Sentry init.
- Bilingual Impressum + Datenschutzerklärung templates authored.
- Hero copy softened and DSGVO/Impressum links wired into the SPA.

---

## [0.0.4] — 2026-08-13 (Newcomer lens, private preview)

- New "Newcomer" lens covering the first 90 days of a Berlin move: Bürgeramt reach, coworking density, English-speaking clinics, GESIx band, international food, transit reach.
- Address card gained a "Get History" affordance backed by OSM `historic=*` features + a local llama.cpp narrative.
- OSM local snapshot layer added — feeds newcomer lens buckets (`intl_food`, `coworking`, `english_clinic`, `packstation`, `wochenmarkt`, etc.).

## [0.0.3] — 2026-08-10 (clickable Life Mode tiles)

- Life Mode tile modals with per-card LLM insight and provenance.
- Compare mode across up to 5 saved addresses.

## [0.0.2] — 2026-08-09 (Young Family lens)

- First Life Mode lens ships: 9 tiles covering the situation of a family with a young child in a new flat. Traffic-light tier system.
- Bureaucracy lens (Bürgeramt / Finanzamt / Standesamt / LEA / Arbeitsagentur) — later moved into the raw view.

## [0.0.1] — 2026-07 (Geofabrik prototype, private)

- First working Berlin address → open-data lookup, no LLM, no lenses.
- Geofabrik weekly OSM snapshot to sidestep Overpass rate limits.
- Static frontend + FastAPI backend, Shapely trees for point-layer queries.

---

## Notes on versioning

The repo also carries `phase0/`, `phase1/`, `phase2/`, `phase3/`, and `micro-service/` directories from earlier design iterations. These are preserved as-shipped for reference; nothing new lands in them. All active development happens in [`v0.1/`](v0.1/).
