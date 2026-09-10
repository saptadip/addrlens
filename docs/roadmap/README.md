# Roadmap — feature proposals

Long-form design docs for features that are proposed but not scheduled. Each doc captures motivation, scope, effort, grant-fit, risks, and open decision points so the idea survives a re-read in six months without context loss.

## Current proposals

- [`berlin-open-data-adapter.md`](berlin-open-data-adapter.md) — extract `v0.1/app/core/` aggregation layer as a standalone `pip`-installable Python library. Grant-fit target: SovTech Fund / NLnet NGI Zero.
- [`public-api.md`](public-api.md) — turn internal `/api/*` endpoints into a versioned, documented, key-guarded `/api/v1/*` public API. Companion to the adapter above.

## What lives here vs. `README.md#roadmap`

- **`README.md#roadmap`** — public, brief, grant-panel-facing list of deliverables in rough order.
- **`docs/roadmap/*.md`** — full internal design docs with effort, risks, decision points.

Move a proposal here → schedule it in `README.md` roadmap → land the PR → the proposal doc gets a `Status: shipped in PR #NN` header and moves to `docs/history/` for archive.
