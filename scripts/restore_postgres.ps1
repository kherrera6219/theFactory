param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    # Skip the interactive confirmation prompt (e.g. for scripted/automated use,
    # such as run_automated_dr_drill.py's --execute path).
    [switch]$Yes,
    # Skip the pre-restore safety snapshot of the current live database.
    [switch]$SkipPreRestoreSnapshot
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path $BackupFile)) {
    throw "backup file not found: $BackupFile"
}

# 1. Verify the backup's manifest/checksum before restoring over the live DB —
#    refuse to restore a possibly corrupted or tampered backup.
$manifestPath = "$BackupFile.json"
$checksumPath = "$BackupFile.sha256"
$actualHash = (Get-FileHash -Algorithm SHA256 -Path $BackupFile).Hash.ToLowerInvariant()

if (Test-Path $manifestPath) {
    $manifest = Get-Content -Path $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.sha256 -and $manifest.sha256 -ne $actualHash) {
        throw "backup checksum mismatch: manifest says $($manifest.sha256), file hash is $actualHash. Refusing to restore a possibly corrupted/tampered backup."
    }
    Write-Host "Manifest checksum verified: $actualHash"
}
elseif (Test-Path $checksumPath) {
    $expected = (Get-Content -Path $checksumPath -Raw).Split(" ")[0].Trim()
    if ($expected -and $expected -ne $actualHash) {
        throw "backup checksum mismatch: .sha256 file says $expected, file hash is $actualHash. Refusing to restore a possibly corrupted/tampered backup."
    }
    Write-Host "Checksum file verified: $actualHash"
}
else {
    Write-Warning "No manifest (.json) or checksum (.sha256) file found alongside $BackupFile -- integrity cannot be verified. Proceeding without a checksum check."
}

# 2. Require explicit confirmation before restoring over the live database.
if (-not $Yes) {
    $confirmation = Read-Host "This will OVERWRITE the live 'ulr' database with $BackupFile. Type 'yes' to continue"
    if ($confirmation -ne "yes") {
        Write-Host "Aborted: restore not confirmed."
        exit 1
    }
}

# 3. Pre-restore safety snapshot of the current live database, so an
#    accidental or wrong restore can itself be undone.
if (-not $SkipPreRestoreSnapshot) {
    $preRestoreTimestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    Write-Host "Snapshotting current live database before restore (pre-restore safety net)..."
    & (Join-Path $PSScriptRoot "backup_postgres.ps1") -Timestamp "prerestore_$preRestoreTimestamp"
}

Write-Host "Restoring PostgreSQL from $BackupFile"
Get-Content -Path $BackupFile | docker compose -f deploy/docker-compose.yaml exec -T postgres psql -U postgres -d ulr
Write-Host "Restore complete"
