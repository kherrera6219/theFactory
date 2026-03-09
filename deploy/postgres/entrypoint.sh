#!/usr/bin/env bash
set -euo pipefail

cp /run/postgres-certs/server.crt /var/lib/postgresql/server.crt
cp /run/postgres-certs/server.key /var/lib/postgresql/server.key
chown postgres:postgres /var/lib/postgresql/server.crt /var/lib/postgresql/server.key
chmod 644 /var/lib/postgresql/server.crt
chmod 600 /var/lib/postgresql/server.key

exec docker-entrypoint.sh postgres -c config_file=/etc/postgresql/postgresql.conf
