param(
  [string]$BaseUrl = "http://localhost:8100",
  [string]$ComposeFile = "deploy/docker-compose.yaml",
  [string]$OutputFile = "docs/evidence/operator_route_oidc_matrix_latest.json",
  # Without -Execute, the qualification runs in dry-run mode: it prints the
  # commands it would run and the auth mode it would flip, and mutates
  # nothing. Pass -Execute to actually force-recreate/rebuild the live
  # api-gateway container.
  [switch]$Execute
)

$pyArgs = @(
  "scripts/operator_route_auth_matrix_qualification.py",
  "--base-url", $BaseUrl,
  "--compose-file", $ComposeFile,
  "--output-file", $OutputFile
)
if ($Execute) {
  $pyArgs += "--execute"
}

python @pyArgs

if ($LASTEXITCODE -ne 0) {
  exit $LASTEXITCODE
}
