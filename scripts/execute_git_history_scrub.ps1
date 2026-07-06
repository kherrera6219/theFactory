# execute_git_history_scrub.ps1 - Staged Git history scrub for theFactory
# This script scrubs local TLS key commits locally to preserve safety.
# DO NOT FORCE PUSH to remote origin until Claude Code has finished Phase 25.
#
# This is a one-shot, project-history script kept for reference/re-run in a
# fresh clone only. It rewrites git history, which is irreversible outside a
# backup. Defaults to dry-run; pass -Execute to actually rewrite history.
# --force is never passed to git-filter-repo, so its own built-in safety
# check (refuse to run outside a pristine fresh clone) stays active.

param(
    [switch]$Execute
)

Write-Host "================================────────────────=========" -ForegroundColor Cyan
Write-Host "  theFactory — Staged Git History TLS Key Scrubbing      " -ForegroundColor Cyan
Write-Host "================================────────────────=========" -ForegroundColor Cyan

# 1. Check if git repository
if (-not (Test-Path .git)) {
    Write-Error "This script must be executed from the root of a git repository."
    Exit 1
}

$filterCommands = @(
    @("--path", "deploy/postgres/certs/server.key", "--invert-paths"),
    @("--path", "deploy/redis/certs/redis.key", "--invert-paths")
)

if (-not $Execute) {
    Write-Host "`nDRY-RUN: would run the following history-rewriting commands:" -ForegroundColor Yellow
    foreach ($cmdArgs in $filterCommands) {
        Write-Host "  git filter-repo $($cmdArgs -join ' ')"
    }
    Write-Host "`nDRY-RUN: would then verify no commits reference deploy/postgres/certs/server.key or deploy/redis/certs/redis.key" -ForegroundColor Yellow
    Write-Host "DRY-RUN: would then regenerate fresh local dev certs ('make tls-certs')" -ForegroundColor Yellow
    Write-Host "`nNo -Force is passed to git-filter-repo, so its own built-in safety check (refuse to run outside a pristine fresh clone) stays active even with -Execute." -ForegroundColor Yellow
    Write-Host "Pass -Execute to actually rewrite history." -ForegroundColor Yellow
    Exit 0
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
# git-filter-repo's own default behavior refuses to run outside a fresh
# clone (no --force here) -- that check is the real backup guarantee.
foreach ($cmdArgs in $filterCommands) {
    git filter-repo @cmdArgs
}

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
