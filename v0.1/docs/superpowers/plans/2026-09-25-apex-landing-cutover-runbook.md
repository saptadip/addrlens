# Apex Landing Cutover Runbook

**Prereq:** PR for `feat/apex-landing-migration` merged to `main`. `ops/deploy/update.sh` completed on prod (Hetzner box), all 3 app containers healthy per `docker compose ps`.

**Target duration:** 15 minutes wall-clock. **Downtime:** 0. **Rollback:** dashboard-only, 2-3 min.

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
  curl -fsS https://hamburg.addrlens.de/ | grep -c 'data-website-id="<hamburg-id>"'
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
                                      "/static/landing.css"}
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

## Post-cutover monitoring (first 48h)

- [ ] Re-run Step 6 smoke every 12h — catches any dashboard-only rule drift.
- [ ] GSC Coverage → check for spike in 4xx on the old apex property.
- [ ] Umami — verify 3 separate websites are receiving traffic; landing gets any signal at all (proves injection worked).
- [ ] Watch for 2-4wk SEO stabilization: apex + berlin property authority split; ranks may dip 5-15% during transition.
