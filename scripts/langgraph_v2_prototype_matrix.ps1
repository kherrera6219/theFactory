param(
  [string]$GatewayBaseUrl = "http://localhost:8100",
  [string]$OrchestratorBaseUrl = "http://localhost:8101",
  [string]$OrchestratorReadyUrl = "http://localhost:8101/readyz",
  [string]$ComposeFile = "deploy/docker-compose.yaml",
  [string]$OutputFile = "docs/evidence/langgraph_v2_prototype_matrix_latest.json"
)

python scripts/langgraph_v2_prototype_matrix.py `
  --gateway-base-url $GatewayBaseUrl `
  --orchestrator-base-url $OrchestratorBaseUrl `
  --orchestrator-ready-url $OrchestratorReadyUrl `
  --compose-file $ComposeFile `
  --allow-prototype-failure `
  --output-file $OutputFile

if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
