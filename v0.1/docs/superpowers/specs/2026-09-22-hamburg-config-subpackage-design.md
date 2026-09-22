# Hamburg CityConfig subpackage split — design

**Status:** approved, ready for implementation planning
**Date:** 2026-09-22
**Owner:** saptadip.sarkar@beyonnex.io
**Cities affected:** Hamburg (this spec), Berlin (follow-up PR-C, same pattern)

---

## Problem

`v0.1/app/cities/hamburg.py` is a 666-LOC flat file that owns everything about Hamburg: WFS URL constants, per-layer field maps, seven curated address directories, two `LensConfig` objects, the glossary regex list, an attribution dict, `OTHERS_ADMIN_CARDS`, the `HAMBURG = CityConfig(...)` assembly, and the `__main__` selfcheck asserts. It grew organically as Hamburg data-source parity landed (PR #45 through PR #90).

`v0.1/app/cities/berlin.py` sits at 913 LOC with the same shape. Both files will grow as validation logic, lens configs, and curated directories accumulate. A flat file is fine at 300 LOC; at ~700 it makes changes harder to review (the recent Hamburg PRs each touched between 3 and 6 unrelated concerns in the same file), and future onboarding of a third city (Munich, Cologne) will duplicate the same overgrowth if the pattern isn't fixed now.

**Non-goals** (explicitly rejected):
- Splitting the codebase into per-city GitHub repos. See `docs/architecture-notes/2026-09-22-monorepo-vs-multirepo.md` (or inline in the brainstorm transcript). Repo split solves nothing that CityConfig injection + per-city Docker containers don't already solve, and introduces ~5000 LOC duplication + UX drift + N-way CI + N-way deploy.
- Refactoring `berlin.py` in this spec. That is PR-C, out of scope here (sketched in §7 for continuity).
- Adding city-specific loaders or validators as new files today. Loaders live in `app/core/loaders/`; Hamburg-specific validation lives in `app/selfcheck.py:_live_selfcheck_hamburg`. Neither has content that warrants a dedicated per-city file yet — YAGNI.

## Constraints

- **Production is live.** Berlin serves `addrlens.de`; Hamburg serves `hamburg.addrlens.de`. Both are single-container-per-city on one Hetzner box behind Cloudflare tunnels. Deploy is manual SSH + `./ops/deploy/update.sh`; rollback is `./ops/deploy/rollback.sh <sha>`.
- **No blue/green.** `update.sh` restarts containers in place and gates on `/ready` (90s budget) before declaring success. Any import-level breakage fails the readiness gate → brief 502s on `hamburg.addrlens.de` and `addrlens.de` until rollback runs.
- **Every consumer imports `HAMBURG` via `from app.cities.hamburg import HAMBURG`.** The subpackage MUST preserve this import path — every route, dep, index method, test would otherwise need touching.
- **The invocation `python -m app.cities.hamburg` MUST keep running the selfcheck asserts** — it's used by the CI selfchecks matrix, developer workflow, and referenced in the hamburg.py docstring.

## Approach

Two PRs, both Hamburg-only, in strict order.

### PR-A — safety net (no runtime code changes)

Purpose: harden CI to catch what today's CI misses, before we touch runtime code.

1. Add pytest markers `berlin` + `hamburg` in `pyproject.toml`.
2. Decorate the 8 clearly-Hamburg test files with `pytestmark = pytest.mark.hamburg` (no file moves in PR-A).
3. Decorate Berlin-adjacent tests (`test_lookup_dispatch.py`, `test_parse_address.py`) with `pytestmark = pytest.mark.berlin`.
4. In `.github/workflows/test.yml`, replace the single `pytest -v --cov=...` step with three steps in the same job, chained with `--cov-append` so combined coverage across all three slices matches today's single-run number (a naive per-step `--cov=app --cov-report=xml` would leave only the last slice measured):
   - Step 1 (shared): `pytest -v -m "not berlin and not hamburg" --cov=app --cov-report= ` (no `CITY` env; writes `.coverage` in append mode disabled = fresh file)
   - Step 2 (Berlin): `pytest -v -m berlin --cov=app --cov-append --cov-report= ` (`CITY=berlin`)
   - Step 3 (Hamburg): `pytest -v -m hamburg --cov=app --cov-append --cov-report=xml --cov-report=term-missing` (`CITY=hamburg`; final step emits the XML report)

   Rationale: coverage sums the three complementary slices into one report; the artefact upload (`coverage-xml`) sees the same combined `coverage.xml` shape it sees today; the CI-badge doesn't silently drop by 15-20% just because we split the run.
5. Add `app.cities.hamburg` to the `selfchecks:` matrix `module:` list (one line).
6. Fix `v0.1/ops/deploy/rollback.sh` to rebuild `app app-hh inference` (currently only rebuilds `app inference`; the Hamburg container is silently skipped on rollback). Match `update.sh`'s treatment; add a comment pinning the parity requirement.

**Deploy risk: zero.** No runtime code touched. Merging PR-A cannot break either production app. Recommended: run the rollback script as a no-op rehearsal against the current SHA after PR-A merges, to prove the app-hh fix works before we need it in anger.

### PR-B — refactor (subpackage split + deploy smoke)

Purpose: split `hamburg.py` into a subpackage with focused files; extend `update.sh` post-`/ready` smoke to catch runtime regressions at deploy time.

1. **Subpackage creation** — 5 new files under `v0.1/app/cities/hamburg/`:

   | File | Content | Approx LOC |
   |---|---|---|
   | `__init__.py` | Import shim: re-exports every public symbol current consumers import by name. See §Public surface below for the exact list. | ~12 |
   | `config.py` | WFS URL constants, field maps, attribution dict, `_BEZIRK_ID_TO_NAME`, `HAMBURG = CityConfig(...)` assembly. Imports directories + lenses from siblings. | ~280 |
   | `directories.py` | Curated tuples: `_STANDESAMTS_BY_BEZIRK`, `_KUNDENZENTREN`, `_FINANZAMTS`, `_ARBEITSAGENTURS`, `_LEA_OFFICE`, `_INTL_SCHOOLS`, `_REGIONAL_RAIL`, `_HAMBURG_GLOSSARY`, `OTHERS_ADMIN_CARDS`. Grouped by their shared maintenance property (hand-curated, annual re-verification). | ~150 |
   | `lenses.py` | `NEWCOMER_LENS`, `COMMUTER_LENS` `LensConfig` assemblies. | ~200 |
   | `__main__.py` | The `if __name__ == "__main__":` assert block from today's `hamburg.py`. Preserves `python -m app.cities.hamburg` invocation. | ~60 |

2. **Delete old flat file** — `v0.1/app/cities/hamburg.py`, in the SAME commit that creates the subpackage. A two-commit sequence would leave a moment where both `hamburg.py` and `hamburg/` exist, which is ambiguous for Python's import machinery (finder order varies by Python version). Python resolves `app.cities.hamburg` to the new subpackage; no consumer needs an edit provided the shim in §Public surface is complete.

**Public surface** — the shim MUST re-export every symbol current consumers import by name. Confirmed by `grep "from app.cities.hamburg import"` (2026-09-22, 4 call sites):

| Symbol | Imported by |
|---|---|
| `HAMBURG` | `app/deps.py` (indirect via city registry), `tests/unit/test_hamburg_config.py`, `tests/unit/test_hamburg_lens_composers.py` |
| `NEWCOMER_LENS` | `tests/unit/test_hamburg_config.py`, `inference/templates/lens_newcomer_hamburg_insight.py` |
| `COMMUTER_LENS` | `tests/unit/test_hamburg_config.py`, `inference/templates/lens_commuter_hamburg_insight.py` |
| `OTHERS_ADMIN_CARDS` | asserted in the moved `__main__.py` (`HAMBURG.others_admin_cards is OTHERS_ADMIN_CARDS`); also the Berlin convention (`berlin.py:889`) |

The shim contract:
```python
# v0.1/app/cities/hamburg/__init__.py
"""Hamburg CityConfig subpackage. Re-exports the public symbols current
consumers import by name so `from app.cities.hamburg import ...` keeps
working with zero touch on routes/tests/inference templates. Adding a
new public symbol here means a call site is about to import it — pin
it in this list so `__init__.py` and the caller stay in sync."""
from app.cities.hamburg.config      import HAMBURG
from app.cities.hamburg.lenses      import NEWCOMER_LENS, COMMUTER_LENS
from app.cities.hamburg.directories import OTHERS_ADMIN_CARDS

__all__ = ["HAMBURG", "NEWCOMER_LENS", "COMMUTER_LENS", "OTHERS_ADMIN_CARDS"]
```

Regression guard: add a smoke assert in PR-B's `__main__.py` after the existing selfcheck asserts: `from app.cities import hamburg as _pkg; assert set(_pkg.__all__) >= {"HAMBURG","NEWCOMER_LENS","COMMUTER_LENS","OTHERS_ADMIN_CARDS"}` — fails the CI selfcheck if a future edit narrows the public surface.

3. **Test relocation** (Q5 option b: move city-specific + city-adjacent):

   Move to `v0.1/tests/cities/hamburg/`:
   - `test_hamburg_config.py`
   - `test_hamburg_lens_composers.py`
   - `test_sozialmonitoring.py`
   - `test_sozialmonitoring_legend.py`
   - `test_oaf_geocoder.py`
   - `test_oaf_geocoder_remap.py`
   - `test_ferry_lookup.py`
   - `test_hospital_info_int_coerce.py`

   Move to `v0.1/tests/cities/berlin/`:
   - `test_lookup_dispatch.py`
   - `test_parse_address.py`

   Add `tests/cities/{berlin,hamburg}/__init__.py` (empty) and a directory-level `conftest.py` that applies the marker to every collected item — **NOT** a bare `pytestmark = ...` at conftest module level, which pytest silently ignores (conftest.py is not a test module, so module-level marks don't propagate to sibling tests). Use the `pytest_collection_modifyitems` hook instead:
   ```python
   # v0.1/tests/cities/hamburg/conftest.py
   import pytest

   def pytest_collection_modifyitems(config, items):
       """Every test under tests/cities/hamburg/ auto-picks up the
       @pytest.mark.hamburg marker so `pytest -m hamburg` selects it.
       Equivalent to putting `pytestmark = pytest.mark.hamburg` in every
       test module, but centralised so a new file dropped in this
       directory is marked without touching the file."""
       hamburg = pytest.mark.hamburg
       for item in items:
           if "tests/cities/hamburg/" in str(item.fspath):
               item.add_marker(hamburg)
   ```
   Berlin's `conftest.py` uses the same pattern with `pytest.mark.berlin`. Keep the module-level `pytestmark` decorators added in PR-A on tests that remain in `tests/unit/` (Berlin-adjacent files not yet moved); remove them only from files physically relocated into `tests/cities/{berlin,hamburg}/` since the conftest hook now covers them.

   **Verification** — after PR-B locally: `pytest -m hamburg --collect-only -q | wc -l` must report the same count as the pre-PR-B run of `pytest tests/unit/test_hamburg_*.py tests/unit/test_sozialmonitoring*.py ... --collect-only -q`. If the count drops to 0, the hook isn't firing (usually a path-check typo) — do NOT merge until the count matches.

4. **Deploy-script smoke extension** — `v0.1/ops/deploy/update.sh`. The smoke runs INSIDE the existing readiness `for svc_port in "app:8001" "app-hh:8002"` loop, in the branch where `READY=1` is set, immediately before `break`. Placement inside the loop is what keeps `$svc` and `$port` in scope (both are for-loop-locals derived from `svc_port`); placing this block after the loop would leave both variables set to the last iteration's values only, which would smoke Hamburg twice and Berlin never. Bash double-quotes around the `-c` argument are required so `${port}` and `$ADDR` interpolate before Python sees them:
   ```bash
   # Inside `for svc_port in "app:8001" "app-hh:8002"; do ... done`,
   # after the readiness loop declares READY="1" and before `break`:
   case "$svc" in
     app)    ADDR="Kastanienallee 12, 10435" ;;
     app-hh) ADDR="Heidenkampsweg 40, 20097" ;;
   esac
   if ! "${COMPOSE[@]}" exec -T "$svc" python -c "
   import json, urllib.request, urllib.parse, sys
   q = urllib.parse.urlencode({'address': '$ADDR'})
   r = urllib.request.urlopen(f'http://127.0.0.1:${port}/api/lookup?{q}', timeout=15)
   if r.status != 200: sys.exit(2)
   d = json.load(r)
   if not d.get('address') or (not d.get('schools') and not d.get('nearest_school')):
       sys.exit(3)
   print('ok')
   "; then
       echo "[deploy] ERROR: $svc smoke failed on address '$ADDR'"
       echo "[deploy] Rollback with: ./ops/deploy/rollback.sh $PREV_SHA"
       exit 4
   fi
   ```
   If the smoke fails, `update.sh` exits non-zero → operator runs `rollback.sh` with the `$PREV_SHA` echoed above.

**Explicit non-changes in PR-B:** `berlin.py` untouched, `app/core/*` untouched, `app/routes/*` untouched, `app/deps.py` untouched, frontend untouched, `Dockerfile` untouched, `docker-compose*.yml` untouched. Deliberately minimal blast radius.

## End-state layout (after PR-B and eventual PR-C)

```
v0.1/app/cities/
├── __init__.py
├── base.py                     # CityConfig dataclass — unchanged
├── berlin/                     # PR-C, future
│   ├── __init__.py             # shim: from .config import BERLIN
│   ├── config.py
│   ├── directories.py
│   ├── lenses.py
│   └── __main__.py
├── hamburg/                    # PR-B, this spec
│   ├── __init__.py             # shim: from .config import HAMBURG
│   ├── config.py               # CityConfig assembly + WFS constants
│   ├── directories.py          # curated tuples
│   ├── lenses.py               # LensConfig objects
│   └── __main__.py             # selfcheck asserts
└── data/                       # existing per-city CSV/JSON — unchanged
```

## CI shape (after PR-A)

**`pytest` job** — one workflow job, three steps:
1. `pytest -m "not berlin and not hamburg"` — shared tests, no `CITY` env
2. `pytest -m berlin --cov=app --cov-report=xml` — `CITY=berlin`, keeps coverage output
3. `pytest -m hamburg` — `CITY=hamburg`

Rationale: catches "test accidentally depends on the wrong `CITY`" and mirrors the deploy topology.

**`selfchecks` matrix** — adds `app.cities.hamburg` entry (today only `app.cities.base` and `app.cities.berlin` are present for `app.cities.*`).

**No new CI job.** A boot-and-curl smoke against real WFS was considered and rejected — cold boot triggers ~15 live WFS calls per city depending on `api.hamburg.de` + `geodienste.hamburg.de` + `gdi.berlin.de` uptime. Blocking every PR on external open-data portal availability is flaky. The equivalent signal is instead captured in `update.sh` at deploy time (`§approach.PR-B.4`), where a failure triggers rollback within the operator's shell instead of blocking unrelated PRs.

## Deploy choreography

### PR-A

1. Merge PR-A. CI runs new three-step pytest + expanded selfcheck matrix.
2. `ssh sapta@<box>; cd /srv/addrlens/repo/v0.1; ./ops/deploy/update.sh`. Behaviour byte-identical to today.
3. Rollback rehearsal:
   ```bash
   CURRENT=$(git rev-parse HEAD)
   ./ops/deploy/rollback.sh <old-sha>   # rebuilds app + app-hh + inference now
   curl -sf https://addrlens.de/ready && curl -sf https://hamburg.addrlens.de/ready
   ./ops/deploy/rollback.sh "$CURRENT"
   ```
   Proves the app-hh fix works before it's needed in anger.
4. **If rehearsal fails at any step** (Cloudflare hiccup, WFS cold-start timeout, an unrelated regression exposed by the rebuild): re-run `./ops/deploy/rollback.sh "$CURRENT"` to restore, treat PR-A as if unmerged for deploy purposes, and do NOT proceed to PR-B until the rehearsal is clean end-to-end. The refactor's safety net depends on this fix landing first — deploying PR-B against a still-buggy `rollback.sh` in prod means an app-hh regression cannot be rolled back atomically.

### PR-B

1. Merge PR-B. CI runs per-city pytest (with the new subpackage) + expanded selfcheck matrix.
2. Pre-deploy sanity (one-time, first PR-B deploy only):
   ```bash
   cd /srv/addrlens/repo/v0.1
   git fetch origin && git log --oneline HEAD..origin/main
   docker compose exec app-hh python -c \
     "from app.cities.hamburg import HAMBURG, NEWCOMER_LENS, COMMUTER_LENS, OTHERS_ADMIN_CARDS; \
      print(HAMBURG.slug, len(HAMBURG.finanzamts), len(NEWCOMER_LENS.tiles))"
   # Expect: "hamburg 9 13". Proves the shim's public surface resolves inside
   # the actual running Hamburg container (not a fresh one-off `run` container).
   ```
3. `./ops/deploy/update.sh` — now runs the extended smoke after `/ready`. Success = `[deploy] app ready` + `[deploy] app-hh ready` + both smoke `ok`.
4. Rollback on failure: `./ops/deploy/rollback.sh` (defaults to the SHA in `/srv/addrlens/last-deployed.sha`).

## Failure-mode matrix

| Failure mode | Caught by | Where |
|---|---|---|
| Import error in `hamburg/config.py` | `pytest` collect step surfaces package-level error | CI, pre-merge |
| Missing symbol in `__init__.py` shim | selfchecks matrix (`python -m app.cities.hamburg` runs `__main__.py` which asserts on `HAMBURG` identity) | CI, pre-merge |
| Config data regression (curated tuple count wrong) | `pytest -m hamburg` (existing asserts in `test_hamburg_config.py` check counts) | CI, pre-merge |
| Runtime shape regression on `/api/lookup` | `update.sh` smoke curl (rolls back on non-200 or missing `address`/`schools`/`nearest_school`) | Deploy time, pre-cutover |
| Silent Berlin regression | `pytest -m berlin` + selfcheck matrix + Berlin smoke curl | CI + deploy time |

## Testing plan

**PR-A verifiable locally before push:**
- `pytest -m hamburg` runs the 8 Hamburg tests, nothing else.
- `pytest -m berlin` (with `CITY=berlin`) runs Berlin-marked tests.
- `pytest -m "not berlin and not hamburg"` runs shared tests, no `CITY` env drift.
- `python -m app.cities.hamburg` runs selfcheck asserts (proves it belongs in CI matrix).
- Read the `rollback.sh` diff — confirm `app app-hh inference` and the parity comment.

**PR-B verifiable locally before push:**
- All PR-A checks still green.
- `python -c "from app.cities.hamburg import HAMBURG, NEWCOMER_LENS, COMMUTER_LENS, OTHERS_ADMIN_CARDS; print(HAMBURG.slug)"` prints `hamburg` and does not `ImportError` — proves the shim's public-surface contract.
- `python -c "from app.cities.hamburg.config import HAMBURG"`, `... .directories import _FINANZAMTS`, `... .lenses import NEWCOMER_LENS` all resolve.
- `python -m app.cities.hamburg` runs the moved-to-`__main__.py` assert block (including the new `__all__` regression guard).
- `CITY=hamburg python -m app.selfcheck` — runs the cities-isolation block (`app/selfcheck.py:62`) which enumerates `app.cities` via `pkgutil.iter_modules` and `getattr(mod, slug.upper())`. `pkgutil.iter_modules` still yields subpackages (`ispkg=True`); `getattr(mod, "HAMBURG")` resolves through the `__init__.py` shim. Failure here means the shim doesn't re-export `HAMBURG` correctly.
- `CITY=hamburg uvicorn app.main:app --port 8002` → `/ready` returns `{"status":"ready","city":"hamburg"}`; `/api/lookup?address=Heidenkampsweg 40, 20097` returns a shape identical to pre-refactor (diff two responses).
- `CITY=berlin uvicorn app.main:app --port 8001` — same verification for Berlin (proves untouched).
- `pytest -m hamburg --collect-only -q` reports the same count as `pytest tests/unit/test_hamburg_*.py tests/unit/test_sozialmonitoring*.py tests/unit/test_oaf_*.py tests/unit/test_ferry_lookup.py tests/unit/test_hospital_info_int_coerce.py --collect-only -q` did pre-move. A drop to 0 means the conftest hook isn't firing (§Approach PR-B step 3 verification).
- Run the new `update.sh` smoke curl inline against local containers — proves the rollback trigger works before it's needed.

**Note on shared fixtures:** `test_lookup_dispatch.py` imports `_FakeOSMLocal` from `tests/conftest.py`. After the move to `tests/cities/berlin/`, the root `tests/conftest.py` remains discoverable because pytest's rootdir is `v0.1/` — no fixture-relocation needed. Confirmed by pytest docs: rootdir determines conftest discovery for every collected item, not the item's directory.

## Berlin follow-up (PR-C, sketched, out of scope for this spec)

Mirror of PR-B applied to `berlin.py`. Split into `v0.1/app/cities/berlin/{__init__, config, directories, lenses, __main__}.py`. `__init__.py` re-exports `BERLIN`. `directories.py` owns Berlin's curated tuples (`FINANZAMTS`, `STANDESAMTS_BY_BEZIRK`, `BUERGERAMTS` if any curated, `LEA_OFFICE`, `ARBEITSAGENTURS`, `REGIONAL_RAIL`, `BILINGUAL_SCHOOLS`, `BERLIN_GLOSSARY`, `OTHERS_ADMIN_CARDS`). `lenses.py` owns `YOUNG_FAMILY_LENS`, `NEWCOMER_LENS`, `QUIET_LIVING_LENS`, `COMMUTER_LENS`. `__main__.py` preserves `python -m app.cities.berlin`. Selfcheck matrix already includes `app.cities.berlin`; no CI change needed. Deploy choreography identical to PR-B (same `update.sh` + smoke + rollback).

Timing: merge PR-C ~1 week after PR-B ships to prod, once Sentry + user reports confirm Hamburg's subpackage is stable.

## Open questions

None. All design decisions locked in during the brainstorm (Q1–Q6 in the session transcript).

## Success criteria

- PR-A merges, both prod containers deploy via `update.sh`, rollback rehearsal succeeds. Zero user-visible change.
- PR-B merges, prod deploys succeed on first try, `/api/lookup` returns byte-identical shape for canonical addresses in both cities.
- `wc -l app/cities/hamburg/*.py` shows each file ≤ 320 LOC (allows a small margin over the ~280 LOC `config.py` estimate for shebang/comments/imports drift).
- A greenfield Munich onboarding one month later takes ~1 day to scaffold `app/cities/munich/` by copying the Hamburg layout, vs. ~1 week starting from `hamburg.py` today.
