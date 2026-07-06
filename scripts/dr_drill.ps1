# SUPERSEDED: This script validates readiness/backup/mission-table checks and now
# throws (rather than silently continuing) on a real failure in any of them, but it
# still does not exercise an actual disaster/restore cycle. It is retained only for
# Windows operators who specifically need the PowerShell path (`make dr-ps1`). The
# canonical, cross-platform drill that actually performs backup/disaster/restore and
# reports a real pass/fail is scripts/run_automated_dr_drill.py (`make dr`). Prefer
# that for any qualification or CI use.
param(
    [switch]$DryRun,
    [string]$Timestamp
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$started = Get-Date
Write-Host "== DR drill start =="

Write-Host "[1/4] Validate service readiness"
if ($DryRun) {
    Write-Host "Dry-run mode enabled. Skipping readiness HTTP checks."
}
else {
    # $ErrorActionPreference="Stop" only affects PowerShell cmdlets, not native
    # executables — curl.exe's exit code must be checked explicitly, or a
    # failed readiness check would silently be ignored and the drill would
    # still report passed=true below.
    curl.exe -sS --fail http://localhost:8100/readyz > $null
    if ($LASTEXITCODE -ne 0) { throw "api-gateway readyz check failed (curl exit $LASTEXITCODE)" }
    curl.exe -sS --fail http://localhost:8101/readyz > $null
    if ($LASTEXITCODE -ne 0) { throw "orchestrator readyz check failed (curl exit $LASTEXITCODE)" }
}

Write-Host "[2/4] Create fresh backup"
if ($DryRun) {
    & "$PSScriptRoot/backup_postgres.ps1" -DryRun -Timestamp $Timestamp
}
else {
    & "$PSScriptRoot/backup_postgres.ps1" -Timestamp $Timestamp
}

$latestBackup = Get-ChildItem -Path backups -Filter "ulr_*.sql" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $latestBackup) {
    throw "no backup file available after backup step"
}

Write-Host "[3/4] Verify backup content"
$head = Get-Content -Path $latestBackup.FullName -TotalCount 5
if ($head.Count -eq 0) {
    throw "backup file appears empty"
}

Write-Host "[4/4] Verify mission table readable"
if ($DryRun) {
    Write-Host "Dry-run mode enabled. Skipping postgres mission-count query."
}
else {
    docker compose -f deploy/docker-compose.yaml exec -T postgres psql -U postgres -d ulr -c "select count(*) as missions from missions;"
    if ($LASTEXITCODE -ne 0) { throw "mission-count query failed (psql exit $LASTEXITCODE)" }
}

$ended = Get-Date
$duration = [math]::Round(($ended - $started).TotalSeconds, 2)
$reportDir = Join-Path $root "reports"
New-Item -ItemType Directory -Path $reportDir -Force > $null
$reportPath = Join-Path $reportDir "dr-drill-latest.json"
$manifestPath = "$($latestBackup.FullName).json"
$report = @{
    started_at_utc = $started.ToUniversalTime().ToString("o")
    completed_at_utc = $ended.ToUniversalTime().ToString("o")
    duration_seconds = $duration
    dry_run = [bool]$DryRun
    passed = $true
    rto_target_minutes = 30
    rpo_target_hours = 24
    latest_backup = $latestBackup.FullName
    latest_backup_manifest = $(if (Test-Path $manifestPath) { $manifestPath } else { $null })
}
$report | ConvertTo-Json -Depth 4 | Set-Content -Path $reportPath -Encoding UTF8

Write-Host "DR drill complete. Duration: $duration sec"
Write-Host "Latest backup: $($latestBackup.FullName)"
Write-Host "DR report: $reportPath"
