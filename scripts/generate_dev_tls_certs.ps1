param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$dockerMountRoot = $repoRoot.Replace("\", "/")
$generateArgs = if ($Force) { " --force" } else { "" }

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker CLI is required to generate local TLS certs."
}

$dockerArgs = @(
    "run",
    "--rm",
    "-v", "${dockerMountRoot}:/workspace",
    "-w", "/workspace",
    "alpine:3.21",
    "sh",
    "-lc",
    "apk add --no-cache openssl >/dev/null && tr -d '\r' < scripts/generate_dev_tls_certs.sh > /tmp/generate_dev_tls_certs.sh && sh /tmp/generate_dev_tls_certs.sh$generateArgs"
)

& docker @dockerArgs

if ($LASTEXITCODE -ne 0) {
    throw "Failed to generate local TLS certs."
}
