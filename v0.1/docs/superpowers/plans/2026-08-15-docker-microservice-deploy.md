# Docker microservice deploy — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `v0.1/` tree to a Hetzner VM in Falkenstein, fronted by Cloudflare Tunnel at `https://addrlens.de`, without breaking the local bare-uvicorn dev flow.

**Architecture:** Three docker containers (`app`, `inference`, `cloudflared`) on one internal bridge. `cloudflared` is the only ingress (no public ports). Model file and OSM snapshot are bind-mounted from the host, not baked. A prod compose overlay (`docker-compose.prod.yml`) layers production behavior on top of the untouched dev `docker-compose.yml`. Weekly OSM snapshot refresh runs via a systemd timer that calls `docker compose run --rm` on the app image.

**Tech Stack:** Docker Engine + Compose plugin, Cloudflare Tunnel (`cloudflared`), Ubuntu 24.04 (x86_64), Python 3.11 (FastAPI, uvicorn, llama-cpp-python, osmium, sentry-sdk), systemd, ufw, fail2ban.

**Spec:** [`../specs/2026-08-15-docker-microservice-deploy-design.md`](../specs/2026-08-15-docker-microservice-deploy-design.md)

## Global Constraints

- **Deploy tree:** `v0.1/` — NOT `micro-service/`. All file paths in this plan are relative to `v0.1/`.
- **Local dev preservation:** the following commands MUST still work unchanged after every task:
  ```bash
  uv pip install --system -r pyproject.toml
  CITY=berlin INFERENCE_URL=http://localhost:8080 uvicorn app.main:app --port 8001
  INFERENCE_BACKEND=mlx uvicorn inference.main:app --port 8080
  ```
- **Order-sensitive gates:**
  - DNS migration (delete `www` AAAA, change `www` A → CNAME) MUST happen BEFORE the tunnel wizard's Public Hostname step.
  - First OSM snapshot (`docker compose run --rm` refresh script) MUST run BEFORE `docker compose up -d` — the app's `Index` build reads `data/osm/berlin-amenities.json` at boot.
- **Alert email:** `informsapta@gmail.com` for Sentry + UptimeRobot.
- **Sentry region:** EU (Frankfurt).
- **Ubuntu 24.04 x86_64.** Docker Compose plugin ≥ 2.24 required for `!reset []` YAML tag.
- **Docker containers run as uid 10001** (from Dockerfile `useradd`). Host bind-mount directory ownership must permit read by uid 10001 — plan uses `chown sapta:sapta` with dir mode 0755, which is world-readable.
- **File paths on the box:** all under `/srv/addrlens/`.
- **Secrets never in git:** `.env.production` is in `/srv/addrlens/`, not the repo. `.gitignore` already covers it after Task 1.
- **CF plan:** Free (1 rate-limit rule, sufficient for `/api/card_insight`).
- **Domain:** apex `addrlens.de`, `www.addrlens.de` 301-redirects to apex.

## File structure

Repo changes (all inside `v0.1/`):

| Path | Kind | Task |
|---|---|---|
| `.gitignore` | modify | 1 |
| `.env.production.example` | new | 2 |
| `ops/Dockerfile.app` | modify | 3 |
| `ops/Dockerfile.inference` | modify | 4 |
| `app/main.py` | modify | 5 |
| `inference/main.py` | modify | 6 |
| `docker-compose.prod.yml` | new | 7 |
| `ops/systemd/refresh-osm-amenities.service` | new | 8 |
| `ops/systemd/refresh-osm-amenities.timer` | new | 8 |
| `ops/deploy/bootstrap.sh` | new | 9 |
| `ops/deploy/update.sh` | new | 10 |
| `ops/deploy/rollback.sh` | new | 11 |
| `ops/deploy/README.md` | new | 12 |
| `ops/cloudflared/README.md` | new | 12 |

Off-repo actions (Cloudflare dashboard, Hetzner box):

| Action | Task |
|---|---|
| Local verification of dev flow | 13 |
| DNS migration in CF dashboard | 14 |
| Create tunnel + copy token | 15 |
| Public hostname routing (replaces apex A/AAAA) | 16 |
| `www` → apex redirect rule | 17 |
| Rate limit rule (5 req/min on `/api/card_insight`) | 18 |
| Other CF settings (SSL/TLS, Bot Fight, Cache Rules) | 19 |
| Create Sentry projects (2) | 20 |
| SSH to box, clone repo, run bootstrap.sh | 21 |
| Fetch model file to `/srv/addrlens/models/` | 22 |
| SSH hardening | 23 |
| Fill `/srv/addrlens/.env.production` | 24 |
| First cold build of images | 25 |
| First OSM snapshot | 26 |
| First `up -d` + verify via CF | 27 |
| Configure UptimeRobot probes | 28 |
| Trigger manual OSM refresh + verify timer | 29 |
| Rate limit synthetic verification | 30 |
| Update project CLAUDE.md with prod commands | 31 |

Working directory unless otherwise noted: repo root `v0.1/`.

---

## Task 1: `.gitignore` additions

**Files:**
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nothing
- Produces: `.env.production` and OSM/model artifact patterns are ignored — later tasks rely on this to safely leave these files uncommitted.

- [ ] **Step 1: Read current `.gitignore`**

```bash
cat .gitignore
```

Note existing content; you will append, not overwrite.

- [ ] **Step 2: Append the new entries**

Append the following lines (create the file if it does not exist):

```
# Production runtime state — lives on the box, never in git
.env.production
/srv/

# Large binaries — kept out of the repo; fetched separately on the box
models/*.gguf
data/osm/*.pbf
data/osm/berlin-amenities.json
```

- [ ] **Step 3: Verify no already-tracked file matches the new patterns**

```bash
git ls-files | grep -E '\.env\.production$|\.gguf$|\.pbf$|data/osm/berlin-amenities\.json$' || echo "clean"
```

Expected: `clean`. If any file is listed, do NOT proceed — the ignore pattern would be a no-op for tracked files and the file may need to be `git rm --cached`ed first. Stop and escalate.

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore(deploy): ignore prod env file, model weights, and OSM snapshots"
```

---

## Task 2: `.env.production.example` template

**Files:**
- Create: `.env.production.example`

**Interfaces:**
- Consumes: nothing.
- Produces: variable name contract that `docker-compose.prod.yml` (Task 7) and `app/main.py` (Task 5) + `inference/main.py` (Task 6) rely on. Variable names are: `CITY`, `INFERENCE_URL`, `TUNNEL_TOKEN`, `SENTRY_DSN_APP`, `SENTRY_DSN_INFERENCE`, `SENTRY_ENV`, `GIT_SHA`, `LOG_LEVEL`.

- [ ] **Step 1: Create the file with the exact content below**

```bash
# Template for /srv/addrlens/.env.production on the Hetzner box.
# Copy to /srv/addrlens/.env.production and fill in real values.
# NEVER commit the filled version. .env.production is git-ignored.

# --- App service ---
CITY=berlin
INFERENCE_URL=http://inference:8080
LOG_LEVEL=info

# --- Cloudflare Tunnel ---
# Copy the token from Zero Trust → Networks → Tunnels → addrlens-prod
# (only the token from the "docker run ... --token eyJ..." snippet)
TUNNEL_TOKEN=REPLACE_ME_WITH_CLOUDFLARED_TOKEN

# --- Sentry (EU / Frankfurt region) ---
# Two separate Sentry projects. DSN format: https://<key>@<host>/<project>
SENTRY_DSN_APP=REPLACE_ME_WITH_APP_SENTRY_DSN
SENTRY_DSN_INFERENCE=REPLACE_ME_WITH_INFERENCE_SENTRY_DSN
SENTRY_ENV=production

# --- Release tracking ---
# Written by ops/deploy/update.sh on each deploy — do not set manually.
GIT_SHA=
```

- [ ] **Step 2: Verify file is present and has no stray secrets**

```bash
grep -E "^[A-Z_]+=REPLACE_ME" .env.production.example | wc -l
```

Expected: `3` (TUNNEL_TOKEN, SENTRY_DSN_APP, SENTRY_DSN_INFERENCE).

- [ ] **Step 3: Commit**

```bash
git add .env.production.example
git commit -m "chore(deploy): add production env template"
```

---

## Task 3: `ops/Dockerfile.app` — add prod deps layer

**Files:**
- Modify: `ops/Dockerfile.app`

**Interfaces:**
- Consumes: nothing.
- Produces: an app image that has `sentry-sdk[fastapi]` + `osmium` available at runtime. Task 6 (inference Sentry init) and Task 26 (OSM refresh via app image) depend on these being present.

- [ ] **Step 1: Read the current file**

```bash
cat ops/Dockerfile.app
```

Note the section `RUN uv pip install --system --no-cache -r pyproject.toml` — you will add a new `RUN` layer immediately after it.

- [ ] **Step 2: Apply the edit**

Change the deps layer from:

```dockerfile
# ---- deps layer (cacheable) ----
# Copy the manifest first so `docker build` reuses the deps layer whenever only
# app code has changed.
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -r pyproject.toml

# ---- app layer ----
```

to:

```dockerfile
# ---- deps layer (cacheable) ----
# Copy the manifest first so `docker build` reuses the deps layer whenever only
# app code has changed.
COPY pyproject.toml ./
RUN uv pip install --system --no-cache -r pyproject.toml
# Prod-only deps: Sentry SDK (env-guarded init) + osmium (weekly OSM refresh
# script runs inside this image). Kept out of pyproject.toml to avoid pulling
# them into the local bare-uvicorn dev environment.
RUN uv pip install --system --no-cache \
        "sentry-sdk[fastapi]>=2.0" "osmium>=3.7"

# ---- app layer ----
```

- [ ] **Step 3: Build the image locally to prove the layer resolves**

```bash
docker build -f ops/Dockerfile.app -t addrlens-app:test .
```

Expected: build succeeds. `sentry-sdk` and `osmium` wheels install cleanly. Total image size increase ~15 MB.

If build fails on `osmium` wheel (needs `libboost-python-dev` etc.), STOP and escalate — osmium wheel availability for Debian slim may need `apt-get install` line to be extended.

- [ ] **Step 4: Verify osmium + sentry importable inside the image**

```bash
docker run --rm addrlens-app:test python -c "import osmium, sentry_sdk; print('osmium', osmium.__version__, 'sentry', sentry_sdk.VERSION)"
```

Expected: prints version strings for both.

- [ ] **Step 5: Clean up the test image**

```bash
docker image rm addrlens-app:test
```

- [ ] **Step 6: Commit**

```bash
git add ops/Dockerfile.app
git commit -m "feat(deploy): install sentry-sdk + osmium in app image for prod + OSM refresh"
```

---

## Task 4: `ops/Dockerfile.inference` — remove model bake, add sentry install

**Files:**
- Modify: `ops/Dockerfile.inference`

**Interfaces:**
- Consumes: nothing.
- Produces: an inference image that reads its model from a bind-mounted volume at `/models/`, not from a `COPY`-baked path. Task 7 (compose overlay) provides the mount.

- [ ] **Step 1: Read the current file**

```bash
cat ops/Dockerfile.inference
```

Locate three sections to change: the deps `RUN` line, the `COPY models/...` line, and the `RUN useradd ... chown` line.

- [ ] **Step 2: Apply the edits**

Replace the block:

```dockerfile
# ---- deps layer ----
COPY inference/pyproject.toml ./pyproject.toml
RUN uv pip install --system --no-cache ".[prod]"

# ---- inference code + model ----
COPY inference ./inference
# Bake the GGUF in — plan §7.4 default. Comment out + mount if you'd rather
# ship the model separately.
COPY models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf /models/

RUN useradd -u 10001 -m -s /sbin/nologin addrlens \
    && chown -R addrlens:addrlens /srv /models
USER addrlens
```

with:

```dockerfile
# ---- deps layer ----
COPY inference/pyproject.toml ./pyproject.toml
RUN uv pip install --system --no-cache ".[prod]"
# Prod-only: Sentry SDK. Init in inference/main.py is env-guarded so local
# dev (bare uvicorn on Apple Silicon) is unaffected.
RUN uv pip install --system --no-cache "sentry-sdk[fastapi]>=2.0"

# ---- inference code ----
COPY inference ./inference
# Model file is bind-mounted at runtime from /srv/addrlens/models/ into
# /models/:ro (see docker-compose.prod.yml). The mountpoint must exist.
RUN mkdir -p /models

RUN useradd -u 10001 -m -s /sbin/nologin addrlens \
    && chown -R addrlens:addrlens /srv
USER addrlens
```

Note: the final `chown` no longer includes `/models` — the bind mount inherits the host's ownership, which is `sapta:sapta` (uid may not be 10001, but dir mode is 0755 so read succeeds).

- [ ] **Step 3: Build the image WITHOUT a `models/` directory in the build context**

```bash
# Temporarily rename any local models/ dir if present so we prove the build
# doesn't need it.
if [ -d models ]; then mv models models.bak; fi
docker build -f ops/Dockerfile.inference -t addrlens-inference:test .
BUILD_RC=$?
if [ -d models.bak ]; then mv models.bak models; fi
[ "$BUILD_RC" = "0" ] || { echo "BUILD FAILED"; exit 1; }
```

Expected: build succeeds even with no `models/` directory. Any earlier version would fail here because `COPY models/... /models/` would break.

- [ ] **Step 4: Verify sentry importable**

```bash
docker run --rm addrlens-inference:test python -c "import sentry_sdk; print('sentry', sentry_sdk.VERSION)"
```

Expected: prints a version string.

- [ ] **Step 5: Clean up**

```bash
docker image rm addrlens-inference:test
```

- [ ] **Step 6: Commit**

```bash
git add ops/Dockerfile.inference
git commit -m "feat(deploy): mount inference model as volume; add sentry-sdk to image"
```

---

## Task 5: `app/main.py` — env-guarded Sentry init

**Files:**
- Modify: `app/main.py`

**Interfaces:**
- Consumes: `SENTRY_DSN_APP`, `SENTRY_ENV`, `GIT_SHA` env vars (defined by `.env.production.example` in Task 2).
- Produces: nothing runtime — the init is a side effect of importing.

- [ ] **Step 1: Read the current `app/main.py`**

```bash
cat app/main.py
```

Identify the import block near the top. The insertion point is immediately after the last `import` line and before the `@asynccontextmanager` decorator.

- [ ] **Step 2: Add the Sentry init block**

Insert this block immediately after all existing `import` statements, before the `@asynccontextmanager async def lifespan(app: FastAPI):` line:

```python
# ---------- Sentry (production error tracking) ----------
# Env-guarded: local dev leaves SENTRY_DSN_APP unset, so this block is a no-op
# and sentry_sdk is never imported. Prod-only sentry-sdk dep is installed at
# the Dockerfile layer (see ops/Dockerfile.app), not in pyproject.toml.
if os.environ.get("SENTRY_DSN_APP"):
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN_APP"],
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.1,
        environment=os.environ.get("SENTRY_ENV", "production"),
        release=os.environ.get("GIT_SHA") or None,
    )
```

If `import os` is not already present at the top of the file, add it in the import block. (Reading `os.environ` requires it.)

- [ ] **Step 3: Verify bare uvicorn boots without `SENTRY_DSN_APP` set**

```bash
# Terminal 1 (leave running):
INFERENCE_BACKEND=mlx uvicorn inference.main:app --port 8080 &
INF_PID=$!
sleep 15

# Terminal 2 (main check):
unset SENTRY_DSN_APP
CITY=berlin INFERENCE_URL=http://localhost:8080 \
    uvicorn app.main:app --port 8001 &
APP_PID=$!
sleep 12

curl -sSf http://localhost:8001/health
# Expected: {"status":"ok"}

kill $APP_PID $INF_PID 2>/dev/null
wait 2>/dev/null
```

Expected: `/health` returns `{"status":"ok"}`. If it fails, the Sentry block or its indentation is wrong — Sentry is unset, so it should be inert. Restore and retry.

- [ ] **Step 4: Verify Sentry init path is exercised when DSN is set**

Set a dummy DSN and confirm the process still boots (`sentry_sdk.init` with a bogus DSN logs a warning to stderr but does NOT crash).

```bash
INFERENCE_BACKEND=mlx uvicorn inference.main:app --port 8080 &
INF_PID=$!
sleep 15

SENTRY_DSN_APP="https://public@dummy.ingest.example/1" \
CITY=berlin INFERENCE_URL=http://localhost:8080 \
    uvicorn app.main:app --port 8001 &
APP_PID=$!
sleep 12

curl -sSf http://localhost:8001/health
# Expected: {"status":"ok"} (Sentry may log a network error to stderr — that's fine)

kill $APP_PID $INF_PID 2>/dev/null
wait 2>/dev/null
```

- [ ] **Step 5: Commit**

```bash
git add app/main.py
git commit -m "feat(deploy): add env-guarded Sentry init to app service"
```

---

## Task 6: `inference/main.py` — env-guarded Sentry init

**Files:**
- Modify: `inference/main.py`

**Interfaces:**
- Consumes: `SENTRY_DSN_INFERENCE`, `SENTRY_ENV`, `GIT_SHA` env vars.
- Produces: nothing runtime.

- [ ] **Step 1: Read the current file**

```bash
cat inference/main.py
```

Locate the import block. The insertion point is immediately after all existing top-level `import` statements, before the `# --- config ---` comment (or the first non-import top-level statement).

- [ ] **Step 2: Add the Sentry init block**

Insert this block after the last import in the module's top-of-file import block:

```python
# ---------- Sentry (production error tracking) ----------
# Env-guarded. Local dev (Apple Silicon, INFERENCE_BACKEND=mlx) leaves the DSN
# unset, so this is a no-op and sentry_sdk is never imported.
if os.environ.get("SENTRY_DSN_INFERENCE"):
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=os.environ["SENTRY_DSN_INFERENCE"],
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.1,
        environment=os.environ.get("SENTRY_ENV", "production"),
        release=os.environ.get("GIT_SHA") or None,
    )
```

Confirm `import os` is present at top; add if missing.

- [ ] **Step 3: Verify inference still boots on Apple Silicon (MLX backend)**

```bash
unset SENTRY_DSN_INFERENCE
INFERENCE_BACKEND=mlx uvicorn inference.main:app --port 8080 &
INF_PID=$!
sleep 15

curl -sSf http://localhost:8080/health
# Expected: {"status":"ok"}

# /ready may return 503 during model warm — that's fine; we only test /health here.

kill $INF_PID 2>/dev/null
wait 2>/dev/null
```

Expected: `/health` returns `{"status":"ok"}` with no DSN set.

- [ ] **Step 4: Commit**

```bash
git add inference/main.py
git commit -m "feat(deploy): add env-guarded Sentry init to inference service"
```

---

## Task 7: `docker-compose.prod.yml` — production overlay

**Files:**
- Create: `docker-compose.prod.yml`

**Interfaces:**
- Consumes: the untouched `docker-compose.yml` (base). Bind-mount source paths `/srv/addrlens/data/osm` and `/srv/addrlens/models`. Env file `/srv/addrlens/.env.production`.
- Produces: a compose overlay that Task 25 (`docker compose build`) and Task 27 (`up -d`) load with `-f docker-compose.yml -f docker-compose.prod.yml`.

- [ ] **Step 1: Confirm base compose is unchanged**

```bash
git status docker-compose.yml
# Expected: nothing (or unrelated modifications only)
```

The base file must keep `ports:` on `app` and `inference` for local dev.

- [ ] **Step 2: Create `docker-compose.prod.yml` with the exact content below**

```yaml
# Prod overlay. Load with:
#   docker compose \
#       -f docker-compose.yml \
#       -f docker-compose.prod.yml \
#       --env-file /srv/addrlens/.env.production \
#       up -d
#
# What it changes vs docker-compose.yml:
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

- [ ] **Step 3: Validate compose config parses (locally, without the env file)**

Create a temporary env file for local validation only (this is NOT the real .env.production):

```bash
cat > /tmp/env.prodtest <<'EOF'
CITY=berlin
INFERENCE_URL=http://inference:8080
TUNNEL_TOKEN=dummy
SENTRY_DSN_APP=
SENTRY_DSN_INFERENCE=
SENTRY_ENV=production
GIT_SHA=
LOG_LEVEL=info
EOF

# The compose CLI must accept the overlay + resolve variables.
# Skip the bind-mount source checks by validating config only (no `up`).
mkdir -p /tmp/addrlens-fake/{models,data/osm}
docker compose \
    -f docker-compose.yml \
    -f docker-compose.prod.yml \
    --env-file /tmp/env.prodtest \
    config > /tmp/compose-rendered.yml 2>&1
echo "exit: $?"
```

Expected: exit 0. If it errors on the `!reset []` tag, upgrade Docker Compose plugin locally to ≥ 2.24. Note: this validation is local (macOS Docker Desktop); the actual bind-mount paths point at `/srv/addrlens/...` which don't exist on the Mac — that's fine, `config` doesn't verify mount source existence.

- [ ] **Step 4: Verify the rendered config drops the port publishing**

```bash
grep -A2 "^  app:" /tmp/compose-rendered.yml | head -10
grep -A2 "^  inference:" /tmp/compose-rendered.yml | head -10
```

Expected: no `ports:` line under either service in the rendered config, or if present, an empty list. If `8001:8001` or `8080:8080` still appear, the `!reset []` syntax is not being applied — check Compose version.

- [ ] **Step 5: Verify the dev compose still works alone**

```bash
docker compose config > /tmp/compose-dev-rendered.yml 2>&1
grep -E "8001:8001|8080:8080" /tmp/compose-dev-rendered.yml
```

Expected: both port lines present in dev-only render. This proves the prod overlay is opt-in.

- [ ] **Step 6: Clean up**

```bash
rm -f /tmp/env.prodtest /tmp/compose-rendered.yml /tmp/compose-dev-rendered.yml
rm -rf /tmp/addrlens-fake
```

- [ ] **Step 7: Commit**

```bash
git add docker-compose.prod.yml
git commit -m "feat(deploy): add prod compose overlay with cloudflared, mem limits, bind mounts"
```

---

## Task 8: systemd unit + timer for weekly OSM refresh

**Files:**
- Create: `ops/systemd/refresh-osm-amenities.service`
- Create: `ops/systemd/refresh-osm-amenities.timer`

**Interfaces:**
- Consumes: `docker compose` on the host, the built app image (has osmium from Task 3), the running compose stack.
- Produces: a systemd unit installed by `bootstrap.sh` (Task 9). When fired, the timer runs the refresh script inside a throwaway container reusing the app image, then restarts `app` so its `Index` picks up the new snapshot.

- [ ] **Step 1: Ensure the dir exists**

```bash
mkdir -p ops/systemd
```

- [ ] **Step 2: Create `ops/systemd/refresh-osm-amenities.service`**

```ini
[Unit]
Description=Weekly Berlin OSM amenities refresh (Geofabrik -> filtered JSON)
Wants=network-online.target
After=network-online.target docker.service

[Service]
Type=oneshot
User=sapta
WorkingDirectory=/srv/addrlens/repo/v0.1
ExecStart=/usr/bin/docker compose \
    -f docker-compose.yml -f docker-compose.prod.yml \
    --env-file /srv/addrlens/.env.production \
    run --rm --entrypoint python app \
    -m scripts.refresh_osm_amenities
ExecStartPost=/usr/bin/docker compose \
    -f docker-compose.yml -f docker-compose.prod.yml \
    --env-file /srv/addrlens/.env.production \
    restart app
TimeoutStartSec=30min
StandardOutput=journal
StandardError=journal
```

- [ ] **Step 3: Create `ops/systemd/refresh-osm-amenities.timer`**

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

- [ ] **Step 4: Lint the unit files locally**

Both files use standard systemd syntax. There is no linter check available on macOS; the unit is validated by `systemctl daemon-reload` on the box (bootstrap.sh runs this in Task 21).

Sanity check the file contents:

```bash
grep -c "^\[Unit\]" ops/systemd/refresh-osm-amenities.service
grep -c "^\[Service\]" ops/systemd/refresh-osm-amenities.service
grep -c "^\[Unit\]" ops/systemd/refresh-osm-amenities.timer
grep -c "^\[Timer\]" ops/systemd/refresh-osm-amenities.timer
grep -c "^\[Install\]" ops/systemd/refresh-osm-amenities.timer
```

Expected: all print `1`.

- [ ] **Step 5: Commit**

```bash
git add ops/systemd/refresh-osm-amenities.service ops/systemd/refresh-osm-amenities.timer
git commit -m "feat(deploy): systemd timer for weekly OSM snapshot refresh"
```

---

## Task 9: `ops/deploy/bootstrap.sh` — host provisioning

**Files:**
- Create: `ops/deploy/bootstrap.sh`

**Interfaces:**
- Consumes: a fresh Ubuntu 24.04 host with `sapta` (sudo) as the deploy user; git repo already cloned to `/srv/addrlens/repo` (Task 21 handles the clone).
- Produces: docker installed, ufw enabled, swap active, `/srv/addrlens/` layout, systemd units from Task 8 installed and timer enabled, docker log rotation configured. Idempotent — safe to re-run.

- [ ] **Step 1: Ensure the dir exists**

```bash
mkdir -p ops/deploy
```

- [ ] **Step 2: Create the file with the exact content below**

```bash
#!/usr/bin/env bash
# One-shot Hetzner Ubuntu 24.04 provisioning for addrlens.de.
# Idempotent — safe to re-run after partial failures.
# Invocation (on the box, as root): sudo bash ops/deploy/bootstrap.sh
set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-sapta}"
SRV_ROOT="/srv/addrlens"
REPO_ROOT="${SRV_ROOT}/repo/v0.1"

log() { printf '[bootstrap] %s\n' "$*"; }

if [ "$EUID" -ne 0 ]; then
    echo "bootstrap.sh must run as root (sudo bash ops/deploy/bootstrap.sh)"
    exit 1
fi

# --- 1. System packages -----------------------------------------------------
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg lsb-release \
    ufw fail2ban unattended-upgrades \
    git tzdata

timedatectl set-timezone Europe/Berlin

# --- 2. Docker Engine + Compose plugin --------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    log "installing docker"
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io \
                       docker-buildx-plugin docker-compose-plugin
fi
usermod -aG docker "$DEPLOY_USER"

# --- 3. Directory layout ----------------------------------------------------
mkdir -p "$SRV_ROOT"/{models,data/osm,logs}
chown -R "$DEPLOY_USER:$DEPLOY_USER" "$SRV_ROOT"
touch "$SRV_ROOT/.env.production"
chmod 600 "$SRV_ROOT/.env.production"
chown "$DEPLOY_USER:$DEPLOY_USER" "$SRV_ROOT/.env.production"

# --- 4. Swap (4 GB) — RAM headroom for llama.cpp + Index spikes -------------
if [ ! -f /swapfile ]; then
    log "creating 4 GB swapfile"
    fallocate -l 4G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
    sysctl -w vm.swappiness=10
    grep -q '^vm.swappiness' /etc/sysctl.conf \
        || echo 'vm.swappiness=10' >> /etc/sysctl.conf
fi

# --- 5. Firewall ------------------------------------------------------------
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw --force enable

# --- 6. fail2ban (SSH brute-force protection) -------------------------------
systemctl enable --now fail2ban

# --- 7. Unattended security upgrades ----------------------------------------
dpkg-reconfigure -f noninteractive unattended-upgrades
systemctl enable --now unattended-upgrades

# --- 8. Docker log rotation (avoid 40 GB disk fill) -------------------------
mkdir -p /etc/docker
cat >/etc/docker/daemon.json <<'JSON'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "20m", "max-file": "5" }
}
JSON
systemctl restart docker

# --- 9. Systemd unit for OSM weekly refresh ---------------------------------
if [ -d "$REPO_ROOT/ops/systemd" ]; then
    install -m 0644 "$REPO_ROOT/ops/systemd/refresh-osm-amenities.service" \
        /etc/systemd/system/
    install -m 0644 "$REPO_ROOT/ops/systemd/refresh-osm-amenities.timer" \
        /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable --now refresh-osm-amenities.timer
else
    log "WARN: $REPO_ROOT/ops/systemd not found — clone the repo first, then re-run"
fi

log "bootstrap complete. next:"
log "  1. hf download bartowski/Qwen2.5-1.5B-Instruct-GGUF Qwen2.5-1.5B-Instruct-Q4_K_M.gguf --local-dir $SRV_ROOT/models"
log "  2. fill $SRV_ROOT/.env.production"
log "  3. cd $REPO_ROOT && docker compose -f docker-compose.yml -f docker-compose.prod.yml build"
log "  4. cd $REPO_ROOT && docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm --entrypoint python app -m scripts.refresh_osm_amenities"
log "  5. cd $REPO_ROOT && docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file $SRV_ROOT/.env.production up -d"
```

- [ ] **Step 3: Make it executable**

```bash
chmod +x ops/deploy/bootstrap.sh
```

- [ ] **Step 4: Shell-lint the script**

```bash
bash -n ops/deploy/bootstrap.sh && echo "syntax ok"
```

Expected: `syntax ok`.

If `shellcheck` is available locally, run:

```bash
shellcheck ops/deploy/bootstrap.sh || echo "shellcheck not installed or found issues (review)"
```

Address any severity-error findings before proceeding. Warnings on `mkdir -p` etc. are fine to ignore.

- [ ] **Step 5: Commit**

```bash
git add ops/deploy/bootstrap.sh
git commit -m "feat(deploy): host bootstrap script — docker, ufw, swap, systemd timer install"
```

---

## Task 10: `ops/deploy/update.sh` — ship a new version

**Files:**
- Create: `ops/deploy/update.sh`

**Interfaces:**
- Consumes: the box is already bootstrapped (Task 9 ran) and the stack is running.
- Produces: a deploy runner that pulls the branch, rebuilds, brings the stack up, records the previous SHA for rollback, and gates on `/ready`.

- [ ] **Step 1: Create the file**

```bash
#!/usr/bin/env bash
# Deploy a new version. Build-on-server model — no registry, no CI pull.
# Invocation (on the box, as sapta):
#   cd /srv/addrlens/repo/v0.1 && ./ops/deploy/update.sh
# Optional env: DEPLOY_BRANCH (default: main).
set -euo pipefail

REPO="/srv/addrlens/repo"
BRANCH="${DEPLOY_BRANCH:-main}"
ENV_FILE="/srv/addrlens/.env.production"
COMPOSE=(docker compose \
    -f docker-compose.yml \
    -f docker-compose.prod.yml \
    --env-file "$ENV_FILE")

cd "$REPO"

# --- 1. Record what we're leaving, for possible rollback --------------------
PREV_SHA="$(git rev-parse HEAD)"
echo "$PREV_SHA" > /srv/addrlens/last-deployed.sha
echo "[deploy] leaving $PREV_SHA"

# --- 2. Fetch + fast-forward ------------------------------------------------
git fetch --tags origin
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"
NEW_SHA="$(git rev-parse HEAD)"
echo "[deploy] deploying $NEW_SHA"

# --- 3. Write GIT_SHA into the env file so Sentry release-tracking works ---
# Replace or insert the GIT_SHA line.
if grep -q '^GIT_SHA=' "$ENV_FILE"; then
    sed -i "s|^GIT_SHA=.*|GIT_SHA=${NEW_SHA}|" "$ENV_FILE"
else
    echo "GIT_SHA=${NEW_SHA}" >> "$ENV_FILE"
fi

cd "$REPO/v0.1"

# --- 4. Rebuild only images whose sources changed --------------------------
"${COMPOSE[@]}" build --pull app inference

# --- 5. Recreate containers that need it ------------------------------------
"${COMPOSE[@]}" up -d --remove-orphans

# --- 6. Readiness gate — 90 s budget ---------------------------------------
echo "[deploy] waiting for app /ready"
READY=""
for i in $(seq 1 30); do
    if "${COMPOSE[@]}" exec -T app python -c \
        "import urllib.request,sys; \
         sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8001/ready', timeout=2).status==200 else 1)" \
        2>/dev/null
    then
        READY="1"
        echo "[deploy] app ready after ~$((i*3))s"
        break
    fi
    sleep 3
done
if [ -z "$READY" ]; then
    echo "[deploy] ERROR: app never became ready in 90s. Check logs:"
    echo "[deploy]   ${COMPOSE[*]} logs --tail=100 app"
    echo "[deploy] Rollback with: ./ops/deploy/rollback.sh $PREV_SHA"
    exit 1
fi

# --- 7. Prune dangling images (weekly discipline; safe here) ---------------
docker image prune -f --filter "until=168h"

echo "[deploy] done. deployed $NEW_SHA on top of $PREV_SHA"
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x ops/deploy/update.sh
```

- [ ] **Step 3: Shell-lint**

```bash
bash -n ops/deploy/update.sh && echo "syntax ok"
```

Expected: `syntax ok`.

- [ ] **Step 4: Commit**

```bash
git add ops/deploy/update.sh
git commit -m "feat(deploy): update.sh with readiness gate and SHA-based release tagging"
```

---

## Task 11: `ops/deploy/rollback.sh` — revert to previous SHA

**Files:**
- Create: `ops/deploy/rollback.sh`

**Interfaces:**
- Consumes: `/srv/addrlens/last-deployed.sha` (written by `update.sh`) OR an explicit SHA argument.
- Produces: previous SHA checked out, images rebuilt, containers force-recreated.

- [ ] **Step 1: Create the file**

```bash
#!/usr/bin/env bash
# Rollback to a previous git SHA. Build-on-server means rollback = rebuild.
# Usage: ./rollback.sh <sha>
#    Or: ./rollback.sh  (reads /srv/addrlens/last-deployed.sha)
set -euo pipefail

TARGET="${1:-$(cat /srv/addrlens/last-deployed.sha 2>/dev/null || echo)}"
if [ -z "$TARGET" ]; then
    echo "no target SHA. Usage: $0 <sha>" >&2
    exit 1
fi

REPO="/srv/addrlens/repo"
ENV_FILE="/srv/addrlens/.env.production"
COMPOSE=(docker compose \
    -f docker-compose.yml \
    -f docker-compose.prod.yml \
    --env-file "$ENV_FILE")

echo "[rollback] target: $TARGET"

cd "$REPO"
git fetch --tags origin
git checkout "$TARGET"

# Update GIT_SHA in env file so Sentry release matches.
if grep -q '^GIT_SHA=' "$ENV_FILE"; then
    sed -i "s|^GIT_SHA=.*|GIT_SHA=${TARGET}|" "$ENV_FILE"
else
    echo "GIT_SHA=${TARGET}" >> "$ENV_FILE"
fi

cd "$REPO/v0.1"
"${COMPOSE[@]}" build app inference
"${COMPOSE[@]}" up -d --force-recreate app inference
echo "[rollback] done. now on $TARGET"
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x ops/deploy/rollback.sh
```

- [ ] **Step 3: Shell-lint**

```bash
bash -n ops/deploy/rollback.sh && echo "syntax ok"
```

- [ ] **Step 4: Commit**

```bash
git add ops/deploy/rollback.sh
git commit -m "feat(deploy): rollback.sh — revert to previous SHA and rebuild"
```

---

## Task 12: Operator documentation (`ops/deploy/README.md`, `ops/cloudflared/README.md`)

**Files:**
- Create: `ops/deploy/README.md`
- Create: `ops/cloudflared/README.md`

**Interfaces:**
- Consumes: nothing runtime.
- Produces: on-box operator documentation — first-deploy checklist, SSH hardening, model/env fetch, tunnel token rotation.

- [ ] **Step 1: Create `ops/deploy/README.md`**

```markdown
# Deploy operations — addrlens.de

## First deploy on a fresh box

Prerequisites: Ubuntu 24.04 x86_64, sudo user `sapta`, SSH access.

1. **Clone the repo:**

   ```bash
   ssh sapta@<box-ip>
   sudo mkdir -p /srv/addrlens
   sudo chown sapta:sapta /srv/addrlens
   cd /srv/addrlens
   git clone <git-remote-url> repo
   ```

2. **Bootstrap the host:**

   ```bash
   cd /srv/addrlens/repo/v0.1
   sudo bash ops/deploy/bootstrap.sh
   # Installs docker, ufw, swap, systemd timer. Idempotent.
   ```

3. **Log out and back in** so the `sapta` user picks up the `docker` group.

4. **Fetch the model file** (~1 GB, once):

   ```bash
   pip install --user huggingface_hub[cli]
   hf download bartowski/Qwen2.5-1.5B-Instruct-GGUF \
       Qwen2.5-1.5B-Instruct-Q4_K_M.gguf \
       --local-dir /srv/addrlens/models
   ls -lh /srv/addrlens/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf
   ```

5. **Fill in `/srv/addrlens/.env.production`** using `.env.production.example` as the template. Required values: `TUNNEL_TOKEN`, `SENTRY_DSN_APP`, `SENTRY_DSN_INFERENCE`.

   ```bash
   cp /srv/addrlens/repo/v0.1/.env.production.example /srv/addrlens/.env.production
   chmod 600 /srv/addrlens/.env.production
   vim /srv/addrlens/.env.production
   ```

   After editing, back the file up to your password manager. It is git-ignored and never leaves the box.

6. **Build images cold** (~10 min: llama-cpp-python wheel + shapely + fastapi):

   ```bash
   cd /srv/addrlens/repo/v0.1
   docker compose -f docker-compose.yml -f docker-compose.prod.yml \
       --env-file /srv/addrlens/.env.production \
       build
   ```

7. **Run the first OSM snapshot** (needed BEFORE `up -d` — the app reads this file at boot):

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml \
       --env-file /srv/addrlens/.env.production \
       run --rm --entrypoint python app -m scripts.refresh_osm_amenities
   ls -lh /srv/addrlens/data/osm/berlin-amenities.json
   ```

8. **Bring the stack up:**

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml \
       --env-file /srv/addrlens/.env.production \
       up -d
   docker compose logs -f cloudflared
   # Expect: "Registered tunnel connection connIndex=0 ..."
   ```

9. **Sanity-check through Cloudflare:**

   ```bash
   curl -sSf https://addrlens.de/health   # {"status":"ok"}
   curl -sSf https://addrlens.de/ready    # {"status":"ready","city":"berlin"}
   ```

## Updates

```bash
cd /srv/addrlens/repo/v0.1
./ops/deploy/update.sh
```

## Rollback

```bash
cd /srv/addrlens/repo/v0.1
./ops/deploy/rollback.sh           # to the SHA in /srv/addrlens/last-deployed.sha
./ops/deploy/rollback.sh <sha>     # to any SHA
```

## SSH hardening (not scripted — do manually once)

Auto-modifying `/etc/ssh/sshd_config` risks lockout. After confirming pubkey login works:

```bash
sudo vim /etc/ssh/sshd_config
# Set: PermitRootLogin no
#      PasswordAuthentication no
#      PubkeyAuthentication yes
sudo systemctl reload sshd
# KEEP THE CURRENT SESSION OPEN. Open a NEW terminal, try to SSH in fresh.
# Only close the original session after a fresh session works.
```

Optional: move SSH to a random high port. Update `ufw allow <port>/tcp comment 'SSH'` accordingly.

## Verifying the OSM refresh timer

```bash
systemctl list-timers refresh-osm-amenities.timer
# NEXT column should show next Sunday 03:00.
sudo systemctl start refresh-osm-amenities.service   # force a run now
sudo journalctl -u refresh-osm-amenities.service -n 100 --no-pager
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

- **502 from CF:** origin app is restarting (during `update.sh`), or `cloudflared` lost its connection. Check `docker compose ps` and `docker compose logs cloudflared`.
- **/ready 503 forever:** `Index` boot failed (Berlin WFS down, or OSM snapshot missing). Check `docker compose logs app`. If OSM missing: `ls /srv/addrlens/data/osm/berlin-amenities.json` — should be > 10 MB. If empty, run step 7 above.
- **Inference OOM:** `docker inspect inference | grep -i oom`. If `OOMKilled: true`, the `mem_limit` (2800m) is too tight. Options: increase swap, drop to a smaller quant (Q3_K_M), or upgrade the box.
- **CF Tunnel disconnected:** `docker compose restart cloudflared`. If it keeps failing, `TUNNEL_TOKEN` may be stale — regenerate in the CF dashboard.
```

- [ ] **Step 2: Create `ops/cloudflared/README.md`**

```markdown
# Cloudflare Tunnel — addrlens.de

## Creating the tunnel (once)

1. Cloudflare dashboard → **Zero Trust** → **Networks** → **Tunnels** → **Create a tunnel**.
2. Connector type: **Cloudflared**.
3. Tunnel name: `addrlens-prod`.
4. Environment: **Docker**. The dashboard shows a `docker run cloudflare/cloudflared:latest tunnel --token eyJ...` snippet.
5. Copy **only the token** (the long `eyJ...` string). Paste it into `/srv/addrlens/.env.production` as `TUNNEL_TOKEN=eyJ...`. Ignore the rest of the snippet — the compose file supplies the container spec.

## Public hostname routing

Wizard → **Public Hostnames** step:

| Field | Value |
|---|---|
| Subdomain | *(blank — apex)* |
| Domain | `addrlens.de` |
| Path | *(blank — all paths)* |
| Service Type | HTTP |
| URL | `app:8001` |

**Additional Application Settings:**
- HTTP Host Header: `addrlens.de`
- HTTP2 connection: On
- Connection timeout: 30 s

The wizard automatically creates a proxied CNAME `addrlens.de` → `<tunnel-id>.cfargotunnel.com`. If existing A/AAAA records exist on apex, accept the wizard's "replace" prompt.

## Token rotation

If the token is compromised or you want to rotate:

1. CF dashboard → Zero Trust → Networks → Tunnels → `addrlens-prod` → delete.
2. Create a new tunnel with the same public hostname config.
3. Update `TUNNEL_TOKEN=` in `/srv/addrlens/.env.production` on the box.
4. `docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file /srv/addrlens/.env.production up -d cloudflared` — restarts only cloudflared with the new token.

## Troubleshooting

- **Tunnel status "disconnected" in CF dashboard:**
  ```bash
  docker compose logs cloudflared --tail=100
  ```
  Look for auth failures (rotate token) or network errors (check outbound 443).

- **Users see CF error page but origin is healthy:**
  Check CF dashboard → Zero Trust → Networks → Tunnels for connection status.
  ```bash
  docker compose restart cloudflared
  ```

- **Want to bypass CF for debugging:** you can't — the box has no public port other than SSH. Debug via `curl -sSf http://localhost:8001/health` from inside the box (or `docker compose exec app curl -sSf http://127.0.0.1:8001/health`).
```

- [ ] **Step 3: Commit**

```bash
mkdir -p ops/cloudflared
git add ops/deploy/README.md ops/cloudflared/README.md
git commit -m "docs(deploy): first-deploy checklist, tunnel setup, ops runbook"
```

---

## Task 13: Local-dev preservation verification (last check before touching prod)

**Files:**
- Modify: none
- Test: run the local dev flow end-to-end

**Interfaces:**
- Consumes: all repo changes from Tasks 1-12.
- Produces: proof that bare-uvicorn dev on Apple Silicon still works. This gates the entire prod push.

- [ ] **Step 1: Fresh base install**

```bash
uv pip install --system -r pyproject.toml
```

Expected: succeeds. Base deps only — no `sentry-sdk`, no `osmium` (those are Dockerfile-layer only).

- [ ] **Step 2: Reinstall inference dev extra (MLX)**

```bash
uv pip install --system -e "inference[dev]"
```

Expected: succeeds. `mlx-lm` installs on Apple Silicon.

- [ ] **Step 3: Verify Sentry SDK is NOT installed locally**

```bash
python -c "import sentry_sdk" 2>&1
```

Expected: `ModuleNotFoundError: No module named 'sentry_sdk'`. This proves local dev does NOT pull the prod-only dep.

- [ ] **Step 4: Boot inference (bare, MLX)**

```bash
unset SENTRY_DSN_INFERENCE
INFERENCE_BACKEND=mlx uvicorn inference.main:app --port 8080 &
INF_PID=$!
sleep 20
curl -sSf http://localhost:8080/health
# Expected: {"status":"ok"}
```

- [ ] **Step 5: Boot app (bare)**

```bash
unset SENTRY_DSN_APP
CITY=berlin INFERENCE_URL=http://localhost:8080 \
    uvicorn app.main:app --port 8001 &
APP_PID=$!
sleep 15
curl -sSf http://localhost:8001/health
# Expected: {"status":"ok"}
curl -sSf http://localhost:8001/ready
# Expected: 200 with body {"status":"ready","city":"berlin"} (or 503 "loading" if Index still building — wait 10 s and retry)
```

- [ ] **Step 6: Run selfcheck**

```bash
python -m app.selfcheck
# Expected: all assertions pass
```

- [ ] **Step 7: Stop background processes**

```bash
kill $APP_PID $INF_PID 2>/dev/null
wait 2>/dev/null
```

- [ ] **Step 8: Verify dev docker-compose still boots without prod overlay**

```bash
docker compose up -d
sleep 30
curl -sSf http://localhost:8001/health
# Expected: {"status":"ok"}
docker compose down
```

- [ ] **Step 9: Gate check — if ANY step 1-8 failed, DO NOT PROCEED to prod tasks.**

Roll back the failed edit, fix, and re-run this task. This is the last local-only gate.

- [ ] **Step 10: Tag the local-verified commit (optional but recommended)**

```bash
git tag -a "prod-ready-$(date +%Y%m%d)" -m "Local dev flow verified; ready to deploy"
```

---

## Task 14: DNS migration in Cloudflare dashboard (BEFORE tunnel wizard)

**Files:** none (dashboard actions)

**Interfaces:**
- Consumes: current DNS state on `addrlens.de` as documented in spec §7.1.
- Produces: `www.addrlens.de` is a proxied CNAME to `addrlens.de`. Apex A/AAAA still exist and will be replaced by the tunnel wizard in Task 16.

**Order gate:** this task MUST complete before Task 16 (Public Hostname). Do NOT skip.

- [ ] **Step 1: Open the DNS records page**

Navigate to Cloudflare dashboard → `addrlens.de` → **DNS** → **Records**.

- [ ] **Step 2: Delete `www.addrlens.de` AAAA record**

Find the row: name `www`, type `AAAA`, content `2a01:4f8:d0a:27bd::2`, Proxied.
Click the row → **Edit** → **Delete**.

Confirm the deletion.

- [ ] **Step 3: Change `www.addrlens.de` A record to a CNAME**

Find the row: name `www`, type `A`, content `88.198.219.246`, Proxied.
Click **Edit**:
- Type: **CNAME**
- Name: `www`
- Target: `addrlens.de`
- Proxy status: **Proxied**
- TTL: Auto

Save.

- [ ] **Step 4: Verify from an external resolver**

Wait ~30 s for propagation (CF is fast), then:

```bash
dig +short A www.addrlens.de @1.1.1.1
# Expected: same CF anycast IPs as apex (172.67.* or 104.21.*)
dig +short AAAA www.addrlens.de @1.1.1.1
# Expected: same CF IPv6 as apex (2606:4700:*)
dig +short CNAME www.addrlens.de @1.1.1.1
# CF flattens CNAMEs at proxy — this may be empty; that's expected.
```

- [ ] **Step 5: Verify mail records are UNTOUCHED**

Check the DNS records page — these must still be present:

- `addrlens.de` MX → `www4.your-server.de`
- `autoconfig.addrlens.de` CNAME → `mail.your-server.de` (Proxied)
- `_autodiscover._tcp.addrlens.de` SRV
- `_imaps._tcp.addrlens.de` SRV
- `_pop3s._tcp.addrlens.de` SRV
- `_submission._tcp.addrlens.de` SRV
- `addrlens.de` TXT `"v=spf1 +a +mx ?all"`

If ANY of these is missing, restore from CF's audit log before proceeding.

- [ ] **Step 6: Send yourself a test email to `informsapta@addrlens.de` (or whatever mailbox you use)**

Verify mail still delivers. If mail is broken, restore mail records before touching the tunnel wizard.

---

## Task 15: Create Cloudflare Tunnel and copy token

**Files:** none

**Interfaces:**
- Consumes: nothing.
- Produces: a running-ready `TUNNEL_TOKEN` string to be placed into `.env.production` in Task 24.

- [ ] **Step 1: Navigate**

CF dashboard → **Zero Trust** → **Networks** → **Tunnels** → **Create a tunnel**.

- [ ] **Step 2: Configure the tunnel**

- Connector type: **Cloudflared**
- Tunnel name: `addrlens-prod`
- Save. Advance to the "Choose your environment" screen.
- Environment: **Docker**.

- [ ] **Step 3: Copy the token**

The dashboard shows a snippet like:

```
docker run cloudflare/cloudflared:latest tunnel --token eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9....
```

Copy ONLY the token (the `eyJ...` string, everything after `--token `). Store it temporarily in a password manager entry called `addrlens.de TUNNEL_TOKEN`. Do NOT paste into any file yet — Task 24 handles that.

- [ ] **Step 4: DO NOT run the shown docker command locally.** The compose file handles it. Proceed to the next dashboard step (Public Hostnames) — Task 16.

---

## Task 16: Public hostname routing (replaces apex A/AAAA)

**Files:** none

**Interfaces:**
- Consumes: the tunnel created in Task 15, DNS migration from Task 14.
- Produces: apex `addrlens.de` becomes a proxied CNAME to `<tunnel-id>.cfargotunnel.com`. The wizard replaces the existing apex A + AAAA.

**Order gate:** Task 14 (DNS migration) MUST be complete.

- [ ] **Step 1: In the tunnel wizard, Public Hostnames step, click "Add a public hostname"**

Configure:

| Field | Value |
|---|---|
| Subdomain | *(leave blank — apex)* |
| Domain | `addrlens.de` |
| Path | *(leave blank)* |
| Type | `HTTP` |
| URL | `app:8001` |

- [ ] **Step 2: Expand "Additional Application Settings"**

- HTTP Host Header: `addrlens.de`
- HTTP2 connection: **On**
- Connection timeout: `30s`
- Leave everything else at defaults.

- [ ] **Step 3: Save**

The wizard will detect the existing A + AAAA records on apex and prompt something like: *"The DNS record for addrlens.de already exists. Do you want to overwrite it?"*

**Accept the overwrite.**

If the wizard silently succeeds (no prompt), verify manually in the next step.

- [ ] **Step 4: Verify DNS**

Navigate to DNS → Records. Confirm:

- `addrlens.de` is now a **CNAME** to `<tunnel-id>.cfargotunnel.com`, Proxied.
- The old A record on apex (`88.198.219.246`) is gone.
- The old AAAA on apex (`2a01:4f8:d0a:27bd::2`) is gone.
- Mail records (MX, SRV, TXT, autoconfig CNAME) are UNTOUCHED.

If any apex A/AAAA remains, delete it manually.

- [ ] **Step 5: Verify from external resolver**

```bash
dig +short A addrlens.de @1.1.1.1
# Expected: CF anycast IPs
dig +short AAAA addrlens.de @1.1.1.1
# Expected: CF IPv6

# Note: the origin isn't running yet (Task 25-27). CF will show 502 or 5xx.
# That's expected. DNS resolution is what matters at this step.
```

---

## Task 17: `www` → apex redirect rule

**Files:** none

**Interfaces:**
- Consumes: the redirected `www` CNAME from Task 14.
- Produces: `https://www.addrlens.de/*` → 301 → `https://addrlens.de/*` (preserving query string).

- [ ] **Step 1: Navigate**

CF dashboard → `addrlens.de` → **Rules** → **Redirect Rules** → **Create rule**.

- [ ] **Step 2: Configure**

- Rule name: `www to apex`
- When incoming requests match: click **Custom filter expression** editor if needed, or use the visual builder:
  - Field: **Hostname**
  - Operator: **equals**
  - Value: `www.addrlens.de`
- Then:
  - Type: **Static** → change to **Dynamic**
  - Expression: `concat("https://addrlens.de", http.request.uri.path)`
  - Status code: **301**
  - Preserve query string: **On**

- [ ] **Step 3: Deploy the rule**

Click **Save** or **Deploy**.

- [ ] **Step 4: Verify (after Task 27's stack is up)** — deferred

Return to this once the stack is live:

```bash
curl -sSI https://www.addrlens.de/health
# Expected: HTTP/2 301, Location: https://addrlens.de/health
```

---

## Task 18: Rate limit rule on `/api/card_insight`

**Files:** none

**Interfaces:**
- Consumes: the CF Free plan's 1 rate limiting rule slot.
- Produces: 5 req/min per IP on `/api/card_insight` returns 429.

- [ ] **Step 1: Navigate**

CF dashboard → `addrlens.de` → **Security** → **WAF** → **Rate limiting rules** → **Create rule**.

- [ ] **Step 2: Configure**

- Rule name: `insight-per-ip`
- **When incoming requests match:**
  - Field: **URI Path**
  - Operator: **contains**
  - Value: `/api/card_insight`
- **Rate limit characteristics:**
  - Requests: `5`
  - Period: `1 minute`
- **Then:**
  - Action: **Custom response**
  - Response code: `429`
  - Response body: `{"error":"rate_limited","retry_after_s":60}`
  - Response header: `Content-Type: application/json`
- **Duration of the block:** `60 seconds`

- [ ] **Step 3: Deploy the rule**

Click **Deploy**.

- [ ] **Step 4: Verify (after Task 27's stack is up)** — deferred

Return to this once the stack is live. Task 30 covers the synthetic test.

---

## Task 19: Other CF settings (SSL/TLS, Bot Fight, Cache Rules, minify)

**Files:** none

- [ ] **Step 1: SSL/TLS**

CF dashboard → `addrlens.de` → **SSL/TLS** → **Overview**.

- Mode: **Full**.

- [ ] **Step 2: Always Use HTTPS**

SSL/TLS → **Edge Certificates** → **Always Use HTTPS**: **On**.

- [ ] **Step 3: Automatic HTTPS Rewrites**

Same page → **Automatic HTTPS Rewrites**: **On**.

- [ ] **Step 4: Bot Fight Mode**

**Security** → **Bots** → **Bot Fight Mode**: **On**.

- [ ] **Step 5: Security Level**

**Security** → **Settings** → **Security Level**: **Medium** (default).

- [ ] **Step 6: Cache Rule — bypass `/api/`**

**Rules** → **Cache Rules** → **Create rule**.

- Rule name: `bypass-api`
- When: URI Path **starts with** `/api/`
- Then: **Bypass cache**
- Deploy.

- [ ] **Step 7: Cache Rule — cache `/static/`**

Create another Cache Rule.

- Rule name: `cache-static`
- When: URI Path **starts with** `/static/`
- Then: **Cache eligible**
  - Edge TTL: **1 day**
  - Browser TTL: **1 hour**
- Deploy.

- [ ] **Step 8: Speed → Auto Minify**

**Speed** → **Optimization** → **Auto Minify**: all off (JS, CSS, HTML unchecked).

---

## Task 20: Create Sentry projects (2)

**Files:** none

**Interfaces:**
- Consumes: nothing.
- Produces: two DSNs for Task 24 to paste into `.env.production` (`SENTRY_DSN_APP`, `SENTRY_DSN_INFERENCE`).

- [ ] **Step 1: Sign up / log in at `https://sentry.io/`**

Region: **EU (Frankfurt)** at signup. If your account is already US-region, create a new EU-region account (Sentry does not allow region migration).

- [ ] **Step 2: Create the app project**

Sentry → **Projects** → **Create Project**.
- Platform: **Python — FastAPI**.
- Alert frequency: default.
- Name: `addrlens-app`.
- Team: default.

After creation, Sentry shows a "Configure Python SDK" screen. Copy the DSN — format: `https://<key>@<host>.ingest.de.sentry.io/<project-id>`.

Store it temporarily as `SENTRY_DSN_APP` in your password manager.

- [ ] **Step 3: Create the inference project**

Same flow.
- Platform: **Python — FastAPI**.
- Name: `addrlens-inference`.

Copy its DSN, store as `SENTRY_DSN_INFERENCE`.

- [ ] **Step 4: Configure alerts to `informsapta@gmail.com`**

For each project → **Settings** → **Alerts** → **Alert Rules**. Ensure the default rule (new issue → send email) points at `informsapta@gmail.com`.

- [ ] **Step 5: Note the environment tag** — the code uses `SENTRY_ENV=production` (Task 24 sets this). All events on the box will land under `environment: production` in Sentry.

---

## Task 21: SSH to box, clone repo, run `bootstrap.sh`

**Files:** none (host actions)

**Interfaces:**
- Consumes: `ops/deploy/bootstrap.sh` from Task 9, systemd units from Task 8.
- Produces: box is provisioned — docker installed, ufw enabled, swap active, `/srv/addrlens/` layout, systemd timer registered.

- [ ] **Step 1: SSH in**

```bash
ssh sapta@<box-ip>
```

- [ ] **Step 2: Create the deploy root and clone**

```bash
sudo mkdir -p /srv/addrlens
sudo chown sapta:sapta /srv/addrlens
cd /srv/addrlens
git clone <git-remote-url> repo
```

Replace `<git-remote-url>` with the actual URL (GitHub SSH clone URL if the box has a deploy key, or HTTPS with a PAT). Verify:

```bash
ls /srv/addrlens/repo/v0.1/ops/deploy/bootstrap.sh
# Expected: file exists
```

- [ ] **Step 3: Run bootstrap**

```bash
cd /srv/addrlens/repo/v0.1
sudo bash ops/deploy/bootstrap.sh
```

Expected: script completes with `[bootstrap] bootstrap complete.` followed by the "next steps" hints.

- [ ] **Step 4: Log out and back in** so `sapta` picks up the `docker` group.

```bash
exit
ssh sapta@<box-ip>
docker ps
# Expected: no permission error. Empty table is fine.
```

- [ ] **Step 5: Verify swap active**

```bash
free -h
# Expected: Swap line shows 4.0 GiB
```

- [ ] **Step 6: Verify ufw**

```bash
sudo ufw status
# Expected: Status: active, 22/tcp ALLOW
```

- [ ] **Step 7: Verify systemd timer registered**

```bash
systemctl list-timers refresh-osm-amenities.timer
# Expected: shows the timer with NEXT column = next Sunday 03:00
```

---

## Task 22: Fetch model file to `/srv/addrlens/models/`

**Files:** none (host action)

**Interfaces:**
- Consumes: `hf` CLI installed on the box.
- Produces: `/srv/addrlens/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf` (~1 GB).

- [ ] **Step 1: Install the huggingface CLI**

```bash
pip install --user huggingface_hub[cli]
# Verify:
~/.local/bin/hf --version
```

If `hf` is not on `$PATH`, add `~/.local/bin` to `$PATH` in `~/.bashrc`.

- [ ] **Step 2: Download the model**

```bash
cd /srv/addrlens/models
hf download bartowski/Qwen2.5-1.5B-Instruct-GGUF \
    Qwen2.5-1.5B-Instruct-Q4_K_M.gguf \
    --local-dir .
```

Expected: file lands at `/srv/addrlens/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf` (~1.0 GB). Download time depends on box's network — Hetzner Falkenstein → HuggingFace CDN is typically 10-30 s.

- [ ] **Step 3: Verify file size + permissions**

```bash
ls -lh /srv/addrlens/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf
# Expected: -rw-r--r-- (mode 0644 or 0664), owner sapta, size ~1.0G
```

If the mode has no read for "other", `chmod 0644` the file. Container uid 10001 must be able to read it.

- [ ] **Step 4: Verify total disk usage is within budget**

```bash
df -h /srv
# Expected: /srv on the root FS with plenty of headroom (< 30% used after model + repo).
```

---

## Task 23: SSH hardening (manual, once)

**Files:** `/etc/ssh/sshd_config` on the box (not in repo)

**Interfaces:**
- Consumes: pubkey-authenticated `sapta` SSH access already working.
- Produces: no password auth, no root SSH.

- [ ] **Step 1: Verify pubkey works BEFORE tightening**

Log in from your Mac with the SSH key. If it prompts for a password, STOP — set up the key first (`ssh-copy-id sapta@<box-ip>` from your Mac).

- [ ] **Step 2: Edit sshd_config**

```bash
sudo vim /etc/ssh/sshd_config
```

Set (or add if missing):

```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

Save.

- [ ] **Step 3: Reload sshd (KEEP THE CURRENT SESSION OPEN)**

```bash
sudo systemctl reload sshd
```

- [ ] **Step 4: In a NEW terminal, try to SSH in**

```bash
ssh sapta@<box-ip>
```

Expected: succeeds via key. If it fails, the current terminal (still open) can undo — revert the sshd_config changes and reload. Do NOT close the original session until the fresh session works.

- [ ] **Step 5: (Optional) change SSH port**

Not required. If you want to reduce log noise from bots:

```bash
sudo vim /etc/ssh/sshd_config
# Set: Port 2222 (or any random high port)
sudo ufw allow 2222/tcp comment 'SSH'
sudo systemctl reload sshd
# Verify fresh session with: ssh -p 2222 sapta@<box-ip>
sudo ufw delete allow 22/tcp
```

---

## Task 24: Fill `/srv/addrlens/.env.production`

**Files:** `/srv/addrlens/.env.production` on the box

**Interfaces:**
- Consumes: `TUNNEL_TOKEN` from Task 15, `SENTRY_DSN_APP` + `SENTRY_DSN_INFERENCE` from Task 20.
- Produces: env file the compose overlay (Task 7) reads on every `docker compose ... up`.

- [ ] **Step 1: Copy the template**

```bash
cp /srv/addrlens/repo/v0.1/.env.production.example /srv/addrlens/.env.production
chmod 600 /srv/addrlens/.env.production
```

- [ ] **Step 2: Fill values**

```bash
vim /srv/addrlens/.env.production
```

Replace the three `REPLACE_ME_...` values with the real ones from your password manager. Leave `GIT_SHA=` empty — `update.sh` writes it.

- [ ] **Step 3: Verify permissions and ownership**

```bash
ls -l /srv/addrlens/.env.production
# Expected: -rw------- 1 sapta sapta ... (mode 0600)
```

- [ ] **Step 4: Sanity-check with a dry compose config**

```bash
cd /srv/addrlens/repo/v0.1
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --env-file /srv/addrlens/.env.production \
    config | grep -E "TUNNEL_TOKEN|SENTRY_DSN" | head -10
```

Expected: values appear in the render (as environment vars on containers). If the token or DSNs show as empty or `REPLACE_ME_...`, re-open the file and fix.

- [ ] **Step 5: Back up the filled file to your password manager**

Copy the entire contents of `.env.production` into a password-manager entry named `addrlens.de .env.production`. This file lives only on the box; if the box dies you need it to rebuild.

---

## Task 25: First cold build of images

**Files:** none (host action)

**Interfaces:**
- Consumes: repo cloned (Task 21), Dockerfiles from Tasks 3-4.
- Produces: local docker images `addrlens_app` + `addrlens_inference` on the box, ready to run.

- [ ] **Step 1: Build**

```bash
cd /srv/addrlens/repo/v0.1
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --env-file /srv/addrlens/.env.production \
    build
```

Expected: ~5-10 min cold build on 2 vCPU. `llama-cpp-python` wheel is the slowest layer. If it fails on wheel build (unlikely on 24.04 x86_64), STOP and escalate.

- [ ] **Step 2: Verify images built**

```bash
docker images | grep addrlens
# Expected: 2 rows (app, inference), sizes roughly 300-500 MB each
```

- [ ] **Step 3: Verify the model can be read from inside the inference image**

```bash
docker run --rm \
    -v /srv/addrlens/models:/models:ro \
    -e LLAMA_MODEL_PATH=/models/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf \
    v01-inference \
    python -c "import os; print(os.path.getsize(os.environ['LLAMA_MODEL_PATH']))"
```

Adjust the image name if `docker images` shows a different tag (`v0.1-inference`, `addrlens-inference`, etc.). Expected: prints a number roughly `990000000` (~1 GB).

If the file is unreadable, check `ls -l /srv/addrlens/models/`; the mode must be `0644`+ with world-read.

---

## Task 26: First OSM snapshot

**Files:** creates `/srv/addrlens/data/osm/berlin-amenities.json` + `/srv/addrlens/data/osm/berlin-latest.osm.pbf`

**Interfaces:**
- Consumes: built app image (Task 25), network to `download.geofabrik.de`.
- Produces: filtered JSON snapshot the app's `Index` reads on boot.

**Order gate:** MUST run BEFORE Task 27's `up -d`.

- [ ] **Step 1: Run the refresh script inside a throwaway container**

```bash
cd /srv/addrlens/repo/v0.1
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --env-file /srv/addrlens/.env.production \
    run --rm --entrypoint python app \
    -m scripts.refresh_osm_amenities
```

Expected output includes lines about downloading `berlin-latest.osm.pbf` (~94 MB), filtering, and writing `berlin-amenities.json`. Runtime: ~1 min.

- [ ] **Step 2: Verify outputs**

```bash
ls -lh /srv/addrlens/data/osm/
# Expected:
#   berlin-amenities.json  ~13 MB
#   berlin-latest.osm.pbf  ~94 MB
```

- [ ] **Step 3: Sanity-check JSON is well-formed and non-empty**

```bash
python3 -c "import json; d=json.load(open('/srv/addrlens/data/osm/berlin-amenities.json')); print(sum(len(v) for v in d.values() if isinstance(v, list)))"
# Expected: a positive integer (thousands of features)
```

If parsing fails, the refresh script failed silently — re-run step 1 and read the logs.

---

## Task 27: First `up -d` and CF verification

**Files:** none (host action)

**Interfaces:**
- Consumes: images built (Task 25), OSM snapshot present (Task 26), env file filled (Task 24), CF Tunnel + routing configured (Tasks 15-19).
- Produces: live prod stack answering at `https://addrlens.de`.

- [ ] **Step 1: Bring the stack up**

```bash
cd /srv/addrlens/repo/v0.1
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --env-file /srv/addrlens/.env.production \
    up -d
```

Expected: 3 containers start. `inference` warms in background (30-60 s to model load). `cloudflared` connects to CF edge.

- [ ] **Step 2: Watch cloudflared connect**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --env-file /srv/addrlens/.env.production \
    logs -f cloudflared
```

Expected log line within ~5 s: `Registered tunnel connection connIndex=0 ... location=fra-XX`. If it repeats "reconnecting" for >30 s, the `TUNNEL_TOKEN` is wrong — recheck `.env.production`.

Ctrl-C out of the log tail once you see the registration.

- [ ] **Step 3: Verify app /health from inside the box**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --env-file /srv/addrlens/.env.production \
    exec app curl -sSf http://127.0.0.1:8001/health
# Expected: {"status":"ok"}
```

- [ ] **Step 4: Verify app /ready — wait for Index to build (~15 s)**

```bash
for i in $(seq 1 20); do
    docker compose -f docker-compose.yml -f docker-compose.prod.yml \
        --env-file /srv/addrlens/.env.production \
        exec -T app curl -sSf http://127.0.0.1:8001/ready 2>/dev/null && break
    echo "waiting ready... $i"
    sleep 3
done
```

Expected: eventually `{"status":"ready","city":"berlin"}`.

- [ ] **Step 5: Verify inference /ready — wait for model warm (~30-60 s)**

```bash
for i in $(seq 1 30); do
    docker compose -f docker-compose.yml -f docker-compose.prod.yml \
        --env-file /srv/addrlens/.env.production \
        exec -T inference curl -sSf http://127.0.0.1:8080/ready 2>/dev/null && break
    echo "waiting inference ready... $i"
    sleep 3
done
```

Expected: eventually `{"ready":true,...}`.

- [ ] **Step 6: Verify through Cloudflare (external check)**

From your Mac (not the box):

```bash
curl -sSf https://addrlens.de/health
# Expected: {"status":"ok"}

curl -sSf https://addrlens.de/ready
# Expected: {"status":"ready","city":"berlin"}

curl -sSI https://www.addrlens.de/
# Expected: HTTP/2 301, Location: https://addrlens.de/
```

- [ ] **Step 7: Open `https://addrlens.de/` in a browser**

Verify the SPA loads. Do a full address lookup (e.g., a real Berlin address) and confirm tiles render, provenance shows up.

- [ ] **Step 8: If any of steps 3-7 fails:**

Check container status and logs:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --env-file /srv/addrlens/.env.production ps
docker compose logs --tail=200 app
docker compose logs --tail=200 inference
docker compose logs --tail=200 cloudflared
```

If a service is unhealthy, common causes:
- **app 503 forever:** OSM snapshot missing — verify `/srv/addrlens/data/osm/berlin-amenities.json` exists.
- **inference OOMKilled:** `docker inspect inference | grep -i oom`. Increase swap or drop mem_limit expectations.
- **cloudflared reconnecting:** wrong `TUNNEL_TOKEN`.

Do NOT proceed to Task 28 until steps 3-7 all pass.

---

## Task 28: Configure UptimeRobot probes

**Files:** none (UptimeRobot dashboard)

**Interfaces:**
- Consumes: live URLs from Task 27.
- Produces: two HTTP monitors alerting `informsapta@gmail.com` on failure.

- [ ] **Step 1: Sign up / log in at `https://uptimerobot.com/`**

Free tier: 50 monitors, 5-min interval.

- [ ] **Step 2: Add monitor "addrlens.de /health"**

- Type: **HTTP(s)**
- Friendly name: `addrlens.de /health`
- URL: `https://addrlens.de/health`
- Interval: **5 minutes**
- Keyword monitoring: **Keyword exists** → keyword `"ok"`
- Alert contact: `informsapta@gmail.com` (add if not already)
- Create.

- [ ] **Step 3: Add monitor "addrlens.de /ready"**

- Type: **HTTP(s)**
- Friendly name: `addrlens.de /ready`
- URL: `https://addrlens.de/ready`
- Interval: **5 minutes**
- Keyword monitoring: **Keyword exists** → keyword `"berlin"`
- Alert contact: same
- Create.

- [ ] **Step 4: Trigger a synthetic failure to verify alerting**

Only if you want to prove the pipeline. Not required — creating the monitors is sufficient for v1.

- [ ] **Step 5: Verify both monitors go green within 5 min**

Dashboard should show both monitors "UP".

---

## Task 29: Trigger manual OSM refresh + verify timer schedule

**Files:** none (host action)

**Interfaces:**
- Consumes: systemd units installed (bootstrap.sh from Task 21), OSM snapshot fetched (Task 26).
- Produces: proof that the weekly cron path works.

- [ ] **Step 1: Trigger the service manually**

```bash
sudo systemctl start refresh-osm-amenities.service
```

Expected: returns quickly (fires the oneshot). The service will download+filter+restart in background. Runtime: ~1-2 min.

- [ ] **Step 2: Watch the run**

```bash
sudo journalctl -u refresh-osm-amenities.service -n 200 --no-pager -f
```

Expected: log lines from the refresh script (download progress, filter, restart of `app` container). Wait until you see "Deactivated successfully".

Ctrl-C.

- [ ] **Step 3: Confirm the JSON was rewritten**

```bash
stat -c '%y %s' /srv/addrlens/data/osm/berlin-amenities.json
# Expected: modified time = just now, size ~13 MB
```

- [ ] **Step 4: Verify app is healthy after the restart**

```bash
curl -sSf https://addrlens.de/ready
# Expected: {"status":"ready","city":"berlin"}
```

- [ ] **Step 5: Confirm the timer schedule**

```bash
systemctl list-timers refresh-osm-amenities.timer
# Expected: NEXT column = upcoming Sunday 03:00
```

---

## Task 30: Rate limit synthetic verification

**Files:** none

**Interfaces:**
- Consumes: live `https://addrlens.de/api/card_insight` endpoint, CF rate limit rule from Task 18.
- Produces: proof that the rate limit fires at ~5 req/min.

- [ ] **Step 1: Prepare a request body**

Use whatever payload the `/api/card_insight` endpoint expects. Check the code:

```bash
grep -n "card_insight" app/routes/*.py
```

Craft a valid POST body (or a GET if that's the actual method). Save to `/tmp/insight-body.json`.

If crafting a real payload is tricky, just hit the endpoint 8 times fast with an empty JSON body — the rate limit fires at CF edge before the request reaches origin, so the payload doesn't need to be valid.

- [ ] **Step 2: Fire 8 requests in ~10 s from your Mac**

```bash
for i in $(seq 1 8); do
    HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}\n" \
        -X POST "https://addrlens.de/api/card_insight" \
        -H "Content-Type: application/json" \
        -d @/tmp/insight-body.json 2>/dev/null || echo "err")
    echo "req $i: $HTTP_CODE"
    sleep 1
done
```

Expected: first ~5 requests return normal HTTP codes (200 / 4xx / 5xx depending on payload). Requests 6-8 return **429**.

- [ ] **Step 3: Verify the 429 body**

```bash
curl -sS -X POST "https://addrlens.de/api/card_insight" \
    -H "Content-Type: application/json" -d '{}' -w "\n%{http_code}\n"
```

Expected (still within the block window): `{"error":"rate_limited","retry_after_s":60}` followed by `429`.

- [ ] **Step 4: Wait 60 s, verify unblocking**

Then a single request should succeed again (or at least not 429).

- [ ] **Step 5: If the rate limit doesn't fire:**

- Check CF dashboard → Security → Events. Look for a rule match on your test.
- Verify rule status is Enabled.
- Verify URI Path field matches your endpoint (`/api/card_insight` — not `/api/insight/`).

---

## Task 31: Update v0.1/CLAUDE.md with prod commands

**Files:**
- Modify: `v0.1/CLAUDE.md`

**Interfaces:**
- Consumes: nothing.
- Produces: on-repo documentation of the prod deploy commands so a future maintainer (or a future you) doesn't have to re-read the design doc.

- [ ] **Step 1: Read the current CLAUDE.md**

```bash
cat v0.1/CLAUDE.md
```

Note the existing "Commands" section — you'll add a new "Production" subsection.

- [ ] **Step 2: Add a new section after the existing Commands section**

Append the following after the existing Commands section (before `## Architecture`):

```markdown
## Production deploy (Hetzner Falkenstein → addrlens.de)

Design doc: `docs/superpowers/specs/2026-08-15-docker-microservice-deploy-design.md`
Implementation plan: `docs/superpowers/plans/2026-08-15-docker-microservice-deploy.md`
Ops runbook: `ops/deploy/README.md`

Stack: three docker containers (`app`, `inference`, `cloudflared`) on an internal
bridge. `cloudflared` is the only ingress; no public port other than SSH. Model
file and OSM snapshot bind-mounted from `/srv/addrlens/{models,data/osm}` — never
baked into images.

Deploy a new version (on the box, as `sapta`):

```bash
cd /srv/addrlens/repo/v0.1
./ops/deploy/update.sh                 # git pull, rebuild, up -d, /ready gate
./ops/deploy/rollback.sh               # revert to /srv/addrlens/last-deployed.sha
./ops/deploy/rollback.sh <sha>         # revert to any SHA
```

Watch runtime (on the box):

```bash
cd /srv/addrlens/repo/v0.1
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --env-file /srv/addrlens/.env.production ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
    --env-file /srv/addrlens/.env.production logs -f app
```

Weekly OSM refresh is a systemd timer (Sun 03:00 Europe/Berlin). Trigger manually:

```bash
sudo systemctl start refresh-osm-amenities.service
sudo journalctl -u refresh-osm-amenities.service -n 100 --no-pager
```

Health endpoints from external:

```bash
curl -sSf https://addrlens.de/health   # liveness
curl -sSf https://addrlens.de/ready    # readiness (includes city)
```

Monitoring:
- Sentry EU: `addrlens-app` + `addrlens-inference` projects, alerts to `informsapta@gmail.com`.
- UptimeRobot: two 5-min HTTP probes on `/health` and `/ready`, alerts to same.
- Cloudflare Analytics + WAF events (Free plan, 24 h retention).
```

- [ ] **Step 3: Commit**

```bash
git add v0.1/CLAUDE.md
git commit -m "docs(deploy): document production deploy commands in CLAUDE.md"
```

---

## Post-completion: what "done" looks like

At the end of Task 31:

- Repo has 8 new files, 6 modified files (all in `v0.1/`).
- `https://addrlens.de/health` returns 200 through Cloudflare Tunnel.
- `https://www.addrlens.de/` 301-redirects to apex.
- `/api/card_insight` returns 429 after 5 hits from one IP within 1 minute.
- OSM refresh timer fires next Sunday 03:00 Europe/Berlin (verified manually working).
- UptimeRobot monitors are green.
- Sentry receives its first synthetic error event (see `sentry_sdk.capture_message("deploy-verify")` if you want to trigger one manually).
- Local `uvicorn app.main:app --port 8001` on Apple Silicon still boots and serves `/health` = 200.
- SSH is key-only. UFW allows only 22/tcp.
