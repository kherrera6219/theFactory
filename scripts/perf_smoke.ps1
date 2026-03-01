param(
    [int]$Requests = 40,
    [int]$Concurrency = 10,
    [double]$MaxP95Seconds = 2.0
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python scripts/perf_smoke.py --requests $Requests --concurrency $Concurrency --max-p95-seconds $MaxP95Seconds
