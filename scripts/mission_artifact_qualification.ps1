param(
  [string]$GatewayBaseUrl = "http://localhost:8100",
  [string]$OrchestratorBaseUrl = "http://localhost:8101",
  [string]$ProfileLabel = "shared-workers",
  [string]$Language = "python",
  [string]$OutputFile = "docs/evidence/mission_artifact_qualification_latest.json"
)

python scripts/mission_artifact_qualification.py `
  --gateway-base-url $GatewayBaseUrl `
  --orchestrator-base-url $OrchestratorBaseUrl `
  --profile-label $ProfileLabel `
  --language $Language `
  --output-file $OutputFile

exit $LASTEXITCODE
