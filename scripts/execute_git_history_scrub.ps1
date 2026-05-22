# execute_git_history_scrub.ps1 - Staged Git history scrub for theFactory
# This script scrubs local TLS key commits locally to preserve safety.
# DO NOT FORCE PUSH to remote origin until Claude Code has finished Phase 25.

Write-Host "================================────────────────=========" -ForegroundColor Cyan
Write-Host "  theFactory — Staged Git History TLS Key Scrubbing      " -ForegroundColor Cyan
Write-Host "================================────────────────=========" -ForegroundColor Cyan

# 1. Check if git repository
if (-not (Test-Path .git)) {
    Write-Error "This script must be executed from the root of a git repository."
    Exit 1
}

# 2. Check if git-filter-repo is available
$filterRepoCheck = Get-Command git-filter-repo -ErrorAction SilentlyContinue
if (-not $filterRepoCheck) {
    Write-Host "git-filter-repo not found on Path. Attempting to install via pip..." -ForegroundColor Yellow
    python -m pip install git-filter-repo
    $filterRepoCheck = Get-Command git-filter-repo -ErrorAction SilentlyContinue
    if (-not $filterRepoCheck) {
        Write-Error "git-filter-repo is required. Please install it ('pip install git-filter-repo') and ensure python scripts are in your Path."
        Exit 1
    }
}

Write-Host "[1/3] Executing git filter-repo to scrub TLS keys locally..." -ForegroundColor Yellow
# Run filter-repo to invert-path out the cert keys
git filter-repo --path deploy/postgres/certs/server.key --invert-paths --force
git filter-repo --path deploy/redis/certs/redis.key --invert-paths --force

Write-Host "[2/3] Verifying clean local git log..." -ForegroundColor Yellow
$postgresLog = git log --all -- deploy/postgres/certs/server.key
$redisLog = git log --all -- deploy/redis/certs/redis.key

$isClean = ($null -eq $postgresLog -or $postgresLog.Trim() -eq "") -and ($null -eq $redisLog -or $redisLog.Trim() -eq "")

if ($isClean) {
    Write-Host "✓ Verification PASS: No commits trace deploy/postgres/certs/server.key or deploy/redis/certs/redis.key in history." -ForegroundColor Green
} else {
    Write-Warning "Scrub verification failed! Commits were still found in git history."
    if ($null -ne $postgresLog -and $postgresLog.Trim() -ne "") {
        Write-Host "Postgres commits: $postgresLog" -ForegroundColor Red
    }
    if ($null -ne $redisLog -and $redisLog.Trim() -ne "") {
        Write-Host "Redis commits: $redisLog" -ForegroundColor Red
    }
    Exit 1
}

Write-Host "[3/3] Regenerating fresh local development certs..." -ForegroundColor Yellow
# Restore local development certificates
make tls-certs

Write-Host "================================────────────────=========" -ForegroundColor Green
Write-Host "  Scrub Complete (Staged Locally)                        " -ForegroundColor Green
Write-Host "  DO NOT run 'git push --force' until Phase 25 merges!   " -ForegroundColor Yellow
Write-Host "================================────────────────=========" -ForegroundColor Green
