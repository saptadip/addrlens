# Onboarding a new city — recipe for AI agents

**Audience.** An AI coding agent (or a human engineer) asked to add a third city (Munich, Cologne, Frankfurt…) to this codebase. You are expected to end with the new city live in prod on `<slug>.addrlens.de`, following the exact conventions Berlin and Hamburg already use. No new patterns — this is a *copy the existing shape* exercise.

**Prereqs (read these first, in this order, before writing any code):**
1. `v0.1/app/cities/base.py` — the `CityConfig` dataclass. This is the target shape. ~145 fields; most are optional.
2. `v0.1/app/cities/hamburg/` and `v0.1/app/cities/berlin/` — the two canonical subpackage implementations. Study both. Their differences are informative: Hamburg has 2 lenses + no `_ATTRIBUTION` dict (inline attribution) is different — Berlin has 4 lenses + inline attribution. New cities inherit whichever pattern fits their data landscape better.
3. `v0.1/docs/superpowers/specs/2026-09-22-hamburg-config-subpackage-design.md` — the design that fixed the layout. Every convention on this page traces back to it.
4. `v0.1/docs/superpowers/plans/2026-09-22-berlin-config-subpackage.md` — the executable plan for the Berlin split. Task C2 (Steps 1-16) is the mechanical template you will follow, just against a fresh city.
5. `v0.1/docs/hetzner-deploy.md` — the imperative deploy procedure. § "Deploying Hamburg alongside Berlin" is the template for adding a per-city container.

**Scope: what "onboarding a city" means here.**
- New Python subpackage under `app/cities/<slug>/` with 5 files (see Phase 2).
- New Docker container `app-<slug>` sharing the app image with Berlin and Hamburg.
- New Cloudflare Tunnel subdomain `<slug>.addrlens.de`.
- New CI wiring: pytest marker `<slug>`, per-city pytest step, selfchecks-matrix entry.
- New `update.sh` case + `rollback.sh` service entry.
- Data-source discovery + curated tuples (Standesamt, Finanzamt, LEA, glossary, etc.).

**Explicit non-goals.**
- Do NOT introduce a new pattern. If it looks different from Berlin/Hamburg, stop and justify — the odds are you missed a convention.
- Do NOT touch `app/core/`, `app/routes/`, `app/deps.py`, the frontend, or any inference template unless the third city genuinely needs a new upstream data source type (a new WFS shape, a new loader). If in doubt, ship without that touch first and add it in a follow-up.
- Do NOT split the codebase into per-city repos. The monorepo + `CityConfig` injection + per-city Docker container is the sanctioned architecture. See spec §Non-goals.

---

## Phase 0 — Read-first, in the order above

Load the 5 files listed under Prereqs into your context window before touching anything else. Every convention below is a summary of what lives in those files; when this doc and the source files disagree, the source files win.

Run this checklist to confirm you're at the current tip of main:

```bash
cd /Users/sapta/Documents/personal/myStage/claude-personal/berlin-address-intelligence
git checkout main && git pull --ff-only
git log --oneline -10
# Expect: recent merges include #93 (Hamburg subpackage) and #94 (Berlin subpackage).
```

If either merge is missing, the codebase is on an older shape — stop and align with the user before proceeding.

---

## Phase 1 — Data landscape discovery

Every city's open-data footprint is different. Do this before touching code.

**Tooling:**
- ODIS GeoExplorer (semantic search across German open-data portals) + WFS-Explorer (test/preview). See project memory `reference_odis_tools.md` for URLs.
- The city's own geoportal (e.g. `gdi.berlin.de`, `geoportal-hamburg.de`, `opendata.muenchen.de`).
- The city's service portal (`service.berlin.de`, `service.hamburg.de`) for Bürgeramt / Standesamt equivalents.

**Output of this phase is a table**, saved as a design note before you start coding:

| Data source | Purpose in `CityConfig` | URL(s) | Format | License | Refresh cadence | Notes / caveats |
|---|---|---|---|---|---|---|
| Address geocoder | `geocoder_wfs_url` + `geocoder_field_map` | | WFS / OAF / Nominatim | | | Does the city expose a full-address WFS or must you fall back to Nominatim? |
| School catchments | `catchment_wfs_url`, `catchment_layer` | | | | | Some cities publish catchments per-Bezirk, not city-wide. |
| Schools (all types) | `schools_wfs_url`, `schools_field_map`, `schools_public_value` | | | | | The "public school" flag is city-specific — verify the exact string. |
| Bilingual / international schools | `bilingual_schools` dict + `schools_intl_keywords` | (curated) | | | | Hand-curated; not always in the WFS. |
| Kitas | `kita_wfs_url`, `kita_field_map` | | | | | Field names for capacity + operator type vary. |
| Hospitals | `hospital_wfs_url`, `hospital_layers`, `hospital_field_map` | | | | | Some cities split into general + specialty layers. |
| Fountains | `fountains_wfs_url` (optional) | | | | | Skip if the city doesn't publish. |
| Green (parks + playgrounds) | `green_wfs_url` + layer names | | | | | Often two layers on one endpoint. |
| Noise (Stratlaerm) | `noise_wfs_url` + `noise_field_map` + `noise_year` | | | | | EU 5-year cadence — verify current year. |
| Fire zones | `fire_wfs_url` (optional) + `fire_stations_layer` | | | | | Optional; only ~half of German cities publish. |
| Air quality (Klimabewertung) | `air_wfs_url` | | | | | Often static / rarely updated. |
| Heat islands | `heat_wfs_url` | | | | | Ditto. |
| Quiet zones (Ruhige Gebiete) | `quiet_wfs_url` | | | | | Optional. |
| Speed limits | `tempolimits_wfs_url` | | | | | Optional. |
| Arterial road network | `arterial_wfs_url` | | | | | Feeds commuter lens. |
| Pools + natural swim | `pools_wfs_url`, `swim_natural_wfs_url` | | | | | Optional. |
| Bezirk polygons | `bezirksgrenzen_wfs_url` | | | | | Needed for per-Bezirk lookups. |
| Buergeramt / Kundenzentrum | `_BUERGERAEMTER_URL` (loader URL) or curated tuple | | GeoJSON / curated | | | Berlin: REST GeoJSON via sentinel `_geojson` layer. Hamburg: curated `_KUNDENZENTREN` tuple. Choose the shape that matches the city. |
| Standesamts | `_STANDESAMTS_BY_BEZIRK` (curated dict) | (city website) | | | annual re-verification | Hand-curated. |
| Finanzamts | `_FINANZAMTS` (curated tuple) | | | | annual re-verification | |
| Arbeitsagenturs | `_ARBEITSAGENTURS` (curated tuple) | | | | annual re-verification | |
| LEA (Landesamt für Einwanderung) | `_LEA_OFFICE` (curated single) | | | | annual re-verification | |
| Regional rail stations | `_REGIONAL_RAIL` (curated tuple) — Hamburg-style | | | | | Only if the city has a regional rail backbone not covered by transit CSV. |
| Bilingual schools glossary | `_BERLIN_GLOSSARY`-style regex list | (curated) | | | | Used by the glossary loader. |
| Christmas markets | `xmas_market_url` (optional) | | GeoJSON | | annual | Empty most of the year. |
| Transit stations (S/U/tram/bus) | `stations_data_path` (CSV bind-mount) | (GTFS) | CSV | | monthly `refresh-*.timer` | Committed CSV + a systemd timer refreshes it. See `hetzner-deploy.md` for the volume mount + timer wiring. |
| Ferry stops | (city-specific) | | | | | Hamburg-only today. |
| Cycling network | (city-specific, Overpass fallback) | | | | | May come from OSM Overpass rather than WFS. |
| Car-sharing, EV charging | (Overpass) | | | | | Same as above. |
| Sozialmonitoring / equivalent | `sozialmonitoring_wfs_url` (Hamburg has, Berlin doesn't) | | | | | Skip if not published. |
| GESIX / equivalent socio-index | `gesix_wfs_url` (Berlin has, Hamburg doesn't) | | | | | Skip if not published. |

**Verify every URL you plan to use.** For each WFS URL:
```bash
curl -sSf "<url>?service=WFS&request=GetCapabilities" | head -40
```
Confirm the layer name in the response matches what you plan to put in `<layer>_layer` fields. WFS URLs that 404 or 500 must not ship — the boot-time selfcheck will fail readiness gate.

**Save the completed table** to `v0.1/docs/superpowers/specs/YYYY-MM-DD-<slug>-data-landscape.md` and commit it before writing any Python. This is the same pattern Hamburg used (`2026-09-20-hamburg-data-landscape.md`).

---

## Phase 2 — Scaffold the CityConfig subpackage

**Directory layout — copy exactly.** File names, imports, header docstring shapes all follow Hamburg + Berlin verbatim.

```
v0.1/app/cities/<slug>/
├── __init__.py       # shim re-exporting the public surface + __all__
├── config.py         # WFS URLs + attribution + `<SLUG> = CityConfig(...)`
├── directories.py    # curated tuples (Standesamt, Finanzamt, …) + OTHERS_ADMIN_CARDS
├── lenses.py         # LensConfig objects (Newcomer, Commuter, and any others)
└── __main__.py       # selfcheck asserts + __all__ regression guard
```

**Path convention (MANDATORY, easy to miss):** any `Path(__file__).resolve().parent / "data" / "<file>.csv"` in the FLAT-file era MUST become `Path(__file__).resolve().parent.parent / "data" / "<file>.csv"` inside `config.py`, because `config.py` sits one directory deeper. Both Hamburg PR #93 and Berlin PR #94 fixed this — verify with `grep -n "Path(__file__)" v0.1/app/cities/<slug>/config.py` after paste and confirm every reference uses `.parent.parent`.

**Public-surface convention.** Start with a broad `__all__`:
```python
__all__ = ["<SLUG>", "NEWCOMER_LENS", "COMMUTER_LENS", "OTHERS_ADMIN_CARDS"]
```
Add each `<LENS>_LENS` symbol only if that lens exists for this city. Berlin has 4 (`YOUNG_FAMILY_LENS`, `NEWCOMER_LENS`, `QUIET_LIVING_LENS`, `COMMUTER_LENS`), Hamburg has 2. Only add a lens if the city has enough tiles to warrant it (~10 tiles minimum). The `__all__` is the contract — narrowing it later breaks call sites silently.

**Copy discipline.** Every LensTileConfig entry, every threshold dict, every caveat string, every curated tuple — copy verbatim once written. Do NOT paraphrase, refactor "for clarity", or rename any string, key, or threshold value during moves. Rationale: LLM insight templates + `__main__` selfcheck asserts encode exact strings. Paraphrasing = broken insights + failed selfchecks. This is enforced by the shim contract test and the __main__ regression guard.

**File header template — `<slug>/config.py`:**
```python
"""<SLUG> CityConfig assembly.

Every URL + field name was verified against the <city> Geoportal at
data-source pull dated YYYY-MM-DD; see
`v0.1/docs/superpowers/specs/YYYY-MM-DD-<slug>-data-landscape.md`.
When re-adding a field or fixing a URL, cross-check the same section
in that doc so the config and the reference stay in sync.
"""
import os
import re                     # only if config.py actually uses re; drop if not
from pathlib import Path

from app.cities.base import CityConfig
from app.cities.<slug>.directories import (
    # ...list all curated names used in the CityConfig(...) assembly
)
from app.cities.<slug>.lenses import (
    # ...list all lenses used in the CityConfig(...) assembly
)
```

**File header template — `<slug>/directories.py`:**
```python
"""<SLUG> curated data directories — hand-verified addresses, office
tuples, glossary regexes, and OTHERS_ADMIN_CARDS registration.

Every entry here needs annual re-verification against its <city>.de
source — an out-of-date Standesamt address ships to production without
a data-quality signal. Keep that discipline: when re-verifying, cross
this file against the same landscape doc that guided the initial pull.
"""
import re

from app.cities.base import OthersAdminCardConfig
```

**File header template — `<slug>/lenses.py`:**
```python
"""<SLUG> lens configs.

Extracted into a dedicated module so lens changes touch only the lens
file. The audience-hint prose, per-tile threshold dicts, and caveat
strings live here verbatim. LLM insight templates depend on the exact
`slug`, `label`, `audience_hint`, threshold dicts, and caveat strings —
DO NOT paraphrase.
"""
from app.cities.base import LensConfig, LensTileConfig
```

**File — `<slug>/__init__.py`:**
```python
"""<SLUG> CityConfig subpackage. Re-exports the public symbols current
consumers import by name so `from app.cities.<slug> import ...` keeps
working with zero touch on routes/tests/inference templates. Adding a
new public symbol here means a call site is about to import it — pin
it in __all__ below so this file and the caller stay in sync."""
from app.cities.<slug>.config      import <SLUG>
from app.cities.<slug>.lenses      import NEWCOMER_LENS, COMMUTER_LENS      # + any other lenses
from app.cities.<slug>.directories import OTHERS_ADMIN_CARDS

__all__ = ["<SLUG>", "NEWCOMER_LENS", "COMMUTER_LENS", "OTHERS_ADMIN_CARDS"]  # + any other lenses
```

**File — `<slug>/__main__.py`:**
Use Hamburg's `__main__.py` as the template (it's the more thorough of the two — 60 lines with ~30 asserts). Copy the asserts, adapt the field-count numbers to your city, and keep the two invariants at the bottom:
```python
# Regression guard — do NOT remove
from app.cities import <slug> as _pkg
assert set(_pkg.__all__) >= {"<SLUG>", "NEWCOMER_LENS", "COMMUTER_LENS", "OTHERS_ADMIN_CARDS"}, \
    f"__init__.py __all__ narrowed to {sorted(_pkg.__all__)} — restore missing symbols before merge"

print("selfcheck ok: <SLUG> lenses wired")   # keep the "selfcheck ok" prefix — CI greps for it
```

**What to assert in `__main__.py`** (mirror Hamburg's structure — see `v0.1/app/cities/hamburg/__main__.py`):
1. `<SLUG>.slug == "<slug>"` + version-ish invariants (`wfs_output_format`, `geocoder`, model choices).
2. `bezirk_id_to_name[1] == "<expected>"` — proves the Bezirk dict wired correctly.
3. Length asserts for every curated tuple (`len(<SLUG>.standesamts_by_bezirk) == N`, `len(<SLUG>.finanzamts) == N`, etc.).
4. `is None` / `is not None` for optional data sources — encodes which sources this city ships.
5. Lens presence: `assert <SLUG>.newcomer_lens is not None; assert len(<SLUG>.newcomer_lens.tiles) == N`.
6. Identity asserts: `assert <SLUG>.newcomer_lens is NEWCOMER_LENS` (guards against duplicate LensConfig assembly bug).
7. Tile-key ordering asserts — the full `[t.key for t in <SLUG>.newcomer_lens.tiles] == [...]` list literal for every lens. This is the strictest gate you have — any accidental tile reorder or rename trips it.
8. `admin_keys = [c.key for c in <SLUG>.others_admin_cards]; assert admin_keys == [...]` — pins the Others tab card order.
9. `<SLUG>.smoke_address` truthy — required by `update.sh` per-city smoke.
10. Attribution: for every provenance-bearing dataset key, `assert k in <SLUG>.attribution`.

Rule of thumb: any invariant that would have caught a real regression in Hamburg or Berlin's history goes into `__main__.py`. This file runs on every CI selfchecks matrix build — cheap to over-invest.

---

## Phase 3 — Tests + CI wiring

**Register the pytest marker.** Edit `v0.1/pyproject.toml` `[tool.pytest.ini_options]` `markers` list — add one line:
```toml
"<slug>: tests exercising <SLUG> config/data (run with CITY=<slug>)",
```

**Scaffold `tests/cities/<slug>/`.** Copy the shape from `tests/cities/berlin/` or `tests/cities/hamburg/`:
```
v0.1/tests/cities/<slug>/
├── __init__.py                              # empty
├── conftest.py                              # pytest_collection_modifyitems auto-marker hook
├── test_hook_applies_marker.py              # 1-test smoke that the conftest hook fires
└── test_subpackage_public_surface.py        # shim contract test — see Phase 2's __all__ table
```

**`conftest.py` auto-marker template** (copy from `tests/cities/hamburg/conftest.py`, change one string):
```python
import pytest

def pytest_collection_modifyitems(config, items):
    """Every test under tests/cities/<slug>/ auto-picks up the
    @pytest.mark.<slug> marker so `pytest -m <slug>` selects it.
    Equivalent to putting `pytestmark = pytest.mark.<slug>` in every
    test module, but centralised so a new file dropped in this
    directory is marked without touching the file."""
    marker = pytest.mark.<slug>
    for item in items:
        if "tests/cities/<slug>/" in str(item.fspath):
            item.add_marker(marker)
```

**`test_subpackage_public_surface.py` template** — mirror `tests/cities/berlin/test_subpackage_public_surface.py`. Five tests:
1. `<SLUG>` importable as `CityConfig`.
2. Every lens importable as `LensConfig` with the correct `slug`.
3. `OTHERS_ADMIN_CARDS` importable + right shape.
4. `set(pkg.__all__) >= {expected 4-6 symbols}`.
5. `<SLUG> is <slug>.config.<SLUG>` identity check.

**CI wiring — three edits in `.github/workflows/`:**
1. Add a per-city pytest step (mirrors the `berlin` and `hamburg` steps in the same job):
   ```yaml
   - name: pytest — <SLUG>
     run: pytest -v -m <slug> --cov=app --cov-append --cov-report= 
     env:
       CITY: <slug>
   ```
   Chain `--cov-append` so combined coverage matches today's number.
2. Add `app.cities.<slug>` to the `selfchecks:` matrix `module:` list.
3. No other CI change needed — no new job hits external WFS.

**Verify locally before push:**
```bash
cd v0.1
pytest -m <slug> --collect-only -q   # confirms the marker registered + hook fires
pytest -m <slug> -v                  # actual test run — should be ~5 (shim contract + smoke)
python -m app.cities.<slug>          # runs __main__ — expect "selfcheck ok: <SLUG> …" line
CITY=<slug> python -m app.selfcheck  # runs cities-isolation block — no ERROR/FAIL
```

---

## Phase 4 — Container + Cloudflare Tunnel + deploy scripts

**Docker Compose.** Add a new service `app-<slug>` mirroring `app-hh`. Same image, same `Dockerfile.app`, port `8003` (or next free port), env `CITY=<slug>`, appropriate `<SLUG>_STATIONS_PATH` bind-mount if the city needs a transit CSV. See `hetzner-deploy.md` § "Deploying Hamburg alongside Berlin" for the exact block to copy.

**Cloudflare Tunnel.** Add a public hostname `<slug>.addrlens.de` → `http://app-<slug>:8003` in the tunnel config. See `docs/cloudflare-waf-setup.md` for the WAF rule pattern to duplicate for the new subdomain.

**`ops/deploy/update.sh` — add ONE `case` arm** in the readiness loop's per-city smoke dispatch:
```bash
for svc_port in "app:8001" "app-hh:8002" "app-<slug>:8003"; do   # add tuple
  ...
  case "$svc" in
    app)         ADDR=$(... from app.cities.berlin  import BERLIN;  print(BERLIN.smoke_address)) ;;
    app-hh)      ADDR=$(... from app.cities.hamburg import HAMBURG; print(HAMBURG.smoke_address)) ;;
    app-<slug>)  ADDR=$(... from app.cities.<slug>  import <SLUG>;  print(<SLUG>.smoke_address)) ;;   # add arm
  esac
```

**`ops/deploy/rollback.sh` — add to the rebuild list:**
```bash
docker compose build --pull app app-hh app-<slug> inference     # add app-<slug>
```
Same edit in `update.sh`'s `build` line. If you skip either, the new container silently stays on new-code during a rollback (this is the exact bug PR #92 fixed for `app-hh`).

**Bind-mounted data.** If the city needs a transit CSV or ferry CSV or similar, add it to `docker-compose.prod.yml` bind mounts + document the seed step in a new `docs/<slug>-rollout-checklist.md` (Hamburg's post-deploy checklist is the template).

---

## Phase 5 — First deploy

Follow `docs/hetzner-deploy.md` § "Deploying <city> alongside Berlin" — bump the CityConfig's `smoke_address` to a canonical address in that city BEFORE deploy (this is what `update.sh` smoke curls). Choose a known-good address that has both a `nearest_school` and returns a non-empty `.address.street` — usually a residential address near the city centre.

**Deploy:**
```bash
ssh sapta@<box-ip>
cd /srv/addrlens/repo/v0.1
./ops/deploy/update.sh
# Success signal: [deploy] app ready, [deploy] app-hh ready, [deploy] app-<slug> ready,
#                 three `ok` lines from the per-city smoke, [deploy] done.
```

**External post-deploy verify (from your laptop, ~30s after "done"):**
```bash
curl -sSf 'https://<slug>.addrlens.de/api/lookup?address=<smoke-address-url-encoded>' | jq -r '.address.street'
# Expect: the street name from smoke_address.
```

**Rollback (if anything fails):**
```bash
./ops/deploy/rollback.sh    # defaults to /srv/addrlens/last-deployed.sha
```
`rollback.sh` rebuilds app + app-hh + app-<slug> + inference (assuming you added the arm above).

**Write a `docs/<slug>-rollout-checklist.md`.** Copy `docs/hamburg-rollout-checklist.md` verbatim, replace `hamburg` → `<slug>` and `app-hh` → `app-<slug>`, adjust the data-seed step for whatever this city's transit CSV situation is. This file is the on-call reference for the next person who has to redeploy or verify this city.

---

## Guardrails (violate at your peril)

1. **Atomic subpackage commit.** When you refactor an existing flat file, the split into 5 files + delete of the flat file MUST be ONE commit. Python's import machinery resolves `app.cities.<slug>` inconsistently across versions when both a flat module and a subpackage of the same name exist mid-history. Two-commit sequences have caused CI amber-until-second-commit before. See PR #93 and PR #94 for the pattern.
2. **Verbatim copy for lens tile lists, curated directories, and the `__main__` assert block.** LLM insight templates + selfcheck asserts encode exact strings/keys/thresholds. Do NOT paraphrase, refactor, rename, or "improve" during moves. Reviewers should not flag this as "duplication" — the plan mandates it. If a reviewer does flag it, adjudicate the finding as plan-mandated (parked, not fixed).
3. **`__all__` is a contract.** The `__init__.py` `__all__` list defines the public surface. `__main__.py` MUST include a regression guard `assert set(_pkg.__all__) >= {...}` so a future narrowing trips CI. Never remove a symbol from `__all__` without grepping the call sites that would break.
4. **`Path(__file__)` in `config.py` needs `.parent.parent`.** The subpackage sits one level deeper than the flat file did. Every stations CSV, ferry CSV, etc. path reference needs the bump. Verify with `grep -n "Path(__file__)" v0.1/app/cities/<slug>/config.py`.
5. **CI is offline-only.** No new CI job that hits external WFS (`api.hamburg.de`, `geodienste.hamburg.de`, `gdi.berlin.de`, and any new city's portal). Those portals blip too often to gate PRs on. Boot-time smoke happens at deploy time inside `update.sh`, gates the readiness cutover, and triggers rollback on failure. See spec §CI shape.
6. **Every commit message includes the co-author trailer** `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`. Yes, even if a human wrote the commit — the trailer identifies this project's provenance.
7. **When dispatching subagents to do the refactor** (see below), pin the working branch verbatim in every dispatch prompt. A missing branch-pin has caused an implementer to commit on `main` accidentally (PR-B post-mortem, memory `feedback_subagent_branch_pin.md`). Format:
   > **HARD CONSTRAINT — do not switch branches.** You are on `<branch-name>`. Verify via `git branch --show-current` before your first commit (must print `<branch-name>`). If it prints anything else, STOP with BLOCKED — do NOT `git checkout`, `git switch`, or otherwise change branch.
8. **Attribution claims live on THREE surfaces** (memory `feedback_attribution_three_surfaces.md`): `v0.1/app/frontend/index.html`, `datenschutzerklaerung.html`, `impressum.html`. When you add a new data source to a city, grep all three together before editing any AI/data/tile/privacy claim. Legal doc (`impressum.html`) wins on conflicts.
9. **Never introduce a new pattern.** If Berlin and Hamburg do X differently, pick the one whose data landscape matches your new city — do not invent option C. If both do the same thing, do the same thing. Deviation is a review-blocking finding.

---

## AI-agent execution recipe

**Workflow to hand a fresh AI agent** (this is the recipe that shipped Berlin PR #94 cleanly):

1. **Brainstorming (short design check).** Invoke `/superpowers:brainstorming` with:
   - Which existing city (Hamburg or Berlin) is the closer template + why.
   - The completed Phase 1 data-landscape table.
   - Any open design question (e.g. "does <city> have a regional-rail curated tuple, or does its GTFS cover it?").
   - Classify as **bounded** — this is a well-scoped copy of an existing pattern, not architectural. Approve or push back on the agent's design in chat, no separate spec file needed unless the data landscape is materially novel.

2. **Writing plans.** Invoke `/superpowers:writing-plans` with:
   - Path to the reference plan (`v0.1/docs/superpowers/plans/2026-09-22-berlin-config-subpackage.md` — Task C2 is the 16-step mechanical template).
   - The city-specific deltas (lens count, curated-tuple names, `__main__` assert counts, `smoke_address` value).
   - Instruction to save the plan to `v0.1/docs/superpowers/plans/YYYY-MM-DD-<slug>-config-subpackage.md`.
   - The plan should have 3 tasks: create branch → atomic subpackage commit (16 steps mirroring PR-C Task C2) → push/PR/merge/deploy.

3. **Execution.** Invoke `/superpowers:subagent-driven-development` with:
   - Path to the plan.
   - Working branch name (recommend `refactor/<slug>-config-subpackage` or `feat/<slug>-onboarding`).
   - **Every implementer dispatch MUST include the HARD CONSTRAINT branch-pin (verbatim) + a FINAL TOOL CALL REQUIREMENT line** telling the subagent to write its report file as the final tool call. Both from memory `feedback_subagent_branch_pin.md`.
   - Between-task review via `caveman:cavecrew-reviewer` — pre-adjudicate "verbatim copy is plan-mandated" so reviewers don't waste cycles flagging duplication.
   - The `sonnet` model is the right tier for the subpackage-split implementer (Berlin PR-C used it, first-try success). Save `opus` for the final whole-branch review only.

4. **Deploy.** Do this manually — SSH + `./ops/deploy/update.sh`. Do NOT hand SSH to a subagent. When the agent reports the code is merged, hand you a copy-paste block for the deploy, and pause. Verify the post-deploy curl returns the expected `.address.street`.

**Anti-patterns to reject in a subagent's dispatch:**
- Dispatch prompt containing pasted history from previous tasks (bloats context, adds no value).
- Dispatch prompt without the branch-pin.
- Dispatch prompt without the FINAL TOOL CALL REQUIREMENT.
- Implementer dispatched on `haiku` for the subpackage split (has failed to hold verbatim discipline in past runs — use `sonnet` minimum).
- Multiple implementer subagents in parallel on the same branch (git conflicts).

---

## Reference PRs + files (canonical examples)

- **PR #91** — Berlin scoring bugfix + compare table backfill. Not city-onboarding, but sets the pre-refactor baseline for what `berlin.py` looked like before it was split.
- **PR #92** — CI per-city safety net (PR-A). Introduced pytest markers `berlin` + `hamburg`, per-city pytest steps, selfcheck matrix additions, `rollback.sh` app-hh fix. Any new city needs the same pattern of edits.
- **PR #93** — Hamburg subpackage split (PR-B). The FIRST subpackage refactor. Introduced the 5-file layout, the shim `__all__`, the `__main__` regression guard, and the `update.sh` per-city smoke.
- **PR #94** — Berlin subpackage split (PR-C). The SECOND subpackage refactor, proving the pattern generalises. Followed PR #93's Task B4 as a mechanical template. Reference implementation for any future city onboarding.

**Key files to read in order:**
1. `v0.1/app/cities/base.py` — `CityConfig` shape (authoritative).
2. `v0.1/app/cities/hamburg/{__init__,config,directories,lenses,__main__}.py` — canonical example (2-lens city with `_ATTRIBUTION` inline in the `CityConfig(...)` call).
3. `v0.1/app/cities/berlin/{__init__,config,directories,lenses,__main__}.py` — canonical example (4-lens city, otherwise identical).
4. `v0.1/docs/superpowers/specs/2026-09-22-hamburg-config-subpackage-design.md` — the design that fixed the layout. §Berlin follow-up and §CI shape are the most cited sections.
5. `v0.1/docs/superpowers/plans/2026-09-22-berlin-config-subpackage.md` — the executable plan (Task C2 = the 16-step mechanical template).
6. `v0.1/docs/hetzner-deploy.md` — imperative deploy procedure, single-node Hetzner + Cloudflare Tunnels topology.
7. `v0.1/docs/hamburg-rollout-checklist.md` — post-deploy on-call reference template.
8. `v0.1/ops/deploy/update.sh` + `rollback.sh` — the deploy scripts you WILL edit to add a per-city arm.

---

## Appendix — quick-command cheat sheet

```bash
# ─── local verify after Phase 2 scaffold ─────────────────────────────
python -m app.cities.<slug>                       # __main__ selfcheck
CITY=<slug> python -m app.selfcheck               # cities-isolation
CITY=<slug> pytest -m <slug> -v                   # per-city test slice
python -m app.cities.berlin                       # Berlin untouched?
python -m app.cities.hamburg                      # Hamburg untouched?

# ─── boot the new city locally ───────────────────────────────────────
cd v0.1 && CITY=<slug> uvicorn app.main:app --port 8003 --log-level warning &
sleep 45 && curl -sSf http://127.0.0.1:8003/ready
curl -sSf 'http://127.0.0.1:8003/api/lookup?address=<smoke-address>' \
  | python -c "import json, sys; d = json.load(sys.stdin); print('address ok:', bool(d.get('address'))); print('nearest_school ok:', bool(d.get('nearest_school') or d.get('schools')))"

# ─── open the PR ─────────────────────────────────────────────────────
git push -u origin refactor/<slug>-config-subpackage
gh pr create --title "feat(cities): onboard <SLUG> as third city" --body "..."
gh pr checks --watch

# ─── ship ────────────────────────────────────────────────────────────
gh pr merge --merge --delete-branch
ssh sapta@<box-ip>
cd /srv/addrlens/repo/v0.1 && ./ops/deploy/update.sh
```
