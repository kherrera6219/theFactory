param(
  [string]$GatewayBaseUrl = "http://localhost:8100",
  [string]$OrchestratorBaseUrl = "http://localhost:8101",
  [string]$Language = "python",
  [string]$OutputFile = "docs/evidence/dedicated_agent_canary_rollout_latest.json"
)

python scripts/dedicated_agent_canary_rollout.py `
  --gateway-base-url $GatewayBaseUrl `
  --orchestrator-base-url $OrchestratorBaseUrl `
  --language $Language `
  --output-file $OutputFile

exit $LASTEXITCODE
