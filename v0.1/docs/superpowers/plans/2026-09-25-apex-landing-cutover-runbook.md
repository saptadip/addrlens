# Apex Landing Cutover Runbook

**Prereq:** PR for `feat/apex-landing-migration` merged to `main`. `ops/deploy/update.sh` completed on prod (Hetzner box), all 3 app containers healthy per `docker compose ps`.

**Target duration:** 15 minutes wall-clock. **Downtime:** 0. **Rollback:** dashboard-only, 2-3 min.

## Phase overview

The full production deploy has 6 phases. This runbook is the definitive step-by-step for all of them.

| Phase | When | Duration | User-visible? |
|---|---|---|---|
| 0. Pre-merge review | Before merging PR to `main` | ~15 min | No |
| 1. Prep window | Any time post-merge; can be same day or later | ~10 min | No (containers dormant) |
| 2. Cutover window | Scheduled — see picking rules below | ~20 min | Yes (0 downtime) |
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

Get new code onto prod but leave it dormant. Fully reversible via `./ops/deploy/rollback.sh <PREV_SHA>`.

- [ ] SSH to Hetzner prod box.
- [ ] Pull main:
  ```bash
  cd /srv/addrlens
  git pull origin main
  ```
- [ ] Run deploy script:
  ```bash
  ./ops/deploy/update.sh
  ```
  Builds all 3 app images (app + app-hh + app-landing) + inference. Brings up all containers with the compose overlay. Runs smoke gate on all three (Berlin `/api/lookup` on smoke_address; Hamburg `/api/lookup`; Landing `/health` via compose exec with 90s retry budget).
- [ ] Verify:
  ```bash
  docker compose ps app app-hh app-landing
  # All 3: STATUS = "Up X (healthy)"
  docker compose logs app-landing --tail=20
  # uvicorn startup log; no tracebacks
  ```
- [ ] **State at end of Phase 1:** `app-landing` running + healthy inside docker network. NO Cloudflare hostname points at it yet. Users see zero change. Berlin still serves apex. This is the reversible checkpoint before Phase 2.

**Rollback from Phase 1:** if anything misbehaves, `./ops/deploy/rollback.sh <PREV_SHA>` reverts. Landing container disappears; users see no change.

## Phase 2 — Cutover window (~20 min, 0 downtime)

The 8-step CF Tunnel + Redirect Rule dance. **Session-safety tip:** pre-write the Step 6 Redirect Rule as *disabled* BEFORE you touch the apex tunnel in Step 4. Then Step 6 becomes a single toggle instead of form-filling. Halves the vulnerable window.

Have three tabs/windows open:
1. Cloudflare dashboard
2. Local terminal (for smoke curls)
3. This runbook file

## Pre-flight (5 min, on box)

- [ ] SSH to prod box, verify state:
  ```bash
  cd /srv/addrlens
  docker compose ps app app-hh app-landing
  # All 3 must show STATUS = "Up X (healthy)"
  ```
- [ ] Verify landing is reachable inside docker network:
  ```bash
  docker compose exec app-landing python -c \
    "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read())"
  # Expect: b'{"status":"ok"}'
  ```
- [ ] Verify Berlin app still healthy:
  ```bash
  docker compose exec app python -c \
    "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=3).read())"
  ```
- [ ] Verify Hamburg untouched:
  ```bash
  curl -fsS https://hamburg.addrlens.de/health
  ```

## Step 1: Umami websites (2 min, Umami dashboard)

- [ ] Log in to `https://umami.addrlens.de/`.
- [ ] Create website: name `AddrLens Landing`, domain `addrlens.de`. Copy the new website ID.
- [ ] Create website: name `AddrLens Hamburg`, domain `hamburg.addrlens.de`. Copy the new website ID. (Skip if already exists.)
- [ ] Existing website: rename to `AddrLens Berlin`, change domain to `berlin.addrlens.de`. Copy its ID.

## Step 2: Prod env vars (2 min, SSH on box)

- [ ] Edit `/srv/addrlens/.env.production` (as root):
  ```bash
  sudo vim /srv/addrlens/.env.production
  ```
- [ ] Rename the existing `UMAMI_WEBSITE_ID=…` line to `UMAMI_WEBSITE_ID_BERLIN=…` (same value).
- [ ] Add `UMAMI_WEBSITE_ID_LANDING=<landing-id from Step 1>`.
- [ ] Add `UMAMI_WEBSITE_ID_HAMBURG=<hamburg-id from Step 1>` (if not already present).
- [ ] Save file.
- [ ] Restart the 3 app containers to pick up new env:
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --env-file /srv/addrlens/.env.production \
    up -d --force-recreate app app-hh app-landing
  ```
- [ ] Verify Umami injection worked for each host:
  ```bash
  HAMBURG_ID='<paste hamburg website-id from Step 1>'
  curl -fsS https://hamburg.addrlens.de/ | grep -c "data-website-id=\"$HAMBURG_ID\""
  # Expect: 1
  # (apex not yet flipped — landing will be verified after Step 4)
  ```

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

## Step 4: CF Tunnel — repoint apex to landing (2 min, CF dashboard)

- [ ] Same tunnel page → click the existing apex public hostname (`addrlens.de`) → Edit.
- [ ] Change **URL only** from `http://app:8001` to `http://app-landing:8000`. Host header stays `addrlens.de` (already correct).
- [ ] Save.
- [ ] Verify:
  ```bash
  curl -fsS https://addrlens.de/ | grep -c "AddrLens.*Street intelligence"    # expect >=1
  curl -fsS https://addrlens.de/health   # expect {"status":"ok"}
  curl -fsS https://berlin.addrlens.de/ | grep -c "canonical.*berlin.addrlens.de"  # expect 1
  ```

## Step 5: Purge CF edge cache (1 min, CF dashboard)

- [ ] Cloudflare → Caching → Configuration → Purge Cache → **Custom Purge by URL**.
- [ ] URLs to purge:
  - `https://addrlens.de/`
  - `https://addrlens.de`
  - `https://addrlens.de/impressum`
  - `https://addrlens.de/datenschutzerklaerung`
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
   and not starts_with(http.request.uri.path, "/static/fonts/")
   and not http.request.uri.path eq "/static/landing.css")
  ```
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

### If Step 4 (apex repoint) or Step 6 (Redirect Rule) is the problem

- [ ] CF dashboard → Tunnels → `addrlens-prod` → Public Hostnames → apex → Edit.
- [ ] Change URL back to `http://app:8001`, host header stays `addrlens.de`.
- [ ] Save. Effective in seconds.
- [ ] Delete or disable the Redirect Rule (Rules → Redirect Rules → toggle off).
- [ ] Keep `berlin.addrlens.de` public hostname registered (harmless overlap).

### If landing container is broken

- [ ] `docker compose ps app-landing` → confirm unhealthy.
- [ ] `docker compose logs app-landing --tail=100` → identify cause.
- [ ] If unrecoverable: rollback CF apex per above (users hit Berlin app on apex, works fine).

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

- [ ] `docker compose logs app-landing --tail=100 --follow` — look for tracebacks, unusual 4xx patterns.
- [ ] `docker compose logs cloudflared --tail=100 --follow` — look for tunnel disconnects.
- [ ] Manual sanity from another machine:
  ```bash
  curl -fsS https://addrlens.de/                                       # landing HTML
  curl -fsSI https://addrlens.de/api/lookup?address=foo | head -3      # HTTP/2 301 → berlin.addrlens.de
  curl -fsS https://berlin.addrlens.de/health                           # {"status":"ok"}
  curl -fsS https://hamburg.addrlens.de/health                          # {"status":"ok"}
  ```
- [ ] Umami dashboard: verify all 3 websites are receiving traffic within 5 min. **Landing especially** — if landing shows 0 pageviews at 15 min, injection failed (check `UMAMI_WEBSITE_ID_LANDING` in `.env.production` matches the ID Umami issued).

**If anything breaks in this hour:** trigger Rollback (above). The runbook rollback subsections cover all three failure modes (landing container, Berlin subdomain, Redirect Rule loop).

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

## The one rule for cutover day

**Never skip a runbook step because "it's obvious."** Every checkbox exists because someone thought about a specific failure mode. Skipping to "save time" is exactly how prod incidents happen.
