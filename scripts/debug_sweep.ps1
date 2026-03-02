$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$composeFile = "deploy/docker-compose.yaml"

Write-Host "== Schema validation =="
python scripts/validate_schemas.py

Write-Host "== Python tests =="
python -m pytest -q

Write-Host "== Docker compose config =="
docker compose -f $composeFile config > $null
Write-Host "compose config OK"

Write-Host "== Running services =="
docker compose -f $composeFile ps

Write-Host "== Health checks =="
curl.exe -sS --fail http://localhost:8100/health
curl.exe -sS --fail http://localhost:8101/health
curl.exe -sS --fail http://localhost:8102/health
curl.exe -sS --fail http://localhost:8180/health

Write-Host "== Readiness checks =="
curl.exe -sS --fail http://localhost:8100/readyz
curl.exe -sS --fail http://localhost:8101/readyz
curl.exe -sS --fail http://localhost:8102/readyz

Write-Host "== Metrics checks =="
$gatewayMetrics = curl.exe -sS --fail http://localhost:8100/metrics
$orchestratorMetrics = curl.exe -sS --fail http://localhost:8101/metrics
$mcpMetrics = curl.exe -sS --fail http://localhost:8102/metrics
if (-not ($gatewayMetrics | Select-String -Pattern "api_gateway_http_requests_total" -SimpleMatch)) {
    throw "gateway metrics missing api_gateway_http_requests_total"
}
if (
    -not (
        $orchestratorMetrics | Select-String -Pattern "orchestrator_http_requests_total" -SimpleMatch
    )
) {
    throw "orchestrator metrics missing orchestrator_http_requests_total"
}
if (
    -not (
        $mcpMetrics | Select-String -Pattern "semantic_bus_mcp_http_requests_total" -SimpleMatch
    )
) {
    throw "mcp metrics missing semantic_bus_mcp_http_requests_total"
}

Write-Host "== Recent orchestrator logs =="
docker compose -f $composeFile logs orchestrator --tail 80

Write-Host "Debug sweep complete."
