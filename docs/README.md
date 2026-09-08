# Documentation

Everything that isn't code or legal text lives here. If you're browsing the repo from GitHub, this is the map.

## Where to start

- **New contributor** → [`engineering/v0.1.md`](engineering/v0.1.md) — how the app is laid out, how to run it, how to run tests.
- **Reviewer / grant panel** → [`product/product-brief.md`](product/product-brief.md) — what the app does, who it serves, why the design choices.
- **Operator (deploy / oncall)** → [`../v0.1/docs/hetzner-deploy.md`](../v0.1/docs/hetzner-deploy.md) + [`../v0.1/docs/cloudflare-waf-setup.md`](../v0.1/docs/cloudflare-waf-setup.md).
- **Designer** → [`design-system/berlin-family-address-intelligence/MASTER.md`](design-system/berlin-family-address-intelligence/MASTER.md) — tokens, patterns, page-level overrides.

## Subtree layout

```
docs/
├── README.md                     ← you are here
├── architecture.md               ← 20-min onboarding on how the pieces fit
│
├── product/
│   ├── product-brief.md          ← what & why (long-form; §14 is engineering conventions)
│   └── data-sources.md           ← Berlin Open Data survey; candidate datasets
│
├── engineering/
│   └── v0.1.md                   ← "how to touch the code" — restart discipline, tests, deploy
│
├── design-system/
│   └── berlin-family-address-intelligence/
│       ├── MASTER.md             ← global source of truth (tokens, motion, color)
│       └── pages/                ← per-page overrides
│
└── history/
    ├── microservice-refactor-plan.md      ← shipped plan that produced v0.1/app/core/*
    ├── production-readiness-review-2026-08.md
    └── prototypes/
        ├── README.md              ← what each phase proved + why kept
        ├── phase0/                ← WFS validation + agency outreach
        ├── phase1/                ← single-file FastAPI + Leaflet, first end-to-end
        ├── phase2/                ← BOD-first / OSM-supplement pattern
        └── phase3/                ← every current data category in one 5k-LOC file;
                                     direct ancestor of v0.1/app/core/*
```

## What's NOT under `docs/`

- **`../legal/`** — Impressum + Datenschutzerklärung. Kept at repo root because DSGVO / §5 DDG auditors look for it there.
- **`../v0.1/docs/`** — operator runbooks (Hetzner deploy, Cloudflare WAF, social embed image, superpowers plans/specs). Kept next to the code they operate on.
- **`../.github/`** — CI workflow. Actions expects it at repo root.
