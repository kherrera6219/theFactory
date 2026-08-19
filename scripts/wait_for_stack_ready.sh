#!/usr/bin/env sh
# Block until the gateway and the orchestrator both report ready, then exit 0.
# On timeout, dump enough state to diagnose and exit 1.
#
#   sh scripts/wait_for_stack_ready.sh [attempts] [sleep_seconds]
#
# Both endpoints matter. The gateway's /readyz only checks the orchestrator's
# /livez plus a Redis ping, while the orchestrator's /readyz additionally ANDs in
# every optional backend whose *_ENABLED flag is set. Waiting on the gateway
# alone passes while the deeper check is still failing -- which is exactly how
# the qualification matrix came to run against a stack that could not serve it.
#
# Needed after anything that recreates a container. `docker compose up -d`
# returns once containers are created, not once they answer, so a step that
# reconfigures the gateway (the auth matrix restoring its initial AUTH_MODE, for
# instance) hands the next step a service that is still starting.
set -eu

attempts="${1:-60}"
sleep_seconds="${2:-5}"
gateway="${GATEWAY_BASE_URL:-http://localhost:8100}"
orchestrator="${ORCHESTRATOR_BASE_URL:-http://localhost:8101}"
compose_file="${COMPOSE_FILE_PATH:-deploy/docker-compose.yaml}"

attempt=1
while [ "$attempt" -le "$attempts" ]; do
  if curl -fsS "$gateway/readyz" >/dev/null 2>&1 \
    && curl -fsS "$orchestrator/readyz" >/dev/null 2>&1; then
    echo "stack ready after ${attempt} attempt(s)"
    exit 0
  fi
  attempt=$((attempt + 1))
  sleep "$sleep_seconds"
done

echo "::error::stack did not become ready within $((attempts * sleep_seconds))s" >&2
docker compose -f "$compose_file" ps || true
echo "--- gateway /readyz ---"
curl -sS "$gateway/readyz" || true
echo "--- orchestrator /readyz ---"
curl -sS "$orchestrator/readyz" || true
docker compose -f "$compose_file" logs --tail=120 \
  api-gateway orchestrator postgres pgbouncer neo4j minio milvus || true
exit 1
