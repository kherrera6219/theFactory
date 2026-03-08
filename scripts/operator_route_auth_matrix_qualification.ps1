param(
  [string]$BaseUrl = "http://localhost:8100",
  [string]$ComposeFile = "deploy/docker-compose.yaml",
  [string]$OutputFile = "docs/evidence/operator_route_oidc_matrix_latest.json"
)

python scripts/operator_route_auth_matrix_qualification.py `
  --base-url $BaseUrl `
  --compose-file $ComposeFile `
  --output-file $OutputFile

if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
