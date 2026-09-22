# Berlin CityConfig Subpackage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `v0.1/app/cities/berlin.py` (917 LOC flat file) into a focused subpackage mirroring the Hamburg pattern shipped in PR #93, so per-city changes touch focused files and future onboarding of a third city can copy a proven layout.

**Architecture:** ONE PR containing ONE atomic commit that creates `v0.1/app/cities/berlin/{__init__, config, directories, lenses, __main__}.py` and deletes `v0.1/app/cities/berlin.py` in the same commit (Python's import machinery resolves `app.cities.berlin` inconsistently across versions when both a flat module and a subpackage of the same name exist mid-history). Every existing `from app.cities.berlin import ...` keeps working via the `__init__.py` shim; every existing `python -m app.cities.berlin` invocation keeps working via `__main__.py`. Every guardrail this refactor needs — pytest markers, per-city CI split, selfcheck matrix, `tests/cities/berlin/` scaffold, `update.sh` per-city smoke, `rollback.sh` app-hh rebuild — is already on `main` from PR #92 (PR-A) and PR #93 (PR-B). PR-C is scoped down to only the split.

**Tech Stack:** Python 3.13, pytest 8.x (`--strict-markers` on, `berlin` + `hamburg` markers registered by PR-A), FastAPI/uvicorn, Docker Compose. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-09-22-hamburg-config-subpackage-design.md` (§Berlin follow-up sketches PR-C in one paragraph; the mechanical template is PR-B Task B4 in `docs/superpowers/plans/2026-09-22-hamburg-config-subpackage.md`).

## Global Constraints

- **Working directory** is `v0.1/` for every `pytest`, `python -m`, `uvicorn`, and `docker compose` invocation below. The repo carries a legacy `v0.1/` prefix — deploy scripts, CI, and rootdir all anchor here.
- **Every consumer of `from app.cities.berlin import BERLIN` must keep working with zero touch on the call site.** The shim in `__init__.py` is the contract. Verified call sites at 2026-09-22 (grep of `from app.cities.berlin import`): `tests/conftest.py`, `tests/unit/test_tiers.py`, `tests/unit/test_shape.py`, `tests/cities/hamburg/test_hamburg_lens_composers.py`, `tests/cities/berlin/test_lookup_dispatch.py`, `app/core/gloss.py`, `app/core/index.py`, `app/core/others_admin.py`, `app/core/amenities.py`, `app/core/scorer.py` (×2), plus `berlin.py`'s own `__main__` block. All 11 external sites import `BERLIN` only; the internal `__main__` also imports `NEWCOMER_LENS` + `OTHERS_ADMIN_CARDS`.
- **`python -m app.cities.berlin` must keep running the selfcheck asserts** — referenced by the CI selfchecks matrix (already registered in `.github/workflows/*.yml`), the `app-hh`/`app` container start, and developer workflow.
- **Single atomic commit for the split.** Do NOT stage the new subpackage in one commit and delete `berlin.py` in a follow-up. A two-commit sequence leaves a moment where both `berlin.py` and `berlin/` exist, which Python's finder order resolves version-dependently. Reviewers who want a smaller diff should be pointed at `git diff --find-renames` on the merge commit.
- **Berlin is out of scope beyond the split.** No `app/core/*`, `app/routes/*`, `app/deps.py`, frontend, `Dockerfile`, `docker-compose*.yml`, `.github/workflows/*.yml`, or `hamburg/` touch. The 917-LOC file gets physically re-arranged; no rename of any symbol, no signature change, no logic edit.
- **Every commit message includes the trailer** `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

---

## PR-C — Berlin subpackage split

**Branch:** `refactor/berlin-config-subpackage`
**PR title:** `refactor(cities): split app/cities/berlin.py into a subpackage`

Zero test-relocation work, zero CI work, zero deploy-script work — PR-A and PR-B already shipped every guardrail. This PR is ONE atomic commit plus a shim-contract test file.

### Task C1: Create the working branch

**Files:** none (git operation).

**Interfaces:**
- Consumes: current `main` HEAD (post-PR #93 merge, commit `85ef8ef` or later).
- Produces: local branch `refactor/berlin-config-subpackage` at the same SHA, ready for Task C2 to commit against.

- [ ] **Step 1: Confirm `main` is up-to-date with origin**

```bash
cd /Users/sapta/Documents/personal/myStage/claude-personal/berlin-address-intelligence
git checkout main
git pull --ff-only
git log --oneline -3
```
Expected: HEAD shows the PR #93 merge (`refactor(cities): split app/cities/hamburg.py into a subpackage` or the merge commit `85ef8ef Merge pull request #93 ...`). If HEAD is behind, `git pull --ff-only` will move it forward; if it can't fast-forward, STOP — someone force-pushed main and this plan's assumptions may not hold.

- [ ] **Step 2: Create + switch to the working branch**

```bash
git checkout -b refactor/berlin-config-subpackage
git branch --show-current
```
Expected: `refactor/berlin-config-subpackage`.

- [ ] **Step 3: Confirm the working tree is clean**

```bash
git status --porcelain
```
Expected: no output. Any modified/untracked file here means a prior session left state behind — resolve it (commit, stash, or clean up) before starting Task C2.

---

### Task C2: Split `berlin.py` into a subpackage (atomic commit)

**Files:**
- Create: `v0.1/app/cities/berlin/__init__.py`
- Create: `v0.1/app/cities/berlin/config.py`
- Create: `v0.1/app/cities/berlin/directories.py`
- Create: `v0.1/app/cities/berlin/lenses.py`
- Create: `v0.1/app/cities/berlin/__main__.py`
- Create: `v0.1/tests/cities/berlin/test_subpackage_public_surface.py`
- Delete: `v0.1/app/cities/berlin.py`

All in the SAME commit (except the test file, which is added at the same time — one commit). A two-commit sequence would leave a moment where both `berlin.py` and `berlin/` exist, which Python's import machinery handles inconsistently across versions.

**Interfaces:**
- Consumes: `app.cities.base` (unchanged — `CityConfig`, `LensConfig`, `LensTileConfig`, `OthersAdminCardConfig`).
- Produces: the public surface `BERLIN`, `YOUNG_FAMILY_LENS`, `NEWCOMER_LENS`, `QUIET_LIVING_LENS`, `COMMUTER_LENS`, `OTHERS_ADMIN_CARDS` — all reachable via `from app.cities.berlin import ...` (via `__init__.py` shim). Also preserves `python -m app.cities.berlin` selfcheck (via `__main__.py`).

- [ ] **Step 1: Write the failing shim contract test**

Create `v0.1/tests/cities/berlin/test_subpackage_public_surface.py`:

```python
"""Locks the public surface of the Berlin subpackage. Every symbol
listed in `berlin/__init__.py::__all__` must be importable via
`from app.cities.berlin import <name>` and must be the object the
current call-site expects (see plan Global Constraints, grep 2026-09-22)."""

from app.cities.base import CityConfig, LensConfig, OthersAdminCardConfig


def test_BERLIN_importable_as_CityConfig():
    from app.cities.berlin import BERLIN
    assert isinstance(BERLIN, CityConfig)
    assert BERLIN.slug == "berlin"


def test_all_four_lenses_importable_and_correct_type():
    from app.cities.berlin import (
        YOUNG_FAMILY_LENS,
        NEWCOMER_LENS,
        QUIET_LIVING_LENS,
        COMMUTER_LENS,
    )
    for lens in (YOUNG_FAMILY_LENS, NEWCOMER_LENS, QUIET_LIVING_LENS, COMMUTER_LENS):
        assert isinstance(lens, LensConfig)
    assert YOUNG_FAMILY_LENS.slug == "young_family"
    assert NEWCOMER_LENS.slug == "newcomer"
    assert QUIET_LIVING_LENS.slug == "quiet_living"
    assert COMMUTER_LENS.slug == "commuter"


def test_others_admin_cards_importable_and_correct_shape():
    from app.cities.berlin import OTHERS_ADMIN_CARDS
    assert isinstance(OTHERS_ADMIN_CARDS, tuple)
    assert len(OTHERS_ADMIN_CARDS) >= 1
    assert all(isinstance(c, OthersAdminCardConfig) for c in OTHERS_ADMIN_CARDS)


def test_package___all___pins_the_public_surface():
    """__all__ is the contract — narrowing it silently breaks call-sites.
    Do NOT relax this to a subset; extend it if we intentionally add a
    new public symbol. Broad shape matches the Hamburg pattern from PR #93."""
    from app.cities import berlin as pkg
    assert set(pkg.__all__) >= {
        "BERLIN",
        "YOUNG_FAMILY_LENS",
        "NEWCOMER_LENS",
        "QUIET_LIVING_LENS",
        "COMMUTER_LENS",
        "OTHERS_ADMIN_CARDS",
    }


def test_BERLIN_identity_matches_config_module():
    """BERLIN re-exported via __init__ MUST be the same object as the
    one built in berlin.config — no accidental copy/reassignment."""
    from app.cities.berlin import BERLIN
    from app.cities.berlin.config import BERLIN as _config_BERLIN
    assert BERLIN is _config_BERLIN
```

- [ ] **Step 2: Run the test — expect FAIL**

Run: `cd v0.1 && CITY=berlin pytest tests/cities/berlin/test_subpackage_public_surface.py -v 2>&1 | tail -12`
Expected: at least `test_package___all___pins_the_public_surface` fails (today's flat `berlin.py` has no `__all__`). `test_BERLIN_identity_matches_config_module` will error at collection time on `ModuleNotFoundError: No module named 'app.cities.berlin.config'`. Others may pass because the flat file exports the same symbols. Either way, at least one hard fail — proves the test is exercising real behaviour.

- [ ] **Step 3: Read the current `berlin.py` end-to-end**

Run: `sed -n '1,917p' v0.1/app/cities/berlin.py | wc -l && sed -n '1,917p' v0.1/app/cities/berlin.py > /tmp/berlin_source.txt && wc -l /tmp/berlin_source.txt`
Purpose: hold the whole file in context before splitting. The five files below MUST preserve every symbol currently defined; the split is a physical move, not a rewrite. Note the section boundaries:
- Line 21: `_BERLIN_GLOSSARY`
- Line 33: `_SESB_GRUNDSCHULEN`
- Lines 51-84: `_WFS_*` URL constants (20 of them)
- Line 65: `_BUERGERAEMTER_URL` (Berlin's Bürgeramt loader URL — sentinel layer `_geojson`)
- Line 69: `_WEIHNACHTSMARKT_URL`
- Line 95: `_STANDESAMTS_BY_BEZIRK`
- Line 138: `_FINANZAMTS`
- Line 177: `_ARBEITSAGENTURS`
- Line 201: `_LEA_OFFICE`
- Line 213: `YOUNG_FAMILY_LENS`
- Line 299: `OTHERS_ADMIN_CARDS` (this appears BEFORE the remaining three lenses — unlike Hamburg, where directories cluster before lenses)
- Line 311: `NEWCOMER_LENS`
- Line 406: `QUIET_LIVING_LENS`
- Line 518: `COMMUTER_LENS`
- Line 588: `BERLIN = CityConfig(`
- Line 755: `stations_data_path=str(Path(__file__).resolve().parent / "data" / "vbb_berlin_su.csv")` — MUST bump to `.parent.parent` when moved into `berlin/config.py` (see Step 6)
- Line 802: inline `attribution={...}` dict inside the `CityConfig(...)` call — Berlin has NO separate `_ATTRIBUTION` module-level dict (differs from Hamburg)
- Line 876: `smoke_address="Kastanienallee 12, 10435"` — MUST be preserved verbatim (used by `update.sh` per-city smoke from PR #93)
- Lines 891-917: `if __name__ == "__main__":` selfcheck block (extra status line + more asserts than Hamburg — see Step 8)

- [ ] **Step 4: Create `v0.1/app/cities/berlin/lenses.py`**

Move the four lens blocks from `berlin.py` verbatim (`YOUNG_FAMILY_LENS` from line 213; `NEWCOMER_LENS` from line 311; `QUIET_LIVING_LENS` from line 406; `COMMUTER_LENS` from line 518). The file's top should be:

```python
"""Berlin lens configs — Young Family + Newcomer + Quiet Living + Commuter tile lists.

Extracted from the flat `berlin.py` into a dedicated module so lens
changes touch only the lens file. The audience-hint prose, per-tile
threshold dicts, and caveat strings live here verbatim from the flat
file; only imports changed. Any LLM insight template that consumes a
tile's `slug`, `label`, `audience_hint`, or threshold dict is depending
on the exact strings here — DO NOT paraphrase.
"""
from app.cities.base import LensConfig, LensTileConfig


YOUNG_FAMILY_LENS: LensConfig = LensConfig(
    slug="young_family",
    # ...copy every LensTileConfig(...) entry from berlin.py's YOUNG_FAMILY_LENS verbatim, including label, audience_hint, tiles tuple, caveat strings...
)

NEWCOMER_LENS: LensConfig = LensConfig(
    slug="newcomer",
    # ...copy every LensTileConfig(...) entry from berlin.py's NEWCOMER_LENS verbatim...
)

QUIET_LIVING_LENS: LensConfig = LensConfig(
    slug="quiet_living",
    # ...copy every LensTileConfig(...) entry from berlin.py's QUIET_LIVING_LENS verbatim...
)

COMMUTER_LENS: LensConfig = LensConfig(
    slug="commuter",
    # ...copy every LensTileConfig(...) entry from berlin.py's COMMUTER_LENS verbatim...
)
```

Copy the tile lists EXACTLY from the current `berlin.py`. Do not paraphrase; the LLM insight templates and the `__main__` assert block both depend on the exact `slug`, `label`, `audience_hint`, threshold dicts, and caveat strings. Sanity check after the copy: `wc -l v0.1/app/cities/berlin/lenses.py` should read ~310 LOC.

- [ ] **Step 5: Create `v0.1/app/cities/berlin/directories.py`**

Move these curated data structures from `berlin.py` into the new file, verbatim, in the same order they appear in `berlin.py`:
- `_BERLIN_GLOSSARY` (line 21)
- `_SESB_GRUNDSCHULEN` (line 33)
- `_STANDESAMTS_BY_BEZIRK` (line 95)
- `_FINANZAMTS` (line 138)
- `_ARBEITSAGENTURS` (line 177)
- `_LEA_OFFICE` (line 201)
- `OTHERS_ADMIN_CARDS` (line 299)

File header:
```python
"""Berlin curated data directories — hand-verified addresses, office
tuples, SESB bilingual-school registry, glossary regexes, and
OTHERS_ADMIN_CARDS registration.

Every entry here needs annual re-verification against its berlin.de
source — an out-of-date Standesamt address ships to production without
a data-quality signal. Keep that discipline: when re-verifying, cross
this file against the same landscape doc that guided the initial pull.
"""
import re

from app.cities.base import OthersAdminCardConfig
```

Then paste the module-level names in the same order they appear in `berlin.py`. Sanity checks after the paste:
- `grep -c "^_[A-Z]\|^OTHERS_ADMIN_CARDS" v0.1/app/cities/berlin/directories.py` — expect 7 (matches the 7 module-level names above).
- `python -c "from app.cities.berlin.directories import _STANDESAMTS_BY_BEZIRK, _FINANZAMTS, OTHERS_ADMIN_CARDS; print(len(_STANDESAMTS_BY_BEZIRK), len(_FINANZAMTS), len(OTHERS_ADMIN_CARDS))"` — expect three integers; compare against the flat file with `cd /tmp && python -c "import sys; sys.path.insert(0, '/Users/sapta/Documents/personal/myStage/claude-personal/berlin-address-intelligence/v0.1'); from app.cities.berlin import BERLIN; print(len(BERLIN.standesamts_by_bezirk), len(BERLIN.finanzamts), len(BERLIN.others_admin_cards))"` — the three numbers MUST match.

*(That second sanity check can only be run BEFORE the flat file is deleted in Step 9 — do it now so you have the baseline.)*

- [ ] **Step 6: Create `v0.1/app/cities/berlin/config.py`**

Move the WFS URL constants block (all `_WFS_*` names from lines 51-84), `_BUERGERAEMTER_URL` (line 65), `_WEIHNACHTSMARKT_URL` (line 69), and the entire `BERLIN = CityConfig(...)` assembly (from line 588 through line 889) from `berlin.py`. File header:

```python
"""Berlin CityConfig assembly.

Every URL + field name was verified against the Berlin Geoportal at
initial data-source pull. When re-adding a field or fixing a URL,
cross-check with `docs/architecture-notes/` or the relevant landscape
snapshot so the config and the reference stay in sync.

Attribution is inlined in the CityConfig(...) call (unlike Hamburg,
which factors it into a module-level dict) — preserve that shape.
"""
import os
import re
from pathlib import Path

from app.cities.base import CityConfig
from app.cities.berlin.directories import (
    _BERLIN_GLOSSARY,
    _SESB_GRUNDSCHULEN,
    _STANDESAMTS_BY_BEZIRK,
    _FINANZAMTS,
    _ARBEITSAGENTURS,
    _LEA_OFFICE,
    OTHERS_ADMIN_CARDS,
)
from app.cities.berlin.lenses import (
    YOUNG_FAMILY_LENS,
    NEWCOMER_LENS,
    QUIET_LIVING_LENS,
    COMMUTER_LENS,
)
```

Then paste the WFS URLs, `_BUERGERAEMTER_URL`, `_WEIHNACHTSMARKT_URL`, and the `BERLIN = CityConfig(...)` in the same order they appear in `berlin.py`. Do NOT change any field name, field map key, or URL string — this is a physical move.

**MANDATORY PATH BUMP (Berlin equivalent of Hamburg's PR-B fix):** Line 755 of the old `berlin.py` reads:

```python
    stations_data_path=str(Path(__file__).resolve().parent / "data" / "vbb_berlin_su.csv"),
```

After the move, `Path(__file__)` resolves to `.../app/cities/berlin/config.py` (one directory deeper). `.parent` would point at `.../app/cities/berlin/`, but the CSV lives at `.../app/cities/data/vbb_berlin_su.csv`. Change the line to:

```python
    stations_data_path=str(Path(__file__).resolve().parent.parent / "data" / "vbb_berlin_su.csv"),
```

That's the ONLY intentional edit in `config.py` beyond the physical move. If you find any other `Path(__file__).resolve().parent / "data" / ...` line in this block (a second CSV, a GeoJSON, whatever), apply the same `.parent.parent` bump — grep for `Path(__file__)` inside the pasted block after paste to confirm you caught them all.

Sanity check after the paste: `python -c "from app.cities.berlin.config import BERLIN; print(BERLIN.slug, len(BERLIN.finanzamts), BERLIN.smoke_address)"` should print `berlin <N> Kastanienallee 12, 10435` (where `<N>` matches the count you recorded in Step 5's baseline).

- [ ] **Step 7: Create `v0.1/app/cities/berlin/__init__.py`**

Broad `__all__` matching the Hamburg pattern from PR #93. Only `BERLIN` has external consumers today (per Global Constraints), but the lenses and `OTHERS_ADMIN_CARDS` are re-exported for pattern parity, for `__main__.py`'s internal use, and so a future LLM insight template can `from app.cities.berlin import YOUNG_FAMILY_LENS` without editing the shim first.

```python
"""Berlin CityConfig subpackage. Re-exports the public symbols current
consumers import by name so `from app.cities.berlin import ...` keeps
working with zero touch on routes/tests/inference templates. Adding a
new public symbol here means a call site is about to import it — pin
it in __all__ below so this file and the caller stay in sync."""
from app.cities.berlin.config      import BERLIN
from app.cities.berlin.lenses      import (
    YOUNG_FAMILY_LENS,
    NEWCOMER_LENS,
    QUIET_LIVING_LENS,
    COMMUTER_LENS,
)
from app.cities.berlin.directories import OTHERS_ADMIN_CARDS

__all__ = [
    "BERLIN",
    "YOUNG_FAMILY_LENS",
    "NEWCOMER_LENS",
    "QUIET_LIVING_LENS",
    "COMMUTER_LENS",
    "OTHERS_ADMIN_CARDS",
]
```

- [ ] **Step 8: Create `v0.1/app/cities/berlin/__main__.py`**

Move the entire `if __name__ == "__main__":` block from `berlin.py` (lines 891-917) verbatim into `__main__.py`, drop the `if __name__ == "__main__":` guard (running via `python -m app.cities.berlin` invokes this file with `__name__ == "__main__"` automatically), drop the 4-space indent that the guard introduced, and ADD the `__all__` regression guard at the end. The `print(...)` line at the end of the old block MUST survive verbatim — CI's selfcheck matrix greps for it.

Target file (fill the `# ...` placeholder with the exact asserts from the old block, lines 892-916):

```python
"""Selfcheck asserts for the Berlin CityConfig subpackage.

Invoked by `python -m app.cities.berlin` — matches the pre-split
invocation shape byte-for-byte so CI (selfchecks matrix) and dev
workflow keep working without an edit.

Asserts every invariant the old berlin.py `__main__` block had, plus
an extra guard that the __init__ shim's __all__ hasn't been narrowed."""
from app.cities.berlin import (
    BERLIN,
    YOUNG_FAMILY_LENS,
    NEWCOMER_LENS,
    QUIET_LIVING_LENS,
    COMMUTER_LENS,
    OTHERS_ADMIN_CARDS,
)
from app.cities import berlin as _pkg

# ... paste the assert block from berlin.py lines 892-916 verbatim
#     here, dropping the enclosing `if __name__ == "__main__":` guard
#     and the 4-space indent. Includes:
#       - `BERLIN.newcomer_lens is NEWCOMER_LENS` identity check
#       - `BERLIN.others_admin_cards is OTHERS_ADMIN_CARDS` identity check
#       - `BERLIN.buergeramt_wfs_url is not None` WFS wired check
#       - the exact `keys == [...]` list for newcomer_lens tiles (15 keys)
#       - the exact `commuter_keys == [...]` list for commuter_lens tiles (10 keys)
#       - the exact `admin_keys == [...]` list for others_admin_cards (5 keys)
#       - `"buergeramt" in BERLIN.attribution` check
#       - `BERLIN.smoke_address` truthiness check
#     (Note: the old block re-imports BERLIN/NEWCOMER_LENS/OTHERS_ADMIN_CARDS
#     inside the guard. In this file those imports are already at module top
#     — remove the redundant `from app.cities.berlin import ...` line that
#     was inside the old guard.)

# Regression guard: the __init__ shim's __all__ must not be narrowed
# below the six symbols we chose to publish (Hamburg-parity broad set).
assert set(_pkg.__all__) >= {
    "BERLIN",
    "YOUNG_FAMILY_LENS",
    "NEWCOMER_LENS",
    "QUIET_LIVING_LENS",
    "COMMUTER_LENS",
    "OTHERS_ADMIN_CARDS",
}, f"__init__.py __all__ narrowed to {sorted(_pkg.__all__)} — restore missing symbols before merge"

print("selfcheck ok: NEWCOMER_LENS + OTHERS_ADMIN_CARDS wired")
```

Copy-paste of the assert block is non-negotiable — those ~10 asserts encode the exact tile-key ordering, admin-card key list, and attribution wiring that the flat file's `__main__` already validated. Do NOT re-write them from memory. Verify byte-parity of the assert block: `diff <(sed -n '892,916p' /tmp/berlin_source.txt | sed 's/^    //') <(grep -A 100 "^assert\|^    assert\|^keys = \|^commuter_keys = \|^admin_keys = " v0.1/app/cities/berlin/__main__.py | head -25)` — expect only whitespace / import-line differences.

- [ ] **Step 9: Delete the flat file**

```bash
git rm v0.1/app/cities/berlin.py
```

- [ ] **Step 10: Run the shim contract test from Step 1 — expect PASS**

Run: `cd v0.1 && CITY=berlin pytest tests/cities/berlin/test_subpackage_public_surface.py -v 2>&1 | tail -12`
Expected: 5 passed. Any failure = the shim doesn't expose the symbol (edit `__init__.py`), OR `BERLIN` isn't identity-equal across the two import paths (usually means the flat file wasn't deleted OR `config.py` re-assembles a second `CityConfig(...)`).

- [ ] **Step 11: Run the moved `__main__` block**

Run: `cd v0.1 && python -m app.cities.berlin 2>&1 | tail -3`
Expected: `selfcheck ok: NEWCOMER_LENS + OTHERS_ADMIN_CARDS wired`. Any AssertionError = one of the invariants from the old `__main__` didn't survive the copy — grep the failed line in `berlin.py` (git history: `git show HEAD~1:v0.1/app/cities/berlin.py | sed -n '891,917p'`) and confirm the assert is byte-identical in `__main__.py`.

- [ ] **Step 12: Run the whole Berlin test slice**

Run: `cd v0.1 && CITY=berlin pytest -m berlin -v 2>&1 | tail -20`
Expected: all Berlin-marked tests pass. If `test_tiers.py` / `test_shape.py` / `test_lookup_dispatch.py` fail on `from app.cities.berlin import BERLIN`, the `__init__.py` shim is incomplete. If `test_parse_address.py` fails on something WFS-related, that's a pre-existing flake — re-run once to confirm; if it flakes twice, STOP and investigate.

- [ ] **Step 13: Verify cities-isolation selfcheck**

Run: `cd v0.1 && CITY=berlin python -m app.selfcheck 2>&1 | grep -E "cities-isolation|ERROR|FAIL" | head -5`
Expected: no `ERROR` or `FAIL` lines (may print `cities-isolation ok` or similar). `app.selfcheck`'s cities-isolation block enumerates `app.cities` subpackages via `pkgutil.iter_modules` and `getattr(mod, slug.upper())`; the subpackage must expose `BERLIN` on the package object (via the shim). If `AttributeError: module 'app.cities.berlin' has no attribute 'BERLIN'`, the shim is misnamed or `__init__.py` didn't import from `config`.

- [ ] **Step 14: Verify Hamburg still boots (proves untouched)**

Run: `cd v0.1 && python -m app.cities.hamburg 2>&1 | tail -3`
Expected: `selfcheck ok: Hamburg Newcomer + Commuter lenses wired` (the exact message from PR #93's `hamburg/__main__.py`). Any change = Hamburg was accidentally touched. Run: `git status app/cities/hamburg/` to confirm no unexpected changes.

- [ ] **Step 15: Boot both apps locally**

Two terminals, one per city (kill them after verification):

```bash
# Terminal 1 — Berlin
cd v0.1 && CITY=berlin uvicorn app.main:app --port 8001 --log-level warning &
BERLIN_PID=$!
sleep 30 && curl -sSf http://127.0.0.1:8001/ready
curl -sSf 'http://127.0.0.1:8001/api/lookup?address=Kastanienallee%2012%2C%2010435' \
  | python -c "import json, sys; d = json.load(sys.stdin); print('address ok:', bool(d.get('address'))); print('nearest_school ok:', bool(d.get('nearest_school') or d.get('schools')))"
kill $BERLIN_PID
```

Expected: `/ready` returns `{"status":"ready","city":"berlin"}`; the `/api/lookup` prints `address ok: True` and `nearest_school ok: True`. If `address ok: False`, the geocoder WFS wiring broke (regression in the `_WFS_ADR` URL or field map). If `nearest_school ok: False`, the schools WFS wiring or `_SESB_GRUNDSCHULEN` reference broke. Either way = STOP, do NOT commit, debug against `git show HEAD:v0.1/app/cities/berlin.py`.

```bash
# Terminal 2 — Hamburg (proves untouched)
cd v0.1 && CITY=hamburg HVV_STATIONS_PATH=$(pwd)/app/cities/data/vbb_hamburg_su.csv HVV_FERRY_PATH=$(pwd)/app/cities/data/hvv_hamburg_ferry.csv OSM_LOCAL_PATH="" ADDRESS_LOCAL_PATH="" uvicorn app.main:app --port 8002 --log-level warning &
HH_PID=$!
sleep 45 && curl -sSf http://127.0.0.1:8002/ready
kill $HH_PID
```

Expected: `/ready` returns `{"status":"ready","city":"hamburg"}`. Failure = you touched Hamburg — STOP.

- [ ] **Step 16: Commit (atomic — split + delete + test in one)**

```bash
cd /Users/sapta/Documents/personal/myStage/claude-personal/berlin-address-intelligence
git add v0.1/app/cities/berlin/ v0.1/tests/cities/berlin/test_subpackage_public_surface.py
git status --porcelain    # sanity — expect the 5 new berlin/*.py files + the new test + the deletion of berlin.py
git commit -m "$(cat <<'EOF'
refactor(cities): split app/cities/berlin.py into a subpackage

Splits the 917-LOC flat file into five focused modules mirroring the
Hamburg pattern from PR #93:

  berlin/__init__.py       shim re-exporting the public surface
  berlin/config.py         CityConfig assembly + WFS URLs + inline
                            attribution (Path bumped .parent → .parent.parent
                            for the stations CSV, matching Hamburg's fix)
  berlin/directories.py    curated tuples (Standesamt, Finanzamt, LEA,
                            Arbeitsagentur, SESB bilingual schools,
                            glossary) + OTHERS_ADMIN_CARDS
  berlin/lenses.py         YoungFamily + Newcomer + QuietLiving +
                            Commuter LensConfig assemblies (all four)
  berlin/__main__.py       selfcheck asserts + __all__ regression
                            guard (preserves `python -m app.cities.berlin`)

The __init__.py shim re-exports BERLIN, YOUNG_FAMILY_LENS,
NEWCOMER_LENS, QUIET_LIVING_LENS, COMMUTER_LENS, OTHERS_ADMIN_CARDS.
The external grep at 2026-09-22 shows only BERLIN is imported by
call-sites (app/core/*, tests/, tests/conftest.py), but the lenses
and OTHERS_ADMIN_CARDS are re-exported for pattern parity with
Hamburg and for internal use in __main__.py.

__main__.py adds an __all__ regression guard that fails the
selfcheck matrix if the shim's public surface is ever narrowed.

Consumers unchanged: every `from app.cities.berlin import ...` still
resolves. `python -m app.cities.berlin` still prints
"selfcheck ok: NEWCOMER_LENS + OTHERS_ADMIN_CARDS wired". Hamburg
untouched.

Implements PR-C of the design at
docs/superpowers/specs/2026-09-22-hamburg-config-subpackage-design.md
(§Berlin follow-up).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task C3: Push, open PR, wait for CI green, merge, deploy

**Files:** none (git + deploy operations).

**Interfaces:**
- Consumes: the atomic commit from Task C2.
- Produces: shipped Berlin subpackage in prod, verified via `update.sh` per-city smoke.

- [ ] **Step 1: Push the branch**

```bash
cd /Users/sapta/Documents/personal/myStage/claude-personal/berlin-address-intelligence
git push -u origin refactor/berlin-config-subpackage
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --title "refactor(cities): split berlin.py into a subpackage" --body "$(cat <<'EOF'
## Summary
Splits \`v0.1/app/cities/berlin.py\` (917 LOC flat file) into a focused subpackage of five modules, mirroring the Hamburg pattern shipped in #93. Every existing \`from app.cities.berlin import ...\` keeps working via the \`__init__.py\` shim; \`python -m app.cities.berlin\` still runs the selfcheck asserts. Hamburg untouched.

Implements PR-C of the design at \`docs/superpowers/specs/2026-09-22-hamburg-config-subpackage-design.md\` (§Berlin follow-up).

## New files
- \`app/cities/berlin/__init__.py\` — shim re-exporting BERLIN, YOUNG_FAMILY_LENS, NEWCOMER_LENS, QUIET_LIVING_LENS, COMMUTER_LENS, OTHERS_ADMIN_CARDS + \`__all__\` pin
- \`app/cities/berlin/config.py\` — CityConfig assembly + WFS URLs + inline attribution (\`Path(__file__)\` bumped \`.parent → .parent.parent\` for the stations CSV, matching Hamburg's fix)
- \`app/cities/berlin/directories.py\` — curated tuples (Standesamt, Finanzamt, LEA, Arbeitsagentur, SESB bilingual schools, Berlin glossary) + OTHERS_ADMIN_CARDS
- \`app/cities/berlin/lenses.py\` — YoungFamily + Newcomer + QuietLiving + Commuter LensConfig assemblies (all four)
- \`app/cities/berlin/__main__.py\` — selfcheck asserts + \`__all__\` regression guard (preserves \`python -m app.cities.berlin\`)
- \`tests/cities/berlin/test_subpackage_public_surface.py\` — locks the shim public surface

## Deleted
- \`app/cities/berlin.py\` — replaced by the subpackage above (same commit as subpackage creation to avoid Python import-resolution ambiguity).

## Scope this PR intentionally does NOT touch
- \`hamburg/\` subpackage
- CI workflows (selfchecks matrix already includes \`app.cities.berlin\`; per-city pytest split already in place from PR-A)
- \`tests/cities/berlin/\` scaffold (already scaffolded in PR-B)
- \`update.sh\` / \`rollback.sh\` (per-city smoke + app-hh rebuild already shipped)
- Any \`app/core/*\`, \`app/routes/*\`, \`app/deps.py\`, frontend, or Docker config

## Test plan
- [x] Local: shim contract tests pass (\`tests/cities/berlin/test_subpackage_public_surface.py\`, 5 tests)
- [x] Local: \`python -m app.cities.berlin\` prints \`selfcheck ok: NEWCOMER_LENS + OTHERS_ADMIN_CARDS wired\` including new \`__all__\` guard
- [x] Local: \`CITY=berlin python -m app.selfcheck\` runs cities-isolation without \`AttributeError\`
- [x] Local: Hamburg still boots (\`python -m app.cities.hamburg\`, \`CITY=hamburg uvicorn ...\` /ready)
- [x] Local: \`CITY=berlin pytest -m berlin\` — full Berlin slice green
- [x] Local: \`CITY=berlin uvicorn ...\` /ready + \`/api/lookup?address=Kastanienallee 12, 10435\` returns \`address ok + nearest_school ok\`
- [ ] CI: three per-city pytest steps + selfchecks matrix (already includes \`app.cities.berlin\`) all green
- [ ] Prod deploy: \`update.sh\` per-city smoke prints \`ok\` for both \`app\` and \`app-hh\`, no rollback needed

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Wait for CI**

Run: `gh pr checks --watch`
Expected: exit 0. If any check fails, do NOT merge — fix the underlying issue locally, push, re-await. The most likely failure is the selfchecks matrix step complaining about the `__all__` guard message; fix `__main__.py` and push.

- [ ] **Step 4: Merge**

Run: `gh pr merge --merge --delete-branch`

- [ ] **Step 5: Sync local main + review the diff about to ship**

```bash
git checkout main && git pull
git log --oneline -5
git diff HEAD~1 HEAD --stat   # confirms the subpackage delete/create is the merge
```

- [ ] **Step 6: Pre-deploy sanity on the Hetzner box**

```bash
ssh sapta@<box-ip>
cd /srv/addrlens/repo/v0.1
git fetch origin
git log --oneline HEAD..origin/main   # confirm the refactor commit is what we expect
docker compose exec app python -c \
  "from app.cities.berlin import BERLIN, NEWCOMER_LENS, YOUNG_FAMILY_LENS, QUIET_LIVING_LENS, COMMUTER_LENS, OTHERS_ADMIN_CARDS; \
   print(BERLIN.slug, len(BERLIN.finanzamts), len(NEWCOMER_LENS.tiles), BERLIN.smoke_address)"
# Expect a line ending in "Kastanienallee 12, 10435". The container is still on the OLD flat berlin.py
# at this point (we haven't run update.sh yet) — the flat file also exposes all six symbols, so the
# import statement above must succeed against BOTH pre- and post-deploy shapes. Failure here means the
# pre-refactor state is different from what the plan assumed — STOP and re-check.
```

- [ ] **Step 7: Deploy**

```bash
./ops/deploy/update.sh
```
Success signal:
- `[deploy] app ready after ~<N>s`
- `[deploy] app-hh ready after ~<M>s`
- Two `ok` lines from the per-city smoke (one for `app`, one for `app-hh`)
- `[deploy] done. deployed <new-sha> on top of <prev-sha>`

- [ ] **Step 8: Post-deploy verification (external)**

Wait ~30s after `[deploy] done`, then:

```bash
curl -sSf 'https://addrlens.de/api/lookup?address=Kastanienallee%2012%2C%2010435' | jq -r '.address.street'
curl -sSf 'https://hamburg.addrlens.de/api/lookup?address=Heidenkampsweg%2040%2C%2020097' | jq -r '.address.street'
```
Expected: `Kastanienallee` and `Heidenkampsweg` respectively. Berlin proves the refactor works end-to-end against real WFS; Hamburg proves this deploy didn't collateral-damage the sibling container.

- [ ] **Step 9: If deploy fails at any step**

```bash
./ops/deploy/rollback.sh   # defaults to /srv/addrlens/last-deployed.sha
```
Recovery time ~5-10 min (rebuild). Both containers restart. Verify `/ready` on both public URLs; open a follow-up PR with the fix + a regression test that would have caught it. `rollback.sh` was fixed in PR #92 to rebuild `app app-hh inference` — no manual step needed for the Hamburg container.

---

## Summary

- **1 branch:** `refactor/berlin-config-subpackage`
- **1 PR:** `refactor(cities): split berlin.py into a subpackage`
- **1 atomic commit:** creates 5 new files under `app/cities/berlin/` + 1 new test + deletes `app/cities/berlin.py`
- **0 CI edits, 0 test relocations, 0 deploy-script edits** — every guardrail was pre-shipped in PR #92 (PR-A) + PR #93 (PR-B)
- **Deploy is standard:** `ssh sapta@<box>; cd /srv/addrlens/repo/v0.1; ./ops/deploy/update.sh` on the Hetzner box; per-city smoke gates the cutover; `rollback.sh` covers both containers

## New files

- `app/cities/berlin/__init__.py` — shim (~15 LOC)
- `app/cities/berlin/config.py` — CityConfig assembly + WFS constants + inline attribution (~340 LOC)
- `app/cities/berlin/directories.py` — curated tuples + OTHERS_ADMIN_CARDS (~200 LOC)
- `app/cities/berlin/lenses.py` — 4 LensConfig assemblies (~310 LOC)
- `app/cities/berlin/__main__.py` — selfcheck asserts + regression guard (~45 LOC)
- `tests/cities/berlin/test_subpackage_public_surface.py` — shim contract tests (~55 LOC)

## Deleted

- `app/cities/berlin.py` (917 LOC)

## Test plan

- `pytest tests/cities/berlin/test_subpackage_public_surface.py -v` — 5 green (locks public surface)
- `python -m app.cities.berlin` — prints `selfcheck ok: NEWCOMER_LENS + OTHERS_ADMIN_CARDS wired`
- `CITY=berlin python -m app.selfcheck` — no ERROR/FAIL
- `python -m app.cities.hamburg` — still prints Hamburg's selfcheck ok line (untouched)
- `CITY=berlin pytest -m berlin` — full Berlin slice green
- `CITY=berlin uvicorn app.main:app --port 8001` — `/ready` returns ready; `/api/lookup?address=Kastanienallee 12, 10435` returns `address ok + nearest_school ok`
- `CITY=hamburg uvicorn app.main:app --port 8002` — `/ready` returns ready (proves untouched)
- CI: three per-city pytest steps + selfchecks matrix (includes `app.cities.berlin`) all green
- Prod: `update.sh` per-city smoke prints `ok` for both `app` and `app-hh`

## Self-Review

**Spec coverage:**
- Spec §Berlin follow-up (5-file subpackage layout) → Task C2 Steps 4-8 ✓
- Spec §Berlin follow-up (`__init__.py` re-exports BERLIN) → Task C2 Step 7 ✓ (broadened to include 4 lenses + OTHERS_ADMIN_CARDS per approved design)
- Spec §Berlin follow-up (`__main__.py` preserves `python -m app.cities.berlin`) → Task C2 Step 8 ✓
- Spec §Berlin follow-up (selfcheck matrix already includes `app.cities.berlin` — no CI change needed) → Global Constraints ✓
- Spec §Berlin follow-up (deploy choreography identical to PR-B) → Task C3 Steps 6-8 ✓
- Memory `project_pr_c_berlin_subpackage.md` (all 4 gotchas: atomic commit; every symbol re-exported; explicit `__all__` + regression guard; branch pin) → Task C2 Steps 9+16; Steps 1+10; Steps 7+8; and (branch pin, addressed at dispatch time in the subagent-driven-development phase, not in the plan text) ✓
- Memory `feedback_subagent_branch_pin.md` (implementer must verify `git branch --show-current` before first commit) → Task C1 Step 2 sets up the branch; the HARD CONSTRAINT branch-pin block belongs in the subagent dispatch prompt (not in the plan file itself)

**Placeholder scan:** The `# ...` placeholder in Task C2 Step 4 (lens tile lists) and Step 8 (assert block) are DELIBERATE — they instruct the implementer to copy the corresponding source lines verbatim, with explicit line references, byte-parity checks, and reference reads (`/tmp/berlin_source.txt`, `git show HEAD~1:v0.1/app/cities/berlin.py`) to make the copy mechanical. Every command block, every test file, and every commit message is complete.

**Type consistency:** The six-symbol public-surface set `{BERLIN, YOUNG_FAMILY_LENS, NEWCOMER_LENS, QUIET_LIVING_LENS, COMMUTER_LENS, OTHERS_ADMIN_CARDS}` is IDENTICAL in Task C2 Step 1 (shim contract test), Step 7 (`__init__.py::__all__`), Step 8 (`__main__.py` regression guard), Step 16 (commit message), Task C3 Step 2 (PR body), and Task C3 Step 6 (pre-deploy sanity). The `smoke_address="Kastanienallee 12, 10435"` string is IDENTICAL across `berlin.py:876`, Task C2 Step 3 (landmark table), Step 6 (paste destination), Step 15 (local smoke curl), Task C3 Step 6 (pre-deploy sanity), and Task C3 Step 8 (post-deploy verification). The Path-bump `.parent → .parent.parent` appears in Task C2 Step 3 (landmark) and Step 6 (mandatory edit) — nowhere else, because there is no second occurrence to fix.

**One thing worth calling out** to the executor: Task C2 is by far the largest task (~45 minutes careful work). It's not further decomposed because splitting it into "create lenses.py first, then directories.py, then config.py" is not testable in isolation — the imports don't resolve until every file exists AND the flat file is deleted. Its Step 10 shim-contract test IS the TDD gate; Steps 11-15 are integration checks that catch what a unit test can't. If a subagent implementer times out mid-Task-C2, the partial state on disk is usually salvageable — verify byte-parity via `wc -l` + `grep -c` against `/tmp/berlin_source.txt` before deciding to restart.
