#!/usr/bin/env bash
set -euo pipefail

# Production Postgres entrypoint — identical cert handling to the base
# entrypoint, but additionally points Postgres at the SSL-required pg_hba.conf
# so plaintext remote connections are rejected. Mounted by the prod overlay.

cp /run/postgres-certs/server.crt /var/lib/postgresql/server.crt
cp /run/postgres-certs/server.key /var/lib/postgresql/server.key
chown postgres:postgres /var/lib/postgresql/server.crt /var/lib/postgresql/server.key
chmod 644 /var/lib/postgresql/server.crt
chmod 600 /var/lib/postgresql/server.key

exec docker-entrypoint.sh postgres \
  -c config_file=/etc/postgresql/postgresql.conf \
  -c hba_file=/etc/postgresql/pg_hba.conf
