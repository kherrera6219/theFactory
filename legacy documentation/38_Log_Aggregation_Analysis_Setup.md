# DOCUMENT 38: LOG AGGREGATION & ANALYSIS SETUP
## Holy Grail Refinery - Operations & Deployment

**Document ID:** 38  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Operations & Deployment  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document provides **complete implementation specifications** for centralized log aggregation and analysis using Grafana Loki, Promtail, and LogQL. It enables unified log collection from all 35 agents, infrastructure components, and application services with powerful search, filtering, and analysis capabilities.

**Key Components:**
- 📊 **Grafana Loki:** Centralized log aggregation database
- 🚀 **Promtail:** Log collection agent for all containers
- 🔍 **LogQL:** Query language for log analysis
- 🏷️ **Structured Logging:** JSON format with consistent fields
- ⚡ **Real-time Streaming:** Live log tailing and alerts
- 🗂️ **Log Retention:** Tiered storage with automatic archival

**Architecture:**
- **Collection:** Promtail agents on all Docker containers
- **Aggregation:** Loki cluster with distributed storage
- **Analysis:** Grafana Explore + LogQL queries
- **Retention:** 7 days hot, 30 days warm, 90 days cold
- **Compression:** ~10:1 compression ratio with chunking

---

## TABLE OF CONTENTS

1. [Loki Installation & Configuration](#1-loki-installation--configuration)
2. [Promtail Agent Setup](#2-promtail-agent-setup)
3. [Structured Logging Standards](#3-structured-logging-standards)
4. [Log Labels & Indexing Strategy](#4-log-labels--indexing-strategy)
5. [LogQL Query Patterns](#5-logql-query-patterns)
6. [Log Analysis Workflows](#6-log-analysis-workflows)
7. [Log Retention & Archival](#7-log-retention--archival)
8. [Performance Optimization](#8-performance-optimization)
9. [Troubleshooting Common Issues](#9-troubleshooting-common-issues)
10. [Integration with Monitoring](#10-integration-with-monitoring)

---

## 1. LOKI INSTALLATION & CONFIGURATION

### 1.1 Docker Compose Configuration

**File:** `logging/docker-compose.loki.yml`

```yaml
version: '3.8'

services:
  loki:
    image: grafana/loki:2.9.3
    container_name: hgr-loki
    restart: unless-stopped
    ports:
      - "3100:3100"
    volumes:
      - ./loki/config.yml:/etc/loki/config.yml
      - ./loki/data:/loki
      - ./loki/rules:/loki/rules
    command: -config.file=/etc/loki/config.yml
    networks:
      - logging
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:3100/ready"]
      interval: 10s
      timeout: 5s
      retries: 5

  promtail:
    image: grafana/promtail:2.9.3
    container_name: hgr-promtail
    restart: unless-stopped
    volumes:
      - ./promtail/config.yml:/etc/promtail/config.yml
      - /var/log:/var/log:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock
    command: -config.file=/etc/promtail/config.yml
    networks:
      - logging
    depends_on:
      - loki

networks:
  logging:
    external: true
```

### 1.2 Loki Configuration

**File:** `logging/loki/config.yml`

```yaml
auth_enabled: false

server:
  http_listen_port: 3100
  grpc_listen_port: 9096
  log_level: info

ingester:
  lifecycler:
    address: 127.0.0.1
    ring:
      kvstore:
        store: inmemory
      replication_factor: 1
    final_sleep: 0s
  chunk_idle_period: 5m
  chunk_retain_period: 30s
  max_chunk_age: 1h
  max_transfer_retries: 0
  wal:
    enabled: true
    dir: /loki/wal

schema_config:
  configs:
    - from: 2024-01-01
      store: boltdb-shipper
      object_store: filesystem
      schema: v11
      index:
        prefix: index_
        period: 24h

storage_config:
  boltdb_shipper:
    active_index_directory: /loki/boltdb-shipper-active
    cache_location: /loki/boltdb-shipper-cache
    cache_ttl: 24h
    shared_store: filesystem
  
  filesystem:
    directory: /loki/chunks

compactor:
  working_directory: /loki/compactor
  shared_store: filesystem
  compaction_interval: 10m
  retention_enabled: true
  retention_delete_delay: 2h
  retention_delete_worker_count: 150

limits_config:
  reject_old_samples: true
  reject_old_samples_max_age: 168h
  ingestion_rate_mb: 10
  ingestion_burst_size_mb: 20
  max_query_length: 721h
  max_query_parallelism: 32
  max_streams_per_user: 10000
  max_global_streams_per_user: 50000
  max_entries_limit_per_query: 10000

chunk_store_config:
  max_look_back_period: 0s

table_manager:
  retention_deletes_enabled: true
  retention_period: 2160h  # 90 days

ruler:
  storage:
    type: local
    local:
      directory: /loki/rules
  rule_path: /loki/rules-temp
  alertmanager_url: http://alertmanager:9093
  ring:
    kvstore:
      store: inmemory
  enable_api: true
```

### 1.3 Log Retention Rules

**File:** `logging/loki/rules/retention.yml`

```yaml
# Retention rules for different log types

overrides:
  # Critical logs: 90 days
  "critical":
    retention_period: 2160h
  
  # Agent logs: 30 days
  "agent":
    retention_period: 720h
  
  # Debug logs: 7 days
  "debug":
    retention_period: 168h
  
  # Access logs: 14 days
  "access":
    retention_period: 336h
```

---

## 2. PROMTAIL AGENT SETUP

### 2.1 Promtail Configuration

**File:** `logging/promtail/config.yml`

```yaml
server:
  http_listen_port: 9080
  grpc_listen_port: 0
  log_level: info

positions:
  filename: /tmp/positions.yaml

clients:
  - url: http://loki:3100/loki/api/v1/push
    batchwait: 1s
    batchsize: 1048576
    timeout: 10s

scrape_configs:
  # Docker container logs
  - job_name: docker
    docker_sd_configs:
      - host: unix:///var/run/docker.sock
        refresh_interval: 5s
    
    relabel_configs:
      # Only scrape HGR containers
      - source_labels: ['__meta_docker_container_name']
        regex: '/(hgr-.*)'
        target_label: 'container'
      
      # Extract agent ID
      - source_labels: ['__meta_docker_container_name']
        regex: '/hgr-agent-(.*)'
        target_label: 'agent_id'
      
      # Extract pod name
      - source_labels: ['__meta_docker_container_name']
        regex: '/hgr-pod-([a-d])-.*'
        target_label: 'pod'
      
      # Extract service type
      - source_labels: ['__meta_docker_container_name']
        regex: '/hgr-(agent|postgres|redis|api).*'
        target_label: 'service_type'
      
      # Add environment label
      - target_label: 'environment'
        replacement: 'production'
      
      # Add system label
      - target_label: 'system'
        replacement: 'holy_grail_refinery'
    
    pipeline_stages:
      # Parse JSON logs
      - json:
          expressions:
            timestamp: timestamp
            level: level
            message: message
            agent: agent
            mission_id: mission_id
            trace_id: trace_id
            error: error
      
      # Extract timestamp
      - timestamp:
          source: timestamp
          format: RFC3339Nano
      
      # Set log level
      - labels:
          level:
      
      # Drop debug logs older than 7 days (optional)
      - match:
          selector: '{level="debug"}'
          stages:
            - drop:
                older_than: 168h
  
  # System logs
  - job_name: system
    static_configs:
      - targets:
          - localhost
        labels:
          job: system
          __path__: /var/log/*.log
    
    pipeline_stages:
      - regex:
          expression: '^(?P<timestamp>\S+\s+\S+)\s+(?P<hostname>\S+)\s+(?P<service>\S+)\[(?P<pid>\d+)\]:\s+(?P<message>.*)$'
      
      - timestamp:
          source: timestamp
          format: 'Jan _2 15:04:05'
      
      - labels:
          hostname:
          service:
  
  # Application-specific log files
  - job_name: hgr_agents
    static_configs:
      - targets:
          - localhost
        labels:
          job: hgr_agents
          __path__: /var/log/hgr/agents/*.log
    
    pipeline_stages:
      - json:
          expressions:
            timestamp: timestamp
            level: level
            agent: agent
            message: message
      
      - timestamp:
          source: timestamp
          format: RFC3339Nano
      
      - labels:
          agent:
          level:
```

### 2.2 Docker Container Logging Configuration

**Add to all agent containers in `docker-compose.yml`:**

```yaml
services:
  agent-python:
    # ... other config
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
        labels: "agent,pod,environment"
        tag: "{{.Name}}/{{.ID}}"
```

---

## 3. STRUCTURED LOGGING STANDARDS

### 3.1 Python Logging Configuration

**File:** `agents/common/logging_config.py`

```python
"""
Structured logging configuration for all agents
"""

import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict
import traceback

class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON
        """
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add agent information from record
        if hasattr(record, 'agent_id'):
            log_data['agent_id'] = record.agent_id
        
        if hasattr(record, 'pod'):
            log_data['pod'] = record.pod
        
        if hasattr(record, 'mission_id'):
            log_data['mission_id'] = record.mission_id
        
        if hasattr(record, 'trace_id'):
            log_data['trace_id'] = record.trace_id
        
        # Add exception information
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields
        if hasattr(record, 'extra'):
            log_data.update(record.extra)
        
        return json.dumps(log_data)


def setup_logging(
    agent_id: str,
    pod: str = None,
    log_level: str = "INFO"
) -> logging.Logger:
    """
    Setup structured logging for an agent
    
    Args:
        agent_id: Unique agent identifier (e.g., "AGENT-PY-001")
        pod: Pod identifier (e.g., "A", "B", "C", "D")
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(agent_id)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    logger.handlers.clear()
    
    # Console handler with JSON format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JSONFormatter())
    logger.addHandler(console_handler)
    
    # Add agent context to all logs
    old_factory = logging.getLogRecordFactory()
    
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.agent_id = agent_id
        if pod:
            record.pod = pod
        return record
    
    logging.setLogRecordFactory(record_factory)
    
    return logger


# Example usage in agent
if __name__ == "__main__":
    logger = setup_logging("AGENT-PY-001", pod="A", log_level="INFO")
    
    # Standard logging
    logger.info("Agent started successfully")
    
    # With mission context
    logger.info(
        "Processing code file",
        extra={
            "mission_id": "MSN-001",
            "filename": "example.py",
            "lines_of_code": 150
        }
    )
    
    # With trace ID for distributed tracing
    logger.info(
        "Sending message to Semantic Bus",
        extra={
            "trace_id": "abc123",
            "protocol": "Alpha",
            "target_agent": "ARCH-001"
        }
    )
    
    # Error logging with exception
    try:
        raise ValueError("Example error")
    except Exception as e:
        logger.error("Failed to process request", exc_info=True)
```

### 3.2 Log Field Standards

**Required Fields (all logs):**
- `timestamp`: ISO8601 format with timezone
- `level`: DEBUG, INFO, WARNING, ERROR, CRITICAL
- `logger`: Logger name (usually agent_id)
- `message`: Human-readable message

**Contextual Fields (when applicable):**
- `agent_id`: Agent identifier
- `pod`: Pod identifier (A, B, C, D)
- `mission_id`: Mission identifier
- `trace_id`: Distributed tracing ID
- `user_id`: User identifier (for user-initiated requests)
- `duration_ms`: Operation duration in milliseconds
- `status_code`: HTTP/gRPC status code
- `error`: Error details

---

## 4. LOG LABELS & INDEXING STRATEGY

### 4.1 Label Design

**High-Cardinality Labels (indexed):**
```yaml
labels:
  - container: "hgr-agent-python-001"
  - agent_id: "AGENT-PY-001"
  - pod: "A"
  - service_type: "agent"
  - environment: "production"
  - level: "error"
```

**Low-Cardinality Metadata (not indexed):**
- `mission_id`: Stored in log line, not indexed
- `trace_id`: Stored in log line, not indexed
- `user_id`: Stored in log line, not indexed

### 4.2 Label Cardinality Analysis

**File:** `scripts/analyze_log_labels.sh`

```bash
#!/bin/bash
# Analyze label cardinality in Loki

echo "Analyzing Loki label cardinality..."

# Get label stats
curl -s "http://localhost:3100/loki/api/v1/label" | jq '.data[]' | \
while read -r label; do
    label=$(echo "$label" | tr -d '"')
    count=$(curl -s "http://localhost:3100/loki/api/v1/label/$label/values" | \
        jq '.data | length')
    
    echo "$label: $count unique values"
done | sort -t: -k2 -nr
```

---

## 5. LOGQL QUERY PATTERNS

### 5.1 Basic Query Examples

```logql
# All logs from Python agent
{agent_id="AGENT-PY-001"}

# All error logs across all agents
{level="error"}

# Logs from Pod A
{pod="A"}

# Logs from specific mission
{mission_id="MSN-123"} |= "mission_id"

# Logs with specific error message
{service_type="agent"} |= "connection refused"

# Rate of error logs per second
rate({level="error"}[5m])

# Count of log lines per agent
sum by (agent_id) (count_over_time({service_type="agent"}[1h]))
```

### 5.2 Advanced Query Patterns

```logql
# Filter JSON logs and extract fields
{agent_id="AGENT-PY-001"} 
  | json 
  | duration_ms > 1000

# Calculate p95 latency
quantile_over_time(0.95, 
  {service_type="api"} 
    | json 
    | unwrap duration_ms [5m]
)

# Pattern matching for errors
{level="error"} 
  | pattern `<_> error: <error_type> - <message>`
  | line_format "{{.error_type}}: {{.message}}"

# Detect mission failures
sum by (mission_id) (
  rate({service_type="agent"} 
    | json 
    | status="failed" [5m])
) > 0

# Find slow queries
{service_type="api"} 
  | json 
  | duration_ms > 5000 
  | line_format "Slow query: {{.message}} ({{.duration_ms}}ms)"
```

### 5.3 Saved Queries

**File:** `logging/saved_queries.yml`

```yaml
queries:
  - name: "Agent Health Check"
    description: "Find agents with high error rates"
    query: |
      sum by (agent_id) (
        rate({level="error"}[5m])
      ) > 0.01
  
  - name: "Mission Failures"
    description: "All failed missions in last hour"
    query: |
      {service_type="agent"} 
        | json 
        | status="failed" 
        | __timestamp__ > now() - 1h
  
  - name: "API Latency"
    description: "P95 API latency by endpoint"
    query: |
      quantile_over_time(0.95,
        {service_type="api"}
          | json
          | unwrap duration_ms
        by (endpoint) [5m]
      )
  
  - name: "Semantic Bus Messages"
    description: "Message throughput on Semantic Bus"
    query: |
      sum(
        rate({service_type="redis"}
          |= "semantic_bus" [1m])
      )
  
  - name: "Security Events"
    description: "Authentication failures and security alerts"
    query: |
      {level=~"warning|error"}
        |~ "auth|security|unauthorized"
```

---

## 6. LOG ANALYSIS WORKFLOWS

### 6.1 Debugging Mission Failures

**Workflow:**

1. **Find failed missions:**
```logql
{service_type="agent"} | json | status="failed"
```

2. **Get mission ID:**
```logql
{mission_id="MSN-123"}
```

3. **Trace full execution:**
```logql
{trace_id="abc123"} | json
```

4. **Find error context:**
```logql
{mission_id="MSN-123"} | json | level="error"
```

### 6.2 Performance Analysis

**Script:** `scripts/analyze_performance.sh`

```bash
#!/bin/bash
# Analyze agent performance from logs

LOKI_URL="http://localhost:3100"

echo "=== Agent Performance Analysis ==="

# Average response times
echo -e "\n1. Average Response Times:"
curl -s -G "$LOKI_URL/loki/api/v1/query" \
    --data-urlencode 'query=avg by (agent_id) (
        avg_over_time({service_type="agent"} 
            | json 
            | unwrap duration_ms [1h])
    )' | jq -r '.data.result[] | 
        "\(.metric.agent_id): \(.value[1]) ms"'

# Error rates
echo -e "\n2. Error Rates:"
curl -s -G "$LOKI_URL/loki/api/v1/query" \
    --data-urlencode 'query=sum by (agent_id) (
        rate({level="error"}[5m])
    )' | jq -r '.data.result[] | 
        "\(.metric.agent_id): \(.value[1]) errors/sec"'

# Slowest operations
echo -e "\n3. Slowest Operations (last hour):"
curl -s -G "$LOKI_URL/loki/api/v1/query_range" \
    --data-urlencode 'query={service_type="agent"} 
        | json 
        | duration_ms > 5000' \
    --data-urlencode "start=$(date -d '1 hour ago' +%s)" \
    --data-urlencode "end=$(date +%s)" | \
    jq -r '.data.result[].values[] | 
        "\(.[0]): \(.[1])"' | head -10

echo -e "\nAnalysis complete."
```

### 6.3 Security Audit

**Query for suspicious activity:**

```logql
# Failed authentication attempts
{service_type="api"} 
  | json 
  | status_code=~"401|403"
  
# Unusual access patterns
{service_type="api"} 
  | json 
  | rate([5m]) > 100  # More than 100 req/sec

# Error spikes
sum(rate({level="error"}[1m])) > 10
```

---

## 7. LOG RETENTION & ARCHIVAL

### 7.1 Tiered Storage Configuration

**File:** `logging/loki/retention_config.yml`

```yaml
storage_tiers:
  # Hot tier: 7 days, fast SSD storage
  hot:
    retention_period: 168h
    storage_path: /loki/hot
    storage_type: ssd
  
  # Warm tier: 30 days, HDD storage
  warm:
    retention_period: 720h
    storage_path: /loki/warm
    storage_type: hdd
  
  # Cold tier: 90 days, compressed archive
  cold:
    retention_period: 2160h
    storage_path: /loki/cold
    storage_type: archive
    compression: gzip

# Automatic tier migration rules
migration_rules:
  - from: hot
    to: warm
    after: 7d
  
  - from: warm
    to: cold
    after: 30d
  
  - from: cold
    to: delete
    after: 90d
```

### 7.2 Log Archival Script

**File:** `scripts/archive_logs.sh`

```bash
#!/bin/bash
# Archive old logs to cold storage

set -e

LOG_DIR="/loki"
ARCHIVE_DIR="/backups/loki-archives"
DAYS_TO_KEEP=7

echo "Starting log archival process..."

# Find chunks older than 7 days
find "$LOG_DIR/chunks" -type f -mtime +$DAYS_TO_KEEP -print0 | \
while IFS= read -r -d '' file; do
    # Get relative path
    rel_path="${file#$LOG_DIR/}"
    
    # Create archive directory
    archive_path="$ARCHIVE_DIR/$(dirname "$rel_path")"
    mkdir -p "$archive_path"
    
    # Compress and move
    echo "Archiving: $file"
    gzip -c "$file" > "$archive_path/$(basename "$file").gz"
    rm "$file"
done

echo "✓ Log archival complete"
```

### 7.3 Log Deletion Policy

**File:** `logging/loki/deletion_policy.yml`

```yaml
deletion_rules:
  # Delete debug logs after 7 days
  - selector: '{level="debug"}'
    retention: 168h
  
  # Delete access logs after 14 days
  - selector: '{service_type="api"} |= "access"'
    retention: 336h
  
  # Keep error logs for 90 days
  - selector: '{level="error"}'
    retention: 2160h
  
  # Keep critical logs indefinitely
  - selector: '{level="critical"}'
    retention: 0  # Never delete
```

---

## 8. PERFORMANCE OPTIMIZATION

### 8.1 Query Performance Tuning

**Best Practices:**

```logql
# ✓ GOOD: Use label filters first
{agent_id="AGENT-PY-001"} |= "error"

# ✗ BAD: Full-text search without labels
{} |= "error"

# ✓ GOOD: Use parsers efficiently
{service_type="agent"} | json | level="error"

# ✗ BAD: Parse then filter
{} | json | agent_id="AGENT-PY-001"

# ✓ GOOD: Use appropriate time ranges
{agent_id="AGENT-PY-001"}[5m]

# ✗ BAD: Unnecessarily large time ranges
{agent_id="AGENT-PY-001"}[30d]
```

### 8.2 Ingestion Rate Limiting

**File:** `logging/loki/rate_limits.yml`

```yaml
limits:
  # Per-agent limits
  per_stream_rate_limit: 3MB
  per_stream_rate_limit_burst: 5MB
  
  # Global limits
  ingestion_rate_mb: 10
  ingestion_burst_size_mb: 20
  
  # Query limits
  max_query_length: 721h  # 30 days
  max_entries_limit_per_query: 10000
  max_streams_per_user: 10000
```

### 8.3 Cache Configuration

**File:** `logging/loki/cache_config.yml`

```yaml
chunk_store_config:
  chunk_cache_config:
    enable_fifocache: true
    fifocache:
      max_size_bytes: 1GB
      ttl: 1h
  
  write_dedupe_cache_config:
    enable_fifocache: true
    fifocache:
      max_size_bytes: 100MB
      ttl: 10m

query_range:
  results_cache:
    cache:
      enable_fifocache: true
      fifocache:
        max_size_bytes: 500MB
        ttl: 24h
```

---

## 9. TROUBLESHOOTING COMMON ISSUES

### 9.1 High Memory Usage

**Symptoms:**
- Loki container OOMKilled
- Slow query performance

**Solutions:**

```bash
# Check Loki memory usage
docker stats hgr-loki

# Reduce query parallelism
# In loki/config.yml:
limits_config:
  max_query_parallelism: 16  # Reduce from 32

# Enable streaming
querier:
  max_concurrent: 10
```

### 9.2 Missing Logs

**Debugging steps:**

```bash
# 1. Check Promtail is running
docker ps | grep promtail

# 2. Check Promtail logs
docker logs hgr-promtail

# 3. Verify Promtail can reach Loki
docker exec hgr-promtail wget -O- http://loki:3100/ready

# 4. Check positions file
docker exec hgr-promtail cat /tmp/positions.yaml

# 5. Verify log format
docker logs hgr-agent-python-001 --tail 10
```

### 9.3 Slow Queries

**Optimization steps:**

```bash
# 1. Analyze query plan
curl -G "http://localhost:3100/loki/api/v1/query" \
    --data-urlencode 'query={agent_id="AGENT-PY-001"}' \
    --data-urlencode 'stats=true' | jq '.data.stats'

# 2. Add more specific labels
# ✗ BAD
{service_type="agent"}

# ✓ GOOD
{service_type="agent", pod="A", agent_id="AGENT-PY-001"}

# 3. Use smaller time ranges
# ✗ BAD
{agent_id="AGENT-PY-001"}[30d]

# ✓ GOOD
{agent_id="AGENT-PY-001"}[1h]
```

---

## 10. INTEGRATION WITH MONITORING

### 10.1 Loki Alerts in Prometheus

**File:** `monitoring/prometheus/rules/loki_alerts.yml`

```yaml
groups:
  - name: loki_health
    interval: 30s
    rules:
      - alert: LokiDown
        expr: up{job="loki"} == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Loki is down"
          description: "Loki has been down for 5 minutes"
      
      - alert: LokiHighIngestionRate
        expr: rate(loki_ingester_bytes_received_total[5m]) > 10485760
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High log ingestion rate"
          description: "Loki ingestion rate is {{ $value | humanize }}B/s"
      
      - alert: LokiRequestErrors
        expr: rate(loki_request_duration_seconds_count{status_code=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Loki experiencing errors"
          description: "{{ $value }}% of Loki requests are failing"

  - name: log_patterns
    interval: 1m
    rules:
      - alert: HighErrorRate
        expr: |
          sum(rate({level="error"}[5m])) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected in logs"
          description: "Error rate is {{ $value }} errors/sec"
      
      - alert: CriticalErrorDetected
        expr: |
          count_over_time({level="critical"}[5m]) > 0
        labels:
          severity: critical
        annotations:
          summary: "Critical error detected"
          description: "A critical error was logged"
```

### 10.2 Grafana Explore Integration

**Create Explore link from metrics:**

```json
{
  "datasource": "Loki",
  "queries": [
    {
      "refId": "A",
      "expr": "{agent_id=\"${agent_id}\"}",
      "queryType": "range"
    }
  ],
  "range": {
    "from": "now-1h",
    "to": "now"
  }
}
```

### 10.3 Trace-to-Log Correlation

**Configuration in Grafana:**

```yaml
# In Tempo data source
tracesToLogs:
  datasourceUid: loki
  tags: ['mission_id', 'trace_id']
  mappedTags: [
    {key: 'service.name', value: 'agent_id'}
  ]
  mapTagNamesEnabled: true
  spanStartTimeShift: '1h'
  spanEndTimeShift: '1h'
  filterByTraceID: true
  filterBySpanID: true
```

---

## DOCUMENT METADATA

**Document ID:** 38  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Operations & Deployment  
**Owner:** Observability Lead  
**Dependencies:** Documents 25 (Monitoring), 37 (Dashboards)  
**Next Document:** 39 (Alerting & Notification System)

---

*End of Log Aggregation & Analysis Setup*
