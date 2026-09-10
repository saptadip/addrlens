# Berlin Open Data Adapter — feature proposal

**Status:** Proposal · not scheduled · needs grant-funder validation first
**Author:** Saptadip
**Last updated:** 2026-09-09

## What

Extract the aggregation layer currently living in `v0.1/app/core/` (`wfs.py`, `overpass.py`, `merge.py`, `addr.py`, `geo.py`, `amenities.py`, `loaders/*.py`) into a standalone `pip`-installable Python package **`berlin-open-data-adapter`**. The library exposes a typed, provenance-aware interface to Berlin Geoportal WFS + OSM Overpass so other civic-tech projects don't reinvent the ~3 000 LOC of glue code AddrLens already wrote.

AddrLens becomes user #1 (dogfood via `import berlin_open_data_adapter as boa` in `v0.1/app/core/`). Other Berlin civic apps become potential users.

## Why

- **Ecosystem hole:** Every Berlin civic-tech project currently reinvents Geoportal WFS clients + OSM Overpass mirror rotation + BOD/OSM dedupe. No maintained shared library exists.
- **Value AddrLens can spin out:** BOD-first / OSM-supplement dedupe pattern, tiered Overpass mirror rotation, Berlin-specific address parser, per-dataset provenance tagging. Not solved by generic `owslib` / `pygeoapi`.
- **Grant-fit:** SovTech Fund + NLnet NGI Zero both fund reusable open-source infrastructure. Front-end civic apps like AddrLens do not fit their current criteria; a library that AddrLens depends on does.
- **Snapshot resilience:** The Berlin Senate WFS had multi-day maintenance in August 2026 (see `docs/history/production-readiness-review-2026-08.md`). A library-level snapshot fallback benefits every Berlin civic-tech consumer, not just AddrLens.

## Current state — 85 % of the extraction is already written

Every module needed is under `v0.1/app/core/`:

| Module | Extraction fit | Notes |
|---|---|---|
| `wfs.py` (234 LOC, 77 % test cov) | Ready | Generic WFS helpers, TTL cache, CQL escape |
| `overpass.py` | Ready | Tiered mirror rotation with retry |
| `merge.py` | Ready | BOD-first / OSM-supplement dedupe (centroid clustering) |
| `addr.py` | Ready | Berlin street-suffix + umlaut normalisation |
| `geo.py` (100 % test cov) | Ready | Haversine + bbox helpers |
| `amenities.py`, `loaders/*.py` | Ready | Per-dataset fetchers |
| `index.py` (~1 000 LOC) | Needs split | Tightly coupled to AddrLens response shape; break into per-domain modules |
| `scoring/` | Stays in AddrLens | Product opinion, not infrastructure |

## Scope by phase

### v0.5 — minimum viable extract (6-8 weeks solo)

- New repo `berlin-open-data-adapter/` or a monorepo subdir under `packages/` (decide based on maintenance model).
- Copy 5-6 clean modules as-is with `pyproject.toml`, MIT LICENSE, README, CHANGELOG.
- Provenance as first-class `@dataclass` (currently a dict in `v0.1/app/core/scoring/provenance.py`).
- Sphinx or MkDocs Material documentation.
- Publish to PyPI under `berlin-open-data-adapter` (or similar).
- AddrLens migrates one module at a time from local `app.core.wfs` to `from berlin_open_data_adapter import wfs`. Dogfooding.
- Guest-user PR: find one other Berlin civic-tech project + submit a PR migrating them to the library. Proves reusability.

### v1.0 — grant-worthy public infrastructure (4-6 months on top of v0.5)

- Snapshot fallback layer (offline JSON snapshots per dataset with weekly refresh cron; addresses the Aug 2026 Senate downtime issue).
- Multi-city adapters: Hamburg (`hh-open-data-adapter`) + München (`m-open-data-adapter`) as sibling packages, or a single `de-open-data-adapter` with per-city config plugins.
- Sync + async dual API (`fetch_*` + `afetch_*`).
- Rate-limit + cache decorators as public surface.
- Contract tests against live Geoportal + OSM Overpass (opt-in, matches AddrLens pytest `integration` marker).
- Governance doc + `CODE_OF_CONDUCT.md`.

### v2 — the network-effect target (opportunistic, not scheduled)

- Wikidata / OpenAddresses / OSM tooling channel integrations.
- Community contributions from other DE cities (Frankfurt, Köln, Leipzig).
- CLI (`bod-adapter fetch kitas 52.5 13.4 --radius 800`) for one-off queries from data-desk journalists.

## Grant angles

**SovTech Fund** (best fit for v1.0):
- Pitch: "Berlin's civic-tech ecosystem lacks a maintained Python interface to the 20+ Geoportal WFS + OSM Overpass sources. Every project reinvents ~3 000 LOC of glue. Extracting AddrLens's aggregation layer as public infrastructure."
- Ask: €50-150 k for v1.0 (6 months development + 6 months maintenance runway).
- Precedent: SovTech has funded `libjpeg-turbo`, `curl`, `Python packaging` — an ecosystem-specific glue library fits their brief.

**NLnet NGI Zero** (best fit for v0.5):
- €5-50 k, rolling submissions, fast answer.
- Frame as "public-interest open-source data-access library for the German open-data ecosystem."
- Application ~10 pages. Time investment ~3 days.

**Technologiestiftung Berlin / ODIS Berlin**:
- Not typically a funder; offers showcase + partnership + endorsement letter.
- Endorsement doubles SovTech/NLnet application signal.
- Contact channel: `odis-berlin@technologiestiftung-berlin.de`.

## Risks

1. **Consumer count.** Realistic universe of Berlin civic-tech projects: 10-20. Small. Mitigation: package as a general-purpose German-cities adapter with Berlin as reference; contribute back to `owslib` / OSM tooling channels.
2. **Maintenance burden.** Berlin Senate changes endpoints, adds fields, breaks CQL filters. Grant should include 30 % maintenance time.
3. **`owslib` overlap.** Reviewers will ask "why not contribute upstream?" Answer: `owslib` is generic transport; adapter depends on `owslib` and adds Berlin normalisation + dedupe + provenance. Complementary, not competing.
4. **Naming.** "Berlin-open-data-adapter" reads like a personal-project name. Consider a memorable one (e.g., `berolina`, `bod-py`) if adoption becomes the goal.

## Decision points that need user input

1. **Monorepo or separate repo?** Monorepo (`packages/adapter/` under AddrLens) simplifies dogfooding but couples release cadence. Separate repo cleaner for external contributors.
2. **Package naming.** Above.
3. **License.** MIT (matches AddrLens) or Apache 2.0 (more common for infrastructure libraries)?
4. **v0.5 timing.** Ship BEFORE contacting SovTech (evidence in hand) or AFTER (validate scope first)?
5. **Maintenance commitment.** Realistically how many hours/month can you sustain if grants don't land? A published-then-abandoned library is worse than none.
