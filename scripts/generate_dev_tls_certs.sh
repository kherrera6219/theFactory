#!/usr/bin/env sh
set -eu

force="${1:-}"

postgres_dir="deploy/.local/postgres-certs"
redis_dir="deploy/.local/redis-certs"

ensure_dir() {
  mkdir -p "$1"
}

bundle_exists() {
  dir="$1"
  base="$2"
  [ -f "$dir/ca.crt" ] && [ -f "$dir/$base.crt" ] && [ -f "$dir/$base.key" ]
}

generate_bundle() {
  dir="$1"
  base="$2"
  common_name="$3"
  ca_name="$4"
  san="$5"

  ensure_dir "$dir"
  rm -f "$dir"/ca.crt "$dir"/ca.key "$dir"/ca.srl "$dir"/"$base".crt "$dir"/"$base".csr "$dir"/"$base".ext "$dir"/"$base".key

  openssl genrsa -out "$dir/ca.key" 2048 >/dev/null 2>&1
  openssl req -x509 -new -nodes -key "$dir/ca.key" -sha256 -days 825 -out "$dir/ca.crt" -subj "/CN=$ca_name" >/dev/null 2>&1
  openssl genrsa -out "$dir/$base.key" 2048 >/dev/null 2>&1
  openssl req -new -key "$dir/$base.key" -out "$dir/$base.csr" -subj "/CN=$common_name" >/dev/null 2>&1

  cat > "$dir/$base.ext" <<EOF
subjectAltName=$san
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
EOF

  openssl x509 -req \
    -in "$dir/$base.csr" \
    -CA "$dir/ca.crt" \
    -CAkey "$dir/ca.key" \
    -CAcreateserial \
    -out "$dir/$base.crt" \
    -days 825 \
    -sha256 \
    -extfile "$dir/$base.ext" >/dev/null 2>&1

  chmod 600 "$dir/$base.key"
  rm -f "$dir/ca.key" "$dir/ca.srl" "$dir/$base.csr" "$dir/$base.ext"
}

ensure_dir "$postgres_dir"
ensure_dir "$redis_dir"

if [ "$force" != "--force" ] && bundle_exists "$postgres_dir" "server" && bundle_exists "$redis_dir" "redis" ]; then
  echo "Dev TLS certs already exist. Use --force to regenerate."
  exit 0
fi

generate_bundle "$postgres_dir" "server" "postgres" "theFactory Postgres Dev CA" "DNS:postgres,DNS:localhost,IP:127.0.0.1"
generate_bundle "$redis_dir" "redis" "redis" "theFactory Redis Dev CA" "DNS:redis,DNS:localhost,IP:127.0.0.1"

echo "Generated local TLS certs under deploy/.local/postgres-certs and deploy/.local/redis-certs."
