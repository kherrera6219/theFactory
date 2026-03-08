param(
  [string]$GatewayBaseUrl = "http://localhost:8100",
  [string]$OrchestratorBaseUrl = "http://localhost:8101",
  [string]$OutputFile = "docs/evidence/dedicated_agent_canary_trend_latest.json",
  [string]$HistoryFile = "docs/evidence/dedicated_agent_canary_trend_history.jsonl"
)

python scripts/dedicated_agent_canary_trend.py `
  --gateway-base-url $GatewayBaseUrl `
  --orchestrator-base-url $OrchestratorBaseUrl `
  --output-file $OutputFile `
  --history-file $HistoryFile

if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
