$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$backupDir = Join-Path $root "backups"
New-Item -ItemType Directory -Path $backupDir -Force > $null

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupPath = Join-Path $backupDir "ulr_$timestamp.sql"

Write-Host "Creating PostgreSQL backup: $backupPath"
docker compose -f deploy/docker-compose.yaml exec -T postgres pg_dump -U postgres -d ulr > $backupPath

if (-not (Test-Path $backupPath)) {
    throw "backup file was not created"
}

$size = (Get-Item $backupPath).Length
Write-Host "Backup complete ($size bytes)"
