param(
    [double]$DurationSeconds = 300,
    [double]$RequestsPerSecond = 2.0,
    [int]$Concurrency = 12,
    [double]$MinSuccessRate = 99.0,
    [double]$MaxP95Seconds = 2.5,
    [string]$BaseUrl = "http://localhost:8100",
    [string[]]$ReadinessEndpoints = @("http://localhost:8100/readyz", "http://localhost:8101/readyz"),
    [double]$ReadinessPollSeconds = 5.0,
    [int]$MaxReadinessFailures = 8,
    [int]$MaxConsecutiveReadinessFailures = 4,
    [double]$RecoveryTimeoutSeconds = 120.0,
    [double]$RecoveryPollSeconds = 3.0,
    [int]$RecoveryConsecutiveSuccesses = 3,
    [string]$OutputFile = "reports/reliability-qualification.local.json",
    [switch]$InjectOrchestratorRestart,
    [double]$FailureInjectAfterSeconds = 90
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$args = @(
    "scripts/reliability_qualification.py",
    "--base-url", $BaseUrl,
    "--duration-seconds", $DurationSeconds,
    "--requests-per-second", $RequestsPerSecond,
    "--concurrency", $Concurrency,
    "--min-success-rate", $MinSuccessRate,
    "--max-p95-seconds", $MaxP95Seconds,
    "--readiness-endpoints"
)

foreach ($endpoint in $ReadinessEndpoints) {
    $args += $endpoint
}

$args += @(
    "--readiness-poll-seconds", $ReadinessPollSeconds,
    "--max-readiness-failures", $MaxReadinessFailures,
    "--max-consecutive-readiness-failures", $MaxConsecutiveReadinessFailures,
    "--recovery-timeout-seconds", $RecoveryTimeoutSeconds,
    "--recovery-poll-seconds", $RecoveryPollSeconds,
    "--recovery-consecutive-successes", $RecoveryConsecutiveSuccesses,
    "--output-file", $OutputFile
)

if ($InjectOrchestratorRestart) {
    $args += @(
        "--failure-command", "docker compose -f deploy/docker-compose.yaml restart orchestrator",
        "--failure-inject-after-seconds", $FailureInjectAfterSeconds
    )
}

python @args
