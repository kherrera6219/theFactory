param(
    [string]$OutputFile = "reports/langgraph-postgres-recovery-qualification.local.json",
    [double]$TransitionStepSeconds = 3.0,
    [double]$RestartAfterSeconds = 0.5,
    [double]$MissionTimeoutSeconds = 180.0
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$args = @(
    "scripts/langgraph_postgres_recovery_qualification.py",
    "--output-file", $OutputFile,
    "--transition-step-seconds", $TransitionStepSeconds,
    "--restart-after-seconds", $RestartAfterSeconds,
    "--mission-timeout-seconds", $MissionTimeoutSeconds
)

python @args
