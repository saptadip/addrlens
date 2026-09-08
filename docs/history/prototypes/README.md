# Prototype archive — `phase0` / `phase1` / `phase2` / `phase3`

Four historical prototypes that led to the production tree at `../../v0.1/`. Kept for lineage — comments throughout `v0.1/app/core/**` reference them as `verbatim from phase3/server.py` etc. Not built, not tested, not deployed.

## Timeline

| Phase | What it proved | Files of note |
|-------|----------------|---------------|
| `phase0/` | Berlin Geoportal WFS is queryable from Python (`catchment_check.py`), and the address-parser regex holds against real BOD addresses. | `catchment_check.py`, `wfs-validation-report.md`, `agency-outreach-kit.md` |
| `phase1/` | Single-file FastAPI + Leaflet + vanilla-JS SPA renders a school catchment result from a typed address. | `server.py`, `index.html` |
| `phase2/` | Kitas + fountains + hospitals + transit + noise layer added; BOD-first-OSM-fallback dedupe pattern proven. | `server.py`, `index.html` |
| `phase3/` | Every current data category present in a single 5k-LOC `server.py`. This is the direct ancestor of `v0.1/` — the microservice refactor plan ([`../microservice-refactor-plan.md`](../microservice-refactor-plan.md)) split this file into `v0.1/app/core/*.py`. | `server.py`, `index.html`, per-request snapshots |

## Why keep them

- Many modules under `v0.1/app/core/**` still carry `# verbatim from phase3/server.py:...` comments as lineage pointers. Removing the archive would turn those into dead references.
- Ship-C (see the plan) has not landed; phase3's approach to some edge cases may still be the reference implementation.

## Do NOT

- Import from these files. Not maintained.
- Rely on them for tests, deploys, or CI.
- Cite them as documentation for how the current app works — that is [`../../architecture.md`](../../architecture.md) + [`../../product/product-brief.md`](../../product/product-brief.md).

## If you need to browse

Everything is plain Python + HTML. Open in your editor; nothing special to run.
