#!/usr/bin/env sh
# Write the .env that CI workflows use to bring up a disposable compose stack.
#
# Extracted from ci.yml so the perf-smoke stack and the weekly qualification
# stack cannot drift apart. Every override below was earned by a CI failure;
# the comments say which one, so please do not prune them.
#
#   sh scripts/write_ci_env.sh [output_path]   # default: .env
#
# Never run this against a real environment file. It overwrites the target.
set -eu

out="${1:-.env}"

if [ ! -f .env.example ]; then
  echo "write_ci_env: .env.example not found; run from the repository root" >&2
  exit 1
fi

# Derive from the example, swapping every CHANGE_ME secret for a deterministic
# 32-char dev value so check_env.py passes.
sed -E \
  -e 's/CHANGE_ME_local_dev_redis_password_32chars/ci_dev_redis_password_0123456789abcd/g' \
  -e 's/CHANGE_ME_local_dev_postgres_password_32chars/ci_dev_postgres_password_0123456789ab/g' \
  -e 's/CHANGE_ME[A-Za-z0-9_]*/ci_dev_secret_value_0123456789abcdef/g' \
  .env.example > "$out"

{
  echo "INTERNAL_SERVICE_API_KEY=ci-internal-service-key"
  echo "ORCHESTRATOR_ADMIN_API_KEY=ci-admin-key"
  echo "AUTH_MODE=api_key"
  echo "KNOWLEDGE_EMBEDDING_PROVIDER=deterministic"
  echo "KNOWLEDGE_EMBEDDING_MODEL=deterministic-hash-v1"
  # protocol-bus-mcp is not part of these stacks; keep the optional consumer
  # off so it never adds startup work in CI.
  echo "PROTOCOL_BUS_CONSUMER_ENABLED=false"
  # jaeger is absent from these stacks; disabling tracing skips the per-/health
  # socket probe to jaeger:4318.
  echo "OTEL_TRACING_ENABLED=false"
  # CI Redis runs dev config: plaintext on 6379, no TLS. The derived .env has
  # TLS port 6380 plus cert paths that do not exist in CI.
  echo "REDIS_URL=redis://:ci_dev_redis_password_0123456789abcd@redis:6379/0"
  # PgBouncer's edoburu image defaults to md5 auth while postgres pg_hba.conf
  # uses scram-sha-256, which surfaces as "wrong password type".
  echo "PGBOUNCER_AUTH_TYPE=scram-sha-256"
  # .env.example points MIGRATION_POSTGRES_URL's sslrootcert at the host path
  # (deploy/.local/...), which does not exist inside the orchestrator container
  # -- certs are mounted at /run/postgres-certs. A wrong path makes every
  # schema-migration connection fail, so db_ready never flips true and each
  # /health probe re-runs the failing migration until the 3s healthcheck times
  # out. Bypass PgBouncer and use plaintext, matching the CI dev stack.
  echo "MIGRATION_POSTGRES_URL=postgresql://postgres:ci_dev_postgres_password_0123456789ab@postgres:5432/ulr?sslmode=disable"
  # LLM credentials are optional and normally absent. When absent the stack runs
  # the fallback path, generation yields source="fallback", and only the wiring
  # canary can pass -- which is the intended, honest default. When a workflow
  # supplies a key, pass it through so the full-mode canary can actually prove
  # end-to-end generation. Empty values are deliberately not written: an empty
  # assignment would still count as "set" to a naive reader of the env file.
  [ -n "${LLM_PROVIDER:-}" ] && echo "LLM_PROVIDER=${LLM_PROVIDER}"
  [ -n "${OPENAI_API_KEY:-}" ] && echo "OPENAI_API_KEY=${OPENAI_API_KEY}"
  [ -n "${ANTHROPIC_API_KEY:-}" ] && echo "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}"
  [ -n "${GEMINI_API_KEY:-}" ] && echo "GEMINI_API_KEY=${GEMINI_API_KEY}"
  :
} >> "$out"

echo "write_ci_env: wrote $out"
