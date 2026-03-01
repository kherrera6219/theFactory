param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path $BackupFile)) {
    throw "backup file not found: $BackupFile"
}

Write-Host "Restoring PostgreSQL from $BackupFile"
Get-Content -Path $BackupFile | docker compose -f deploy/docker-compose.yaml exec -T postgres psql -U postgres -d ulr
Write-Host "Restore complete"
