param(
    [string]$OutputFile = "reports/langgraph-postgres-recovery-qualification.local.json",
    [double]$TransitionStepSeconds = 3.0,
    [double]$RestartAfterSeconds = 0.5,
    [double]$MissionTimeoutSeconds = 180.0,
    # Without -Execute, the qualification runs in dry-run mode: it prints the
    # commands it would run and mutates nothing. Pass -Execute to actually
    # force-recreate and restart the live orchestrator container.
    [switch]$Execute
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
if ($Execute) {
    $args += "--execute"
}

python @args
