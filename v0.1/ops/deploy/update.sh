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
if grep -q '^GIT_SHA=' "$ENV_FILE"; then
    sed -i "s|^GIT_SHA=.*|GIT_SHA=${NEW_SHA}|" "$ENV_FILE"
else
    echo "GIT_SHA=${NEW_SHA}" >> "$ENV_FILE"
fi

cd "$REPO/v0.1"

# --- 4. Rebuild only images whose sources changed --------------------------
# app-hh (Hamburg) shares ops/Dockerfile.app with app (Berlin) — same COPY
# layers, different runtime CITY env. Both must be rebuilt so a source
# change (e.g. Hamburg trees_bbox MultiPoint fix) lands on both containers.
"${COMPOSE[@]}" build --pull app app-hh app-landing inference

# --- 5. Recreate containers that need it ------------------------------------
"${COMPOSE[@]}" up -d --remove-orphans

# --- 6. Readiness gate — 90 s budget per container --------------------------
# Gate on both app (:8001 = Berlin) + app-hh (:8002 = Hamburg). Either can
# fail independently (different WFS endpoints, different Index shape) so
# both must reach /ready before we declare success.
for svc_port in "app:8001" "app-hh:8002" "app-landing:8000"; do
    svc="${svc_port%%:*}"
    port="${svc_port##*:}"
    # Landing has no lookup — health-only smoke via compose exec (ports: !reset []).
    # Retry 30 × 3s = 90s budget, matches app/app-hh readiness gate.
    if [ "$svc" = "app-landing" ]; then
      echo "[deploy] waiting for $svc /health on :$port"
      LANDING_UP=""
      for i in $(seq 1 30); do
        if "${COMPOSE[@]}" exec -T "$svc" python -c \
            "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${port}/health', timeout=3)" 2>/dev/null; then
          echo "[deploy] $svc: /health OK after ~$((i*3))s"
          LANDING_UP="1"
          break
        fi
        sleep 3
      done
      if [ -z "$LANDING_UP" ]; then
        echo "[deploy] FATAL: $svc /health never came up in 90s"
        echo "[deploy] Rollback with: ./ops/deploy/rollback.sh $PREV_SHA"
        exit 1
      fi
      continue
    fi
    echo "[deploy] waiting for $svc /ready on :$port"
    READY=""
    for i in $(seq 1 30); do
        if "${COMPOSE[@]}" exec -T "$svc" python -c \
            "import urllib.request,sys; \
             sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:${port}/ready', timeout=2).status==200 else 1)" \
            2>/dev/null
        then
            READY="1"
            echo "[deploy] $svc ready after ~$((i*3))s"
            # Post-ready smoke: canonical address read from CityConfig so a
            # city-data change (address renamed, PLZ boundary shift) touches
            # one file — not this script. Empty smoke_address → WARN + skip.
            case "$svc" in
                app)    ADDR=$("${COMPOSE[@]}" exec -T "$svc" python -c "from app.cities.berlin import BERLIN; print(BERLIN.smoke_address)") ;;
                app-hh) ADDR=$("${COMPOSE[@]}" exec -T "$svc" python -c "from app.cities.hamburg import HAMBURG; print(HAMBURG.smoke_address)") ;;
            esac
            if [ -z "$ADDR" ]; then
                echo "[deploy] WARN: $svc has no smoke_address configured — skipping /api/lookup smoke"
            else
            if ! "${COMPOSE[@]}" exec -T "$svc" python -c "
import json, urllib.request, urllib.parse, sys
q = urllib.parse.urlencode({'address': '$ADDR'})
try:
    r = urllib.request.urlopen(f'http://127.0.0.1:${port}/api/lookup?{q}', timeout=15)
except Exception as e:
    print(f'FAIL[urlopen]: {type(e).__name__}: {e}', file=sys.stderr); sys.exit(2)
if r.status != 200:
    print(f'FAIL[http_status]: got {r.status}, want 200', file=sys.stderr); sys.exit(2)
try:
    d = json.load(r)
except Exception as e:
    print(f'FAIL[json_parse]: {type(e).__name__}: {e}', file=sys.stderr); sys.exit(3)
if not d.get('address'):
    print(f'FAIL[missing_address_key]: keys={sorted(d)[:10]}', file=sys.stderr); sys.exit(3)
if not d.get('schools') and not d.get('nearest_school'):
    print(f'FAIL[missing_schools_and_nearest_school]: keys={sorted(d)[:10]}', file=sys.stderr); sys.exit(3)
print('ok')
"; then
                RC=$?
                echo "[deploy] ERROR: $svc smoke failed on address '$ADDR' (python rc=$RC)"
                echo "[deploy] Rollback with: ./ops/deploy/rollback.sh $PREV_SHA"
                exit 4
            fi
            fi
            break
        fi
        sleep 3
    done
    if [ -z "$READY" ]; then
        echo "[deploy] ERROR: $svc never became ready in 90s. Check logs:"
        echo "[deploy]   ${COMPOSE[*]} logs --tail=100 $svc"
        echo "[deploy] Rollback with: ./ops/deploy/rollback.sh $PREV_SHA"
        exit 1
    fi
done

# --- 7. Prune dangling images (weekly discipline; safe here) ---------------
docker image prune -f --filter "until=168h"

echo "[deploy] done. deployed $NEW_SHA on top of $PREV_SHA"
