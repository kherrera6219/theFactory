param(
    [double]$DurationSeconds = 300,
    [double]$RequestsPerSecond = 2.0,
    [int]$Concurrency = 12,
    [double]$MinSuccessRate = 99.0,
    [double]$MaxP95Seconds = 2.5,
    [string]$OutputFile = "reports/reliability-qualification.local.json",
    [switch]$InjectOrchestratorRestart,
    [double]$FailureInjectAfterSeconds = 90
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$args = @(
    "scripts/reliability_qualification.py",
    "--duration-seconds", $DurationSeconds,
    "--requests-per-second", $RequestsPerSecond,
    "--concurrency", $Concurrency,
    "--min-success-rate", $MinSuccessRate,
    "--max-p95-seconds", $MaxP95Seconds,
    "--output-file", $OutputFile
)

if ($InjectOrchestratorRestart) {
    $args += @(
        "--failure-command", "docker compose -f deploy/docker-compose.yaml restart orchestrator",
        "--failure-inject-after-seconds", $FailureInjectAfterSeconds
    )
}

python @args
