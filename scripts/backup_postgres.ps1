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
$hash = (Get-FileHash -Algorithm SHA256 -Path $backupPath).Hash.ToLowerInvariant()
$manifestPath = "$backupPath.json"
$checksumPath = "$backupPath.sha256"
$manifest = @{
    backup_file = (Resolve-Path $backupPath).Path
    generated_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    dry_run = [bool]$DryRun
    size_bytes = $size
    sha256 = $hash
}
$manifest | ConvertTo-Json -Depth 4 | Set-Content -Path $manifestPath -Encoding UTF8
"$hash  $(Split-Path -Leaf $backupPath)" | Set-Content -Path $checksumPath -Encoding UTF8
Write-Host "Backup complete ($size bytes)"
Write-Host "Backup SHA-256: $hash"
Write-Host "Backup manifest: $manifestPath"
