#!/bin/sh
set -eu

runtime_cert_dir="/tmp/redis-runtime-certs"

mkdir -p "$runtime_cert_dir"
cp /usr/local/etc/redis/certs/ca.crt "$runtime_cert_dir/ca.crt"
cp /usr/local/etc/redis/certs/redis.crt "$runtime_cert_dir/redis.crt"
cp /usr/local/etc/redis/certs/redis.key "$runtime_cert_dir/redis.key"
chown redis:redis "$runtime_cert_dir/ca.crt" "$runtime_cert_dir/redis.crt" "$runtime_cert_dir/redis.key"
chmod 644 "$runtime_cert_dir/ca.crt" "$runtime_cert_dir/redis.crt"
chmod 600 "$runtime_cert_dir/redis.key"

exec docker-entrypoint.sh "$@" \
  --tls-cert-file "$runtime_cert_dir/redis.crt" \
  --tls-key-file "$runtime_cert_dir/redis.key" \
  --tls-ca-cert-file "$runtime_cert_dir/ca.crt"
