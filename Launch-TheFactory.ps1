#Requires -Version 5.1
<#
.SYNOPSIS
    theFactory — one-click launcher for Windows.

.DESCRIPTION
    Handles first-time setup (generates .env with secure secrets + TLS certs)
    then starts the full stack via Docker Compose and opens Mission Control
    in the default browser.

.PARAMETER FullDedicated
    Start in full-dedicated-agents topology (38 containers) instead of the
    default condensed topology (~8 containers). Requires more RAM (~12 GB).

.PARAMETER SkipBuild
    Skip --build flag on docker compose up (faster restart when images are
    already current).

.PARAMETER Down
    Tear down the running stack (equivalent to make down).

.EXAMPLE
    .\Launch-TheFactory.ps1
    .\Launch-TheFactory.ps1 -FullDedicated
    .\Launch-TheFactory.ps1 -Down
#>
param(
    [switch]$FullDedicated,
    [switch]$SkipBuild,
    [switch]$Down
)

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"   # suppress slow progress bars

# ── Paths ────────────────────────────────────────────────────────────────────
$RepoRoot   = (Resolve-Path (Join-Path $PSScriptRoot ".")).Path
$EnvFile    = Join-Path $RepoRoot ".env"
$EnvExample = Join-Path $RepoRoot ".env.example"
$ComposeBase = Join-Path $RepoRoot "deploy\docker-compose.yaml"
$ComposeFullDedicated = Join-Path $RepoRoot "deploy\docker-compose.full-dedicated-agents.yaml"
$TlsCertsScript = Join-Path $RepoRoot "scripts\generate_dev_tls_certs.ps1"
$TlsMarker = Join-Path $RepoRoot "deploy\.local\redis-certs\ca.crt"

# ── Colour helpers ───────────────────────────────────────────────────────────
function Write-Step  { param([string]$Msg) Write-Host "  » $Msg" -ForegroundColor Cyan }
function Write-Ok    { param([string]$Msg) Write-Host "  ✓ $Msg" -ForegroundColor Green }
function Write-Warn  { param([string]$Msg) Write-Host "  ! $Msg" -ForegroundColor Yellow }
function Write-Fatal { param([string]$Msg) Write-Host "`n  ✗ $Msg`n" -ForegroundColor Red; exit 1 }
function Write-Banner {
    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════════════╗" -ForegroundColor Magenta
    Write-Host "  ║   theFactory — HolyGrail Multi-Agent Refinery ║" -ForegroundColor Magenta
    Write-Host "  ╚══════════════════════════════════════════════╝" -ForegroundColor Magenta
    Write-Host ""
}

# ── Crypto helper (CSPRNG — same quality as Python secrets.token_hex) ────────
function New-SecureHex {
    param([int]$ByteCount = 32)
    $bytes = [byte[]]::new($ByteCount)
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return ($bytes | ForEach-Object { $_.ToString("x2") }) -join ""
}

# ── Check prerequisites ───────────────────────────────────────────────────────
function Assert-Prerequisites {
    Write-Step "Checking prerequisites..."

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Fatal "Docker is not on PATH. Install Docker Desktop from https://www.docker.com/products/docker-desktop and try again."
    }

    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Fatal "Docker daemon is not running. Start Docker Desktop and try again."
    }

    Write-Ok "Docker is running"
}

# ── Generate .env from .env.example ──────────────────────────────────────────
function Initialize-EnvFile {
    if (Test-Path $EnvFile) {
        Write-Ok ".env already exists — skipping secret generation"
        return
    }

    Write-Step "First run detected — generating .env with secure secrets..."

    if (-not (Test-Path $EnvExample)) {
        Write-Fatal ".env.example not found at $EnvExample"
    }

    $content = Get-Content $EnvExample -Raw

    # Replace every CHANGE_ME_* placeholder with a fresh CSPRNG hex secret.
    # The regex captures the whole "CHANGE_ME_..." token so we replace exactly
    # the token, not surrounding text, preserving the variable name before =.
    $content = [regex]::Replace($content, 'CHANGE_ME_[A-Za-z0-9_]+', {
        param($m)
        return New-SecureHex 32
    })

    # Set MINIO_ROOT_USER to a sensible non-secret default (must be ≥3 chars,
    # not a hex string, so MinIO doesn't reject it).
    $content = $content -replace 'MINIO_ROOT_USER=([^\r\n]+)', 'MINIO_ROOT_USER=thefactory-admin'

    # Switch PROMPT_GUARD_MODE to "block" for local dev (safer default than "log").
    $content = $content -replace 'PROMPT_GUARD_MODE=log', 'PROMPT_GUARD_MODE=block'

    $content | Set-Content $EnvFile -NoNewline -Encoding UTF8

    Write-Ok ".env created with auto-generated secrets"
    Write-Warn "Review .env before exposing the stack to any network"
}

# ── Generate TLS certs if missing ────────────────────────────────────────────
function Initialize-TlsCerts {
    if (Test-Path $TlsMarker) {
        Write-Ok "TLS certs already present"
        return
    }

    Write-Step "Generating dev TLS certificates (requires Docker)..."
    & powershell -ExecutionPolicy Bypass -File $TlsCertsScript
    if ($LASTEXITCODE -ne 0) {
        Write-Fatal "TLS cert generation failed. Check Docker is running and try again."
    }
    Write-Ok "TLS certs generated"
}

# ── Tear down ─────────────────────────────────────────────────────────────────
function Stop-Stack {
    Write-Step "Stopping stack..."
    if ($FullDedicated) {
        docker compose `
            -f $ComposeBase `
            -f $ComposeFullDedicated `
            --profile full-dedicated-agents `
            down -v
    } else {
        docker compose -f $ComposeBase down -v
    }
    if ($LASTEXITCODE -ne 0) { Write-Fatal "docker compose down failed." }
    Write-Ok "Stack stopped and volumes removed"
}

# ── Start stack ───────────────────────────────────────────────────────────────
function Start-Stack {
    $buildFlag = if ($SkipBuild) { @() } else { @("--build") }

    if ($FullDedicated) {
        Write-Step "Starting full-dedicated-agents topology (38 containers)..."
        Write-Warn "This topology needs ~12 GB RAM. Press Ctrl+C within 5s to cancel."
        Start-Sleep 5
        docker compose `
            -f $ComposeBase `
            -f $ComposeFullDedicated `
            --profile full-dedicated-agents `
            up -d @buildFlag
    } else {
        Write-Step "Starting condensed topology (~8 containers)..."
        docker compose -f $ComposeBase up -d @buildFlag
    }

    if ($LASTEXITCODE -ne 0) {
        Write-Fatal "docker compose up failed. Run 'docker compose -f deploy/docker-compose.yaml logs' to investigate."
    }
    Write-Ok "Containers started"
}

# ── Wait for Mission Control to become reachable ──────────────────────────────
function Wait-ForMissionControl {
    $url      = "http://localhost:3100"
    $maxWait  = 120   # seconds
    $interval = 3
    $elapsed  = 0

    Write-Step "Waiting for Mission Control at $url..."

    while ($elapsed -lt $maxWait) {
        try {
            $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($resp.StatusCode -lt 500) {
                Write-Ok "Mission Control is up"
                return
            }
        } catch { <# not ready yet #> }

        Start-Sleep $interval
        $elapsed += $interval
        Write-Host "    ... waiting ($elapsed/$maxWait s)" -ForegroundColor DarkGray
    }

    Write-Warn "Mission Control did not respond within ${maxWait}s. It may still be starting — check 'docker compose logs mission-control'."
}

# ── Open browser ──────────────────────────────────────────────────────────────
function Open-MissionControl {
    $url = "http://localhost:3100"
    Write-Step "Opening Mission Control in your browser..."
    Start-Process $url
    Write-Ok "Launched $url"
}

# ── Service summary ───────────────────────────────────────────────────────────
function Show-ServiceSummary {
    Write-Host ""
    Write-Host "  Stack endpoints:" -ForegroundColor White
    Write-Host "    Mission Control  →  http://localhost:3100"      -ForegroundColor Cyan
    Write-Host "    API Gateway      →  http://localhost:8100"      -ForegroundColor Cyan
    Write-Host "    Orchestrator     →  http://localhost:8101"      -ForegroundColor Cyan
    Write-Host "    Semantic Bus     →  http://localhost:8102"      -ForegroundColor Cyan
    Write-Host "    Dashboard        →  http://localhost:8180"      -ForegroundColor Cyan
    Write-Host "    Jaeger Traces    →  http://localhost:16686"     -ForegroundColor DarkGray
    Write-Host "    Qdrant           →  http://localhost:6334"      -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Useful commands:" -ForegroundColor White
    Write-Host "    docker compose -f deploy/docker-compose.yaml logs -f   (follow logs)"
    Write-Host "    .\Launch-TheFactory.ps1 -Down                          (stop stack)"
    Write-Host ""
}

# ── Main ──────────────────────────────────────────────────────────────────────
Push-Location $RepoRoot
try {
    Write-Banner

    if ($Down) {
        Assert-Prerequisites
        Stop-Stack
        exit 0
    }

    Assert-Prerequisites
    Initialize-EnvFile
    Initialize-TlsCerts
    Start-Stack
    Wait-ForMissionControl
    Open-MissionControl
    Show-ServiceSummary

} finally {
    Pop-Location
}
