param(
    [switch]$DryRun,
    [string]$Timestamp
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$backupDir = Join-Path $root "backups"
New-Item -ItemType Directory -Path $backupDir -Force > $null

$timestamp = if ($Timestamp) { $Timestamp } else { Get-Date -Format "yyyyMMdd_HHmmss" }
$backupPath = Join-Path $backupDir "ulr_$timestamp.sql"

if ($DryRun) {
    Write-Host "Dry-run mode enabled. Writing simulated backup: $backupPath"
    @(
        "-- dry-run backup artifact"
        "-- generated $(Get-Date -Format o)"
        "CREATE TABLE IF NOT EXISTS missions (mission_id text primary key, state text);"
        "INSERT INTO missions (mission_id, state) VALUES ('dry-run-001', 'VERIFIED');"
    ) | Set-Content -Path $backupPath -Encoding UTF8
}
else {
    Write-Host "Creating PostgreSQL backup: $backupPath"
    docker compose -f deploy/docker-compose.yaml exec -T postgres pg_dump -U postgres -d ulr > $backupPath
}

if (-not (Test-Path $backupPath)) {
    throw "backup file was not created"
}

$size = (Get-Item $backupPath).Length
if ($size -lt 64) {
    throw "backup file appears truncated ($size bytes)"
}
Write-Host "Backup complete ($size bytes)"
