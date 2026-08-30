"""Pure scoring primitives split out of `app/core/scorer.py`.

Submodules:
- `constants` — TIER_* strings, `_fmt_dist`, `_walk_minutes`.
- `legends`   — per-tile 3-band legend text.
- `shape`     — feature-shape helpers (kita / playground / office / …)
                plus `_shape_gesix` and the `_tile` dict builder.
- `provenance`— citation composition from `CityConfig.attribution`.
- `tiers`     — pure tier funcs returning `{tier, rule, numeric}`, plus
                the shared `_tier_distance_ladder` and `_tier_count_band`
                helpers that eight+two duplicated newcomer tiers now
                collapse onto.

Lens composers live under `app/core/lenses/*`. `app/core/scorer.py` is
a re-export shim for existing callers and hosts the load-bearing
regression selfcheck.
"""
