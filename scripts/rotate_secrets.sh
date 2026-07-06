#!/usr/bin/env bash
# rotate_secrets.sh — theFactory secret rotation helper
# 2026 best practice: all secrets should be rotatable with a single script
# Usage: bash scripts/rotate_secrets.sh [--dry-run]
set -euo pipefail

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

generate_key() {
    openssl rand -hex 32
}

check_prereqs() {
    for cmd in openssl; do
        if ! command -v "$cmd" &>/dev/null; then
            log_error "Required command not found: $cmd"
            exit 1
        fi
    done
}

check_no_real_secrets_in_env_example() {
    log_info "Checking .env.example for accidental real secrets..."
    local violations=0
    while IFS= read -r line; do
        # Skip comments and empty lines
        [[ "$line" =~ ^#.*$ ]] && continue
        [[ -z "$line" ]] && continue
        # Look for values that don't look like placeholders
        if [[ "$line" =~ =[[:space:]]*[a-f0-9]{32,64}[[:space:]]*$ ]]; then
            log_error "Possible real secret in .env.example: $line"
            violations=$((violations + 1))
        fi
    done < .env.example
    if [[ $violations -gt 0 ]]; then
        log_error "Found $violations potential real secrets in .env.example. Review and replace with CHANGE_ME placeholders."
        exit 1
    fi
    log_info ".env.example is clean — all values are placeholders."
}

rotate_env_file() {
    local env_file="${1:-.env}"
    if [[ ! -f "$env_file" ]]; then
        log_warn "$env_file not found — skipping rotation. Copy from .env.example first."
        return
    fi
    log_info "Rotating secrets in $env_file..."
    local backup="${env_file}.bak.$(date +%Y%m%d_%H%M%S)"
    cp "$env_file" "$backup"
    log_info "Backup saved to $backup"

    local rotatable_keys=(
        "REDIS_PASSWORD"
        "POSTGRES_PASSWORD"
        "INTERNAL_SERVICE_API_KEY"
        "ORCHESTRATOR_ADMIN_API_KEY"
        "ORCHESTRATOR_READONLY_API_KEY"
        "VAULT_ADMIN_KEY"
        "POD_A_SERVICE_API_KEY"
        "POD_B_SERVICE_API_KEY"
        "POD_C_SERVICE_API_KEY"
        "POD_D_SERVICE_API_KEY"
        "AUDIT_SERVICE_API_KEY"
    )

    if $DRY_RUN; then
        for key in "${rotatable_keys[@]}"; do
            log_info "[DRY-RUN] Would rotate: $key"
        done
        return
    fi

    # Apply every rotation to a scratch copy first, then atomically move it
    # into place in one step. Rotating the live $env_file in place, key by
    # key, meant a crash or kill partway through the loop left the file
    # services actually read with a mix of old and new secrets.
    local scratch
    scratch="$(mktemp "${env_file}.rotate.XXXXXX")"
    cp "$env_file" "$scratch"

    for key in "${rotatable_keys[@]}"; do
        new_val=$(generate_key)
        if grep -q "^${key}=" "$scratch"; then
            sed -i "s|^${key}=.*|${key}=${new_val}|" "$scratch"
            log_info "Rotated: $key"
        else
            log_warn "Key not found in $env_file: $key"
        fi
    done

    mv "$scratch" "$env_file"
    log_info "Secret rotation complete. Restart all services after updating: docker compose restart"
    log_warn "Delete backup after confirming services are healthy: rm $backup"
}

check_git_history_clean() {
    log_info "Checking git history for committed secrets..."
    if command -v gitleaks &>/dev/null; then
        if gitleaks detect --config=.gitleaks.toml --no-git 2>/dev/null; then
            log_info "gitleaks: no secrets found in working tree."
        else
            log_warn "gitleaks detected potential secrets. Run: gitleaks detect --config=.gitleaks.toml -v"
        fi
    else
        log_warn "gitleaks not installed. Install: brew install gitleaks  OR  pip install gitleaks"
        log_warn "Manual check: git log --all --full-history -- '*.pem' '*.key' '*.p12' '*.pfx'"
    fi
}

main() {
    log_info "=== theFactory Secret Rotation Tool ==="
    $DRY_RUN && log_warn "DRY-RUN mode: no changes will be written"

    check_prereqs
    check_no_real_secrets_in_env_example
    rotate_env_file ".env"
    check_git_history_clean

    log_info "=== Rotation complete ==="
    log_info "Next steps:"
    log_info "  1. Review .env changes before restarting services"
    log_info "  2. Update any external secret stores (Vault, CI/CD secrets) with new values"
    log_info "  3. Run: docker compose restart"
    log_info "  4. Run: make test to verify services are healthy"
}

main "$@"
