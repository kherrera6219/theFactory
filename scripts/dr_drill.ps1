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
    curl.exe -sS --fail http://localhost:8100/readyz > $null
    curl.exe -sS --fail http://localhost:8101/readyz > $null
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
}

$ended = Get-Date
$duration = [math]::Round(($ended - $started).TotalSeconds, 2)

Write-Host "DR drill complete. Duration: $duration sec"
Write-Host "Latest backup: $($latestBackup.FullName)"
