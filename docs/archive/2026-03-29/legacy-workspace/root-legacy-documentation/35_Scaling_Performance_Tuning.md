# DOCUMENT 35: SCALING & PERFORMANCE TUNING
## Holy Grail Refinery - Operations & Deployment

**Document ID:** 35  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Operations & Deployment  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document provides **comprehensive scaling strategies and performance optimization techniques** for the Holy Grail Refinery system. It covers vertical scaling, horizontal scaling, performance tuning, resource optimization, and capacity planning to maintain optimal system performance as workload increases.

**Scaling Philosophy:**
- **Vertical First:** Maximize single-machine efficiency on AW1
- **Horizontal Ready:** Prepared for multi-node expansion
- **Data-Driven:** Scale based on metrics, not assumptions
- **Cost-Conscious:** Optimize before scaling

**Performance Targets:**
- ⚡ **API Response Time:** < 100ms (P95)
- 🔄 **Mission Completion:** < 30 minutes (standard complexity)
- 💾 **Database Query Time:** < 50ms (P95)
- 📊 **System Throughput:** 100+ LogicNodes/minute

---

## TABLE OF CONTENTS

1. [Scaling Architecture](#1-scaling-architecture)
2. [Vertical Scaling Strategies](#2-vertical-scaling-strategies)
3. [Horizontal Scaling Preparation](#3-horizontal-scaling-preparation)
4. [Agent Performance Tuning](#4-agent-performance-tuning)
5. [Database Optimization](#5-database-optimization)
6. [Redis Performance](#6-redis-performance)
7. [API Gateway Optimization](#7-api-gateway-optimization)
8. [Resource Allocation](#8-resource-allocation)
9. [Load Testing](#9-load-testing)
10. [Capacity Planning](#10-capacity-planning)

---

## 1. SCALING ARCHITECTURE

### 1.1 Current State (AW1 - Single Node)

```
┌─────────────────────────────────────────────────────┐
│                  AW1 HARDWARE                       │
│  CPU: i7-14700F (20 cores, 28 threads)             │
│  RAM: 32GB DDR5-5600                                │
│  GPU: RTX 4060 Ti (16GB VRAM)                       │
│  Storage: 1TB NVMe SSD                              │
│                                                     │
│  ┌─────────────────────────────────────────────┐  │
│  │     35 Agent Containers                     │  │
│  │     + 5 Infrastructure Containers           │  │
│  │     = 40 Total Containers                   │  │
│  └─────────────────────────────────────────────┘  │
│                                                     │
│  Current Utilization:                               │
│    CPU: ~60% average, 85% peak                     │
│    RAM: ~28GB used, 4GB free                       │
│    Disk I/O: ~30% of SSD capacity                  │
│    Network: < 10% of 1Gbps                         │
└─────────────────────────────────────────────────────┘
```

### 1.2 Scaling Decision Tree

```
Start
  │
  ├─> Is CPU > 80% sustained? ──YES─> Vertical Scale (Add CPU)
  │                              │
  │                              NO
  │                              │
  ├─> Is RAM > 85% used? ──YES──> Vertical Scale (Add RAM)
  │                         │
  │                         NO
  │                         │
  ├─> Is Disk I/O > 70%? ──YES─> Upgrade Storage (NVMe RAID)
  │                         │
  │                         NO
  │                         │
  ├─> Are queues backing up? ──YES─> Horizontal Scale (Add Nodes)
  │                            │
  │                            NO
  │                            │
  └─> System Healthy ──> Monitor & Optimize
```

---

## 2. VERTICAL SCALING STRATEGIES

### 2.1 CPU Optimization

**File:** `scripts/scaling/optimize_cpu.sh`

```bash
#!/bin/bash
# CPU optimization and allocation

set -e

echo "CPU Optimization for Holy Grail Refinery"
echo "========================================="

# 1. Analyze current CPU usage
echo "Current CPU allocation per agent:"
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}" | \
    grep "hgr-" | sort -k2 -rn | head -20

# 2. Identify high-CPU agents
echo ""
echo "High CPU agents (>50% usage):"
HIGH_CPU_AGENTS=$(docker stats --no-stream --format "{{.Name}} {{.CPUPerc}}" | \
    grep "hgr-" | awk '$2 > 50.0 {print $1}')

if [ -z "$HIGH_CPU_AGENTS" ]; then
    echo "  No high-CPU agents detected"
else
    echo "$HIGH_CPU_AGENTS"
    
    # Recommend actions
    echo ""
    echo "Recommendations:"
    for AGENT in $HIGH_CPU_AGENTS; do
        CURRENT_CPU=$(docker inspect $AGENT | \
            jq -r '.[0].HostConfig.NanoCpus' | \
            awk '{print $1/1000000000}')
        
        if [ "$CURRENT_CPU" == "null" ] || [ -z "$CURRENT_CPU" ]; then
            CURRENT_CPU="unlimited"
            RECOMMENDED="2.0"
        else
            RECOMMENDED=$(echo "$CURRENT_CPU * 1.5" | bc)
        fi
        
        echo "  $AGENT: Current=$CURRENT_CPU CPUs, Recommend=$RECOMMENDED CPUs"
    done
fi

# 3. CPU affinity optimization
echo ""
echo "Setting CPU affinity for critical agents..."

# Pin CEO agent to performance cores (0-7)
docker update hgr-ceo-001 --cpuset-cpus="0-7"
echo "  CEO Agent: Cores 0-7 (Performance)"

# Pin PM agent to performance cores
docker update hgr-pm-001 --cpuset-cpus="0-7"
echo "  PM Agent: Cores 0-7 (Performance)"

# Pin audit agents to efficiency cores (8-19)
for AUDIT in hgr-audit-lead-001 hgr-audit-correctness-001 hgr-audit-perf-001; do
    docker update $AUDIT --cpuset-cpus="8-19" 2>/dev/null || true
    echo "  $AUDIT: Cores 8-19 (Efficiency)"
done

# 4. Verify changes
echo ""
echo "Updated CPU allocations:"
docker inspect $(docker ps --filter "name=hgr-ceo" --format "{{.Names}}") | \
    jq -r '.[0] | "\(.Name): CPUs=\(.HostConfig.CpusetCpus), Shares=\(.HostConfig.CpuShares)"'

echo ""
echo "✓ CPU optimization complete"
```

### 2.2 Memory Optimization

**File:** `scripts/scaling/optimize_memory.sh`

```bash
#!/bin/bash
# Memory optimization and allocation

set -e

echo "Memory Optimization for Holy Grail Refinery"
echo "==========================================="

# 1. Current memory usage
echo "Current memory usage:"
free -h

echo ""
echo "Per-agent memory usage:"
docker stats --no-stream --format "table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}" | \
    grep "hgr-" | sort -k3 -rn | head -20

# 2. Identify memory-heavy agents
echo ""
echo "Memory-intensive agents (>1GB):"
docker stats --no-stream --format "{{.Name}} {{.MemUsage}}" | \
    grep "hgr-" | \
    awk '{
        split($2, a, "G");
        if (a[1] > 1.0) print $1, $2
    }'

# 3. Set memory limits per agent type
echo ""
echo "Setting optimized memory limits..."

# Executive agents (higher limits)
docker update hgr-ceo-001 --memory="2G" --memory-swap="2G"
docker update hgr-pm-001 --memory="2G" --memory-swap="2G"
echo "  Executive agents: 2GB limit"

# Language specialists (standard limits)
for AGENT in $(docker ps --filter "name=hgr-agent-" --format "{{.Names}}"); do
    docker update $AGENT --memory="1G" --memory-swap="1G"
done
echo "  Language specialists: 1GB limit"

# Support agents (lower limits)
for AGENT in $(docker ps --filter "name=hgr-support-" --format "{{.Names}}"); do
    docker update $AGENT --memory="512M" --memory-swap="512M"
done
echo "  Support agents: 512MB limit"

# 4. Enable memory compression
echo ""
echo "Enabling memory compression..."
sysctl vm.swappiness=10  # Reduce swap usage
sysctl vm.vfs_cache_pressure=50  # Reduce inode/dentry cache pressure

# 5. Clear page cache (safe operation)
echo "Clearing page cache..."
sync && echo 3 > /proc/sys/vm/drop_caches

echo ""
echo "Updated memory allocation:"
free -h

echo ""
echo "✓ Memory optimization complete"
```

### 2.3 Storage Optimization

**File:** `scripts/scaling/optimize_storage.sh`

```bash
#!/bin/bash
# Storage optimization

set -e

echo "Storage Optimization for Holy Grail Refinery"
echo "==========================================="

# 1. Current storage usage
echo "Disk usage:"
df -h / /var/lib/docker

echo ""
echo "Docker storage breakdown:"
docker system df

# 2. Clean up unused resources
echo ""
echo "Cleaning up unused Docker resources..."

# Remove stopped containers
STOPPED=$(docker ps -a --filter "status=exited" --format "{{.Names}}" | wc -l)
if [ $STOPPED -gt 0 ]; then
    docker container prune -f
    echo "  Removed $STOPPED stopped containers"
fi

# Remove unused images
DANGLING=$(docker images -f "dangling=true" -q | wc -l)
if [ $DANGLING -gt 0 ]; then
    docker image prune -f
    echo "  Removed $DANGLING dangling images"
fi

# Remove unused volumes
UNUSED_VOLUMES=$(docker volume ls -f "dangling=true" -q | wc -l)
if [ $UNUSED_VOLUMES -gt 0 ]; then
    docker volume prune -f
    echo "  Removed $UNUSED_VOLUMES unused volumes"
fi

# 3. Optimize Docker storage driver
echo ""
echo "Checking storage driver..."
DRIVER=$(docker info --format '{{.Driver}}')
echo "  Current driver: $DRIVER"

if [ "$DRIVER" != "overlay2" ]; then
    echo "  ⚠ Recommend switching to overlay2 for better performance"
fi

# 4. Compress old logs
echo ""
echo "Compressing old logs..."
find /var/log/hgr -name "*.log" -mtime +7 -exec gzip {} \;
echo "  Compressed logs older than 7 days"

# 5. Archive old backups
echo ""
echo "Archiving old backups..."
OLD_BACKUPS=$(find /opt/hgr/backups -name "*.tar.gz" -mtime +30 | wc -l)
if [ $OLD_BACKUPS -gt 0 ]; then
    mkdir -p /opt/hgr/backups/archive
    find /opt/hgr/backups -name "*.tar.gz" -mtime +30 \
        -exec mv {} /opt/hgr/backups/archive/ \;
    echo "  Archived $OLD_BACKUPS old backups"
fi

# 6. Final disk usage
echo ""
echo "Updated disk usage:"
df -h / /var/lib/docker

echo ""
echo "✓ Storage optimization complete"
```

---

## 3. HORIZONTAL SCALING PREPARATION

### 3.1 Multi-Node Architecture

```
┌─────────────────────────────────────────────────────┐
│              NODE 1 (Executive + Support)           │
│  - PM Agent, CEO Agent                              │
│  - IS Agent, Support Ring                           │
│  - PostgreSQL Primary                               │
│  - Redis Primary                                    │
└─────────────────┬───────────────────────────────────┘
                  │
    ┌─────────────┼─────────────┬─────────────┐
    │             │             │             │
┌───▼────┐  ┌────▼────┐  ┌─────▼────┐  ┌────▼────┐
│ NODE 2 │  │ NODE 3  │  │ NODE 4   │  │ NODE 5  │
│ Pod A  │  │ Pod B   │  │ Pod C    │  │ Pod D   │
│        │  │         │  │          │  │         │
│ 6 Agents│ │6 Agents │  │6 Agents  │  │6 Agents │
└────────┘  └─────────┘  └──────────┘  └─────────┘
    │             │             │             │
    └─────────────┴─────────────┴─────────────┘
                  │
         Shared Network Storage
```

### 3.2 Distributed Configuration

**File:** `config/distributed/docker-compose.distributed.yml`

```yaml
version: '3.8'

# This configuration enables horizontal scaling
# across multiple physical nodes

networks:
  hgr-network:
    driver: overlay
    attachable: true

services:
  # Executive node services
  ceo-001:
    image: hgr-ceo:latest
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.labels.role == executive
    environment:
      - REDIS_HOSTS=redis-1:6379,redis-2:6379,redis-3:6379
      - POSTGRES_HOSTS=pg-1:5432,pg-2:5432,pg-3:5432
  
  # Pod A services (can scale across nodes)
  agent-py-001:
    image: hgr-agent-python:latest
    deploy:
      replicas: 2  # Can scale horizontally
      placement:
        constraints:
          - node.labels.pod == A
    environment:
      - REDIS_HOSTS=redis-1:6379,redis-2:6379,redis-3:6379
  
  # Redis cluster
  redis-1:
    image: redis:7-cluster
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.labels.role == executive
    command: >
      redis-server
      --cluster-enabled yes
      --cluster-config-file nodes.conf
      --cluster-node-timeout 5000
      --appendonly yes
  
  # PostgreSQL with replication
  postgres-primary:
    image: postgres:16
    deploy:
      replicas: 1
      placement:
        constraints:
          - node.labels.role == executive
    environment:
      - POSTGRES_REPLICATION=on
      - POSTGRES_REPLICATION_SLOT=replica_1
```

### 3.3 Load Balancing Configuration

**File:** `config/distributed/nginx-lb.conf`

```nginx
# Load balancer for API gateway

upstream hgr_api {
    least_conn;  # Least connections algorithm
    
    # Health check
    check interval=3000 rise=2 fall=3 timeout=1000;
    
    # API gateway instances
    server api-gateway-1:8000 max_fails=3 fail_timeout=30s;
    server api-gateway-2:8000 max_fails=3 fail_timeout=30s;
    server api-gateway-3:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name api.hgr.local;
    
    location / {
        proxy_pass http://hgr_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    location /health {
        access_log off;
        proxy_pass http://hgr_api/health;
    }
}
```

---

## 4. AGENT PERFORMANCE TUNING

### 4.1 Context Window Optimization

**File:** `scripts/performance/optimize_context.py`

```python
#!/usr/bin/env python3
"""
Optimize agent context window usage
"""

import json
from typing import Dict, List

class ContextOptimizer:
    """Optimize context window allocation and usage"""
    
    def __init__(self):
        self.context_limits = {
            'PM-001': 1_000_000,
            'CEO-001': 1_000_000,
            'AGENT-*': 1_000_000,
            'AUDIT-*': 500_000,
            'SUPPORT-*': 200_000
        }
    
    def analyze_context_usage(self, agent_id: str) -> Dict:
        """Analyze how agent is using context window"""
        # Query from monitoring database
        usage_data = self._get_usage_data(agent_id)
        
        recommendations = []
        
        # Check if consistently near limit
        if usage_data['avg_usage'] > usage_data['limit'] * 0.9:
            recommendations.append({
                'type': 'increase_limit',
                'current': usage_data['limit'],
                'recommended': int(usage_data['limit'] * 1.5),
                'reason': 'Consistently near context limit'
            })
        
        # Check if mostly empty
        elif usage_data['avg_usage'] < usage_data['limit'] * 0.3:
            recommendations.append({
                'type': 'decrease_limit',
                'current': usage_data['limit'],
                'recommended': int(usage_data['limit'] * 0.7),
                'reason': 'Under-utilizing allocated context'
            })
        
        # Check for context thrashing
        if usage_data['truncation_rate'] > 0.1:
            recommendations.append({
                'type': 'optimize_pinning',
                'truncation_rate': usage_data['truncation_rate'],
                'reason': 'High context truncation rate'
            })
        
        return {
            'agent_id': agent_id,
            'current_usage': usage_data,
            'recommendations': recommendations
        }
    
    def _get_usage_data(self, agent_id: str) -> Dict:
        """Get context usage data from monitoring"""
        # Simplified - would query actual monitoring database
        return {
            'limit': 1_000_000,
            'avg_usage': 750_000,
            'peak_usage': 950_000,
            'truncation_rate': 0.05  # 5% of requests truncated
        }
    
    def optimize_pinning_strategy(self, agent_id: str):
        """Optimize what content stays pinned in context"""
        
        strategies = {
            'language_specialist': {
                'pin_always': [
                    'agent_identity.md',
                    'refined_ir_spec.json',
                    'language_grammar.bnf'
                ],
                'pin_conditional': [
                    'recent_extractions (last 10)',
                    'active_mission_context'
                ],
                'evict_first': [
                    'old_missions',
                    'infrequent_concepts'
                ]
            },
            'audit': {
                'pin_always': [
                    'test_framework.py',
                    'verification_criteria.json'
                ],
                'pin_conditional': [
                    'logicnodes_under_test',
                    'test_results (last 100)'
                ],
                'evict_first': [
                    'historical_test_data'
                ]
            }
        }
        
        agent_type = self._get_agent_type(agent_id)
        return strategies.get(agent_type, strategies['language_specialist'])
    
    def _get_agent_type(self, agent_id: str) -> str:
        """Determine agent type from ID"""
        if agent_id.startswith('AGENT-'):
            return 'language_specialist'
        elif agent_id.startswith('AUDIT-'):
            return 'audit'
        elif agent_id.startswith('MANAGER-'):
            return 'manager'
        else:
            return 'other'


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: optimize_context.py <agent_id>")
        sys.exit(1)
    
    optimizer = ContextOptimizer()
    result = optimizer.analyze_context_usage(sys.argv[1])
    
    print(json.dumps(result, indent=2))
```

### 4.2 Agent Response Time Optimization

**File:** `scripts/performance/profile_agent.py`

```python
#!/usr/bin/env python3
"""
Profile agent performance and identify bottlenecks
"""

import time
import cProfile
import pstats
from io import StringIO

class AgentProfiler:
    """Profile agent execution to find bottlenecks"""
    
    def profile_extraction_pipeline(self, agent_id: str, source_code: str):
        """Profile the LogicNode extraction pipeline"""
        
        profiler = cProfile.Profile()
        
        # Start profiling
        profiler.enable()
        
        # Simulate extraction (would call actual agent)
        result = self._mock_extraction(source_code)
        
        # Stop profiling
        profiler.disable()
        
        # Analyze results
        stream = StringIO()
        stats = pstats.Stats(profiler, stream=stream)
        stats.sort_stats('cumulative')
        stats.print_stats(20)  # Top 20 functions
        
        print(stream.getvalue())
        
        return result
    
    def _mock_extraction(self, source_code: str):
        """Mock extraction for profiling"""
        # Phase 1: Parse source code
        time.sleep(0.1)
        ast = self._parse_code(source_code)
        
        # Phase 2: Query knowledge lake
        time.sleep(0.3)
        context = self._query_knowledge(ast)
        
        # Phase 3: LLM inference
        time.sleep(1.0)
        logicnode = self._generate_logicnode(ast, context)
        
        # Phase 4: Validation
        time.sleep(0.2)
        validated = self._validate(logicnode)
        
        return validated
    
    def _parse_code(self, code: str):
        return {"type": "function", "name": "example"}
    
    def _query_knowledge(self, ast):
        return {"concepts": ["function_definition"]}
    
    def _generate_logicnode(self, ast, context):
        return {"paradigm": "dynamic", "domain": "functions"}
    
    def _validate(self, logicnode):
        return logicnode
    
    def identify_bottlenecks(self, profile_data):
        """Identify performance bottlenecks"""
        
        bottlenecks = []
        
        # Analyze each phase
        phases = {
            'parsing': 0.1,
            'knowledge_query': 0.3,
            'llm_inference': 1.0,
            'validation': 0.2
        }
        
        total_time = sum(phases.values())
        
        for phase, duration in phases.items():
            percentage = (duration / total_time) * 100
            
            if percentage > 50:
                bottlenecks.append({
                    'phase': phase,
                    'duration_s': duration,
                    'percentage': percentage,
                    'optimization': self._get_optimization(phase)
                })
        
        return bottlenecks
    
    def _get_optimization(self, phase: str) -> str:
        """Get optimization recommendations for phase"""
        
        optimizations = {
            'parsing': 'Use compiled grammar, cache parse trees',
            'knowledge_query': 'Add vector index, implement query cache',
            'llm_inference': 'Batch requests, use prompt cache, reduce token count',
            'validation': 'Parallelize validation rules, cache common checks'
        }
        
        return optimizations.get(phase, 'No specific optimization available')


if __name__ == "__main__":
    profiler = AgentProfiler()
    
    sample_code = """
    def example_function(x, y):
        return x + y
    """
    
    result = profiler.profile_extraction_pipeline('AGENT-PY-001', sample_code)
    bottlenecks = profiler.identify_bottlenecks(None)
    
    print("\nIdentified Bottlenecks:")
    for bn in bottlenecks:
        print(f"  {bn['phase']}: {bn['duration_s']}s ({bn['percentage']:.1f}%)")
        print(f"    Optimization: {bn['optimization']}")
```

---

## 5. DATABASE OPTIMIZATION

### 5.1 Query Performance Tuning

**File:** `scripts/performance/optimize_queries.sql`

```sql
-- Query performance optimization for PostgreSQL

-- 1. Analyze slow queries
SELECT 
    query,
    calls,
    total_exec_time / 1000 as total_time_sec,
    mean_exec_time / 1000 as avg_time_sec,
    max_exec_time / 1000 as max_time_sec
FROM pg_stat_statements
WHERE mean_exec_time > 100  -- Queries averaging > 100ms
ORDER BY mean_exec_time DESC
LIMIT 20;

-- 2. Find missing indexes
SELECT 
    schemaname,
    tablename,
    seq_scan,
    seq_tup_read,
    idx_scan,
    seq_tup_read / seq_scan as avg_seq_tup
FROM pg_stat_user_tables
WHERE seq_scan > 100  -- Many sequential scans
  AND idx_scan < seq_scan  -- Indexes not being used
ORDER BY seq_tup_read DESC;

-- 3. Unused indexes (candidates for removal)
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE idx_scan = 0
  AND indexrelname NOT LIKE '%_pkey'
ORDER BY pg_relation_size(indexrelid) DESC;

-- 4. Index bloat check
SELECT 
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) as size,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC
LIMIT 20;

-- 5. Optimize specific tables
-- LogicNode Registry
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_logicnodes_paradigm_domain_concept 
    ON logicnodes(paradigm, domain, concept) 
    WHERE is_deleted = FALSE;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_logicnodes_audit_status 
    ON logicnodes(audit_status) 
    WHERE audit_status IN ('pending', 'testing');

-- Knowledge Lake
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_language_type 
    ON documents(language_id, doc_type) 
    WHERE is_deprecated = FALSE;

-- Traceability
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_logs_timestamp_desc 
    ON logs(timestamp DESC);

-- 6. Update table statistics
ANALYZE logicnodes;
ANALYZE documents;
ANALYZE agent_metrics;

-- 7. Vacuum to reclaim space
VACUUM ANALYZE logicnodes;
VACUUM ANALYZE documents;
```

### 5.2 Connection Pooling

**File:** `config/database/pgbouncer.ini`

```ini
[databases]
hgr_knowledge = host=localhost port=5432 dbname=hgr_knowledge
hgr_state = host=localhost port=5432 dbname=hgr_state
hgr_registry = host=localhost port=5432 dbname=hgr_registry
hgr_traceability = host=localhost port=5432 dbname=hgr_traceability
hgr_models = host=localhost port=5432 dbname=hgr_models

[pgbouncer]
# Connection pooling mode
pool_mode = transaction

# Max connections
max_client_conn = 1000
default_pool_size = 25
min_pool_size = 10
reserve_pool_size = 5

# Connection limits per user/database
max_db_connections = 50
max_user_connections = 50

# Timeouts
server_idle_timeout = 600
server_lifetime = 3600
query_timeout = 300

# Logging
log_connections = 1
log_disconnections = 1
log_pooler_errors = 1

# Performance
server_check_delay = 30
server_check_query = SELECT 1
```

---

## 6. REDIS PERFORMANCE

### 6.1 Redis Configuration Tuning

**File:** `config/redis/redis-optimized.conf`

```conf
# Redis performance-optimized configuration

# Memory
maxmemory 8gb
maxmemory-policy allkeys-lru
maxmemory-samples 10

# Persistence (optimized for performance)
save 900 1
save 300 10
save 60 10000

appendonly yes
appendfsync everysec
no-appendfsync-on-rewrite yes
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# Networking
tcp-backlog 511
timeout 300
tcp-keepalive 300

# Performance
lazyfree-lazy-eviction yes
lazyfree-lazy-expire yes
lazyfree-lazy-server-del yes
replica-lazy-flush yes

# Threading (Redis 6.0+)
io-threads 4
io-threads-do-reads yes

# Slow log
slowlog-log-slower-than 10000  # 10ms
slowlog-max-len 128

# Memory optimization
activedefrag yes
active-defrag-ignore-bytes 100mb
active-defrag-threshold-lower 10
active-defrag-threshold-upper 25
```

### 6.2 Redis Monitoring Script

**File:** `scripts/performance/monitor_redis.sh`

```bash
#!/bin/bash
# Monitor Redis performance

echo "Redis Performance Metrics"
echo "========================"

# Memory usage
echo "Memory Usage:"
redis-cli INFO memory | grep "used_memory_human\|used_memory_peak_human\|mem_fragmentation_ratio"

echo ""

# Command statistics
echo "Top Commands (by calls):"
redis-cli INFO commandstats | grep "cmdstat_" | \
    awk -F'[:,]' '{print $1, $2}' | sort -k2 -rn | head -10

echo ""

# Slow log
echo "Slow Commands:"
redis-cli SLOWLOG GET 10

echo ""

# Connected clients
echo "Connected Clients:"
redis-cli INFO clients | grep "connected_clients"

echo ""

# Keyspace statistics
echo "Keyspace:"
redis-cli INFO keyspace
```

---

## 7. API GATEWAY OPTIMIZATION

### 7.1 FastAPI Performance Configuration

**File:** `api/config/production.py`

```python
"""
Production configuration for FastAPI
"""

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

def create_optimized_app() -> FastAPI:
    """Create production-optimized FastAPI app"""
    
    app = FastAPI(
        title="Holy Grail Refinery API",
        docs_url=None,  # Disable docs in production
        redoc_url=None,
        openapi_url=None
    )
    
    # Compression
    app.add_middleware(
        GZipMiddleware,
        minimum_size=1000,  # Only compress responses > 1KB
        compresslevel=6  # Balance speed/compression
    )
    
    # CORS (restrictive in production)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://hgr.company.com"],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=3600  # Cache preflight for 1 hour
    )
    
    return app


def run_production_server():
    """Run with optimized uvicorn configuration"""
    
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        workers=4,  # One per CPU core recommended
        loop="uvloop",  # Faster event loop
        http="httptools",  # Faster HTTP parser
        log_level="warning",  # Reduce log verbosity
        access_log=False,  # Disable access log for performance
        limit_concurrency=1000,
        limit_max_requests=10000,  # Restart worker after 10k requests
        timeout_keep_alive=5
    )
```

---

## 8. RESOURCE ALLOCATION

### 8.1 Dynamic Resource Allocation

**File:** `scripts/scaling/auto_scale.py`

```python
#!/usr/bin/env python3
"""
Automatic resource scaling based on metrics
"""

import docker
from prometheus_api_client import PrometheusConnect
from datetime import datetime, timedelta

class AutoScaler:
    """Automatically scale agent resources based on load"""
    
    def __init__(self, prometheus_url='http://localhost:9090'):
        self.docker_client = docker.from_env()
        self.prom = PrometheusConnect(url=prometheus_url)
        
        # Scaling thresholds
        self.cpu_scale_up_threshold = 80  # %
        self.cpu_scale_down_threshold = 30  # %
        self.memory_scale_up_threshold = 85  # %
        self.memory_scale_down_threshold = 40  # %
    
    def check_and_scale(self):
        """Check metrics and scale agents if needed"""
        
        agents = self.docker_client.containers.list(
            filters={'name': 'hgr-agent-'}
        )
        
        for agent in agents:
            agent_id = agent.name
            
            # Get metrics
            cpu_usage = self._get_cpu_usage(agent_id)
            memory_usage = self._get_memory_usage(agent_id)
            
            # Scale CPU if needed
            if cpu_usage > self.cpu_scale_up_threshold:
                self._scale_cpu(agent, increase=True)
            elif cpu_usage < self.cpu_scale_down_threshold:
                self._scale_cpu(agent, increase=False)
            
            # Scale memory if needed
            if memory_usage > self.memory_scale_up_threshold:
                self._scale_memory(agent, increase=True)
            elif memory_usage < self.memory_scale_down_threshold:
                self._scale_memory(agent, increase=False)
    
    def _get_cpu_usage(self, agent_id: str) -> float:
        """Get current CPU usage for agent"""
        query = f'rate(container_cpu_usage_seconds_total{{name="{agent_id}"}}[5m]) * 100'
        result = self.prom.custom_query(query)
        
        if result:
            return float(result[0]['value'][1])
        return 0.0
    
    def _get_memory_usage(self, agent_id: str) -> float:
        """Get current memory usage percentage"""
        query = f'(container_memory_usage_bytes{{name="{agent_id}"}} / container_spec_memory_limit_bytes{{name="{agent_id}"}}) * 100'
        result = self.prom.custom_query(query)
        
        if result:
            return float(result[0]['value'][1])
        return 0.0
    
    def _scale_cpu(self, container, increase: bool):
        """Scale CPU allocation"""
        current_cpus = container.attrs['HostConfig']['NanoCpus'] / 1e9
        
        if increase:
            new_cpus = min(current_cpus * 1.5, 4.0)  # Max 4 CPUs per agent
        else:
            new_cpus = max(current_cpus * 0.75, 0.5)  # Min 0.5 CPU
        
        if abs(new_cpus - current_cpus) > 0.1:  # Only if significant change
            container.update(nano_cpus=int(new_cpus * 1e9))
            print(f"Scaled {container.name} CPU: {current_cpus:.2f} → {new_cpus:.2f}")
    
    def _scale_memory(self, container, increase: bool):
        """Scale memory allocation"""
        current_mem = container.attrs['HostConfig']['Memory']
        
        if increase:
            new_mem = min(current_mem * 1.5, 4 * 1024**3)  # Max 4GB
        else:
            new_mem = max(current_mem * 0.75, 512 * 1024**2)  # Min 512MB
        
        if abs(new_mem - current_mem) / current_mem > 0.2:  # Only if >20% change
            container.update(mem_limit=int(new_mem))
            print(f"Scaled {container.name} Memory: {current_mem/1024**3:.2f}GB → {new_mem/1024**3:.2f}GB")


if __name__ == "__main__":
    scaler = AutoScaler()
    
    print("Auto-scaler starting...")
    print("Checking metrics and scaling agents...")
    
    scaler.check_and_scale()
    
    print("Auto-scaling complete")
```

---

## 9. LOAD TESTING

### 9.1 Load Test Suite

**File:** `tests/performance/load_test.py`

```python
#!/usr/bin/env python3
"""
Load testing for Holy Grail Refinery
"""

import asyncio
import aiohttp
import time
from typing import List, Dict
import statistics

class LoadTester:
    """Run load tests against HGR system"""
    
    def __init__(self, base_url='http://localhost:8000'):
        self.base_url = base_url
        self.results = []
    
    async def run_load_test(
        self,
        concurrent_users: int = 10,
        requests_per_user: int = 100
    ):
        """Run load test with specified parameters"""
        
        print(f"Starting load test:")
        print(f"  Concurrent users: {concurrent_users}")
        print(f"  Requests per user: {requests_per_user}")
        print(f"  Total requests: {concurrent_users * requests_per_user}")
        print("")
        
        start_time = time.time()
        
        # Create tasks for concurrent users
        tasks = [
            self._user_session(user_id, requests_per_user)
            for user_id in range(concurrent_users)
        ]
        
        # Run all users concurrently
        await asyncio.gather(*tasks)
        
        end_time = time.time()
        
        # Analyze results
        self._print_results(end_time - start_time)
    
    async def _user_session(self, user_id: int, num_requests: int):
        """Simulate a single user making requests"""
        
        async with aiohttp.ClientSession() as session:
            for i in range(num_requests):
                await self._make_request(session, user_id, i)
    
    async def _make_request(
        self,
        session: aiohttp.ClientSession,
        user_id: int,
        request_id: int
    ):
        """Make a single API request and record metrics"""
        
        url = f"{self.base_url}/api/v1/health"
        start = time.time()
        
        try:
            async with session.get(url, timeout=30) as response:
                duration = time.time() - start
                
                self.results.append({
                    'user_id': user_id,
                    'request_id': request_id,
                    'status': response.status,
                    'duration': duration,
                    'success': response.status == 200
                })
        
        except Exception as e:
            duration = time.time() - start
            self.results.append({
                'user_id': user_id,
                'request_id': request_id,
                'status': 0,
                'duration': duration,
                'success': False,
                'error': str(e)
            })
    
    def _print_results(self, total_time: float):
        """Print load test results"""
        
        total_requests = len(self.results)
        successful = sum(1 for r in self.results if r['success'])
        failed = total_requests - successful
        
        durations = [r['duration'] for r in self.results if r['success']]
        
        print("")
        print("="*50)
        print("LOAD TEST RESULTS")
        print("="*50)
        print(f"Total Time: {total_time:.2f}s")
        print(f"Total Requests: {total_requests}")
        print(f"Successful: {successful} ({successful/total_requests*100:.1f}%)")
        print(f"Failed: {failed} ({failed/total_requests*100:.1f}%)")
        print("")
        print(f"Requests/sec: {total_requests/total_time:.2f}")
        print("")
        
        if durations:
            print("Response Times:")
            print(f"  Min: {min(durations)*1000:.2f}ms")
            print(f"  Max: {max(durations)*1000:.2f}ms")
            print(f"  Mean: {statistics.mean(durations)*1000:.2f}ms")
            print(f"  Median: {statistics.median(durations)*1000:.2f}ms")
            print(f"  P95: {statistics.quantiles(durations, n=20)[18]*1000:.2f}ms")
            print(f"  P99: {statistics.quantiles(durations, n=100)[98]*1000:.2f}ms")
        
        print("="*50)


async def main():
    tester = LoadTester()
    
    # Run multiple test scenarios
    scenarios = [
        (10, 100),   # 10 users, 100 requests each
        (50, 50),    # 50 users, 50 requests each
        (100, 20),   # 100 users, 20 requests each
    ]
    
    for users, requests in scenarios:
        print(f"\nScenario: {users} users, {requests} requests each")
        await tester.run_load_test(users, requests)
        await asyncio.sleep(5)  # Cooldown between scenarios


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 10. CAPACITY PLANNING

### 10.1 Growth Projection

**File:** `scripts/scaling/capacity_forecast.py`

```python
#!/usr/bin/env python3
"""
Capacity planning and growth forecasting
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression

class CapacityForecaster:
    """Forecast future resource needs"""
    
    def __init__(self, historical_data_file='metrics/historical_usage.csv'):
        self.data = pd.read_csv(historical_data_file)
    
    def forecast_cpu_needs(self, days_ahead=90):
        """Forecast CPU requirements"""
        
        # Prepare data
        self.data['date'] = pd.to_datetime(self.data['date'])
        self.data['days'] = (self.data['date'] - self.data['date'].min()).dt.days
        
        # Train model
        X = self.data[['days']].values
        y = self.data['cpu_usage_percent'].values
        
        model = LinearRegression()
        model.fit(X, y)
        
        # Forecast
        future_days = self.data['days'].max() + days_ahead
        forecast = model.predict([[future_days]])[0]
        
        # Calculate when 80% capacity will be reached
        days_to_80 = (80 - y[-1]) / model.coef_[0]
        
        return {
            'current_usage': float(y[-1]),
            'forecast_usage': float(forecast),
            'growth_rate_per_day': float(model.coef_[0]),
            'days_until_80_percent': int(days_to_80) if days_to_80 > 0 else None,
            'recommendation': self._get_cpu_recommendation(forecast, days_to_80)
        }
    
    def forecast_memory_needs(self, days_ahead=90):
        """Forecast memory requirements"""
        # Similar to CPU forecast
        pass
    
    def forecast_storage_needs(self, days_ahead=90):
        """Forecast storage requirements"""
        # Similar to CPU forecast
        pass
    
    def _get_cpu_recommendation(self, forecast_usage, days_to_80):
        """Generate actionable recommendations"""
        
        if days_to_80 and days_to_80 < 30:
            return {
                'action': 'URGENT',
                'message': f'CPU capacity will be reached in {int(days_to_80)} days',
                'steps': [
                    'Plan hardware upgrade immediately',
                    'Consider horizontal scaling',
                    'Optimize high-CPU agents'
                ]
            }
        elif days_to_80 and days_to_80 < 90:
            return {
                'action': 'PLAN',
                'message': f'CPU capacity will be reached in {int(days_to_80)} days',
                'steps': [
                    'Begin evaluating hardware options',
                    'Identify optimization opportunities',
                    'Budget for expansion'
                ]
            }
        else:
            return {
                'action': 'MONITOR',
                'message': 'CPU capacity adequate for forecast period',
                'steps': [
                    'Continue monitoring trends',
                    'Maintain current optimization efforts'
                ]
            }
    
    def generate_capacity_report(self):
        """Generate comprehensive capacity report"""
        
        cpu_forecast = self.forecast_cpu_needs(90)
        
        report = f"""
CAPACITY PLANNING REPORT
========================
Date: {datetime.now().strftime('%Y-%m-%d')}
Forecast Period: 90 days

CPU FORECAST
------------
Current Usage: {cpu_forecast['current_usage']:.1f}%
Forecast (90 days): {cpu_forecast['forecast_usage']:.1f}%
Growth Rate: {cpu_forecast['growth_rate_per_day']:.3f}% per day

Recommendation: {cpu_forecast['recommendation']['action']}
{cpu_forecast['recommendation']['message']}

Action Items:
"""
        for step in cpu_forecast['recommendation']['steps']:
            report += f"  - {step}\n"
        
        return report


if __name__ == "__main__":
    forecaster = CapacityForecaster()
    report = forecaster.generate_capacity_report()
    print(report)
```

---

## DOCUMENT METADATA

**Document ID:** 35  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Operations & Deployment  
**Owner:** Performance Engineering Lead  
**Dependencies:** Documents 32 (Production Deployment), 25 (Monitoring)  
**Next Document:** 36 (Incident Response Playbook)

---

*End of Scaling & Performance Tuning*
