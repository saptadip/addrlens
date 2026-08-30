"""Lens composers — assemble tile lists per (address, lens).

Split from `app/core/scorer.py` in Ship D step 2. Each composer is pure,
runs no I/O on the hot path, and reads its data from a preloaded
`Index` plus the shared `app.core.scoring` primitives.

- `young_family` — 8 tiles for a family with under-6 kids.
- `newcomer`     — 13 tiles for a newly-arrived English-speaking expat.

The Bureaucracy lens was removed in an earlier PR; its underlying
admin-office cards live in `app.core.others_admin` and feed the raw-
view Others tab.
"""
