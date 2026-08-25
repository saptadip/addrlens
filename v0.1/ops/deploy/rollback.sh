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
