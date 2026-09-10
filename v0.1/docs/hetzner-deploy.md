# Hetzner deploy — step-by-step

Zero-to-live playbook for deploying addrlens to a fresh Hetzner box behind a Cloudflare Tunnel. Distilled from `ops/deploy/README.md` and hardened against issues surfaced during local Docker smoke testing.

## Pre-flight (do once, off-box)

- **Provision Hetzner CX22 or CPX21** (x86_64, at least 4 GB RAM, at least 40 GB disk). Choose the **Debian 13 (trixie)** image — `bootstrap.sh` targets Debian's Docker apt repo. Add your SSH public key during creation.
- **Attach a Primary IPv4 to the box.** Hetzner's newer plans only give you IPv6 out of the box; without a public v4 the machine gets a CGNAT `100.64.0.0/10` LAN address and has no route to the public internet (GitHub, Docker Hub, Hugging Face all fail to resolve or connect). Console → **Servers → your box → Networking → Add Primary IPv4** (~€0.60/month), or attach an unassigned Primary IPv4 from the **Primary IPs** tab. After attaching, `sudo reboot` the box so cloud-init picks up the new v4 lease.
- **Create a Cloudflare Zero-Trust Tunnel** in the CF dashboard. Copy the `TUNNEL_TOKEN`. Under the tunnel's *Public Hostname* config point `addrlens.de` at `http://app:8001`. The DNS record is created automatically by the tunnel.
  - **DNS conflict on apex:** if the domain was registered through Hetzner or has any existing A/AAAA at the apex (`addrlens.de` bare), Cloudflare will refuse to create its CNAME with *"A DNS record with this name already exists."* In the CF **DNS → Records** panel, delete the apex `A` and `AAAA` records (typically pointing at Hetzner's shared web hosting, e.g. `88.198.219.246`). Keep the MX / SRV / TXT / `autoconfig` CNAME rows — those are email routing and are unrelated. Then retry the tunnel Public Hostname add. Optionally repeat for `www` if you want both apex and `www` to route through the tunnel.
- **Set up a GitHub deploy key** for the box (before the first `git clone`, because password auth is disabled on github.com and the repo may be private).
  - On the box: `ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_addrlens -N ""` and `cat ~/.ssh/id_ed25519_addrlens.pub`.
  - On GitHub: `https://github.com/saptadip/addrlens/settings/keys` → **Add deploy key**. Title `hetzner-addrlens-prod`. Paste the public key. **Do not** enable write access.
  - On the box, add an SSH config entry so `git` picks the right key:
    ```bash
    cat >> ~/.ssh/config <<'EOF'
    Host github.com
      HostName github.com
      User git
      IdentityFile ~/.ssh/id_ed25519_addrlens
      IdentitiesOnly yes
    EOF
    chmod 600 ~/.ssh/config
    ssh -T git@github.com   # expect: "Hi saptadip/addrlens! You've successfully authenticated…"
    ```
- **Get Sentry DSNs** for the `addrlens-app` and `addrlens-inference` projects. Optional — Sentry initialization is env-guarded, so the DSN variables can be left unset to skip Sentry entirely.

## First deploy

- **SSH in and prepare the tree.** Clone via SSH (uses the deploy key set up above).
  ```bash
  ssh sapta@<box-ip>
  sudo mkdir -p /srv/addrlens && sudo chown sapta:sapta /srv/addrlens
  cd /srv/addrlens
  git clone git@github.com:saptadip/addrlens.git repo
  ```
- **Bootstrap the host.** Installs docker (from the Debian Docker apt repo), ufw rules, swap, and the systemd timer. Idempotent.
  ```bash
  cd /srv/addrlens/repo/v0.1
  sudo bash ops/deploy/bootstrap.sh
  ```
- **Log out and back in** so the `sapta` user picks up the newly-added `docker` group.
- **Fetch the GGUF model file** (about 940 MB, one time). Debian 13 ships without `pip` and blocks system-wide pip installs via PEP 668, so we skip the `hf` CLI and pull the file directly:
  ```bash
  mkdir -p /srv/addrlens/models
  curl -L -o /srv/addrlens/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf \
      "https://huggingface.co/bartowski/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf?download=true"
  ls -lh /srv/addrlens/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf
  ```
- **Create `/srv/addrlens/.env.production`** from the template. Required values: `TUNNEL_TOKEN`, `SENTRY_DSN_APP`, `SENTRY_DSN_INFERENCE`.
  ```bash
  cp /srv/addrlens/repo/v0.1/.env.production.example /srv/addrlens/.env.production
  chmod 600 /srv/addrlens/.env.production
  vim /srv/addrlens/.env.production
  ```
  Back the file up to your password manager. It is git-ignored and never leaves the box.
- **Build images cold** (roughly 10 minutes — llama-cpp-python compiles from source; `build-essential` is already installed in the inference image).
  ```bash
  cd /srv/addrlens/repo/v0.1
  docker compose -f docker-compose.yml -f docker-compose.prod.yml \
      --env-file /srv/addrlens/.env.production build
  ```
- **Seed the OSM snapshot before the first `up`** — the app reads this file at boot.
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.prod.yml \
      --env-file /srv/addrlens/.env.production \
      run --rm --entrypoint python app -m scripts.refresh_osm_amenities
  ls -lh /srv/addrlens/data/osm/berlin-amenities.json   # expect ~13 MB
  ```
- **Bring the stack up.**
  ```bash
  docker compose -f docker-compose.yml -f docker-compose.prod.yml \
      --env-file /srv/addrlens/.env.production up -d
  docker compose logs -f cloudflared   # look for "Registered tunnel connection"
  ```
- **Verify through Cloudflare.**
  ```bash
  curl -sSf https://addrlens.de/health   # {"status":"ok"}
  curl -sSf https://addrlens.de/ready    # {"status":"ready","city":"berlin"}
  curl -sSf 'https://addrlens.de/api/lookup?address=Bergmannstra%C3%9Fe+27,+10961' | jq '.lens|keys'
  ```

## Post-deploy

- **SSH hardening — done manually, once.** Automating this in a script risks locking yourself out.
  ```bash
  sudo vim /etc/ssh/sshd_config
  # PermitRootLogin no
  # PasswordAuthentication no
  # PubkeyAuthentication yes
  sudo systemctl reload sshd
  ```
  Keep the current session open. Open a NEW terminal window, confirm you can SSH in with the pubkey, and only then close the original session.
- **Verify the weekly OSM refresh timer.**
  ```bash
  systemctl list-timers refresh-osm-amenities.timer   # NEXT column should read Sunday 03:00
  ```

- **Turn Sentry on (optional but strongly recommended).** The Sentry init blocks in `app/main.py` and `inference/main.py` are env-guarded, so the containers ship with error tracking dormant. Wiring it live is a five-minute operator task once the site is up:
  1. **Sign up on the EU region** at `sentry.io`. During onboarding, pick the *EU data region* — this makes the account host `de.sentry.io` and keeps event storage in Frankfurt (matches the box, matches your GDPR posture).
  2. **Create two projects** with the Python-FastAPI SDK: `addrlens-app` and `addrlens-inference`.
  3. **Copy each DSN** into `/srv/addrlens/.env.production`:
     ```bash
     sudo vim /srv/addrlens/.env.production
     # SENTRY_DSN_APP=https://<key>@<something>.ingest.de.sentry.io/<project>
     # SENTRY_DSN_INFERENCE=https://<key>@<something>.ingest.de.sentry.io/<project>
     # SENTRY_ENV=production      (already present)
     ```
  4. **Recreate both containers** so the env change takes effect (`docker compose restart` does not — env is fixed at container-create time):
     ```bash
     cd /srv/addrlens/repo/v0.1
     docker compose -f docker-compose.yml -f docker-compose.prod.yml \
         --env-file /srv/addrlens/.env.production \
         up -d --force-recreate app inference
     ```
  5. **Verify events flow** by triggering a controlled error from the box:
     ```bash
     docker exec v01-app-1 python -c \
       "import sentry_sdk; sentry_sdk.capture_message('addrlens Sentry wiring check', level='info')"
     ```
     Refresh the `addrlens-app` project in the Sentry dashboard — the message should appear within ~5 seconds. Repeat with `v01-inference-1` for the inference project.
  6. `ops/deploy/update.sh` already stamps `GIT_SHA` into the env file on each deploy, so Sentry's *Releases* view will show the version each error was introduced in without any extra work.

  Notes on the GDPR scrubber baked into the init blocks:
  - `send_default_pii=False` — Sentry does not attach client IP or user session data.
  - A `before_send` callback redacts the `address`, `street`, `hnr`, `plz` query-string params on the app side, and the entire POST body on the inference side (since `/summarize` payloads embed the searched context). A stack trace attached to a lookup never carries the user's search string to Sentry's servers.

- **Wire up Umami analytics.** The `umami` and `umami-db` services in `docker-compose.prod.yml` self-host a cookieless, GDPR-clean tracker. The app's `/` handler only injects the tracker snippet once `UMAMI_WEBSITE_ID` and `UMAMI_SCRIPT_URL` are set — everything below is a one-time setup task.

  1. **Generate secrets and add them to `/srv/addrlens/.env.production`:**
     ```bash
     UMAMI_DB_PASSWORD=$(openssl rand -hex 24)
     UMAMI_APP_SECRET=$(openssl rand -hex 32)
     sudo bash -c "cat >> /srv/addrlens/.env.production <<EOF
     UMAMI_DB_PASSWORD=$UMAMI_DB_PASSWORD
     UMAMI_APP_SECRET=$UMAMI_APP_SECRET
     EOF"
     # UMAMI_WEBSITE_ID and UMAMI_SCRIPT_URL are filled after step 4 below.
     ```
     Back both secrets up in your password manager. The database password is what protects site-visit data.

  2. **Bring the Umami stack up:**
     ```bash
     cd /srv/addrlens/repo/v0.1
     docker compose -f docker-compose.yml -f docker-compose.prod.yml \
         --env-file /srv/addrlens/.env.production up -d umami-db umami
     docker compose ps umami-db umami   # both should reach "healthy" / "Up"
     ```
     The first boot takes ~30 s while Umami's Prisma runs the DB migrations.

  3. **Add the tunnel hostname.** In the Cloudflare Zero Trust dashboard for the `addrlens.de` tunnel, add a second **Public Hostname**:
     - Subdomain: `umami`
     - Domain: `addrlens.de`
     - Service: HTTP `umami:3000`

     Cloudflare creates the CNAME automatically. Verify with `dig +short umami.addrlens.de` — expect CF anycast IPs, same as the apex.

  4. **First login and website registration:**
     - Open `https://umami.addrlens.de/` in a browser.
     - Log in with default credentials: `admin` / `umami`.
     - Go to **Settings → Profile → Change password** IMMEDIATELY. Set something strong; store it in your password manager.
     - **Settings → Websites → Add website** — Name: `addrlens.de`, Domain: `addrlens.de`.
     - After saving, open the new website row → **Tracking code** tab. Note:
       - The `data-website-id` UUID (e.g. `a1b2c3d4-...`).
       - The `src` URL — always `https://umami.addrlens.de/script.js` on your setup.

  5. **Add the two remaining env vars and recreate the app to inject the tracker:**
     ```bash
     sudo bash -c 'cat >> /srv/addrlens/.env.production <<EOF
     UMAMI_WEBSITE_ID=<paste the UUID from step 4>
     UMAMI_SCRIPT_URL=https://umami.addrlens.de/script.js
     EOF'
     cd /srv/addrlens/repo/v0.1
     docker compose -f docker-compose.yml -f docker-compose.prod.yml \
         --env-file /srv/addrlens/.env.production up -d --force-recreate app
     ```

  6. **Verify from the outside:**
     ```bash
     curl -sS https://addrlens.de/ | grep -c 'data-website-id="'
     # Expect: 1 — the tracker snippet is now in the served HTML.
     ```
     Then load `https://addrlens.de/` in a real browser and refresh the Umami dashboard's *Realtime* view — you should appear as one active visitor within a couple of seconds.

  Notes:
  - The `umami-db` service bind-mounts to `/srv/addrlens/umami-db` so the analytics data survives container recreates. Include this path in any backup / snapshot strategy.
  - Umami is a Next.js app; memory footprint under a small site's traffic is ~100–200 MB. The 350 MB `mem_limit` in the compose file leaves headroom without competing with the inference container.
  - Nothing about Umami touches the app-side rate limits or Cloudflare WAF rules — the tracker script loads from `umami.addrlens.de`, not `addrlens.de/api/*`.

- **Two-Factor Auth for the Umami admin.** Umami v3.3.0+ supports TOTP (Google Authenticator / Authy / 1Password) with 10 single-use backup codes. Only another admin can reset a locked-out user — there is no CLI or env-var override. The steps below make lockout survivable.

  1. **Verify the running Umami is v3.3.0 or newer:**
     ```bash
     docker exec v01-umami-1 sh -c 'grep -m1 "\"version\"" /app/package.json'
     # Expect: "version": "3.3.x"
     ```
     If older, `docker compose pull umami && docker compose up -d --no-deps umami` first, then re-verify.

  2. **Generate the 2FA encryption key — and store it OFF-SERVER before pasting it anywhere on the box:**
     ```bash
     openssl rand -hex 32
     ```
     **Immediately copy the output into your password manager (1Password / Bitwarden vault, sealed field) AND onto a printed sealed copy stored in a physical safe.** This key encrypts every user's TOTP secret + backup codes at rest. If it is ever lost, every stored 2FA secret becomes unrecoverable ciphertext and every user must re-enrol from an admin reset. `umami-db` backups alone are NOT enough — the key must survive independently of the disk.

  3. **Add the key to `/srv/addrlens/.env.production`:**
     ```bash
     sudo bash -c 'echo "UMAMI_TWO_FACTOR_ENCRYPTION_KEY=<paste-the-hex-here>" >> /srv/addrlens/.env.production'
     sudo chmod 600 /srv/addrlens/.env.production   # confirm perms are still tight
     ```

  4. **Restart only the Umami service** (leave `umami-db` running — no DB churn needed):
     ```bash
     cd /srv/addrlens/repo/v0.1
     docker compose -f docker-compose.yml -f docker-compose.prod.yml \
         --env-file /srv/addrlens/.env.production up -d --no-deps umami
     docker compose logs -f umami   # confirm clean boot, no missing-key error
     ```

  5. **Create a break-glass second admin BEFORE enrolling your primary account.** This is the single most important lockout mitigation — if your only admin loses their phone and backup codes, the account is bricked with no recovery path.
     - Log in to `https://umami.addrlens.de/` as your primary admin.
     - `Settings → Users → Create User → role Admin`. Name it e.g. `admin-backup`. Set a strong unique password, store in password manager.
     - Log out, log in as `admin-backup`, enable its own 2FA on a **physically separate device** (spouse's phone / iPad in a locked drawer / hardware TOTP token). Save its backup codes to the same off-server safe.
     - Log out. From here on, either admin can reset the other via `Admin → Users → (user) → Clear 2FA`.

  6. **Enrol your primary admin — with belt-and-suspenders:**
     - Log in as primary admin. `Settings → Security → Enable two-factor authentication`.
     - **Scan the QR code into TWO authenticator apps simultaneously**, on separate devices (TOTP secrets are stateless — the same secret works forever on any device that scanned it). Recommended: phone (primary) + iPad or hardware token on your laptop.
     - Enter the 6-digit code to confirm.
     - **Copy the 10 backup codes immediately — they are shown once.** Store in password manager (primary) and printed sealed copy in the same safe as the encryption key.
     - Log out and log back in with TOTP to confirm the setup works end-to-end BEFORE closing the tab.

  Notes:
  - Five failed TOTP attempts locks further attempts for 15 minutes (Umami built-in).
  - `TWO_FACTOR_ENCRYPTION_KEY` is separate from `APP_SECRET` and `UMAMI_DB_PASSWORD` — do not reuse one for another. Different rotation cadence, different blast radius.
  - `docker-compose.prod.yml` pins Umami to `3.3.1` (not `postgresql-latest`) so a `docker compose pull` never silently upgrades across a breaking 2FA schema change. Bump the pin deliberately after checking release notes; verify the new tag's manifest digest matches the mysql-vs-postgres variant you expect with `docker manifest inspect ghcr.io/umami-software/umami:<new-tag>`.

## Updates

Run from the box after `git push origin main` has landed the new code:

```bash
cd /srv/addrlens/repo/v0.1
./ops/deploy/update.sh
```

The script pulls the latest `main`, rebuilds the images, restarts the stack, and gates on `/ready`. The deployed SHA is written to `/srv/addrlens/last-deployed.sha` so rollback knows the previous version.

## Rollback

```bash
./ops/deploy/rollback.sh           # revert to the SHA in /srv/addrlens/last-deployed.sha
./ops/deploy/rollback.sh <sha>     # revert to any specific SHA
```

## Watching runtime

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --env-file /srv/addrlens/.env.production ps
docker compose logs -f app
docker compose logs -f inference
docker compose logs -f cloudflared
docker stats
```

## Common gotchas

- **502 from Cloudflare.** The origin app is restarting (likely mid-`update.sh`) or `cloudflared` has lost its connection. Check `docker compose ps` and `docker compose logs cloudflared`.
- **`/ready` returns 503 forever.** The `Index` boot failed. Two common causes:
  - Berlin `gdi.berlin.de` WFS is under maintenance — check the maintenance HTML with `curl https://gdi.berlin.de/services/wfs/schulen?...&outputFormat=application/json | head`. If HTML, wait for the Senate to bring it back up.
  - OSM snapshot missing. Run `ls /srv/addrlens/data/osm/berlin-amenities.json` — expect a file over 10 MB. If missing, re-run the seed step from the first-deploy section.
- **Inference OOM.** Run `docker inspect v0.1-inference-1 | grep -i oom`. If `OOMKilled: true`, either increase `mem_limit` in `docker-compose.prod.yml`, increase swap, drop to a smaller quant (Q3_K_M), or upgrade to a larger box.
- **Cloudflare Tunnel disconnected.** Try `docker compose restart cloudflared`. If it keeps failing, the `TUNNEL_TOKEN` may be stale — regenerate it in the Cloudflare dashboard, update `/srv/addrlens/.env.production`, and restart the service.
- **`git clone` fails with "Network is unreachable" or "Failed to connect to github.com port 443 after 1 ms".** The box has no IPv4 default route — a fresh Hetzner box without a Primary IPv4 sits on a CGNAT `100.64.0.0/10` LAN with no path to the public internet. Attach a Primary IPv4 in the Hetzner console as described in Pre-flight and reboot.
- **`git clone` prompts for a password and rejects it** ("Password authentication is not supported for Git operations"). GitHub disabled HTTPS password auth in 2021. Use the SSH deploy-key path in Pre-flight and clone via `git@github.com:saptadip/addrlens.git`.
- **`bootstrap.sh` fails with `404 Not Found` on `https://download.docker.com/linux/ubuntu ... Release`.** You provisioned an Ubuntu image instead of Debian, or a Debian image with the wrong repo pinned. `bootstrap.sh` targets `linux/debian`; either rebuild the box as Debian 13 (trixie) or edit the script back to `linux/ubuntu` with `$(lsb_release -cs)`.
- **Cloudflare Tunnel wizard: "A DNS record with this name already exists."** An A/AAAA/CNAME sits at the apex (`addrlens.de`). Delete only that apex record (and its `www` twin if you want both routes to go through the tunnel). Preserve the MX / SRV / TXT / `autoconfig` rows — they are email routing, not tunnel-related.
- **OSM seed step fails with `PermissionError: '/srv/data/osm/berlin-latest.osm.pbf.tmp'`.** The container runs as UID 10001 (the `addrlens` user baked into `ops/Dockerfile.app`) but a stale run of `bootstrap.sh` left the bind-mounted host directories owned by the deploy user (UID 1000). Fix on the box: `sudo chown -R 10001:10001 /srv/addrlens/data/osm /srv/addrlens/models`. Fresh boxes running the current `bootstrap.sh` already do this.
