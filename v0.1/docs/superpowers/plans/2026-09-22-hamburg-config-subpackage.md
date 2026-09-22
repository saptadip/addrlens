# Hamburg CityConfig Subpackage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `v0.1/app/cities/hamburg.py` (666 LOC flat file) into a focused subpackage while adding a per-city CI safety net that makes the move safe to ship against live production.

**Architecture:** Two ordered PRs. **PR-A** ships a zero-runtime-change safety net (pytest markers, per-city CI runs, Hamburg config in the selfcheck matrix, `rollback.sh` fix so it rebuilds `app-hh`). **PR-B** ships the subpackage split (`hamburg/{__init__, config, directories, lenses, __main__}.py`) plus a per-city deploy smoke in `update.sh`. Every existing `from app.cities.hamburg import ...` keeps working via `__init__.py` re-exports; every existing `python -m app.cities.hamburg` invocation keeps working via `__main__.py`.

**Tech Stack:** Python 3.13, pytest 8.x (`--strict-markers` already on), FastAPI/uvicorn, Docker Compose, GitHub Actions matrix jobs.

**Spec:** `docs/superpowers/specs/2026-09-22-hamburg-config-subpackage-design.md`

## Global Constraints

- **Working directory** is `v0.1/` for every command below (pytest, uvicorn, docker compose, all `python -m` invocations). The repo has a legacy `v0.1/` prefix — deploy scripts, CI, everything anchors here.
- **Every consumer of `from app.cities.hamburg import HAMBURG` must keep working with zero touch on the call site.** The shim in `__init__.py` is the contract.
- **`python -m app.cities.hamburg` must keep running the selfcheck asserts.** Referenced by the CI selfchecks matrix, the deploy scripts, and developer workflow.
- **PR-A ships before PR-B.** PR-B's safety net depends on PR-A's `rollback.sh` fix landing in prod first (see spec §Deploy choreography).
- **No new CI job that hits external WFS.** `api.hamburg.de` and `geodienste.hamburg.de` blip; CI must stay offline. Smoke-testing happens at deploy time inside `update.sh`.
- **Every commit message includes the trailer** `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
- **Berlin path is untouched by both PRs.** `app/cities/berlin.py` is out of scope until follow-up PR-C.

---

## PR-A — Safety net

**Branch:** `chore/ci-per-city-safety-net`
**PR title:** `chore(ci): per-city pytest markers + Hamburg selfcheck + rollback.sh fix`

Zero runtime code changes. Six focused commits, each individually rollback-able.

### Task A1: Register `berlin` + `hamburg` pytest markers

**Files:**
- Modify: `v0.1/pyproject.toml:34-42` (existing `[tool.pytest.ini_options]` block, extend the `markers` list)

**Interfaces:**
- Consumes: nothing.
- Produces: two new registered pytest markers (`berlin`, `hamburg`) that Task A2/A3 can decorate tests with. Without this task, `--strict-markers` (already enabled) would fail any decorated test with "unknown marker".

- [ ] **Step 1: Confirm current markers block**

Run: `sed -n '34,42p' v0.1/pyproject.toml`
Expected: existing block with `markers = [ "integration: ... " ]`.

- [ ] **Step 2: Edit `v0.1/pyproject.toml`**

Replace the existing `markers = [ ... ]` block with:

```toml
markers = [
    "integration: hits live Berlin Geoportal WFS (opt-in via -m integration)",
    "berlin:  tests exercising Berlin config/data (run with CITY=berlin)",
    "hamburg: tests exercising Hamburg config/data (run with CITY=hamburg)",
]
```

- [ ] **Step 3: Verify marker registration**

Run: `cd v0.1 && pytest --collect-only -q > /dev/null && echo OK`
Expected: `OK`. Any `--strict-markers` failure prints to stderr with the offending marker name.

- [ ] **Step 4: Verify a filter on the new markers works**

Run: `cd v0.1 && pytest -m hamburg --collect-only -q | tail -3`
Expected: `no tests ran` — the markers are registered but no test file wears them yet (Task A2 adds them).

- [ ] **Step 5: Commit**

```bash
cd /Users/sapta/Documents/personal/myStage/claude-personal/berlin-address-intelligence
git add v0.1/pyproject.toml
git commit -m "$(cat <<'EOF'
chore(ci): register berlin + hamburg pytest markers

Extends the existing --strict-markers list so upcoming per-city
decorators don't trip strict-mode. Zero test behaviour change.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task A2: Decorate Hamburg-specific tests with `@pytest.mark.hamburg`

**Files:**
- Modify (add `pytestmark` decorator, 2 lines each): `v0.1/tests/unit/test_hamburg_config.py`, `v0.1/tests/unit/test_hamburg_lens_composers.py`, `v0.1/tests/unit/test_sozialmonitoring.py`, `v0.1/tests/unit/test_sozialmonitoring_legend.py`, `v0.1/tests/unit/test_oaf_geocoder.py`, `v0.1/tests/unit/test_oaf_geocoder_remap.py`, `v0.1/tests/unit/test_ferry_lookup.py`, `v0.1/tests/unit/test_hospital_info_int_coerce.py`

**Interfaces:**
- Consumes: `pytest.mark.hamburg` (registered in Task A1).
- Produces: 8 tests now selectable via `pytest -m hamburg`. Consumed by Task A4 (CI split).

- [ ] **Step 1: Capture the pre-change Hamburg test count for later parity check**

Run: `cd v0.1 && pytest tests/unit/test_hamburg_config.py tests/unit/test_hamburg_lens_composers.py tests/unit/test_sozialmonitoring.py tests/unit/test_sozialmonitoring_legend.py tests/unit/test_oaf_geocoder.py tests/unit/test_oaf_geocoder_remap.py tests/unit/test_ferry_lookup.py tests/unit/test_hospital_info_int_coerce.py --collect-only -q 2>/dev/null | tail -1`
Expected: something like `<N> tests collected in 0.02s`. Record `<N>` — needed in Step 3.

- [ ] **Step 2: Add `pytestmark = pytest.mark.hamburg` to each file**

For each of the 8 files listed above, insert this snippet immediately after the last `import` line and before the first test/function:

```python
import pytest

pytestmark = pytest.mark.hamburg
```

If the file already imports `pytest`, skip the `import pytest` line — just add the `pytestmark = ...` line. Do NOT add a blank line before `pytestmark` if the previous line is another `import`.

Concrete edit example for `v0.1/tests/unit/test_hamburg_config.py` (which currently starts with `from app.cities.hamburg import HAMBURG, NEWCOMER_LENS, COMMUTER_LENS`):

```python
from app.cities.hamburg import HAMBURG, NEWCOMER_LENS, COMMUTER_LENS
import pytest

pytestmark = pytest.mark.hamburg
```

- [ ] **Step 3: Verify collect count parity**

Run: `cd v0.1 && pytest -m hamburg --collect-only -q 2>/dev/null | tail -1`
Expected: the same `<N> tests collected` count recorded in Step 1. A mismatch means one of the 8 files didn't pick up the decorator — grep the file for `pytestmark` and re-check.

- [ ] **Step 4: Verify tests still pass under the marker**

Run: `cd v0.1 && CITY=hamburg pytest -m hamburg -q 2>&1 | tail -5`
Expected: `<N> passed in ...s`. If any fail, they were already failing pre-decoration — check via `git stash; pytest -m hamburg; git stash pop`.

- [ ] **Step 5: Commit**

```bash
cd /Users/sapta/Documents/personal/myStage/claude-personal/berlin-address-intelligence
git add v0.1/tests/unit/test_hamburg_config.py v0.1/tests/unit/test_hamburg_lens_composers.py v0.1/tests/unit/test_sozialmonitoring.py v0.1/tests/unit/test_sozialmonitoring_legend.py v0.1/tests/unit/test_oaf_geocoder.py v0.1/tests/unit/test_oaf_geocoder_remap.py v0.1/tests/unit/test_ferry_lookup.py v0.1/tests/unit/test_hospital_info_int_coerce.py
git commit -m "$(cat <<'EOF'
chore(tests): mark 8 Hamburg-specific unit tests with @pytest.mark.hamburg

Enables `pytest -m hamburg` selection introduced by the CI split in
this same PR. Test bodies unchanged; only module-level `pytestmark`
lines added. Files stay in tests/unit/ for now — physical relocation
into tests/cities/hamburg/ happens in the follow-up refactor PR.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task A3: Decorate Berlin-adjacent tests with `@pytest.mark.berlin`

**Files:**
- Modify: `v0.1/tests/unit/test_lookup_dispatch.py`, `v0.1/tests/unit/test_parse_address.py`

**Interfaces:**
- Consumes: `pytest.mark.berlin` (registered in Task A1).
- Produces: 2 tests selectable via `pytest -m berlin`.

- [ ] **Step 1: Capture pre-change collect count**

Run: `cd v0.1 && pytest tests/unit/test_lookup_dispatch.py tests/unit/test_parse_address.py --collect-only -q 2>/dev/null | tail -1`
Expected: something like `<M> tests collected`. Record `<M>`.

- [ ] **Step 2: Add `pytestmark` to both files**

Same pattern as Task A2. For `v0.1/tests/unit/test_lookup_dispatch.py` (existing `from types import SimpleNamespace` at top):

```python
from types import SimpleNamespace
import pytest

pytestmark = pytest.mark.berlin
```

For `v0.1/tests/unit/test_parse_address.py` (existing `import pytest` at line 5):

```python
"""Unit tests for `app.core.addr.parse_address`.

Ground truth: the selfcheck block at the bottom of `app/core/addr.py`.
"""
import pytest

pytestmark = pytest.mark.berlin

from app.core.addr import parse_address
```

- [ ] **Step 3: Verify collect count parity**

Run: `cd v0.1 && pytest -m berlin --collect-only -q 2>/dev/null | tail -1`
Expected: `<M> tests collected` (same as Step 1).

- [ ] **Step 4: Verify Berlin tests still pass under the marker**

Run: `cd v0.1 && CITY=berlin pytest -m berlin -q 2>&1 | tail -5`
Expected: `<M> passed`.

- [ ] **Step 5: Commit**

```bash
git add v0.1/tests/unit/test_lookup_dispatch.py v0.1/tests/unit/test_parse_address.py
git commit -m "$(cat <<'EOF'
chore(tests): mark Berlin-adjacent tests with @pytest.mark.berlin

test_lookup_dispatch uses Berlin stubs; test_parse_address exercises
Berlin street-name/PLZ patterns. Both stay in tests/unit/ for now —
physical relocation into tests/cities/berlin/ happens in the follow-up
refactor PR.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task A4: Split CI pytest into three per-city steps with combined coverage

**Files:**
- Modify: `.github/workflows/test.yml:43-48` (the single `Test` step becomes three).

**Interfaces:**
- Consumes: markers from Task A1 + decorated tests from A2/A3.
- Produces: three named CI steps that fail independently. Coverage combined via `--cov-append` so the emitted `coverage.xml` sums all three slices (matches today's single-run number).

- [ ] **Step 1: Read current step to preserve style**

Run: `sed -n '43,48p' .github/workflows/test.yml`
Expected: the current single-`Test`-step block.

- [ ] **Step 2: Replace the single `Test` step with three steps**

Edit `.github/workflows/test.yml`. Delete lines 43-48 (the single `Test` block) and insert:

```yaml
      - name: Test (shared — no CITY)
        working-directory: v0.1
        env:
          INFERENCE_URL: http://localhost:9999
        # First step writes a fresh .coverage; later steps append. Without
        # --cov-append the last-run step would leave only its slice
        # measured, silently dropping the combined coverage badge.
        run: pytest -v -m "not berlin and not hamburg" --cov=app --cov-report=
      - name: Test (Berlin)
        working-directory: v0.1
        env:
          CITY: berlin
          INFERENCE_URL: http://localhost:9999
        run: pytest -v -m berlin --cov=app --cov-append --cov-report=
      - name: Test (Hamburg)
        working-directory: v0.1
        env:
          CITY: hamburg
          INFERENCE_URL: http://localhost:9999
        # Final step emits the XML+term reports off the combined .coverage.
        run: pytest -v -m hamburg --cov=app --cov-append --cov-report=term-missing --cov-report=xml
```

Note: the `Collect (fail-fast on import errors)` step above (lines 37-42) is unchanged — it still runs with `CITY: berlin` because it's a no-`m` collect that just proves the tree parses. Leave it alone.

- [ ] **Step 3: Validate the workflow file syntax**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))" && echo OK`
Expected: `OK`. Any `yaml.YAMLError` printed to stderr — fix indentation.

- [ ] **Step 4: Locally simulate each of the three commands to confirm they work**

Run:
```bash
cd v0.1
INFERENCE_URL=http://localhost:9999 pytest -v -m "not berlin and not hamburg" --cov=app --cov-report= -q 2>&1 | tail -3
CITY=berlin INFERENCE_URL=http://localhost:9999 pytest -v -m berlin --cov=app --cov-append --cov-report= -q 2>&1 | tail -3
CITY=hamburg INFERENCE_URL=http://localhost:9999 pytest -v -m hamburg --cov=app --cov-append --cov-report=term-missing --cov-report=xml -q 2>&1 | tail -3
```
Expected: three green `passed` summaries. `coverage.xml` should exist after the third command.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/test.yml
git commit -m "$(cat <<'EOF'
chore(ci): split pytest into shared/berlin/hamburg runs with combined coverage

Runs three per-city pytest slices in the same job with --cov-append,
so the combined coverage.xml matches today's single-run number while
each slice can fail independently. Catches "test accidentally depends
on the wrong CITY env" and mirrors the two-container prod topology.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task A5: Add `app.cities.hamburg` to the CI selfchecks matrix

**Files:**
- Modify: `.github/workflows/test.yml` (the `selfchecks:` job's `matrix.module:` list, which currently has `app.cities.base` and `app.cities.berlin` but not Hamburg — line ~94).

**Interfaces:**
- Consumes: the existing `python -m app.cities.hamburg` selfcheck block (unchanged from today; still asserts on the flat file until PR-B moves it into `__main__.py`).
- Produces: one new matrix cell so a Hamburg config regression fails CI at the module-invocation level, not just via `pytest -m hamburg`.

- [ ] **Step 1: Locate the matrix `module:` entry for `app.cities.berlin`**

Run: `grep -n "app.cities.berlin" .github/workflows/test.yml`
Expected: one line like `          - app.cities.berlin` around line 94.

- [ ] **Step 2: Add `app.cities.hamburg` immediately after that line**

Edit `.github/workflows/test.yml`. Below the line containing `- app.cities.berlin`, insert:
```yaml
          - app.cities.hamburg
```
Keep the exact indentation (10 spaces + `- `).

- [ ] **Step 3: Validate YAML + verify locally**

Run:
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))" && echo OK
cd v0.1 && python -m app.cities.hamburg 2>&1 | tail -1
```
Expected first: `OK`. Expected second: `selfcheck ok: Hamburg Newcomer + Commuter lenses wired` (or the current tail line of `hamburg.py`'s `__main__`).

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/test.yml
git commit -m "$(cat <<'EOF'
chore(ci): add app.cities.hamburg to selfchecks matrix

Selfchecks matrix already runs app.cities.berlin + app.cities.base per
module — Hamburg was silently missing. Catches Hamburg CityConfig
assembly regressions that pytest doesn't see (e.g. new required
CityConfig field added but Hamburg's assembly not updated).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task A6: Fix `rollback.sh` to rebuild `app-hh` alongside `app`

**Files:**
- Modify: `v0.1/ops/deploy/rollback.sh:39-40` (the two lines that run `docker compose build` and `up -d --force-recreate`).

**Interfaces:**
- Consumes: nothing.
- Produces: `rollback.sh` now touches both Berlin (`app`) and Hamburg (`app-hh`) containers, matching `update.sh`'s treatment. Prevents "rollback silently leaves Hamburg on new code" scenario that would emerge the moment PR-B needs a rollback.

- [ ] **Step 1: Confirm the current buggy lines**

Run: `sed -n '38,41p' v0.1/ops/deploy/rollback.sh`
Expected:
```
cd "$REPO/v0.1"
"${COMPOSE[@]}" build app inference
"${COMPOSE[@]}" up -d --force-recreate app inference
echo "[rollback] done. now on $TARGET"
```

- [ ] **Step 2: Edit the two `docker compose` lines**

Replace those exact lines with:
```bash
cd "$REPO/v0.1"
# Parity with update.sh: both Berlin (app) and Hamburg (app-hh) must be
# rebuilt on rollback. Omitting app-hh here left Hamburg silently on the
# new-code image while Berlin rolled back (pre-PR#92 bug). Any change to
# update.sh's service list must be mirrored here — keep the two scripts
# service-symmetric.
"${COMPOSE[@]}" build app app-hh inference
"${COMPOSE[@]}" up -d --force-recreate app app-hh inference
echo "[rollback] done. now on $TARGET"
```

- [ ] **Step 3: Verify the script parses (bash syntax check, no execution)**

Run: `bash -n v0.1/ops/deploy/rollback.sh && echo OK`
Expected: `OK`. Any syntax error prints to stderr.

- [ ] **Step 4: Sanity-check that `app-hh` is a real service in compose**

Run: `grep -c "^  app-hh:" v0.1/docker-compose.prod.yml`
Expected: `1`. If `0`, the compose service is named differently — abort the task and re-check `docker-compose.prod.yml`.

- [ ] **Step 5: Commit**

```bash
git add v0.1/ops/deploy/rollback.sh
git commit -m "$(cat <<'EOF'
fix(ops): rollback.sh rebuilds app-hh alongside app

Pre-fix, rollback rebuilt only `app + inference` — Hamburg's container
stayed on the new-code image, so a rollback would leave the two
production apps on different SHAs. Parity with update.sh restored.
Comment pins the two scripts as service-symmetric to prevent regression.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task A7: Push PR-A, wait for CI green, merge, rehearse rollback in prod

**Files:** none (this task is git + deploy operations, not code).

**Interfaces:**
- Consumes: everything landed in Tasks A1-A6.
- Produces: a hardened CI + a fixed `rollback.sh` in prod, ready for PR-B to land against.

- [ ] **Step 1: Push the branch**

```bash
cd /Users/sapta/Documents/personal/myStage/claude-personal/berlin-address-intelligence
git push -u origin chore/ci-per-city-safety-net
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --title "chore(ci): per-city pytest markers + Hamburg selfcheck + rollback.sh fix" --body "$(cat <<'EOF'
## Summary
Safety net for the follow-up Hamburg subpackage refactor. Zero runtime code changes.

- Register \`berlin\` + \`hamburg\` pytest markers; decorate 8 Hamburg-clear tests + 2 Berlin-adjacent tests.
- Split CI pytest into three per-city steps with \`--cov-append\` so combined coverage matches today's single-run number.
- Add \`app.cities.hamburg\` to the selfchecks matrix (was silently missing).
- Fix \`rollback.sh\` to rebuild \`app-hh\` alongside \`app\` (pre-fix: Hamburg silently skipped on rollback).

Implements PR-A of the design at \`v0.1/docs/superpowers/specs/2026-09-22-hamburg-config-subpackage-design.md\`.

## Test plan
- [x] Local: \`pytest -m hamburg\` collects the 8 Hamburg tests, all pass
- [x] Local: \`pytest -m berlin\` collects the 2 Berlin-adjacent tests, all pass
- [x] Local: \`pytest -m "not berlin and not hamburg"\` runs shared tests, no CITY env drift
- [x] Local: \`python -m app.cities.hamburg\` prints selfcheck ok
- [x] Local: \`bash -n ops/deploy/rollback.sh\` syntax-clean
- [ ] CI: all three pytest steps green + selfchecks matrix (35 cells) green

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Wait for CI green**

Run: `gh pr checks --watch`
Expected: exit 0. All checks pass.

- [ ] **Step 4: Merge**

Run: `gh pr merge --merge --delete-branch`

- [ ] **Step 5: Sync local main**

```bash
git checkout main && git pull
git log --oneline -3
```
Expected: merge commit at HEAD.

- [ ] **Step 6: Deploy PR-A to prod (Hetzner box)**

SSH to the box + run the existing update flow. This ships the `rollback.sh` fix. No behaviour change for users.

```bash
ssh sapta@<box-ip>
cd /srv/addrlens/repo/v0.1
./ops/deploy/update.sh
```
Expected: `[deploy] app ready after ~<N>s`, `[deploy] app-hh ready after ~<M>s`, `[deploy] done. deployed <new-sha> on top of <prev-sha>`. Verify via curl:
```bash
curl -sSf https://addrlens.de/ready
curl -sSf https://hamburg.addrlens.de/ready
```
Expected: both return `{"status":"ready","city":"..."}`.

- [ ] **Step 7: Rehearse rollback (recommended, low-risk)**

Prove the `app-hh` fix works BEFORE it's needed in anger. Pick a known-good old SHA (last week's deploy log is fine — read `/srv/addrlens/last-deployed.sha` if unsure).

```bash
CURRENT="$(git rev-parse HEAD)"
OLD_SHA="<pick from git log --oneline -20>"
./ops/deploy/rollback.sh "$OLD_SHA"
curl -sSf https://addrlens.de/ready         # must return ready
curl -sSf https://hamburg.addrlens.de/ready # must return ready — this proves the fix
./ops/deploy/rollback.sh "$CURRENT"         # back to now
curl -sSf https://addrlens.de/ready && curl -sSf https://hamburg.addrlens.de/ready
```
Expected: all four `/ready` curls return `{"status":"ready", ...}`. Each rebuild is ~5-10 min.

- [ ] **Step 8: If rehearsal fails at any step**

Per spec §Deploy choreography PR-A step 4: `./ops/deploy/rollback.sh "$CURRENT"` restores; treat PR-A as if unmerged for deploy purposes; do NOT proceed to PR-B until the rehearsal is clean end-to-end. File an issue with the rehearsal failure logs.

---

## PR-B — Subpackage refactor + deploy smoke

**Branch:** `refactor/hamburg-config-subpackage`
**PR title:** `refactor(cities): split hamburg.py into a subpackage + deploy smoke`

Depends on PR-A being **merged AND deployed to prod** (Task A7 complete). Six commits.

### Task B1: Scaffold `tests/cities/{berlin,hamburg}/` with `pytest_collection_modifyitems` conftests

**Files:**
- Create: `v0.1/tests/cities/__init__.py` (empty)
- Create: `v0.1/tests/cities/berlin/__init__.py` (empty)
- Create: `v0.1/tests/cities/hamburg/__init__.py` (empty)
- Create: `v0.1/tests/cities/berlin/conftest.py`
- Create: `v0.1/tests/cities/hamburg/conftest.py`

**Interfaces:**
- Consumes: `pytest.mark.berlin` + `pytest.mark.hamburg` (from PR-A Task A1).
- Produces: automatic per-city marker application via `pytest_collection_modifyitems` hook. Every test file dropped into `tests/cities/hamburg/` is auto-marked `hamburg` without needing a `pytestmark = ...` line. Consumed by Task B2/B3 (physical test relocation).

- [ ] **Step 1: Write the failing test — assert the hook applies the marker**

Create a temporary test file at `v0.1/tests/cities/hamburg/test_hook_applies_marker.py`:

```python
"""Regression test: the directory-level conftest hook must apply
`@pytest.mark.hamburg` to every test collected under this directory.
Silent-failure guard for the "conftest pytestmark doesn't propagate"
bug that would otherwise make `pytest -m hamburg` collect zero tests."""


def test_this_file_is_auto_marked_hamburg(request):
    marks = {m.name for m in request.node.iter_markers()}
    assert "hamburg" in marks, f"expected hamburg marker; got {marks}"
```

- [ ] **Step 2: Run the test — expect FAIL (hook doesn't exist yet)**

Run: `cd v0.1 && pytest tests/cities/hamburg/test_hook_applies_marker.py -v 2>&1 | tail -5`
Expected: `FAILED` with `AssertionError: expected hamburg marker; got set()`. If instead it errors on collection because `tests/cities/` doesn't exist, that's fine — proves the scaffolding is needed.

- [ ] **Step 3: Create the four `__init__.py` files (empty)**

```bash
mkdir -p v0.1/tests/cities/berlin v0.1/tests/cities/hamburg
touch v0.1/tests/cities/__init__.py v0.1/tests/cities/berlin/__init__.py v0.1/tests/cities/hamburg/__init__.py
```

- [ ] **Step 4: Create `v0.1/tests/cities/hamburg/conftest.py`**

```python
"""Directory-level marker propagation for Hamburg tests.

pytest's module-level `pytestmark = pytest.mark.hamburg` does NOT
propagate from a conftest to sibling test modules (conftest is not a
test module, so its module-level marks are ignored). The
`pytest_collection_modifyitems` hook is the standard pattern: add the
marker to every item collected under this directory. New test files
dropped in here are auto-marked without touching the file."""
import pathlib

import pytest


def pytest_collection_modifyitems(config, items):
    hamburg = pytest.mark.hamburg
    this_dir = pathlib.Path(__file__).parent.resolve()
    for item in items:
        try:
            item_path = pathlib.Path(str(item.fspath)).resolve()
        except (TypeError, ValueError):
            continue
        # `.is_relative_to` is 3.9+; matches every item whose file lives
        # under this conftest's directory (recursively). String matching
        # on "tests/cities/hamburg/" would false-positive on any repo
        # that happens to contain that substring in an unrelated path.
        if this_dir in item_path.parents or item_path == this_dir:
            item.add_marker(hamburg)
```

- [ ] **Step 5: Create `v0.1/tests/cities/berlin/conftest.py`**

Identical shape to Step 4 but with `berlin`:
```python
"""Directory-level marker propagation for Berlin tests. See
tests/cities/hamburg/conftest.py for rationale."""
import pathlib

import pytest


def pytest_collection_modifyitems(config, items):
    berlin = pytest.mark.berlin
    this_dir = pathlib.Path(__file__).parent.resolve()
    for item in items:
        try:
            item_path = pathlib.Path(str(item.fspath)).resolve()
        except (TypeError, ValueError):
            continue
        if this_dir in item_path.parents or item_path == this_dir:
            item.add_marker(berlin)
```

- [ ] **Step 6: Run the guard test — expect PASS**

Run: `cd v0.1 && CITY=hamburg pytest tests/cities/hamburg/test_hook_applies_marker.py -v 2>&1 | tail -5`
Expected: `PASSED`. If still `FAILED`, the hook is silently no-op — most likely `item.fspath` type surprised the `.parents` check. Debug via `pytest --collect-only -q tests/cities/hamburg/` and add `print(item_path, this_dir)` in the hook temporarily.

- [ ] **Step 7: Verify `pytest -m hamburg` picks it up too**

Run: `cd v0.1 && CITY=hamburg pytest -m hamburg tests/cities/hamburg/ -v 2>&1 | tail -5`
Expected: `1 passed`.

- [ ] **Step 8: Verify the Berlin conftest by writing a symmetric guard test**

Create `v0.1/tests/cities/berlin/test_hook_applies_marker.py`:

```python
"""Mirror of tests/cities/hamburg/test_hook_applies_marker.py — proves
the Berlin conftest's `pytest_collection_modifyitems` hook applies
`@pytest.mark.berlin` to every item under this directory."""


def test_this_file_is_auto_marked_berlin(request):
    marks = {m.name for m in request.node.iter_markers()}
    assert "berlin" in marks, f"expected berlin marker; got {marks}"
```

Run: `cd v0.1 && CITY=berlin pytest tests/cities/berlin/test_hook_applies_marker.py -v 2>&1 | tail -3`
Expected: `1 passed`.

- [ ] **Step 9: Commit**

```bash
git add v0.1/tests/cities/
git commit -m "$(cat <<'EOF'
test(scaffold): tests/cities/{berlin,hamburg}/ with marker-applying conftest

Each directory's conftest uses pytest_collection_modifyitems to auto-add
@pytest.mark.<city> to every item collected under it. Rejected: bare
`pytestmark = pytest.mark.<city>` in conftest.py — pytest silently
ignores that pattern (conftest is not a test module, so module-level
marks don't propagate). Guard tests in each directory catch a broken
hook before it makes `pytest -m <city>` a no-op.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task B2: Physically move 8 Hamburg tests into `tests/cities/hamburg/`

**Files:**
- `git mv` each: `test_hamburg_config.py`, `test_hamburg_lens_composers.py`, `test_sozialmonitoring.py`, `test_sozialmonitoring_legend.py`, `test_oaf_geocoder.py`, `test_oaf_geocoder_remap.py`, `test_ferry_lookup.py`, `test_hospital_info_int_coerce.py` — from `v0.1/tests/unit/` to `v0.1/tests/cities/hamburg/`.
- Modify: remove the `pytestmark = pytest.mark.hamburg` line from each moved file (the conftest hook covers them now).

**Interfaces:**
- Consumes: conftest hook from Task B1.
- Produces: cleaner test-tree grouping; `pytest -m hamburg --collect-only -q` count parity with PR-A.

- [ ] **Step 1: Capture pre-move hamburg-collect count**

Run: `cd v0.1 && pytest -m hamburg --collect-only -q 2>/dev/null | tail -1`
Expected: `<N> tests collected` where N is the Task A2 count + 1 (the guard test from Task B1). Record `<N>`.

- [ ] **Step 2: `git mv` each file**

```bash
cd v0.1
for f in test_hamburg_config.py test_hamburg_lens_composers.py test_sozialmonitoring.py test_sozialmonitoring_legend.py test_oaf_geocoder.py test_oaf_geocoder_remap.py test_ferry_lookup.py test_hospital_info_int_coerce.py; do
    git mv "tests/unit/$f" "tests/cities/hamburg/$f"
done
```

- [ ] **Step 3: Remove now-redundant `pytestmark` from each moved file**

For each of the 8 files under `v0.1/tests/cities/hamburg/`, delete the line `pytestmark = pytest.mark.hamburg`. If the block was:
```python
import pytest

pytestmark = pytest.mark.hamburg
```
And `pytest` was ONLY imported to support `pytestmark`, also delete the `import pytest` line. Otherwise leave the import.

Quick check per file: `grep -l "^pytestmark = pytest.mark.hamburg" v0.1/tests/cities/hamburg/*.py` — expect empty after all 8 are cleaned.

- [ ] **Step 4: Verify collect count parity**

Run: `cd v0.1 && pytest -m hamburg --collect-only -q 2>/dev/null | tail -1`
Expected: same `<N> tests collected` as Step 1. A drop = conftest hook missed a file (unlikely) OR one file was left with `pytestmark` AND deletion of the decorator changed collection (impossible; the conftest hook re-marks it). A jump = accidental duplicate file — check `find tests -name test_hamburg_config.py`.

- [ ] **Step 5: Verify tests still pass under the new location**

Run: `cd v0.1 && CITY=hamburg pytest -m hamburg -q 2>&1 | tail -5`
Expected: `<N> passed`.

- [ ] **Step 6: Verify no test collides in the unified suite**

Run: `cd v0.1 && CITY=berlin pytest -q 2>&1 | tail -3`
Expected: full suite passes. (Uses `CITY=berlin` because the shared tests + Berlin tests run; `pytest` selects everything by default. The Hamburg-marked tests still run and pass with `CITY=berlin` if they don't touch runtime `CITY`.)

- [ ] **Step 7: Commit**

```bash
git add v0.1/tests/
git commit -m "$(cat <<'EOF'
test: move 8 Hamburg-specific unit tests into tests/cities/hamburg/

Files physically relocated; the conftest hook there auto-applies
@pytest.mark.hamburg so module-level `pytestmark` lines added in PR-A
are removed. `pytest -m hamburg --collect-only` count parity verified
pre- and post-move.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task B3: Physically move 2 Berlin-adjacent tests into `tests/cities/berlin/`

**Files:**
- `git mv` each: `test_lookup_dispatch.py`, `test_parse_address.py` — from `v0.1/tests/unit/` to `v0.1/tests/cities/berlin/`.
- Modify: remove `pytestmark = pytest.mark.berlin` from both moved files.

**Interfaces:**
- Consumes: conftest hook from Task B1.
- Produces: cleaner test-tree grouping; symmetry with Task B2. `_FakeOSMLocal` fixture in `v0.1/tests/conftest.py` remains discoverable via pytest rootdir (`v0.1/`).

- [ ] **Step 1: Capture pre-move berlin-collect count**

Run: `cd v0.1 && pytest -m berlin --collect-only -q 2>/dev/null | tail -1`
Expected: `<M> tests collected` where M is Task A3 count + 1 (Berlin guard test from B1). Record `<M>`.

- [ ] **Step 2: `git mv` both files**

```bash
cd v0.1
git mv tests/unit/test_lookup_dispatch.py tests/cities/berlin/test_lookup_dispatch.py
git mv tests/unit/test_parse_address.py tests/cities/berlin/test_parse_address.py
```

- [ ] **Step 3: Remove `pytestmark` decorators**

For both moved files, delete the `pytestmark = pytest.mark.berlin` line. If `import pytest` is now unused, delete it too.

- [ ] **Step 4: Verify collect count parity**

Run: `cd v0.1 && pytest -m berlin --collect-only -q 2>/dev/null | tail -1`
Expected: same `<M> tests collected` as Step 1.

- [ ] **Step 5: Verify `_FakeOSMLocal` fixture still resolves after the move**

Run: `cd v0.1 && CITY=berlin pytest -m berlin -q 2>&1 | tail -5`
Expected: `<M> passed`. `test_lookup_dispatch.py` uses `_FakeOSMLocal` from `tests/conftest.py`; pytest's rootdir is `v0.1/`, so the root conftest is discovered for every collected item regardless of directory depth. If ImportError or fixture-not-found: check that `v0.1/tests/conftest.py` still contains `_FakeOSMLocal`.

- [ ] **Step 6: Full suite green check**

Run: `cd v0.1 && CITY=berlin pytest -q 2>&1 | tail -3`
Expected: full suite passes with no collection error, no fixture error.

- [ ] **Step 7: Commit**

```bash
git add v0.1/tests/
git commit -m "$(cat <<'EOF'
test: move 2 Berlin-adjacent tests into tests/cities/berlin/

Files physically relocated; conftest hook auto-applies
@pytest.mark.berlin so module-level `pytestmark` lines added in PR-A
are removed. `_FakeOSMLocal` fixture in v0.1/tests/conftest.py stays
discoverable because pytest rootdir is v0.1/.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task B4: Split `hamburg.py` into a subpackage (atomic commit)

**Files:**
- Create: `v0.1/app/cities/hamburg/__init__.py`
- Create: `v0.1/app/cities/hamburg/config.py`
- Create: `v0.1/app/cities/hamburg/directories.py`
- Create: `v0.1/app/cities/hamburg/lenses.py`
- Create: `v0.1/app/cities/hamburg/__main__.py`
- Delete: `v0.1/app/cities/hamburg.py`

All in the SAME commit. A two-commit sequence would leave a moment where both `hamburg.py` and `hamburg/` exist, which Python's import machinery handles inconsistently across versions.

**Interfaces:**
- Consumes: `app.cities.base` (unchanged — `CityConfig`, `LensConfig`, `LensTileConfig`, `OthersAdminCardConfig`).
- Produces: the public surface `HAMBURG`, `NEWCOMER_LENS`, `COMMUTER_LENS`, `OTHERS_ADMIN_CARDS` — all reachable via `from app.cities.hamburg import ...` (via `__init__.py` shim). Also preserves `python -m app.cities.hamburg` selfcheck (via `__main__.py`).

- [ ] **Step 1: Write the failing shim contract test**

Create `v0.1/tests/cities/hamburg/test_subpackage_public_surface.py`:

```python
"""Locks the public surface of the Hamburg subpackage. Every symbol
listed in `hamburg/__init__.py::__all__` must be importable via
`from app.cities.hamburg import <name>` and must be the object the
current call-site expects (spec §Public surface, grep 2026-09-22)."""

from app.cities.base import CityConfig, LensConfig, OthersAdminCardConfig


def test_HAMBURG_importable_as_CityConfig():
    from app.cities.hamburg import HAMBURG
    assert isinstance(HAMBURG, CityConfig)
    assert HAMBURG.slug == "hamburg"


def test_lenses_importable_and_correct_type():
    from app.cities.hamburg import NEWCOMER_LENS, COMMUTER_LENS
    assert isinstance(NEWCOMER_LENS, LensConfig)
    assert isinstance(COMMUTER_LENS, LensConfig)
    assert NEWCOMER_LENS.slug == "newcomer"
    assert COMMUTER_LENS.slug == "commuter"


def test_others_admin_cards_importable_and_correct_shape():
    from app.cities.hamburg import OTHERS_ADMIN_CARDS
    assert isinstance(OTHERS_ADMIN_CARDS, tuple)
    assert len(OTHERS_ADMIN_CARDS) == 5
    assert all(isinstance(c, OthersAdminCardConfig) for c in OTHERS_ADMIN_CARDS)


def test_package___all___pins_the_public_surface():
    """__all__ is the contract — narrowing it silently breaks call-sites.
    Do NOT relax this to a subset; extend it if we intentionally add a
    new public symbol."""
    from app.cities import hamburg as pkg
    assert set(pkg.__all__) >= {
        "HAMBURG", "NEWCOMER_LENS", "COMMUTER_LENS", "OTHERS_ADMIN_CARDS",
    }


def test_HAMBURG_identity_matches_config_module():
    """HAMBURG re-exported via __init__ MUST be the same object as the
    one built in hamburg.config — no accidental copy/reassignment."""
    from app.cities.hamburg import HAMBURG
    from app.cities.hamburg.config import HAMBURG as _config_HAMBURG
    assert HAMBURG is _config_HAMBURG
```

- [ ] **Step 2: Run the test — expect FAIL**

Run: `cd v0.1 && CITY=hamburg pytest tests/cities/hamburg/test_subpackage_public_surface.py -v 2>&1 | tail -10`
Expected: at least the `test_package___all___pins_the_public_surface` case fails (today's flat `hamburg.py` has no `__all__`). Others may pass because the flat file exports the same symbols. Either way, at least one fail — proves the test is exercising real behaviour.

- [ ] **Step 3: Read the current `hamburg.py` end-to-end**

Run: `cat v0.1/app/cities/hamburg.py`
Purpose: hold the whole file in context before splitting. The five files below MUST preserve every symbol currently defined; the split is a physical move, not a rewrite. Note the section boundaries — the file is already logically organised (WFS URLs, directories, glossary, attribution, lens configs, HAMBURG assembly, `__main__` asserts).

- [ ] **Step 4: Create `v0.1/app/cities/hamburg/lenses.py`**

Move the `NEWCOMER_LENS: LensConfig = LensConfig(...)` block and the `COMMUTER_LENS: LensConfig = LensConfig(...)` block from `hamburg.py`. The file's top should be:

```python
"""Hamburg lens configs — Newcomer + Commuter tile lists.

Extracted from the flat `hamburg.py` into a dedicated module so lens
changes touch only the lens file. The audience-hint prose, per-tile
threshold dicts, and caveat strings live here verbatim from the flat
file; only imports changed.
"""
from app.cities.base import LensConfig, LensTileConfig


NEWCOMER_LENS: LensConfig = LensConfig(
    slug="newcomer",
    label="Newcomer",
    audience_hint="First 90 days in Hamburg — HVV, ferry, Anmeldung, English-friendly services.",
    tiles=(
        # ...copy every LensTileConfig(...) entry from hamburg.py's NEWCOMER_LENS.tiles verbatim...
    ),
)

COMMUTER_LENS: LensConfig = LensConfig(
    slug="commuter",
    label="Commuter",
    audience_hint="For someone who needs a fast, reliable daily commute in Hamburg.",
    tiles=(
        # ...copy every LensTileConfig(...) entry from hamburg.py's COMMUTER_LENS.tiles verbatim...
    ),
)
```

Copy the tile lists EXACTLY from the current `hamburg.py`. Do not paraphrase; the LLM insight templates depend on the exact `slug`, `label`, `audience_hint`, threshold dicts, and caveat strings. Sanity check after the copy: `wc -l v0.1/app/cities/hamburg/lenses.py` should read ~200 LOC.

- [ ] **Step 5: Create `v0.1/app/cities/hamburg/directories.py`**

Move these curated tuples from `hamburg.py` into the new file, verbatim:
- `_BEZIRK_ID_TO_NAME`
- `_STANDESAMTS_BY_BEZIRK`
- `_REGIONAL_RAIL`
- `_HAMBURG_GLOSSARY`
- `_LEA_OFFICE`
- `_ARBEITSAGENTURS`
- `_INTL_SCHOOLS`
- `_KUNDENZENTREN`
- `_FINANZAMTS`
- `OTHERS_ADMIN_CARDS`

File header:
```python
"""Hamburg curated data directories — hand-verified addresses, office
tuples, glossary regexes, and OTHERS_ADMIN_CARDS registration.

Every entry here has a "ponytail" comment on its parent `hamburg.py`
about annual re-verification against the hamburg.de source. Keep that
maintenance discipline: an out-of-date Standesamt address ships to
production without a data-quality signal.
"""
import re

from app.cities.base import OthersAdminCardConfig
```

Then paste the tuples in the same order they appear in `hamburg.py`. Sanity check: `grep -c "^_[A-Z]" v0.1/app/cities/hamburg/directories.py` — expect at least 9 (matches the 9 module-level `_UPPERCASE` names above).

- [ ] **Step 6: Create `v0.1/app/cities/hamburg/config.py`**

Move the WFS URL constants block (`_WFS_*` names), the `_ATTRIBUTION` dict, and the `HAMBURG = CityConfig(...)` assembly from `hamburg.py`. File header:

```python
"""Hamburg CityConfig assembly.

Every URL + field name was verified against the landscape doc dated
2026-09-20; see `v0.1/docs/superpowers/specs/2026-09-20-hamburg-data-landscape.md`.
When re-adding a field or fixing a URL, cross-check the same section
in that doc so the config and the reference stay in sync.
"""
import os
import re
from pathlib import Path

from app.cities.base import CityConfig
from app.cities.hamburg.directories import (
    _BEZIRK_ID_TO_NAME,
    _STANDESAMTS_BY_BEZIRK,
    _REGIONAL_RAIL,
    _HAMBURG_GLOSSARY,
    _LEA_OFFICE,
    _ARBEITSAGENTURS,
    _INTL_SCHOOLS,
    _KUNDENZENTREN,
    _FINANZAMTS,
    OTHERS_ADMIN_CARDS,
)
from app.cities.hamburg.lenses import NEWCOMER_LENS, COMMUTER_LENS
```

Then paste the WFS URLs, attribution dict, and `HAMBURG = CityConfig(...)` in the same order they appear in `hamburg.py`. Do NOT change any field name, field map key, or URL string — this is a physical move. Sanity check after the paste: `python -c "from app.cities.hamburg.config import HAMBURG; print(HAMBURG.slug, len(HAMBURG.finanzamts))"` should print `hamburg 9`.

- [ ] **Step 7: Create `v0.1/app/cities/hamburg/__init__.py`**

Exactly the shim from spec §Public surface:

```python
"""Hamburg CityConfig subpackage. Re-exports the public symbols current
consumers import by name so `from app.cities.hamburg import ...` keeps
working with zero touch on routes/tests/inference templates. Adding a
new public symbol here means a call site is about to import it — pin
it in __all__ below so this file and the caller stay in sync."""
from app.cities.hamburg.config      import HAMBURG
from app.cities.hamburg.lenses      import NEWCOMER_LENS, COMMUTER_LENS
from app.cities.hamburg.directories import OTHERS_ADMIN_CARDS

__all__ = ["HAMBURG", "NEWCOMER_LENS", "COMMUTER_LENS", "OTHERS_ADMIN_CARDS"]
```

- [ ] **Step 8: Create `v0.1/app/cities/hamburg/__main__.py`**

Move the entire `if __name__ == "__main__":` block from `hamburg.py` verbatim into `__main__.py`, remove the `if __name__ == "__main__":` guard (running via `python -m app.cities.hamburg` invokes this file with `__name__ == "__main__"` automatically), and ADD the `__all__` regression guard at the end:

```python
"""Selfcheck asserts for the Hamburg CityConfig subpackage.

Invoked by `python -m app.cities.hamburg` — matches the pre-split
invocation shape byte-for-byte so CI (selfchecks matrix) and dev
workflow keep working without an edit.

Asserts every invariant the old hamburg.py `__main__` block had, plus
an extra guard that the __init__ shim's __all__ hasn't been narrowed."""
from app.cities.hamburg          import HAMBURG, NEWCOMER_LENS, COMMUTER_LENS, OTHERS_ADMIN_CARDS
from app.cities                  import hamburg as _pkg

# ... paste the assert block from hamburg.py's __main__ verbatim here,
#     dropping the enclosing `if __name__ == "__main__":` guard and the
#     4-space indent ...

# Regression guard: the __init__ shim's __all__ must not be narrowed
# below the four symbols current call-sites import by name (grep at
# 2026-09-22: HAMBURG, NEWCOMER_LENS, COMMUTER_LENS, OTHERS_ADMIN_CARDS).
assert set(_pkg.__all__) >= {"HAMBURG", "NEWCOMER_LENS", "COMMUTER_LENS", "OTHERS_ADMIN_CARDS"}, \
    f"__init__.py __all__ narrowed to {sorted(_pkg.__all__)} — restore missing symbols before merge"

print("selfcheck ok: Hamburg Newcomer + Commuter lenses wired")
```

Copy-paste is non-negotiable here — the asserts encode ~30 invariants (curated tuple counts, lens tile-key ordering, attribution keys wired) that the flat file's `__main__` already validated. Do NOT re-write them from memory.

- [ ] **Step 9: Delete the flat file**

```bash
git rm v0.1/app/cities/hamburg.py
```

- [ ] **Step 10: Run the shim contract test from Step 1 — expect PASS**

Run: `cd v0.1 && CITY=hamburg pytest tests/cities/hamburg/test_subpackage_public_surface.py -v 2>&1 | tail -10`
Expected: 5 passed. Any failure = the shim doesn't expose the symbol, OR `HAMBURG` isn't identity-equal across the two import paths (usually means the flat file wasn't deleted).

- [ ] **Step 11: Run the moved `__main__` block**

Run: `cd v0.1 && python -m app.cities.hamburg 2>&1 | tail -3`
Expected: `selfcheck ok: Hamburg Newcomer + Commuter lenses wired`. Any assert failure = one of the invariants from the old `__main__` didn't survive the copy — grep the failed line in `hamburg.py` (git history) and confirm the assert is byte-identical in `__main__.py`.

- [ ] **Step 12: Run the whole Hamburg test slice**

Run: `cd v0.1 && CITY=hamburg pytest -m hamburg -v 2>&1 | tail -15`
Expected: all Hamburg tests pass. If `test_hamburg_config.py` fails on `from app.cities.hamburg import HAMBURG, NEWCOMER_LENS, COMMUTER_LENS`, the `__init__.py` shim is incomplete.

- [ ] **Step 13: Verify cities-isolation selfcheck**

Run: `cd v0.1 && CITY=hamburg python -m app.selfcheck 2>&1 | grep -E "cities-isolation|ERROR|FAIL" | head -5`
Expected: no `ERROR` or `FAIL` lines. `app.selfcheck`'s cities-isolation block enumerates `app.cities` subpackages via `pkgutil.iter_modules` and `getattr(mod, slug.upper())`; the subpackage must expose `HAMBURG` on the package object (via the shim). If `AttributeError`, the shim is misnamed.

- [ ] **Step 14: Verify Berlin still boots (proves untouched)**

Run: `cd v0.1 && python -m app.cities.berlin 2>&1 | tail -3`
Expected: `selfcheck ok: NEWCOMER_LENS + OTHERS_ADMIN_CARDS wired` (or whatever Berlin's current `__main__` prints). Any change = Berlin was accidentally touched.

- [ ] **Step 15: Boot both apps locally**

Two terminals, one per city (kill them after verification):

```bash
# Terminal 1 — Berlin
cd v0.1 && CITY=berlin uvicorn app.main:app --port 8001 --log-level warning &
BERLIN_PID=$!
sleep 30 && curl -sSf http://127.0.0.1:8001/ready
kill $BERLIN_PID

# Terminal 2 — Hamburg
cd v0.1 && CITY=hamburg HVV_STATIONS_PATH=$(pwd)/app/cities/data/vbb_hamburg_su.csv HVV_FERRY_PATH=$(pwd)/app/cities/data/hvv_hamburg_ferry.csv OSM_LOCAL_PATH="" ADDRESS_LOCAL_PATH="" uvicorn app.main:app --port 8002 --log-level warning &
HH_PID=$!
sleep 45 && curl -sSf http://127.0.0.1:8002/ready
curl -sSf 'http://127.0.0.1:8002/api/lookup?address=Heidenkampsweg%2040%2C%2020097' | python -c "import json, sys; d = json.load(sys.stdin); print('address ok:', bool(d.get('address'))); print('nearest_school ok:', bool(d.get('nearest_school') or d.get('schools')))"
kill $HH_PID
```
Expected: both `/ready` return ready; the `/api/lookup` prints `address ok: True` and `nearest_school ok: True`.

- [ ] **Step 16: Commit (atomic — split + delete in one)**

```bash
git add v0.1/app/cities/hamburg/ v0.1/tests/cities/hamburg/test_subpackage_public_surface.py
git commit -m "$(cat <<'EOF'
refactor(cities): split app/cities/hamburg.py into a subpackage

Splits the 666-LOC flat file into five focused modules:
  hamburg/__init__.py       shim re-exporting the public surface
  hamburg/config.py         CityConfig assembly + WFS URLs + attribution
  hamburg/directories.py    curated tuples (Standesamt, Kundenzentrum,
                             Finanzamt, LEA, Arbeitsagentur, intl schools,
                             regional rail, glossary) + OTHERS_ADMIN_CARDS
  hamburg/lenses.py         Newcomer + Commuter LensConfig assemblies
  hamburg/__main__.py       selfcheck asserts (preserves `python -m ...`)

The __init__.py shim re-exports HAMBURG, NEWCOMER_LENS, COMMUTER_LENS,
OTHERS_ADMIN_CARDS — every symbol the 4 known call-sites import by name
(tests + inference templates). __main__.py adds an __all__ regression
guard that fails the selfcheck matrix if the shim's public surface is
ever narrowed.

Consumers unchanged: every `from app.cities.hamburg import ...` still
resolves. `python -m app.cities.hamburg` still runs selfchecks. Berlin
untouched.

Implements PR-B of the design at
docs/superpowers/specs/2026-09-22-hamburg-config-subpackage-design.md.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task B5: Extend `update.sh` with per-city `/api/lookup` smoke curl

**Files:**
- Modify: `v0.1/ops/deploy/update.sh` (insert smoke block inside the readiness `for svc_port in ...` loop, in the `READY="1"` branch before `break`).

**Interfaces:**
- Consumes: containers boot successfully and pass the existing `/ready` gate.
- Produces: a runtime-shape check that runs at deploy time, per city, against canonical addresses. Exits non-zero on non-200 or missing keys → operator runs `rollback.sh`.

- [ ] **Step 1: Confirm the current readiness loop shape**

Run: `sed -n '54,80p' v0.1/ops/deploy/update.sh`
Expected: the `for svc_port in "app:8001" "app-hh:8002"` loop with the inner `for i in $(seq 1 30)` retry loop and the `if [ -z "$READY" ]; then exit 1` branch.

- [ ] **Step 2: Add the smoke block inside the loop**

Edit `v0.1/ops/deploy/update.sh`. Find the line inside the retry loop:
```bash
            READY="1"
            echo "[deploy] $svc ready after ~$((i*3))s"
            break
```
Replace with:
```bash
            READY="1"
            echo "[deploy] $svc ready after ~$((i*3))s"
            # Post-ready smoke: one canonical address per city, assert 200 +
            # expected keys. Runs INSIDE the readiness loop so $svc and $port
            # are in scope (both are for-loop-locals derived from $svc_port).
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
            break
```
Bash double-quotes around the `-c` argument are required so `${port}` and `$ADDR` interpolate before Python sees them — do NOT switch to single quotes.

- [ ] **Step 3: Bash syntax check**

Run: `bash -n v0.1/ops/deploy/update.sh && echo OK`
Expected: `OK`. Any syntax error prints to stderr.

- [ ] **Step 4: Local dry-run against your development containers**

Boot both containers locally (or use the ones from Task B4 Step 15 if still running):

```bash
cd v0.1
# Assumes docker compose is up locally with app + app-hh services.
docker compose exec -T app python -c "
import json, urllib.request, urllib.parse, sys
q = urllib.parse.urlencode({'address': 'Kastanienallee 12, 10435'})
r = urllib.request.urlopen(f'http://127.0.0.1:8001/api/lookup?{q}', timeout=15)
d = json.load(r); print('berlin ok' if d.get('address') and (d.get('schools') or d.get('nearest_school')) else 'berlin FAIL', file=sys.stderr)
"
docker compose exec -T app-hh python -c "
import json, urllib.request, urllib.parse, sys
q = urllib.parse.urlencode({'address': 'Heidenkampsweg 40, 20097'})
r = urllib.request.urlopen(f'http://127.0.0.1:8002/api/lookup?{q}', timeout=15)
d = json.load(r); print('hamburg ok' if d.get('address') and (d.get('schools') or d.get('nearest_school')) else 'hamburg FAIL', file=sys.stderr)
"
```
Expected: `berlin ok` + `hamburg ok`. If either FAILs, the smoke would fail at deploy — investigate BEFORE merging.

If no local docker compose is available, skip this step and rely on the deploy-time invocation to prove the block works. Note the skip in the PR body.

- [ ] **Step 5: Commit**

```bash
git add v0.1/ops/deploy/update.sh
git commit -m "$(cat <<'EOF'
ops(deploy): update.sh smoke-tests /api/lookup per city after /ready

Adds a per-city /api/lookup curl inside the existing readiness loop,
in the READY=1 branch before `break`. Placement pins $svc + $port in
scope (both are for-loop-locals). Uses one canonical address per city
(Kastanienallee 12 for Berlin, Heidenkampsweg 40 for Hamburg); asserts
200 + presence of `address` and either `schools` or `nearest_school`.
Non-zero exit triggers the same rollback-hint message as the existing
readiness-timeout branch.

Runs at deploy time only — CI stays offline (external open-data
portals blip). Rationale + failure-mode matrix in spec §CI shape and
§Failure-mode matrix.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task B6: Push PR-B, wait for CI green, merge, deploy

**Files:** none (git + deploy operations).

**Interfaces:**
- Consumes: all commits from Tasks B1-B5.
- Produces: shipped subpackage in prod with runtime smoke on every future deploy.

- [ ] **Step 1: Push the branch**

```bash
cd /Users/sapta/Documents/personal/myStage/claude-personal/berlin-address-intelligence
git push -u origin refactor/hamburg-config-subpackage
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --title "refactor(cities): split hamburg.py into a subpackage + deploy smoke" --body "$(cat <<'EOF'
## Summary
Splits \`v0.1/app/cities/hamburg.py\` (666 LOC flat file) into a focused subpackage of five modules. Every existing \`from app.cities.hamburg import ...\` keeps working via the \`__init__.py\` shim; \`python -m app.cities.hamburg\` still runs selfcheck asserts. Berlin untouched.

Also extends \`ops/deploy/update.sh\` to smoke-test \`/api/lookup\` per city after \`/ready\` passes; rolls back on non-200 or missing keys.

Implements PR-B of the design at \`docs/superpowers/specs/2026-09-22-hamburg-config-subpackage-design.md\`. Depends on PR-A (\`chore(ci): per-city pytest markers + Hamburg selfcheck + rollback.sh fix\`) being merged AND deployed to prod first.

## New files
- \`app/cities/hamburg/__init__.py\` — shim re-exporting HAMBURG, NEWCOMER_LENS, COMMUTER_LENS, OTHERS_ADMIN_CARDS + \`__all__\` regression guard
- \`app/cities/hamburg/config.py\` — CityConfig assembly + WFS URLs + attribution
- \`app/cities/hamburg/directories.py\` — curated tuples (Standesamt, Kundenzentrum, Finanzamt, LEA, Arbeitsagentur, intl schools, regional rail, glossary) + OTHERS_ADMIN_CARDS
- \`app/cities/hamburg/lenses.py\` — Newcomer + Commuter LensConfig assemblies
- \`app/cities/hamburg/__main__.py\` — selfcheck asserts + \`__all__\` regression guard (preserves \`python -m app.cities.hamburg\`)

## Deleted
- \`app/cities/hamburg.py\` — replaced by the subpackage above (same commit as subpackage creation to avoid Python import-resolution ambiguity).

## Test plan
- [x] Local: shim contract tests pass (\`test_subpackage_public_surface.py\`)
- [x] Local: \`python -m app.cities.hamburg\` prints selfcheck ok including new \`__all__\` guard
- [x] Local: \`CITY=hamburg python -m app.selfcheck\` runs cities-isolation without \`AttributeError\` on the subpackage
- [x] Local: Berlin still boots (\`python -m app.cities.berlin\`, \`CITY=berlin uvicorn ...\` /ready)
- [x] Local: \`pytest -m hamburg\` collect count matches PR-A baseline
- [x] Local: \`update.sh\` smoke curls succeed against local containers
- [ ] CI: three per-city pytest steps + selfchecks matrix (now including \`app.cities.hamburg\`) + full unit-test coverage
- [ ] Prod deploy: \`update.sh\` runs the new smoke inside the readiness loop, prints \`ok\` per city, no rollback needed

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Wait for CI**

Run: `gh pr checks --watch`
Expected: exit 0. If any check fails, do NOT merge — fix the underlying issue locally, push, re-await.

- [ ] **Step 4: Merge**

Run: `gh pr merge --merge --delete-branch`

- [ ] **Step 5: Sync local main + review the diff about to ship**

```bash
git checkout main && git pull
git log --oneline -5
git diff HEAD~1 HEAD --stat   # confirms the subpackage + update.sh diff is the merge
```

- [ ] **Step 6: Pre-deploy sanity on the Hetzner box**

```bash
ssh sapta@<box-ip>
cd /srv/addrlens/repo/v0.1
git fetch origin
git log --oneline HEAD..origin/main   # confirm the refactor commits are what we expect
docker compose exec app-hh python -c \
  "from app.cities.hamburg import HAMBURG, NEWCOMER_LENS, COMMUTER_LENS, OTHERS_ADMIN_CARDS; \
   print(HAMBURG.slug, len(HAMBURG.finanzamts), len(NEWCOMER_LENS.tiles))"
# Expect: "hamburg 9 13"
```
This runs against the CURRENT container (pre-deploy) with the OLD flat `hamburg.py` — it should still print `hamburg 9 13` because the old flat file also exposes those symbols. Failure here means the pre-refactor state is different from what the spec assumed; STOP and re-check.

- [ ] **Step 7: Deploy**

```bash
./ops/deploy/update.sh
```
Success signal:
- `[deploy] app ready after ~<N>s`
- `[deploy] app-hh ready after ~<M>s`
- Two `ok` lines from the new smoke (one per city)
- `[deploy] done. deployed <new-sha> on top of <prev-sha>`

- [ ] **Step 8: Post-deploy verification (external)**

Wait ~30s after `[deploy] done`, then:

```bash
curl -sSf 'https://addrlens.de/api/lookup?address=Kastanienallee%2012%2C%2010435' | jq -r '.address.street'
curl -sSf 'https://hamburg.addrlens.de/api/lookup?address=Heidenkampsweg%2040%2C%2020097' | jq -r '.address.street'
```
Expected: `Kastanienallee` and `Heidenkampsweg` respectively.

- [ ] **Step 9: If deploy fails at any step**

```bash
./ops/deploy/rollback.sh   # defaults to /srv/addrlens/last-deployed.sha
```
Recovery time ~5-10 min (rebuild). Both containers restart. Verify `/ready` on both public URLs; open a follow-up PR with the fix + a regression test that would have caught it.

---

## Self-Review

**Spec coverage:**
- Spec §Approach PR-A step 1 (markers) → Task A1 ✓
- Spec §Approach PR-A step 2-3 (decorate tests) → Task A2 + A3 ✓
- Spec §Approach PR-A step 4 (CI pytest split with `--cov-append`) → Task A4 ✓
- Spec §Approach PR-A step 5 (Hamburg in selfchecks matrix) → Task A5 ✓
- Spec §Approach PR-A step 6 (rollback.sh fix) → Task A6 ✓
- Spec §Deploy choreography PR-A (rehearsal) → Task A7 steps 6-8 ✓
- Spec §Approach PR-B step 1 (5 subpackage files) → Task B4 ✓ (public-surface table encoded in Step 7 shim + Step 1 contract test)
- Spec §Approach PR-B step 2 (atomic subpackage-create + flat-file-delete) → Task B4 Step 9 + 16 ✓
- Spec §Public surface (shim re-exports 4 symbols + `__all__` + regression guard) → Task B4 Steps 1, 7, 8 ✓
- Spec §Approach PR-B step 3 (test relocation with modifyitems conftest) → Task B1 + B2 + B3 ✓
- Spec §Approach PR-B step 4 (update.sh smoke inside readiness loop) → Task B5 ✓
- Spec §Deploy choreography PR-B (pre-flight docker compose exec sanity) → Task B6 Step 6 ✓
- Spec §Testing plan PR-B every bullet → Task B4 Steps 10-15 ✓ (`app.selfcheck`, both cities boot, `pytest -m hamburg` count parity, update.sh smoke inline)

**Placeholder scan:** None. Every code block is complete. Test citations reference real files. Every commit message body is a full paragraph.

**Type consistency:** `pytestmark = pytest.mark.hamburg` used identically in A2 + B1 conftest hook. `--cov-append` used in A4 steps 2/3 with matching semantics (fresh in step 1, append in steps 2/3, XML report in final). Public surface `{HAMBURG, NEWCOMER_LENS, COMMUTER_LENS, OTHERS_ADMIN_CARDS}` is the SAME set in Task B4 Step 1 test, Step 7 `__init__.py`, Step 8 `__main__.py` guard, and Task B6 Step 2 PR body.

**One thing worth calling out** to the executor: Task B4 is by far the largest task (~1 hour careful work). It's not further decomposed because splitting it into "create lenses.py first, then directories.py, then config.py" is not testable in isolation — the imports don't resolve until every file exists. Its Step 10 shim-contract test IS the TDD gate; Steps 11-15 are integration checks that catch what a unit test can't.
