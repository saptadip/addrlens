<!-- README.md — repo root. -->

[![tests](https://github.com/saptadip/addrlens/actions/workflows/test.yml/badge.svg)](https://github.com/saptadip/addrlens/actions/workflows/test.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

<div align="center">

# AddrLens

**Should I rent it?**
Know your Berlin neighbourhood in thirty seconds — schools, transit, noise, air, history — before signing your next lease.

**Live at [addrlens.de](https://addrlens.de/)** · MIT-licensed · No cookies · No signup · GDPR-clean

</div>

---

## What it is

AddrLens takes any Berlin address and, in under 30 seconds, cross-checks it against 20+ open datasets published by the Berlin Senate, VBB, BVG, and OpenStreetMap:

- Assigned Grundschule (Einschulungsbereich)
- Kitas within walking distance
- S-Bahn / U-Bahn / Tram / Bus reachability (VBB + OSM)
- Umweltatlas noise, air (NO₂), heat
- Green refuge, drinking fountains, public pools
- Fire station coverage, quiet zones, Milieuschutzgebiete
- Neighbourhood profile (GESIx 2022 socioeconomic band)
- Nearby historic markers / Stolpersteine
- German admin office reach (Bürgeramt, Finanzamt, Standesamt, LEA, Arbeitsagentur)

Two curated **Life Mode** lenses (`Young Family`, `Newcomer`) surface the tiles most relevant to each situation. A **Raw view** lets anyone browse every dataset with full source attribution and licence tags.

A small language model (llama.cpp locally, optional Cloudflare Workers AI for the neighbourhood-history narrative) turns each tile into a plain-English paragraph. Address-agnostic prompts + a 7-day server-side cache mean that neighbours share the same LLM-derived text, cutting external calls and preserving privacy.

## Screenshots

*(Add screenshots at `docs/img/hero.png` and reference them here before the OSS launch. Placeholder while the images are being cut.)*

## Data sources & licences

| Source | Datasets used | Licence |
|---|---|---|
| Berlin Geoportal / FIS-Broker (gdi.berlin.de) | Schulen, Kitas, Krankenhäuser, Feuerwehr, Milieuschutz, Umweltatlas, Baumbestand, Trinkbrunnen, Grünanlagen, Bezirksgrenzen | dl-de/by-2-0 · dl-de/zero-2-0 |
| VBB Verkehrsverbund Berlin-Brandenburg | S-Bahn / U-Bahn / Tram station coordinates | CC-BY-4.0 |
| BVG Berliner Verkehrsbetriebe | Bus stops, service data | dl-de/by-2-0 |
| Geofabrik weekly extract of OpenStreetMap Berlin | International food, coworking, English clinics, language schools, libraries, Packstationen, Wochenmärkte, historic markers, address autocomplete | ODbL 1.0, © OpenStreetMap contributors |
| Berlin Senate GESIx 2022 (Gesundheits- und Sozialstrukturatlas) | Neighbourhood socioeconomic band per Planungsraum | dl-de/zero-2-0 |

Every card in the product surfaces its dataset name and licence tag. The full attribution list also lives in [`legal/impressum.md`](legal/impressum.md).

## Stack

- **Backend:** Python 3.11+, [FastAPI](https://fastapi.tiangolo.com), [Shapely](https://shapely.readthedocs.io), [httpx](https://www.python-httpx.org), [slowapi](https://slowapi.readthedocs.io) for rate limiting, [cachetools](https://cachetools.readthedocs.io) for the history TTL cache
- **Inference:** llama-cpp-python (Qwen 2.5 1.5B Q4_K_M) for local generation, Cloudflare Workers AI (`@cf/meta/llama-3.1-8b-instruct-fast`) for the neighbourhood-history route with automatic local fallback
- **Frontend:** vanilla HTML / CSS / JS, [Leaflet](https://leafletjs.com/) for maps. **No bundler, no framework, no build step.**
- **Analytics:** self-hosted [Umami](https://umami.is/) (cookieless, no consent banner needed)
- **Errors:** [Sentry](https://sentry.io) EU region, `send_default_pii=False`, address + IP redacted in `before_send`
- **Deploy:** Docker Compose on a Hetzner CX22 (Debian 13, Falkenstein DE) behind a Cloudflare Tunnel; weekly OSM refresh timer, per-endpoint WAF + rate-limit rules

## Repository layout

The active tree is [`v0.1/`](v0.1/). Historical prototypes (`phase0/`–`phase3/`) are archived under [`docs/history/prototypes/`](docs/history/prototypes/) for lineage — many `v0.1/app/core/*` modules are ports of `phase3/server.py` and cite it in their comments.

| Directory | Purpose |
|---|---|
| [`v0.1/app/`](v0.1/app/) | FastAPI app — one process per city, selects `CityConfig` at boot via `CITY=<slug>` |
| [`v0.1/inference/`](v0.1/inference/) | Shared LLM service (city-agnostic), MLX on Apple Silicon dev, llama.cpp on Linux prod, optional Cloudflare Workers AI remote path |
| [`v0.1/web/`](v0.1/web/) | Single-page frontend (no bundler) — `index.html`, `impressum.html`, `datenschutzerklaerung.html`, `static/app.{js,css}` |
| [`v0.1/scripts/`](v0.1/scripts/) | Weekly OSM refresh (extracts amenities + addresses from Geofabrik) |
| [`v0.1/ops/`](v0.1/ops/) | Dockerfiles, Cloudflare Tunnel config, systemd units, deploy scripts |
| [`v0.1/docs/`](v0.1/docs/) | Deploy playbook, WAF setup, social-embed playbook |
| [`legal/`](legal/) | Impressum + Datenschutzerklärung (bilingual DE/EN, DDG §5 + DSGVO Art. 13 compliant) |

## Local development

Two paths — pick one.

### 1. Bare uvicorn on macOS Apple Silicon (fastest for iteration; uses Metal GPU via mlx-lm)

```bash
cd v0.1
uv pip install --system -r pyproject.toml
uv pip install --system -e "inference[dev]"      # mlx-lm

# Terminal 1 — inference on :8080
INFERENCE_BACKEND=mlx uvicorn inference.main:app --port 8080

# Terminal 2 — app on :8003
CITY=berlin INFERENCE_URL=http://localhost:8080 uvicorn app.main:app --port 8003
```

Open `http://localhost:8003/`.

### 2. Docker Compose (matches prod)

```bash
cd v0.1

# Fetch the GGUF language model once (~940 MB)
mkdir -p models
curl -L -o models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf \
  "https://huggingface.co/bartowski/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf?download=true"

# The dev override mounts models/ + data/osm into the containers
docker compose up -d --build
```

Open `http://localhost:8001/`.

Neither path needs a Cloudflare Workers AI token — the app happily runs against the local llama.cpp fallback for every LLM call.

## Selfchecks

There is no pytest suite. Every module ships a pure `__main__` block that asserts its own contract; a single `app.selfcheck` orchestrator runs everything plus live-network checks against `gdi.berlin.de`.

```bash
cd v0.1

# Pure asserts — no network, no model load, sub-second each
python -m app.core.scorer            # tier boundaries + lens composers
python -m app.core.rate_limit         # CF-Connecting-IP key extraction
python -m app.core.address_index      # umlaut + street-suffix normalisation
python -m app.routes.card_insight     # newcomer-card key registration

# Live-network — pulls WFS layers, needs gdi.berlin.de reachable
python -m app.selfcheck
```

## Deployment

See [`v0.1/docs/hetzner-deploy.md`](v0.1/docs/hetzner-deploy.md) for the full playbook — Debian 13 host bootstrap, Cloudflare Tunnel, secrets, systemd OSM refresh timer, Sentry + Umami wire-up.

Related runbooks:

- [`v0.1/docs/social-embed-og-image.md`](v0.1/docs/social-embed-og-image.md) — social preview cards
- [`v0.1/docs/cloudflare-waf-setup.md`](v0.1/docs/cloudflare-waf-setup.md) — free-tier WAF rules

## Roadmap

Concrete deliverables for the next six months, in rough order:

- **Snapshot fallback for `gdi.berlin.de`.** The Berlin Senate WFS had multi-day maintenance in August 2026; snapshot-based resilience is a prerequisite for treating this as public infrastructure.
- **Second city (Hamburg, then München).** The architecture already picks the city per `CityConfig` at boot; each new city needs a data-source map and glossary translation.
- **Public JSON API** with a documented schema, so other Berlin civic-tech projects can reuse the aggregated address data without re-implementing 20 WFS clients.
- **Mietspiegel Wohnlagen integration** — the only openly licensed rent-level signal per address.
- **WCAG 2.2 AA accessibility audit** — screen-reader coverage, keyboard navigation, high-contrast mode.
- **Historical time-series** (e.g. "has noise on this address improved over the last 5 years?") once the data horizon allows.

## Contributing

Bug reports, data-source additions, and small documentation fixes are welcome. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the layout, code style, and selfcheck workflow.

## Licence

MIT — see [`LICENSE`](LICENSE). Data sources retain their own licences (see the table above).

## Acknowledgements

- **Berlin Senate departments** for publishing the datasets that make this possible under open licences.
- **[ODIS Berlin](https://odis-berlin.de/) / Technologiestiftung Berlin** for maintaining the ecosystem around Berlin open data.
- **OpenStreetMap contributors** — every historic marker, café, and bus stop.
- **VBB Verkehrsverbund Berlin-Brandenburg** and **BVG** for open-data-licensing the transit network.

## Contact

- Product: <https://addrlens.de/>
- Feedback: `informsapta@gmail.com`
- Issues + feature requests: [GitHub Issues](https://github.com/saptadip/addrlens/issues)
