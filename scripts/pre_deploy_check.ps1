$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$checksPassed = 0
$checksTotal = 8

Write-Host "== Pre-deployment checks =="

Write-Host "[1/$checksTotal] Docker daemon"
docker info > $null
$checksPassed++

Write-Host "[2/$checksTotal] Compose config"
docker compose -f deploy/docker-compose.yaml config > $null
$checksPassed++

Write-Host "[3/$checksTotal] API health"
curl.exe -sS --fail http://localhost:8100/health > $null
$checksPassed++

Write-Host "[4/$checksTotal] Orchestrator health"
curl.exe -sS --fail http://localhost:8101/health > $null
$checksPassed++

Write-Host "[5/$checksTotal] API readiness"
curl.exe -sS --fail http://localhost:8100/readyz > $null
$checksPassed++

Write-Host "[6/$checksTotal] Orchestrator readiness"
curl.exe -sS --fail http://localhost:8101/readyz > $null
$checksPassed++

Write-Host "[7/$checksTotal] Schema validation"
python scripts/validate_schemas.py > $null
$checksPassed++

Write-Host "[8/$checksTotal] OpenAPI export"
python scripts/export_openapi.py > $null
$checksPassed++

Write-Host "Checks passed: $checksPassed/$checksTotal"
Write-Host "Pre-deployment checks complete."
