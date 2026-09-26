# Apex Landing Cutover Runbook

**Prereq:** PR for `feat/apex-landing-migration` merged to `main`. `ops/deploy/update.sh` completed on prod (Hetzner box), all 3 app containers healthy per `dc ps`.

**Target duration:** 15 minutes wall-clock. **Downtime:** see Phase 2 Step 2 restart window below. **Rollback:** `rollback.sh` (no-arg) + optional dashboard undo; 2-3 min.

## Phase overview

The full production deploy has 6 phases. This runbook is the definitive step-by-step for all of them.

| Phase | When | Duration | User-visible? |
|---|---|---|---|
| 0. Pre-merge review | Before merging PR to `main` | ~15 min | No |
| 1. Prep window | Any time post-merge; can be same day or later | ~10 min | No (containers dormant) |
| 2. Cutover window | Scheduled — see picking rules below | ~20 min | Yes (see Step 2 restart window) |
| 3. First 60 min monitoring | Immediately after Phase 2 | 60 min | Watching only |
| 4. First 48h monitoring | Passive after hour 1 | 48h | Passive |
| 5. Weeks 1-4 stabilization | SEO reallocation window | 2-4 weeks | Traffic patterns settle |

**Picking the cutover window:** weekday morning (Tue-Thu), low-traffic hour. Avoid Friday afternoon, holiday weekends, anything you cannot fully attend for the next 48h. Rollback is 2-3 min but you need to be RESPONSIVE for the first hour to catch anything the smoke tests miss.

## Phase 0 — Pre-merge review (~15 min)

Do this BEFORE merging the PR to `main`. Fresh eyes on the diff catch things reviewers miss.

- [ ] Re-read the PR diff on GitHub (https://github.com/saptadip/addrlens/pull/104) with fresh eyes. Focus especially on:
  - **Landing legal pages** (`web/landing/impressum.html` + `datenschutzerklaerung.html`) — the copy is what a hypothetical German data-protection auditor will actually read.
  - **This runbook** — anything unclear now will be unclear at 3am next Wednesday. Fix wording before merge.
  - **CF Redirect Rule expression** (Step 6 below) — every path the app serves should either match the deny-list or 301 to berlin.
- [ ] Approve + merge PR to `main`. Squash or merge-commit per project convention.
- [ ] **Do NOT deploy immediately after merge.** Deploy is Phase 1 below — a separate, deliberate step.

## Phase 1 — Prep window (~10 min, no user impact)

Get new code onto prod but leave it dormant. Fully reversible via `./ops/deploy/rollback.sh` (no arg needed).

```bash
# On the prod box, once per session:
cd /srv/addrlens/repo/v0.1
alias dc='docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file /srv/addrlens/.env.production'

# Every `dc <cmd>` in the runbook below is shorthand for that full form.
# Every path in the runbook is relative to /srv/addrlens/repo/v0.1
# UNLESS prefixed with /srv/addrlens/ (deploy volume, holds .env.production + data).
```

- [ ] SSH to Hetzner prod box.
- [ ] Run deploy script (fetches + fast-forwards + rebuilds + smoke-tests all 3 app containers):
  ```bash
  cd /srv/addrlens/repo/v0.1
  ./ops/deploy/update.sh
  ```
- [ ] Verify:
  ```bash
  dc ps app app-hh app-landing
  # All 3: STATUS = "Up X (healthy)"
  dc logs app-landing --tail=20
  # uvicorn startup log; no tracebacks
  ```
- [ ] **State at end of Phase 1:** `app-landing` running + healthy inside docker network. NO Cloudflare hostname points at it yet. Users see zero change. Berlin still serves apex. This is the reversible checkpoint before Phase 2.

**Rollback from Phase 1:** if anything misbehaves, `./ops/deploy/rollback.sh` (reads `/srv/addrlens/last-deployed.sha` automatically) reverts. Landing container disappears; users see no change.

## Phase 2 — Cutover window (~20 min)

The 8-step CF Tunnel + Redirect Rule dance. **Session-safety tip:** pre-write the Step 6 Redirect Rule as *disabled* BEFORE you touch the apex tunnel in Step 4. Then Step 6 becomes a single toggle instead of form-filling. Halves the vulnerable window.

Have three tabs/windows open:
1. Cloudflare dashboard
2. Local terminal (for smoke curls)
3. This runbook file

## Pre-flight (5 min, on box)

```bash
# On the prod box, once per session:
cd /srv/addrlens/repo/v0.1
alias dc='docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file /srv/addrlens/.env.production'

# Every `dc <cmd>` in the runbook below is shorthand for that full form.
# Every path in the runbook is relative to /srv/addrlens/repo/v0.1
# UNLESS prefixed with /srv/addrlens/ (deploy volume, holds .env.production + data).
```

- [ ] SSH to prod box, verify state (all on-box checks use `dc exec`):
  ```bash
  dc ps app app-hh app-landing
  # All 3 must show STATUS = "Up X (healthy)"
  ```
- [ ] Verify containers haven't recently auto-restarted (which would suggest a crash loop):
  ```bash
  dc ps --format 'table {{.Name}}\t{{.Status}}\t{{.RunningFor}}' app app-hh app-landing
  ```
  Expected: RUNNING FOR = at least several minutes. If < 30s, check logs before proceeding:
  ```bash
  dc logs app-landing --tail=50
  ```
- [ ] Verify landing is reachable inside docker network:
  ```bash
  dc exec app-landing python -c \
    "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read())"
  # Expect: b'{"status":"ok"}'
  ```
- [ ] Verify Berlin app still healthy:
  ```bash
  dc exec app python -c \
    "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=3).read())"
  ```
- [ ] Verify Hamburg from any machine (full-stack sanity):
  ```bash
  curl -fsS https://hamburg.addrlens.de/health
  # Expect: {"status":"ok"}
  ```
- [ ] Sentry release-tracking uses `GIT_SHA` env — verify it matches the deployed commit:
  ```bash
  grep '^GIT_SHA=' /srv/addrlens/.env.production
  git -C /srv/addrlens/repo rev-parse HEAD
  ```
  Both should print the same SHA. If they diverge, run Phase 1's `update.sh` again — Sentry release-tracking will attribute incidents to the wrong commit.

## Step 1: Umami websites (2 min, Umami dashboard)

- [ ] Log in to `https://umami.addrlens.de/`.
- [ ] Create website: name `AddrLens Landing`, domain `addrlens.de`. Copy the new website ID.
- [ ] Create website: name `AddrLens Hamburg`, domain `hamburg.addrlens.de`. Copy the new website ID. (Skip if already exists.)
- [ ] Existing website: rename to `AddrLens Berlin`, change domain to `berlin.addrlens.de`. Copy its ID.

## Step 2: Prod env vars (2 min, SSH on box)

- [ ] SSH to prod box; check current Umami env state:
  ```bash
  grep -E '^UMAMI_WEBSITE_ID(_BERLIN|_HAMBURG|_LANDING)?=' /srv/addrlens/.env.production
  ```
  Expected output: one or more lines matching the pattern. Note which suffixed forms already exist.

- [ ] Edit `/srv/addrlens/.env.production` (as root, preserving perms):
  ```bash
  sudo -e /srv/addrlens/.env.production
  ```
  Apply based on Step 2's grep result:
  - If you see `UMAMI_WEBSITE_ID=<id>` (flat form): rename to `UMAMI_WEBSITE_ID_BERLIN=<same-id>`.
  - If you see `UMAMI_WEBSITE_ID_BERLIN=` already: leave it alone.
  - If NO `UMAMI_WEBSITE_ID_HAMBURG=` line exists: add `UMAMI_WEBSITE_ID_HAMBURG=<hamburg-id from Step 1>`.
  - Always ADD (never rename): `UMAMI_WEBSITE_ID_LANDING=<landing-id from Step 1>`.
  - Also verify: `grep '^GIT_SHA=' /srv/addrlens/.env.production` — expected: the SHA of the merge commit shipping this cutover. If wrong, Phase 1 `update.sh` didn't run cleanly.

- [ ] Verify env file post-edit:
  ```bash
  grep -E '^UMAMI_WEBSITE_ID' /srv/addrlens/.env.production
  ```
  Expected: exactly 3 lines — `_BERLIN`, `_HAMBURG`, `_LANDING` — each with a non-empty value.
  Expected NOT to see: bare `UMAMI_WEBSITE_ID=` (unsuffixed) — if present, Berlin will fall back to it, potentially serving Berlin's ID on all sites.

- [ ] Restart the 3 app containers to pick up new env. **Warning: `--force-recreate` restarts serially and each takes 15-45s to become healthy. Apex `addrlens.de/` returns 502 Bad Gateway during Berlin's restart window (before Step 4 flips apex to landing). This is the ONE downtime moment in the cutover. Schedule accordingly.**
  ```bash
  dc up -d --force-recreate app app-hh app-landing
  # Wait for all healthy:
  for i in 1 2 3 4 5 6; do
    dc ps app app-hh app-landing --format 'table {{.Name}}\t{{.Status}}'
    echo '---'
    sleep 10
  done
  ```
  Expected: within 60s, all 3 show `Up X (healthy)`.

- [ ] Verify Umami injection worked. From ANY machine (not just the box):
  ```bash
  BERLIN_ID='<paste UMAMI_WEBSITE_ID_BERLIN value>'
  HAMBURG_ID='<paste UMAMI_WEBSITE_ID_HAMBURG value>'
  # Apex still serves Berlin until Step 4, so this checks Berlin's Umami:
  curl -fsS https://addrlens.de/ | grep -q "data-website-id=\"$BERLIN_ID\"" && echo BERLIN_OK
  # Hamburg via its own subdomain (unchanged):
  curl -fsS https://hamburg.addrlens.de/ | grep -q "data-website-id=\"$HAMBURG_ID\"" && echo HAMBURG_OK
  # Landing verification comes after Step 4.
  ```
  Expected: `BERLIN_OK` and `HAMBURG_OK`. If either is missing, STOP — Umami env didn't take; fix before proceeding.

## Step 3: CF Tunnel — add berlin.addrlens.de (3 min, CF dashboard)

- [ ] Cloudflare dashboard → Zero Trust → Networks → Tunnels → `addrlens-prod` → Public Hostnames → **Add a public hostname**.
- [ ] Config:
  - Subdomain: `berlin`
  - Domain: `addrlens.de`
  - Path: (blank)
  - Service Type: HTTP
  - URL: `app:8001`
  - Additional Application Settings → HTTP Host Header: `berlin.addrlens.de`
- [ ] Save. CF auto-creates proxied CNAME.
- [ ] Verify from any machine:
  ```bash
  curl -fsS https://berlin.addrlens.de/health   # expect {"status":"ok"}
  curl -fsSI https://berlin.addrlens.de/ | head -3
  # Expect HTTP/2 200 + content-type: text/html
  ```
- [ ] **State check:** Berlin app now answers on BOTH `addrlens.de` AND `berlin.addrlens.de`. Overlap is intentional and safe.

> **⚠️ Vulnerable window:** between saving Step 4 and deploying Step 6, any traffic to legacy apex paths (`/api/lookup`, `/api/suggest`, `/api/config`, `/api/lens_insight`, `/ready`, `/search`, any `/static/*` not in the landing allow-list) returns **404 from app-landing** — landing has no such routes. Duration: ~30s if Step 6 rule was pre-written as disabled (recommended); ~2-3 min if you fill out the rule form fresh.
>
> **Compress this window:** BEFORE starting Step 4, do Step 6 up to (but not including) enabling the rule. Save it in "disabled" state. Then post-Step 4, Step 6 collapses to a single toggle.

## Step 4: CF Tunnel — repoint apex to landing (2 min, CF dashboard)

- [ ] Same tunnel page → click the existing apex public hostname (`addrlens.de`) → Edit.
- [ ] Change **URL only** from `http://app:8001` to `http://app-landing:8000`. Host header stays `addrlens.de` (already correct).
- [ ] Save.
- [ ] Verify:
  ```bash
  curl -fsS https://addrlens.de/ | grep -q '<title>AddrLens.*Street intelligence' && echo LANDING_OK
  # Expected: LANDING_OK
  curl -fsS https://addrlens.de/health   # expect {"status":"ok"}
  curl -fsS https://berlin.addrlens.de/ | grep -q "canonical.*berlin.addrlens.de" && echo BERLIN_CANONICAL_OK
  # Expected: BERLIN_CANONICAL_OK
  ```

## Step 5: Purge CF edge cache (1 min, CF dashboard)

- [ ] Cloudflare → Caching → Configuration → Purge Cache → **Custom Purge by URL**.
- [ ] URLs to purge:
  - `https://addrlens.de/`
  - `https://addrlens.de`
  - `https://addrlens.de/impressum`
  - `https://addrlens.de/datenschutzerklaerung`
  - `https://addrlens.de/static/landing.css`
  - `https://addrlens.de/static/lang-toggle.js`
  - `https://addrlens.de/static/img/logo.png`
  - `https://addrlens.de/static/img/og-image.jpg`
  - `https://addrlens.de/static/img/berlin-card.png`
  - `https://addrlens.de/static/img/hamburg-card.png`
- [ ] Purge.

## Step 6: Add CF Redirect Rule (3 min, CF dashboard)

- [ ] Cloudflare → your zone → Rules → Redirect Rules → **Create rule**.
- [ ] Name: `apex → berlin for legacy paths`
- [ ] Expression (paste verbatim from spec §12.2):
  ```
  (http.host eq "addrlens.de"
   and not http.request.uri.path in {"/" "/impressum" "/datenschutzerklaerung" "/robots.txt" "/sitemap.xml" "/health"}
   and not http.request.uri.path in {"/static/img/logo.png" "/static/img/og-image.jpg"
                                      "/static/img/berlin-card.png"
                                      "/static/img/hamburg-card.png"
                                      "/static/landing.css"
                                      "/static/lang-toggle.js"}
   and not starts_with(http.request.uri.path, "/static/fonts/"))
  ```
  Note: follow-up ticket filed to fix the duplicate `/static/landing.css` clause in spec §12.2.
- [ ] Action: **Dynamic redirect**
  - Expression: `concat("https://berlin.addrlens.de", http.request.uri.path)`
  - Status: `301`
  - Preserve query string: ✓
- [ ] Deploy rule.
- [ ] Smoke the redirect (from any machine):
  ```bash
  for path in /api/lookup /api/suggest /api/config /api/lens_insight /ready /static/app.js /static/img/hero/berlin.png; do
    printf '%-40s ' "$path"
    curl -sSI "https://addrlens.de${path}" | awk 'NR==1 || tolower($1) ~ /^location:/'
  done
  # Every line: HTTP/2 301 + location: https://berlin.addrlens.de<path>
  ```
- [ ] Smoke the deny-list (landing paths should NOT redirect):
  ```bash
  for path in / /impressum /datenschutzerklaerung /robots.txt /sitemap.xml /health /static/landing.css /static/img/logo.png; do
    printf '%-30s ' "$path"
    curl -sSI "https://addrlens.de${path}" | head -1
  done
  # Every line: HTTP/2 200 (or 304)
  ```

## Step 7: Google Search Console (5 min, GSC)

- [ ] GSC → Add property → `https://berlin.addrlens.de/` → DNS or HTML-tag verification.
- [ ] Once verified: property → Sitemaps → Add → `https://berlin.addrlens.de/sitemap.xml`.
- [ ] Existing apex property → Sitemaps → Add → `https://addrlens.de/sitemap.xml` (re-submit, now points at the new landing sitemap).
- [ ] **Do NOT use the Change of Address tool.** It requires the old property to fully 301-redirect to the new — not the case here (apex keeps landing + legal). 301s on other paths + separate properties do the job.

## Step 8: Announce (optional)

- [ ] Post to relevant channels: "We moved: Berlin now lives at `berlin.addrlens.de`. `addrlens.de` is now a city hub with Berlin + Hamburg links. Old links auto-redirect."

## Rollback

Trigger conditions: prod smoke fails after any step; user report of broken apex.

### Full deploy revert (Phase 1 failed, or Phase 2 not yet started)

If Phase 1's `update.sh` succeeded but you discover a bug BEFORE starting Phase 2 (or Phase 2's Step 2 broke the app containers), revert the whole deploy:

- [ ] On box:
  ```bash
  cd /srv/addrlens/repo/v0.1
  ./ops/deploy/rollback.sh
  # No arg needed — reads /srv/addrlens/last-deployed.sha (SHA before update.sh).
  # For a specific target SHA: ./ops/deploy/rollback.sh <sha>
  ```
- [ ] Verify all containers back on old SHA:
  ```bash
  dc ps app app-hh app-landing
  ```
  If app-landing service isn't declared in the target SHA's compose file, `rollback.sh` auto-detects and omits it (see rollback.sh:44).
- [ ] No CF dashboard change needed — the CF apex was never flipped in this scenario.

### If Step 4 (apex repoint) or Step 6 (Redirect Rule) is the problem

- [ ] CF dashboard → Tunnels → `addrlens-prod` → Public Hostnames → apex → Edit.
- [ ] Change URL back to `http://app:8001`, host header stays `addrlens.de`.
- [ ] Save. Effective in seconds.
- [ ] Delete or disable the Redirect Rule (Rules → Redirect Rules → toggle off).
- [ ] Keep `berlin.addrlens.de` public hostname registered (harmless overlap).

### If landing container is broken

**Pre-Step 4 (apex NOT yet flipped):**
Users still see Berlin on apex — no user-visible break. Run the Full deploy revert (above) to remove the broken landing image.

**Post-Step 4 (apex already flipped):**
Users see landing container errors. TWO actions required:
1. CF apex undo: dashboard → tunnel → apex hostname → change service back to `http://app:8001`. Effective in seconds. Users see Berlin on apex again.
2. Full deploy revert (above) to remove the broken landing image from prod.

Diagnose before deciding:
- [ ] `dc ps app-landing` → confirm unhealthy.
- [ ] `dc logs app-landing --tail=100` → identify cause.

### If Berlin subdomain broken but apex still fine

- [ ] Remove `berlin.addrlens.de` public hostname from CF Tunnel.
- [ ] Users continue to reach Berlin via apex (Step 4 hasn't been done, or Step 4 was reverted).

### Partial cutover — operator disappears mid-flip

If you completed Step 4 (apex repointed to app-landing) but not Step 6 (Redirect Rule created), users hitting legacy apex paths like `addrlens.de/api/lookup`, `addrlens.de/search`, `addrlens.de/ready` get **404 from app-landing** (which has no such routes). Duration: minutes-long window until someone completes the cutover or reverts.

**Preferred recovery — complete Step 6 immediately (~3 min):**
1. Log into Cloudflare dashboard.
2. Add the Redirect Rule per spec §12.2 (expression + destination).
3. Verify with the smoke curl loop from Step 6 in this runbook.

**Fallback recovery — revert Step 4 (~2 min):**
1. Cloudflare Tunnel → apex hostname → Edit.
2. Change service back to `app:8001`. Host header stays `addrlens.de`.
3. Save. Effective within seconds. Apex serves Berlin again; landing container idle but healthy.

**Session-safety tip for the next cutover:** pre-write the Redirect Rule as *disabled* before Step 4, then enable it at Step 6. Reduces the vulnerable window to a single dashboard toggle.

## Phase 3 — First 60 min monitoring

**Stay at your terminal.** What to watch:

- [ ] `dc logs app-landing --tail=100 --follow` — look for tracebacks, unusual 4xx patterns.
- [ ] `dc logs cloudflared --tail=100 --follow` — look for tunnel disconnects.
- [ ] Manual sanity from another machine:
  ```bash
  curl -fsS https://addrlens.de/                                       # landing HTML
  curl -fsSI https://addrlens.de/api/lookup?address=foo | head -3      # HTTP/2 301 → berlin.addrlens.de
  curl -fsS https://berlin.addrlens.de/health                           # {"status":"ok"}
  curl -fsS https://hamburg.addrlens.de/health                          # {"status":"ok"}
  ```
- [ ] Umami dashboard: verify all 3 websites are receiving traffic within 5 min. **Landing especially** — if landing shows 0 pageviews at 15 min, injection failed (check `UMAMI_WEBSITE_ID_LANDING` in `.env.production` matches the ID Umami issued).

**If anything breaks in this hour:** trigger Rollback (above). The runbook rollback subsections cover all failure modes (landing container pre/post-flip, Berlin subdomain, Redirect Rule loop).

## Phase 4 — First 48h monitoring (passive)

- [ ] Re-run Step 6 smoke every 12h — catches any dashboard-only rule drift.
- [ ] GSC Coverage → check for spike in 4xx on the old apex property.
- [ ] Umami — verify 3 separate websites are receiving traffic; landing gets any signal at all (proves injection worked).
- [ ] Watch for 2-4wk SEO stabilization: apex + berlin property authority split; ranks may dip 5-15% during transition.

## Phase 5 — Weeks 1-4 stabilization

- [ ] **Week 1:** watch GSC + Umami. Traffic patterns start stabilizing.
- [ ] **Week 2:** if any Umami dashboard is weird (e.g., landing showing 0 despite prod traffic), debug now while the change is fresh in your memory. Common causes: `UMAMI_WEBSITE_ID_LANDING` ID mismatch, ad-blocker suppression, CSP header conflict.
- [ ] **Week 4:** SEO settled. Landing = discovery surface for new users; berlin. + hamburg. = returning users + direct-link traffic. If landing bounce rate is unexpectedly high (>80%), the city cards' CTAs may need copy tweaks — file as a v2 spec.

## Follow-up tickets (file AFTER cutover succeeds)

None blocking cutover; all captured in PR body. File as separate issues:

- Landing-container-only CI job (`pytest tests/landing/` in isolation on every PR).
- Multi-stage `Dockerfile.landing` to recover the ~80 MB uv layer (saves push time, not runtime).
- Playwright cross-hostname visual-diff smoke.
- CI grep-check for fastapi/uvicorn version sync between `pyproject.toml` + `ops/Dockerfile.landing`.
- German article grammar copyedit in `web/landing/datenschutzerklaerung.html` DE preamble.
- `env_file` scalar vs list form consistency across compose services.
- Fix duplicate `/static/landing.css` clause in spec §12.2 Redirect Rule expression.

## The one rule for cutover day

**Never skip a runbook step because "it's obvious."** Every checkbox exists because someone thought about a specific failure mode. Skipping to "save time" is exactly how prod incidents happen.
