# test_live_agents.ps1
# Queries the live orchestrator to validate agent heartbeats and embedding liveness.

param(
    [string]$OrchestratorUrl = "http://localhost:8101",
    [string]$EnvFile = ".env"
)

# ── Read INTERNAL_SERVICE_API_KEY from .env ─────────────────────────────────
$apiKey = ""
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match "^INTERNAL_SERVICE_API_KEY=(.+)$") { $apiKey = $Matches[1].Trim() }
    }
}
if (-not $apiKey) { $apiKey = "CHANGE_ME_local_dev_internal_service_key_32chars" }
$headers = @{ "X-API-Key" = $apiKey }

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  HGR Live Agent & Embedding Test" -ForegroundColor Cyan
Write-Host "  Orchestrator: $OrchestratorUrl" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# ── 1. /readyz ──────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[ 1/3 ] Database & Runtime Readiness (/readyz)" -ForegroundColor Yellow
try {
    $readyz = Invoke-RestMethod -Uri "$OrchestratorUrl/readyz" -Method GET -TimeoutSec 10
    $dbChecks = @(
        @{ Name = "Redis";          Key = "redis_ready" },
        @{ Name = "PostgreSQL";     Key = "db_ready" },
        @{ Name = "Qdrant";         Key = "qdrant_ready" },
        @{ Name = "Milvus";         Key = "milvus_ready" },
        @{ Name = "Neo4j";          Key = "neo4j_ready" },
        @{ Name = "MinIO (S3)";     Key = "object_storage_ready" },
        @{ Name = "Protocol Bus";   Key = "protocol_ready" },
        @{ Name = "Consumer";       Key = "consumer_running" }
    )
    $allDbReady = $true
    foreach ($check in $dbChecks) {
        $val = $readyz.($check.Key)
        $ok  = ($val -eq $true)
        if (-not $ok) { $allDbReady = $false }
        $icon  = if ($ok) { "[OK]" } else { "[FAIL]" }
        $color = if ($ok) { "Green" } else { "Red" }
        Write-Host ("  {0,-8}  {1}" -f $icon, $check.Name) -ForegroundColor $color
    }
} catch {
    Write-Host "  [ERROR] Could not reach /readyz: $_" -ForegroundColor Red
    $allDbReady = $false
}

# ── 2. /internal/operations/summary — embedding probe ───────────────────────
Write-Host ""
Write-Host "[ 2/3 ] Operations Summary & Embedding Configuration" -ForegroundColor Yellow
try {
    $summary = Invoke-RestMethod -Uri "$OrchestratorUrl/internal/operations/summary" -Headers $headers -TimeoutSec 15
    $rt = $summary.runtime

    # Embedding provider/model from orchestrator env (reflected via runtime summary)
    $embProv  = if ($rt.PSObject.Properties["knowledge_embedding_provider"]) { $rt.knowledge_embedding_provider } else { "N/A" }
    $embModel = if ($rt.PSObject.Properties["knowledge_embedding_model"]) { $rt.knowledge_embedding_model } else { "N/A" }

    Write-Host "  Topology:          $($summary.topology_mode)"
    Write-Host "  Active missions:   $($summary.mission_state_counts.RUNNING ?? 0)"
    Write-Host "  Lifecycle tasks:   $($summary.active_lifecycle_tasks)"

    # Re-print data-plane readiness from summary too
    $rtReady = @("redis_ready","db_ready","qdrant_ready","milvus_ready","neo4j_ready","object_storage_ready","protocol_ready","consumer_running")
    foreach ($k in $rtReady) {
        $val = $rt.$k
        if ($null -eq $val) { continue }
        $ok  = ($val -eq $true)
        $icon  = if ($ok) { "[OK]" } else { "[FAIL]" }
        $color = if ($ok) { "Green" } else { "Red" }
        Write-Host ("  {0,-8}  {1}" -f $icon, $k) -ForegroundColor $color
    }
} catch {
    Write-Host "  [ERROR] Could not reach /internal/operations/summary: $_" -ForegroundColor Red
}

# ── 3. /internal/operations/agents — live heartbeat check ───────────────────
Write-Host ""
Write-Host "[ 3/3 ] Agent Heartbeat Liveness (/internal/operations/agents)" -ForegroundColor Yellow
try {
    $agentsResp = Invoke-RestMethod -Uri "$OrchestratorUrl/internal/operations/agents" -Headers $headers -TimeoutSec 20
    $agents = $agentsResp.agents

    $totalAgents  = $agents.Count
    $liveCount    = ($agents | Where-Object { $_.heartbeat_source -eq "live" }).Count
    $staleCount   = ($agents | Where-Object { $_.heartbeat_source -eq "stale" }).Count
    $managedCount = ($agents | Where-Object { $_.heartbeat_source -eq "heuristic" -or $_.runtime_class -eq "synthesized_heartbeat" }).Count

    Write-Host ""
    Write-Host ("  Total agents registered: {0}" -f $totalAgents)
    Write-Host ("  Live heartbeats:         {0}" -f $liveCount) -ForegroundColor $(if ($liveCount -gt 0) { "Green" } else { "Yellow" })
    Write-Host ("  Stale heartbeats:        {0}" -f $staleCount) -ForegroundColor $(if ($staleCount -gt 0) { "Red" } else { "Green" })
    Write-Host ("  Managed/synthesized:     {0}" -f $managedCount)

    Write-Host ""
    Write-Host "  --- Live Agent Detail ---" -ForegroundColor Cyan
    $liveAgents = $agents | Where-Object { $_.heartbeat_source -eq "live" } | Sort-Object index
    if ($liveAgents.Count -eq 0) {
        Write-Host "  (no live heartbeats yet — agents may still be warming up)" -ForegroundColor Yellow
    } else {
        foreach ($a in $liveAgents) {
            $stateColor = switch ($a.state) {
                "IDLE"    { "Green" }
                "WORKING" { "Cyan" }
                "ERROR"   { "Red" }
                "PAUSED"  { "Yellow" }
                default   { "White" }
            }
            Write-Host ("  [{0}]  {1,-40} state={2}  age={3}s" -f $a.heartbeat_source.ToUpper(), $a.name, $a.state, $a.heartbeat_age_seconds) -ForegroundColor $stateColor
        }
    }

    Write-Host ""
    Write-Host "  --- Non-live (managed/synthesized) ---" -ForegroundColor DarkGray
    $managedAgents = $agents | Where-Object { $_.heartbeat_source -ne "live" } | Sort-Object index
    foreach ($a in $managedAgents) {
        Write-Host ("  [{0}]  {1,-40} runtime={2}" -f $a.heartbeat_source.ToUpper(), $a.name, $a.runtime_class) -ForegroundColor DarkGray
    }

    # Summary verdict
    Write-Host ""
    if ($liveCount -eq $totalAgents) {
        Write-Host "  RESULT: ALL $totalAgents agents reporting live heartbeats." -ForegroundColor Green
    } elseif ($liveCount -gt 0) {
        Write-Host ("  RESULT: {0}/{1} agents live. {2} managed/synthesized (expected for condensed topology)." -f $liveCount, $totalAgents, $managedCount) -ForegroundColor Yellow
    } else {
        Write-Host "  RESULT: No live agent heartbeats detected. Agents may be warming up — retry in 30s." -ForegroundColor Red
    }

} catch {
    Write-Host "  [ERROR] Could not reach /internal/operations/agents: $_" -ForegroundColor Red
}

# ── Quick embedding test via knowledge_lake health ───────────────────────────
Write-Host ""
Write-Host "[ BONUS ] Embedding Provider Check" -ForegroundColor Yellow
try {
    $readyz2 = Invoke-RestMethod -Uri "$OrchestratorUrl/readyz" -Method GET -TimeoutSec 10
    $qdrantOk = $readyz2.qdrant_ready
    $milvusOk = $readyz2.milvus_ready
    Write-Host ("  Qdrant (semantic store): {0}" -f $(if ($qdrantOk) { "[OK] ready for vector writes/reads" } else { "[FAIL]" })) -ForegroundColor $(if ($qdrantOk) { "Green" } else { "Red" })
    Write-Host ("  Milvus (vector store):   {0}" -f $(if ($milvusOk) { "[OK] ready for vector writes/reads" } else { "[FAIL]" })) -ForegroundColor $(if ($milvusOk) { "Green" } else { "Red" })
    if ($qdrantOk -and $milvusOk) {
        Write-Host "  Embedding pipeline: stores ready. Actual embedding calls require GEMINI_API_KEY in .env." -ForegroundColor Cyan
    }
} catch {
    Write-Host "  [ERROR] $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Done." -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""
