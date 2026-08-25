# Docker microservice deploy design — addrlens.de

**Date:** 2026-08-15
**Status:** Draft, awaiting review
**Scope:** Production deployment of the `v0.1/` tree (Berlin Family Address Intelligence) to a Hetzner Cloud VM in Falkenstein, fronted by Cloudflare Tunnel with `addrlens.de` as the public hostname.
**Non-goals:** No changes to the domain model, API contracts, or feature set. No changes to the local (non-docker) development workflow.

---

## 1. Overview

The application is currently a two-service FastAPI microservice architecture:

- `app/` — per-city web service (Berlin only, today). Serves the SPA in `web/` and the `/api/*` endpoints.
- `inference/` — shared LLM service. Serves `POST /summarize` over an internal HTTP call from `app`.

Both services already have working Dockerfiles and a `docker-compose.yml` used for local development. What is missing is a production deployment path — TLS termination, DNS wiring, rate limiting, monitoring hooks, deploy automation, and a story for how the two services communicate in a locked-down box without exposing public ports beyond SSH.

This design fills that gap with the minimum viable production posture. It uses Cloudflare Tunnel as the only ingress path, avoids nginx/traefik entirely for v1, keeps the local uvicorn-only dev flow intact, and adds a small set of new files (deploy scripts, prod compose overlay, systemd units, one new dependency group) without modifying any existing runtime behavior.

## 2. Confirmed decisions

Locked during the brainstorming session:

| Decision | Value | Reasoning |
|---|---|---|
| Reverse proxy | **Cloudflare Tunnel** (`cloudflared`), no nginx/traefik | No public ports on origin, no TLS cert to manage, one moving piece less. Nginx becomes worth adding only when multi-service routing (per-city subdomains) or slow-client buffering matters. |
| Rate limit location | **Cloudflare** (free-tier rate limiting rule on `/api/card_insight`) | Free plan includes 1 rule — sufficient for the one expensive endpoint. Rejected requests never touch origin. No `slowapi` needed at v1. |
| Deploy mechanism | **Build-on-server** | Zero external infra (no registry, no CI push). Fresh VM = git clone + `docker compose up -d --build`. Upgrade path to GHCR-based CI is documented as out-of-scope. |
| Model file placement | **Bind mount** from host `/srv/addrlens/models/` into inference container `/models/:ro`. Not baked into image. | 1 GB GGUF file never enters build context; swap models without rebuilding image. |
| Hetzner box | **Existing** Falkenstein VM: 2 vCPU / 4 GB RAM / 40 GB NVMe / Ubuntu 24.04 x86_64. Bare (docker not installed, no other services), user `sapta` with sudo. | Given constraint. RAM is tight but workable with per-container `mem_limit` + 4 GB swap. |
| Domain scheme | **Apex only** (`addrlens.de`). `www.addrlens.de` 301-redirects to apex. Multi-city subdomains (per plan §0) deferred until real city #2 lands. | Cleanest onboarding URL for Berlin-only v1. |
| Deploy tree | **`v0.1/`**, not `micro-service/` | Per user confirmation. `v0.1/` has the local OSM snapshot (`data/osm/berlin-amenities.json`) + refresh script; `micro-service/` uses live Overpass without a snapshot. |
| Alert email | `informsapta@gmail.com` | For UptimeRobot + Sentry notifications. |
| Sentry region | **EU (Frankfurt)** | Matches "no cross-border data transfer" from `microservice-refactor-plan.md` §0. |

## 3. Topology

```
Internet
   │
   ▼
Cloudflare edge  ── TLS, rate limit rule, WAF, DNS, cache rules
   │
   ▼
Cloudflare Tunnel (outbound-only from box; no public origin port)
   │
   ▼
┌────────────────── Hetzner VM (Falkenstein) ──────────────────┐
│  docker network: addrlens_net (bridge)                        │
│                                                                │
│  ┌──────────────┐  ┌────────┐  ┌──────────────┐              │
│  │ cloudflared  │─▶│  app   │─▶│  inference   │              │
│  │  128 MB      │  │ 700 MB │  │  2800 MB     │              │
│  └──────────────┘  └────────┘  └──────────────┘              │
│                       │  │                                    │
│              ┌────────┘  └────────┐                           │
│              ▼                     ▼                           │
│  /srv/addrlens/data/osm/    /srv/addrlens/models/            │
│  (bind mount, read-only)    (bind mount, read-only)          │
│  13 MB JSON + 94 MB pbf      ~1 GB Qwen2.5-1.5B GGUF          │
│         ▲                                                     │
│         │ writes weekly                                       │
│         │                                                     │
│  systemd timer: refresh-osm-amenities.timer → Sun 03:00 CET   │
│    Runs: docker compose run --rm app                          │
│           python -m scripts.refresh_osm_amenities             │
└────────────────────────────────────────────────────────────────┘

Firewall (ufw): 22/tcp SSH only (your IP).
                Nothing else public. Cloudflared makes only outbound
                connections to Cloudflare edge, so no incoming ports needed.
Outbound allowlist (informal — ufw allows all outbound):
                gdi.berlin.de (Berlin WFS), download.geofabrik.de (weekly OSM),
                sentry.io (error events), Cloudflare edge (tunnel).
```

### 3.1 Data flow — single user request

1. Browser → `https://addrlens.de/api/lookup?...` → Cloudflare edge.
2. Cloudflare evaluates rate rule (only fires on `/api/card_insight`), forwards through the tunnel.
3. `cloudflared` container hands off to `app:8001` on the internal bridge (docker DNS resolves `app`).
4. `app` performs WFS reads to `gdi.berlin.de` and reads the local OSM snapshot at `/srv/data/osm/berlin-amenities.json`. Returns JSON.
5. For `/api/card_insight`, `app` posts to `http://inference:8080/summarize` on the internal bridge. Returns paraphrased prose.

### 3.2 Data flow — weekly OSM refresh

1. `refresh-osm-amenities.timer` fires at Sun 03:00 Europe/Berlin.
2. Timer starts `refresh-osm-amenities.service` (oneshot).
3. Service runs `docker compose run --rm --entrypoint python app -m scripts.refresh_osm_amenities` — reuses the app image.
4. Script downloads `berlin-latest.osm.pbf` from Geofabrik (~94 MB, ~12 s on the VM's network), filters it with `osmium`, atomically writes `berlin-amenities.json`.
5. Service `ExecStartPost` restarts the app container so its `Index` picks up the new snapshot without waiting for the next natural restart.

## 4. File-level repo changes (`v0.1/` tree)

Guiding principle: local uvicorn dev flow (`uvicorn app.main:app --port 8001` bare-metal on Apple Silicon) MUST keep working. Every change is either additive or hidden behind a prod-only env var or the prod compose overlay.

### 4.1 New files

| Path | Purpose |
|---|---|
| `docker-compose.prod.yml` | Overlay for production. Adds `cloudflared` service, `mem_limit`s, restart policies, bind mounts. Cancels `ports:` publishing. |
| `.env.production.example` | Template: `CITY`, `INFERENCE_URL`, `TUNNEL_TOKEN`, `SENTRY_DSN_APP`, `SENTRY_DSN_INFERENCE`, `SENTRY_ENV`, `GIT_SHA`, `LOG_LEVEL`. Real `.env.production` is git-ignored, lives on the box. |
| `ops/deploy/bootstrap.sh` | First-time host provisioning. Installs docker, ufw, unattended-upgrades, fail2ban. Creates `/srv/addrlens/` layout. Configures swap, log rotation, systemd timer. Idempotent. |
| `ops/deploy/update.sh` | `git pull && docker compose build && docker compose up -d`, with a readiness gate. What the operator runs to ship. |
| `ops/deploy/rollback.sh` | Checks out previous SHA, rebuilds, recreates. |
| `ops/deploy/README.md` | First-deploy checklist, SSH hardening steps, model file fetch, first OSM snapshot fetch. |
| `ops/systemd/refresh-osm-amenities.service` | Oneshot systemd unit that runs the refresh script inside a throwaway container. |
| `ops/systemd/refresh-osm-amenities.timer` | Weekly Sun 03:00 Europe/Berlin. |
| `ops/cloudflared/README.md` | Documents CF Tunnel creation flow, token storage, rotation. No secret in git. |

### 4.2 Modified files

| Path | Change | Local-dev impact |
|---|---|---|
| `ops/Dockerfile.app` | Add one `RUN uv pip install --system --no-cache "sentry-sdk[fastapi]>=2.0" "osmium>=3.7"` after the base install layer. Ensures the image has osmium (for `refresh_osm_amenities.py`) and Sentry SDK. Everything else unchanged. | None. Local dev uses bare uvicorn, not this image. |
| `ops/Dockerfile.inference` | (1) Remove the `COPY models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf /models/` line. (2) Remove `/models` from the final `chown` (mounted read-only, ownership from host). (3) Add `RUN mkdir -p /models` so the mountpoint exists. (4) Add one `RUN uv pip install --system --no-cache "sentry-sdk[fastapi]>=2.0"` after base install. `LLAMA_MODEL_PATH` env unchanged. | None. Local dev uses MLX on host, not this Dockerfile. |
| `pyproject.toml` (app) | **Unchanged.** Prod-only deps are added at Dockerfile layer (see `Dockerfile.app` row), not in `pyproject.toml`. Rationale: v0.1's pyproject uses `[tool.uv] package = false`, which makes `[project.optional-dependencies]` awkward to install via `uv pip` — cleaner to install prod-only deps directly in the Dockerfile. | None. |
| `inference/pyproject.toml` | **Unchanged.** Same reason — Sentry SDK added at Dockerfile layer. | None. |
| `app/main.py` | Prepend Sentry init guarded by `if os.environ.get("SENTRY_DSN_APP"):`. If unset (local dev), no-op. Uses `FastApiIntegration` + `StarletteIntegration`. Reads `SENTRY_ENV`, `GIT_SHA` env vars for release tracking. | None if `SENTRY_DSN_APP` unset. |
| `inference/main.py` | Same Sentry init pattern; reads `SENTRY_DSN_INFERENCE`. | None if unset. |
| `docker-compose.yml` | **Untouched.** Stays as dev shape with published ports `8001:8001` and `8080:8080`. | None. |
| `.gitignore` | Add: `.env.production`, `/srv/`, `models/`, `data/osm/*.pbf`, `data/osm/*.json`. | None. |

### 4.3 Explicit non-changes

- `app/config.py` — unchanged.
- `app/routes/*.py` — unchanged.
- `app/core/*.py` — unchanged (boot-resilience refactor is out of scope; see §11 item 1).
- `inference/runtime/*.py` — unchanged.
- `inference/templates/*.py` — unchanged.
- `web/*` — unchanged.
- `scripts/refresh_osm_amenities.py` — unchanged (only its execution environment changes: now runs inside the app image container, not the host venv).

## 5. `docker-compose.prod.yml`

Loaded on top of the dev compose:

```bash
docker compose \
    -f docker-compose.yml \
    -f docker-compose.prod.yml \
    --env-file /srv/addrlens/.env.production \
    up -d
```

```yaml
# Prod overlay. What it changes vs docker-compose.yml:
# 1. Cancels "ports:" publishing (containers stay on internal bridge).
# 2. Adds cloudflared as the only ingress path.
# 3. Bind-mounts /srv/addrlens/{models,data/osm} as read-only.
# 4. Adds mem_limit + memswap_limit so a runaway service OOM-kills itself,
#    not the box.
# 5. restart: unless-stopped for docker-managed liveness.
# 6. Reads secrets from /srv/addrlens/.env.production (git-ignored).

services:
  app:
    ports: !reset []
    env_file:
      - /srv/addrlens/.env.production
    volumes:
      - /srv/addrlens/data/osm:/srv/data/osm:ro
    mem_limit: 700m
    memswap_limit: 1200m
    restart: unless-stopped
    depends_on:
      inference:
        condition: service_healthy
    networks:
      - addrlens_net

  inference:
    ports: !reset []
    env_file:
      - /srv/addrlens/.env.production
    volumes:
      - /srv/addrlens/models:/models:ro
    environment:
      LLAMA_MODEL_PATH: /models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf
    mem_limit: 2800m
    memswap_limit: 3600m
    restart: unless-stopped
    networks:
      - addrlens_net

  cloudflared:
    image: cloudflare/cloudflared:latest
    command: tunnel --no-autoupdate run
    env_file:
      - /srv/addrlens/.env.production
    mem_limit: 128m
    restart: unless-stopped
    depends_on:
      app:
        condition: service_healthy
    networks:
      - addrlens_net

networks:
  addrlens_net:
    driver: bridge
    internal: false
```

### 5.1 Notes on the overlay

- `!reset []` (Compose spec ≥ 2.24) cancels the `ports:` list from the base file. Docker Compose plugin installed by bootstrap is current, so this works.
- `condition: service_healthy` gates `cloudflared` on the app's HEALTHCHECK passing — prevents the tunnel from announcing origin ready before the app can answer.
- `mem_limit` is the RAM ceiling; `memswap_limit` is RAM+swap ceiling. The difference is per-container swap allowance. Total swap used by all containers stays under the 4 GB host swap.
- `env_file` uses an absolute path (`/srv/addrlens/.env.production`). Compose expands variables at deploy time. The file is not in git.
- `networks.addrlens_net` is declared explicitly so all three services share a single bridge with docker-internal DNS. `cloudflared` resolves `app` by service name; `app` resolves `inference` by service name.
- `internal: false` because `cloudflared` needs egress to Cloudflare edge and `app` needs egress to `gdi.berlin.de` (WFS) plus `download.geofabrik.de` (weekly refresh).

## 6. Dockerfile diffs

### 6.1 `ops/Dockerfile.inference`

```diff
 # ---- deps layer ----
 COPY inference/pyproject.toml ./pyproject.toml
 RUN uv pip install --system --no-cache ".[prod]"
+RUN uv pip install --system --no-cache "sentry-sdk[fastapi]>=2.0"

 # ---- inference code + model ----
 COPY inference ./inference
-# Bake the GGUF in — plan §7.4 default. Comment out + mount if you'd rather
-# ship the model separately.
-COPY models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf /models/

+RUN mkdir -p /models
 RUN useradd -u 10001 -m -s /sbin/nologin addrlens \
-    && chown -R addrlens:addrlens /srv /models
+    && chown -R addrlens:addrlens /srv
 USER addrlens
```

`LLAMA_MODEL_PATH=/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf` stays. Only the source of that file changes (bind mount from host, not COPY at build time).

### 6.2 `ops/Dockerfile.app`

```diff
 # ---- deps layer (cacheable) ----
 COPY pyproject.toml ./
 RUN uv pip install --system --no-cache -r pyproject.toml
+# Prod-only deps: Sentry SDK (env-guarded init) + osmium (weekly OSM refresh
+# script runs inside this image). Kept out of pyproject.toml to avoid pulling
+# them into the local bare-uvicorn dev environment.
+RUN uv pip install --system --no-cache \
+        "sentry-sdk[fastapi]>=2.0" "osmium>=3.7"

 # ---- app layer ----
 COPY app ./app
 COPY web ./web
```

Adds ~15 MB to the app image (osmium wheel + sentry-sdk). Local dev is unaffected because local dev doesn't use this Dockerfile.

## 7. Cloudflare configuration

All configured via Cloudflare dashboard. No CF config files land in the repo. The only secret produced is the tunnel token, stored in `/srv/addrlens/.env.production` as `TUNNEL_TOKEN`.

### 7.1 Prerequisites and current DNS state

**Prerequisites (all verified 2026-08-15):**

- `addrlens.de` zone exists on Cloudflare Free plan. Status: **Active**.
- Nameservers at Hetzner registrar point to Cloudflare (`alexa.ns.cloudflare.com`, `elmo.ns.cloudflare.com`). Verified via public DNS lookup.

**Existing DNS records that must be handled during tunnel setup (not blockers, but require the migration steps below):**

The zone already has web + mail records from the pre-tunnel setup. Web records need to be replaced by the tunnel wizard; mail records must be preserved.

| Name | Type | Content | Proxy | Action |
|---|---|---|---|---|
| `addrlens.de` | A | `88.198.219.246` (Hetzner) | Proxied | **Replace** — tunnel wizard's overwrite prompt (accept) replaces this with `CNAME <tunnel-id>.cfargotunnel.com`. |
| `addrlens.de` | AAAA | `2a01:4f8:d0a:27bd::2` (Hetzner) | Proxied | **Replace** — same wizard step handles this. |
| `www.addrlens.de` | A | `88.198.219.246` | Proxied | **Change to CNAME** → `addrlens.de` (proxied). Cosmetic; Redirect Rule (§7.4) fires at CF edge regardless of DNS target as long as `www` is proxied. |
| `www.addrlens.de` | AAAA | `2a01:4f8:d0a:27bd::2` | Proxied | **Delete** after the www A → CNAME change (the CNAME covers both v4 and v6). |
| `addrlens.de` | MX | `www4.your-server.de` prio 10 | DNS only | **Preserve** — Hetzner mail. |
| `autoconfig.addrlens.de` | CNAME | `mail.your-server.de` | Proxied | **Preserve** — Hetzner mail autoconfig. |
| `_autodiscover._tcp.addrlens.de` | SRV | `100 443 mail.your-server.de` | DNS only | **Preserve.** |
| `_imaps._tcp.addrlens.de` | SRV | `100 993 mail.your-server.de` | DNS only | **Preserve.** |
| `_pop3s._tcp.addrlens.de` | SRV | `100 995 mail.your-server.de` | DNS only | **Preserve.** |
| `_submission._tcp.addrlens.de` | SRV | `100 587 mail.your-server.de` | DNS only | **Preserve.** |
| `addrlens.de` | TXT | `"v=spf1 +a +mx ?all"` | DNS only | **Preserve.** SPF for mail auth. |

**Warning shown in dashboard: "Your origin IP address is partially exposed"** — inherent to running proxied web + DNS-only mail on the same zone. Mail records reveal Hetzner IPs. Acceptable trade-off if you want to keep Hetzner mail on this zone; not a blocker for the tunnel setup.

**DNS migration sequence** (do this once, in this order, before the tunnel wizard's Public Hostname step will resolve cleanly):

1. Delete `www.addrlens.de` AAAA record.
2. Change `www.addrlens.de` A record to a CNAME → `addrlens.de` (keep proxied).
3. Leave the apex A + AAAA records alone at this step — the tunnel wizard replaces them automatically when you configure the apex public hostname in §7.3 (it prompts "This will replace the existing A/AAAA records for addrlens.de" — accept).

If the wizard refuses to overwrite (rare), delete apex A + apex AAAA manually first, then re-run the Public Hostname step.

**Do not touch any record with name `_autodiscover`, `_imaps`, `_pop3s`, `_submission`, `autoconfig`, or the MX / TXT SPF entries — those are Hetzner mail and are unrelated to the tunnel.**

### 7.2 Tunnel creation

**Path:** Zero Trust dashboard → Networks → Tunnels → Create a tunnel.

- Connector type: **Cloudflared**
- Tunnel name: `addrlens-prod`
- Environment: **Docker**

The dashboard displays a `docker run cloudflare/cloudflared:latest tunnel --token …eyJ…` snippet. Copy only the token — it becomes `TUNNEL_TOKEN=eyJ…` in `.env.production`. The compose file supplies the rest of the invocation.

Token rotation: delete + recreate the tunnel in the dashboard, update `TUNNEL_TOKEN` in `.env.production`, `docker compose up -d cloudflared`.

### 7.3 Public hostname routing

Wizard → Public Hostnames step:

| Field | Value |
|---|---|
| Subdomain | *(blank — apex)* |
| Domain | `addrlens.de` |
| Path | *(blank — all paths)* |
| Service Type | HTTP |
| URL | `app:8001` |

Additional Application Settings:
- HTTP Host Header: `addrlens.de`
- HTTP2 connection: On
- Connection timeout: 30 s

CF automatically creates the proxied CNAME `addrlens.de` → `<tunnel-id>.cfargotunnel.com`. No manual DNS record on apex.

### 7.4 `www` → apex redirect

**Path:** Rules → Redirect Rules → Create.

| Field | Value |
|---|---|
| Rule name | `www to apex` |
| When incoming requests match | Hostname equals `www.addrlens.de` |
| Then | Static redirect, Dynamic |
| Expression | `concat("https://addrlens.de", http.request.uri.path)` |
| Status code | 301 |
| Preserve query string | On |

Also: add a proxied CNAME `www` → `addrlens.de` in DNS. Redirect fires before origin.

### 7.5 Rate limit rule

**Path:** Security → WAF → Rate limiting rules → Create.

| Field | Value |
|---|---|
| Rule name | `insight-per-ip` |
| Match | URI Path contains `/api/card_insight` |
| Requests | 5 |
| Period | 1 minute |
| Response | Custom 429, body `{"error":"rate_limited","retry_after_s":60}`, `Content-Type: application/json` |
| Block duration | 60 seconds |

### 7.6 Recommended CF settings

- SSL/TLS mode: Full.
- Always Use HTTPS: On.
- Automatic HTTPS Rewrites: On.
- Bot Fight Mode: On.
- Security Level: Medium (default).
- Cache Rules:
  1. `bypass-api`: URI Path starts with `/api/` → Bypass cache.
  2. `cache-static`: URI Path starts with `/static/` → Cache eligible, Edge TTL 1 day, Browser TTL 1 hour.
- Auto Minify: Off (SPA is already small; minify risks breaking JSON payloads on `/api/*`).

### 7.7 What Cloudflare does not provide

- No origin-container mem/CPU visibility — that is Sentry + UptimeRobot + `docker stats`.
- Only 24 h HTTP access log retention on the Free plan.
- Bot Fight Mode is coarse — the real defense is the rate limit rule plus the mem-limited serial inference queue.
- No inference endpoint auth — `POST /api/card_insight` remains unauthenticated. Rate limit is the only throttle.

## 8. Host bootstrap

### 8.1 Filesystem layout

```
/srv/addrlens/
├── repo/                             # git clone
│   └── v0.1/                         # deploy runs `docker compose` from here
├── models/                           # bind-mounted read-only into inference
│   └── Qwen2.5-1.5B-Instruct-Q4_K_M.gguf
├── data/
│   └── osm/                          # bind-mounted read-only into app
│       ├── berlin-amenities.json
│       └── berlin-latest.osm.pbf
├── .env.production                   # 0600, sapta:sapta, git-ignored
├── last-deployed.sha                 # written by update.sh for rollback
└── logs/                             # docker daemon json-file logs
```

Ownership: entire tree `sapta:sapta`, dirs `0755`, `.env.production` `0600`. Docker containers run as uid `10001` from Dockerfile `useradd`; bind-mounted dirs are `0755` so container reads succeed. `.env.production` is read via `env_file`, not mounted.

### 8.2 `ops/deploy/bootstrap.sh`

Purpose: one-shot Hetzner Ubuntu 24.04 provisioning. Idempotent (safe to re-run after partial failures). Invocation: `sudo bash ops/deploy/bootstrap.sh` from cloned repo.

Steps:

1. **System packages.** `apt-get install`: `ca-certificates`, `curl`, `gnupg`, `lsb-release`, `ufw`, `fail2ban`, `unattended-upgrades`, `git`, `tzdata`. Set timezone to `Europe/Berlin`.
2. **Docker Engine + Compose plugin.** Adds Docker apt repo, installs `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`, `docker-compose-plugin`. Adds `sapta` to `docker` group.
3. **Directory layout.** Creates `/srv/addrlens/{models,data/osm,logs}`. Chowns to `sapta:sapta`. Touches `.env.production`, chmods to `0600`.
4. **Swap file (4 GB).** `/swapfile`, `mkswap`, `swapon`, adds to `/etc/fstab`. Sets `vm.swappiness=10` (prefer RAM; only swap under real pressure).
5. **Firewall.** `ufw --force reset`, default deny incoming, default allow outgoing, allow `22/tcp`, `ufw --force enable`.
6. **fail2ban.** `systemctl enable --now fail2ban` (SSH brute-force protection).
7. **Unattended security upgrades.** Reconfigure noninteractive, enable timer.
8. **Docker log rotation.** Writes `/etc/docker/daemon.json` with `json-file` driver, `max-size: 20m`, `max-file: 5`. Restarts docker.
9. **Systemd units.** Installs `refresh-osm-amenities.service` and `.timer` from the repo, enables the timer.

### 8.3 First-time out-of-band steps (manual, once, not in bootstrap)

Documented in `ops/deploy/README.md`:

```bash
# Model file (~1 GB)
cd /srv/addrlens/models
pip install --user huggingface_hub[cli]
hf download bartowski/Qwen2.5-1.5B-Instruct-GGUF \
    Qwen2.5-1.5B-Instruct-Q4_K_M.gguf --local-dir .

# Populate .env.production (template = .env.production.example)
vim /srv/addrlens/.env.production

# First OSM snapshot (would normally run at first timer fire; forced early)
cd /srv/addrlens/repo/v0.1
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    run --rm --entrypoint python app \
    -m scripts.refresh_osm_amenities
```

### 8.4 SSH hardening (documented, not scripted)

Not auto-modified to avoid lockout risk. Steps in `ops/deploy/README.md`:

1. Confirm `sapta` can SSH with public key.
2. Edit `/etc/ssh/sshd_config`: `PermitRootLogin no`, `PasswordAuthentication no`, `PubkeyAuthentication yes`.
3. `systemctl reload sshd`. Keep the current session open until a fresh session verifies.
4. Optional: change SSH port to a random high port, update `ufw allow`.

### 8.5 Systemd unit contents

**`ops/systemd/refresh-osm-amenities.service`:**

```ini
[Unit]
Description=Weekly Berlin OSM amenities refresh (Geofabrik → filtered JSON)
Wants=network-online.target
After=network-online.target docker.service

[Service]
Type=oneshot
User=sapta
WorkingDirectory=/srv/addrlens/repo/v0.1
ExecStart=/usr/bin/docker compose \
    -f docker-compose.yml -f docker-compose.prod.yml \
    run --rm --entrypoint python app \
    -m scripts.refresh_osm_amenities
ExecStartPost=/usr/bin/docker compose \
    -f docker-compose.yml -f docker-compose.prod.yml \
    restart app
TimeoutStartSec=30min
StandardOutput=journal
StandardError=journal
```

**`ops/systemd/refresh-osm-amenities.timer`:**

```ini
[Unit]
Description=Trigger weekly Berlin OSM refresh on Sunday 03:00 Europe/Berlin

[Timer]
OnCalendar=Sun 03:00
Persistent=true
RandomizedDelaySec=15min
Unit=refresh-osm-amenities.service

[Install]
WantedBy=timers.target
```

`Persistent=true` re-fires on next boot if the box was off at the scheduled time. `RandomizedDelaySec` spreads the load against Geofabrik (courtesy).

## 9. Deploy workflow

### 9.1 `ops/deploy/update.sh`

Purpose: ship a new version. Invocation on the box as `sapta`: `cd /srv/addrlens/repo/v0.1 && ./ops/deploy/update.sh`.

Flow:

1. Record current SHA to `/srv/addrlens/last-deployed.sha` (for rollback).
2. `git fetch --tags && git checkout main && git reset --hard origin/main`.
3. Write `GIT_SHA=<new-sha>` into `.env.production` so Sentry release tracking is accurate.
4. `docker compose … build --pull app inference`. Layer caching means unchanged deps → seconds; unchanged code → no rebuild.
5. `docker compose … up -d --remove-orphans`. Only containers whose spec changed are recreated.
6. Readiness gate: poll `app` container's `/ready` for up to 90 s. If it never becomes ready, print rollback command and exit non-zero.
7. `docker image prune -f --filter "until=168h"` to keep disk from filling.

Downtime shape: `docker compose up -d` recreates only containers whose spec changed. App-only change → `inference` and `cloudflared` untouched, `app` restarts (~5 s replace + 10 s `Index` build = ~15 s window during which CF Tunnel returns 502 for that origin). Zero-downtime deploys (rolling replicas behind an LB) are out of scope for v1.

### 9.2 `ops/deploy/rollback.sh`

Purpose: revert to a previous SHA. Invocation: `./ops/deploy/rollback.sh [<sha>]`. With no argument, reads `/srv/addrlens/last-deployed.sha`.

Flow: `git checkout <sha>`, rebuild `app` and `inference`, `up -d --force-recreate app inference`. Rollback speed dominated by rebuild — ~30-60 s if the layer cache is intact.

### 9.3 First-deploy sequence

Once, after bootstrap and after `.env.production` is filled:

```bash
cd /srv/addrlens
git clone <repo-url> repo
cd repo/v0.1

# Cold build (~10 min: llama-cpp-python wheel + fastapi + shapely).
docker compose -f docker-compose.yml -f docker-compose.prod.yml build

# First OSM snapshot.
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    run --rm --entrypoint python app -m scripts.refresh_osm_amenities

# Bring stack up.
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Watch cloudflared connect.
docker compose logs -f cloudflared
# Expect: "Registered tunnel connection connIndex=0 ..."

# Sanity checks through Cloudflare.
curl -sSf https://addrlens.de/health   # {"status":"ok"}
curl -sSf https://addrlens.de/ready    # {"status":"ready","city":"berlin"}
```

## 10. Monitoring hooks

### 10.1 Sentry initialization (both services)

Each service reads a **service-specific DSN env var**, avoiding the need for per-service `environment:` overrides in compose. Both DSNs live in the single `env_file` (`/srv/addrlens/.env.production`) and both containers load the whole file — the code picks the right key.

**`app/main.py`** — prepended after imports:

```python
import os

if os.environ.get("SENTRY_DSN_APP"):
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN_APP"],
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.1,
        environment=os.environ.get("SENTRY_ENV", "production"),
        release=os.environ.get("GIT_SHA"),
    )
```

**`inference/main.py`** — same shape, reads `SENTRY_DSN_INFERENCE`.

**Compose wiring** in `docker-compose.prod.yml`: both services `env_file: /srv/addrlens/.env.production`. No per-service `environment:` overrides needed for Sentry. Each container ignores the DSN key it doesn't consume.

**Dep install:** `sentry-sdk[fastapi]>=2.0` installed in the Dockerfile layer (see §6.1 and §6.2), not in `pyproject.toml`. Bare local install pulls base deps only (no Sentry) — matches local-dev preservation.

### 10.2 UptimeRobot probes

External probes; configured via UptimeRobot UI (not repo).

| Probe | URL | Expected | Alert to |
|---|---|---|---|
| App liveness | `https://addrlens.de/health` | 200, body `{"status":"ok"}` | `informsapta@gmail.com` |
| App readiness | `https://addrlens.de/ready` | 200, body includes `"city":"berlin"` | `informsapta@gmail.com` |

Cadence: 5 min each (free tier limit). Detection window: ~10 min worst case.

Inference is not publicly probeable (no CF Tunnel route), and app's `/ready` transitively covers Index + inference boot. Separate inference probing is deferred until throughput SLO changes.

### 10.3 Weekly OSM refresh verification

After bootstrap:

```bash
systemctl start refresh-osm-amenities.service
journalctl -u refresh-osm-amenities.service -n 50 --no-pager
# Expect: pbf download, filter, JSON write, app container restart.

systemctl list-timers refresh-osm-amenities.timer
# Expect: NEXT column = next Sunday 03:00.
```

### 10.4 Failure modes and observable signals

| Failure | Signal | Location |
|---|---|---|
| Tunnel down | UptimeRobot alert, CF Tunnel dashboard "disconnected" | Email + CF UI |
| Origin app crash | UptimeRobot alert, Sentry crash event, `docker compose ps` unhealthy | Email + Sentry + SSH |
| Inference OOM-killed | Sentry 503s on `/api/card_insight`, `docker inspect inference` shows `OOMKilled: true` | Sentry + SSH |
| WFS 5xx (Berlin Geoportal) | Sentry error waves, per-tile `_error` on frontend, `/ready` still 200 | Sentry + user reports |
| CF rate-limit false positive | Users report 429, CF Analytics spike | CF UI + user reports |
| Weekly OSM refresh fails | Sunday: `journalctl -u refresh-osm-amenities`, stale snapshot still serving | Manual, no alert wired |

Last row is a known gap and is called out in §11 item 7.

## 11. Documented out-of-scope

Deliberately deferred, each with an upgrade trigger and rough cost:

| # | Item | Deferral reason | Upgrade trigger | Cost when it's time |
|---|---|---|---|---|
| 1 | Boot resilience — per-layer WFS try/except in `Index` build | Code refactor of `app/core/index.py`, separate PR | First BOD 5xx causes boot failure in prod, or before any public announcement | ~1 day. Wrap each loader; add `degraded_layers` field to `/api/config`. |
| 2 | Structured JSON logs (`structlog`) | `print()` + docker json-file driver + rotation is sufficient for one operator | Second operator, or need to correlate a bad tile with a request across services | ~half day. Swap `print` → `logger.info`, JSON formatter, propagate `X-Request-ID`. |
| 3 | Analytics (Plausible / Umami) | Own design (SDK vs. proxy, self-host vs. cloud, tile-open schema) | Before public broadcast (Product Hunt / HN); need tile-open events by day 1 to drive v2 decisions | ~1 day self-host on same box, or ~1 hour cloud. |
| 4 | Inference response cache | 2-3 s uncached is fine at soft-launch RPS | Sentry perf shows `/api/card_insight` p50 dominates response time, or CF Analytics shows repeat hits within a day | ~half day. LRU in `inference/main.py` keyed on `(template, hash(context))`, ~24 h TTL. |
| 5 | CI pipeline (GHCR image push) | Build-on-server is faster iteration at v1 | Second box (staging), or want instant rollback without rebuild | ~1 day. GHA workflow, GHCR secrets, switch compose to `image:` from `build:`. |
| 6 | Zero-downtime deploys | ~15 s user-visible interrupt during app restart is acceptable pre-users | Real users AND repeated hotfix pressure | ~1-2 days. HAProxy/nginx between cloudflared and 2× app replicas, rolling swap. |
| 7 | OSM cron failure alerting | Silent-fail on Sunday's refresh; noticed only via stale snapshot symptoms | Any confirmed user impact from stale snapshot | ~1 hour. Systemd `OnFailure=` unit that emails via `msmtp`. |
| 8 | Per-tile error UX | `_error` field exists; frontend not styled for it | User complaints about tiles disappearing | ~1 day frontend. |
| 9 | Impressum + Datenschutzerklärung SPA linking | Already committed on `../legal/impressum.md`; deploy assumes these render | Before public URL is reachable (§5 TMG + DSGVO — hard legal blocker) | ~1 hour if templates exist. Verify before flipping DNS. |
| 10 | Backup / snapshot strategy | Only state is `.env.production` (small) + regenerable data | Any user-persisted data on the box (feedback form, comments, analytics DB) | ~1 hour. Hetzner Cloud Volume snapshot cron + `.env.production` copy to password manager. |
| 11 | DDoS beyond CF free tier | CF free absorbs generic L7 volumetric; rate rule + Bot Fight + no origin IP is strong for v1 | Sustained targeted attack causing Hetzner egress cost | Upgrade CF to Pro ($20/mo) → 5 rate rules + advanced managed WAF. |

## 12. Local-dev preservation contract

Post-implementation, the following bare-metal dev commands MUST work unchanged on Apple Silicon:

```bash
# From v0.1/ root
uv pip install --system -r pyproject.toml
uv pip install --system -e "inference[dev]"

# Terminal 1
INFERENCE_BACKEND=mlx uvicorn inference.main:app --port 8080

# Terminal 2
CITY=berlin INFERENCE_URL=http://localhost:8080 \
    uvicorn app.main:app --port 8001

# http://localhost:8001 → SPA → address lookup works.
```

**Why they keep working:**

1. Sentry SDK is env-guarded. Unset locally → init skipped → zero behavior change. Not even installed in the base dev env (it lives in the `prod` optional extra).
2. `osmium` is in the `scripts` optional extra, not base. `refresh_osm_amenities.py` won't import on a base install — but you don't run that script locally (it targets the host bind mount on the box).
3. `docker-compose.yml` is untouched. Local `docker compose up` still boots both services with ports published.
4. `docker-compose.prod.yml` is opt-in — only loaded when the operator types `-f docker-compose.prod.yml`.
5. `Dockerfile.app` is untouched. `Dockerfile.inference` change (drop `COPY models/…`) does not affect local dev (which uses MLX on host, not this Dockerfile).
6. `app/main.py` + `inference/main.py` add only env-guarded Sentry init; all existing behavior below is intact.

**Automated verification steps I will run before declaring implementation complete:**

1. `uv pip install --system -r pyproject.toml` — base install resolves.
2. `CITY=berlin INFERENCE_URL=http://localhost:8080 uvicorn app.main:app --port 8001` — boots without `SENTRY_DSN` set.
3. `curl -sSf http://localhost:8001/health` returns `{"status":"ok"}`.
4. `python -m app.selfcheck` — no new assertions weakened.
5. `docker compose up -d` (no prod overlay) still boots both services with ports published.
6. `uv pip install --system -e "inference[dev]"` — MLX extra still installs on Apple Silicon.
7. `INFERENCE_BACKEND=mlx uvicorn inference.main:app --port 8080` — MLX backend still loads.

## 13. Open non-decisions (for spec review)

- **Repo hosting.** Assumption: private GitHub repo, SSH deploy key on the box's `sapta` account for `git pull`. If different (GitLab, Bitbucket, public repo, HTTPS token), specify at review.
- **`.env.production` backup.** Documented: "after filling, copy contents to password manager (1Password, Bitwarden, etc.)". Not scripted.
- **CF plan.** Free confirmed. If you upgrade later, the design still holds — you get more rate limit rules.

## 14. Implementation phases (preview — full plan in writing-plans skill)

At a high level, the implementation splits into:

1. **Repo scaffolding.** Add new files, modify existing files, verify locally. No prod resources touched.
2. **Local verification.** Run the §12 automated checks. Merge PR only after all pass.
3. **CF setup.** Create tunnel, configure hostname + rate limit + redirect rules in CF dashboard. Copy token.
4. **Host bootstrap.** SSH to box, clone repo, run `bootstrap.sh`, fetch model file, fill `.env.production` including tunnel token.
5. **First deploy.** Build images, run first OSM snapshot, `up -d`, verify `curl https://addrlens.de/health`.
6. **Verification pass.** UptimeRobot probes green for 30 min. Sentry projects receive a test event each. Rate limit rule triggers on synthetic load. Weekly OSM timer set for next Sunday.
7. **Documentation.** `ops/deploy/README.md` + update `CLAUDE.md` for the v0.1 tree with the new commands.

Detailed step-by-step plan comes from the `writing-plans` skill after this design is approved.
