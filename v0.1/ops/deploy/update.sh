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
