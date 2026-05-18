# DOCUMENT 25: MONITORING & OBSERVABILITY IMPLEMENTATION

Document version: 2026.03.29
Last updated: 2026-03-29
Status: Archived Legacy
## Holy Grail Refinery - Development Specifications

**Document ID:** 25  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

The Holy Grail Refinery implements **comprehensive monitoring and observability** to maintain 99.9999% reliability across all 35 agents. The observability stack provides real-time visibility into system health, performance, and behavior through metrics, logs, traces, and alerts.

**Observability Pillars:**
- **Metrics:** Time-series performance data (Prometheus + Grafana)
- **Logs:** Structured logging with centralized aggregation (Loki)
- **Traces:** Distributed tracing across agents (Jaeger)
- **Alerts:** Proactive alerting and incident response (Alertmanager)

**Key Objectives:**
- 🎯 Sub-second anomaly detection
- 📊 Real-time performance dashboards
- 🔍 Full request tracing across 35 agents
- ⚠️ Intelligent alerting with minimal false positives
- 📈 Historical trend analysis for capacity planning

---

## TABLE OF CONTENTS

1. [Observability Architecture](#1-observability-architecture)
2. [Metrics Collection (Prometheus)](#2-metrics-collection-prometheus)
3. [Log Aggregation (Loki)](#3-log-aggregation-loki)
4. [Distributed Tracing (Jaeger)](#4-distributed-tracing-jaeger)
5. [Visualization (Grafana)](#5-visualization-grafana)
6. [Alerting (Alertmanager)](#6-alerting-alertmanager)
7. [Performance Monitoring](#7-performance-monitoring)
8. [Health Checks](#8-health-checks)
9. [Incident Response](#9-incident-response)
10. [Capacity Planning](#10-capacity-planning)

---

## 1. OBSERVABILITY ARCHITECTURE

### 1.1 Stack Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    35 AGENT CONTAINERS                       │
│  (Each agent exports metrics, logs, traces)                  │
└───────────────┬────────────┬────────────┬───────────────────┘
                │            │            │
         Metrics│     Logs   │    Traces  │
                ▼            ▼            ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────┐
│   PROMETHEUS     │ │     LOKI     │ │    JAEGER    │
│  (Metrics DB)    │ │  (Logs DB)   │ │  (Traces DB) │
└────────┬─────────┘ └──────┬───────┘ └──────┬───────┘
         │                  │                │
         └──────────────────┼────────────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │     GRAFANA     │
                   │  (Visualization) │
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │  ALERTMANAGER   │
                   │   (Alerting)    │
                   └─────────────────┘
                            │
                            ▼
              ┌──────────────────────────┐
              │  Slack, Email, PagerDuty │
              └──────────────────────────┘
```

### 1.2 Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Metrics** | Prometheus | Time-series metrics storage |
| **Logs** | Loki + Promtail | Log aggregation and querying |
| **Traces** | Jaeger | Distributed request tracing |
| **Visualization** | Grafana | Dashboards and analysis |
| **Alerting** | Alertmanager | Alert routing and deduplication |
| **APM** | OpenTelemetry | Unified instrumentation |

---

## 2. METRICS COLLECTION (PROMETHEUS)

### 2.1 Prometheus Setup

**File:** `docker-compose.monitoring.yml`

```yaml
version: '3.8'

services:
  prometheus:
    image: prom/prometheus:latest
    container_name: hgr-prometheus
    restart: unless-stopped
    
    ports:
      - "9090:9090"
    
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
      - ./monitoring/rules:/etc/prometheus/rules
      - prometheus-data:/prometheus
    
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
    
    networks:
      - hgr-network

volumes:
  prometheus-data:

networks:
  hgr-network:
    external: true
```

### 2.2 Prometheus Configuration

**File:** `monitoring/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: 'hgr-aw1'
    environment: 'production'

# Alerting configuration
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093

# Load alerting rules
rule_files:
  - 'rules/*.yml'

# Scrape configurations
scrape_configs:
  # API Gateway
  - job_name: 'api-gateway'
    static_configs:
      - targets:
          - 'api:8000'
    metrics_path: '/metrics'
  
  # Pod A Agents (Python, JavaScript, Ruby, PHP)
  - job_name: 'pod-a-agents'
    static_configs:
      - targets:
          - 'agent-python:9100'
          - 'agent-javascript:9100'
          - 'agent-ruby:9100'
          - 'agent-php:9100'
    relabel_configs:
      - source_labels: [__address__]
        target_label: agent_id
  
  # Pod B Agents (C, C++, Rust, Zig)
  - job_name: 'pod-b-agents'
    static_configs:
      - targets:
          - 'agent-c:9100'
          - 'agent-cpp:9100'
          - 'agent-rust:9100'
          - 'agent-zig:9100'
  
  # Infrastructure
  - job_name: 'postgres'
    static_configs:
      - targets:
          - 'postgres-exporter:9187'
  
  - job_name: 'redis'
    static_configs:
      - targets:
          - 'redis-exporter:9121'
  
  # Node exporter (system metrics)
  - job_name: 'node'
    static_configs:
      - targets:
          - 'node-exporter:9100'
```

### 2.3 Custom Metrics Instrumentation

**File:** `agents/base/metrics.py`

```python
"""
Custom Prometheus metrics for Holy Grail Refinery
"""

from prometheus_client import Counter, Histogram, Gauge, Summary
from prometheus_client import start_http_server
from functools import wraps
import time

# ============================================================================
# AGENT METRICS
# ============================================================================

# Task processing
tasks_processed = Counter(
    'hgr_tasks_processed_total',
    'Total tasks processed by agent',
    ['agent_id', 'task_type', 'status']
)

task_duration = Histogram(
    'hgr_task_duration_seconds',
    'Task processing duration',
    ['agent_id', 'task_type'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

# LogicNode extraction
logicnodes_extracted = Counter(
    'hgr_logicnodes_extracted_total',
    'Total LogicNodes extracted',
    ['agent_id', 'language', 'domain']
)

logicnode_extraction_duration = Histogram(
    'hgr_logicnode_extraction_duration_seconds',
    'LogicNode extraction duration',
    ['agent_id', 'language'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
)

# Agent health
agent_health = Gauge(
    'hgr_agent_health',
    'Agent health status (1=healthy, 0=unhealthy)',
    ['agent_id']
)

agent_memory_usage = Gauge(
    'hgr_agent_memory_bytes',
    'Agent memory usage in bytes',
    ['agent_id']
)

# ============================================================================
# SEMANTIC BUS METRICS
# ============================================================================

messages_sent = Counter(
    'hgr_messages_sent_total',
    'Total messages sent via Semantic Bus',
    ['protocol', 'sender', 'recipient']
)

messages_received = Counter(
    'hgr_messages_received_total',
    'Total messages received via Semantic Bus',
    ['protocol', 'recipient']
)

message_latency = Histogram(
    'hgr_message_latency_seconds',
    'Message delivery latency',
    ['protocol'],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0]
)

dlq_size = Gauge(
    'hgr_dead_letter_queue_size',
    'Number of messages in dead letter queue'
)

# ============================================================================
# API METRICS
# ============================================================================

http_requests = Counter(
    'hgr_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration = Histogram(
    'hgr_http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

active_requests = Gauge(
    'hgr_http_active_requests',
    'Number of active HTTP requests'
)

# ============================================================================
# DATABASE METRICS
# ============================================================================

db_queries = Counter(
    'hgr_db_queries_total',
    'Total database queries',
    ['database', 'operation']
)

db_query_duration = Histogram(
    'hgr_db_query_duration_seconds',
    'Database query duration',
    ['database', 'operation'],
    buckets=[0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
)

db_connections = Gauge(
    'hgr_db_connections_active',
    'Active database connections',
    ['database']
)

# ============================================================================
# DECORATORS FOR AUTOMATIC INSTRUMENTATION
# ============================================================================

def track_task_duration(task_type):
    """Decorator to track task duration"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            start = time.time()
            
            try:
                result = func(self, *args, **kwargs)
                
                # Record success
                tasks_processed.labels(
                    agent_id=self.agent_id,
                    task_type=task_type,
                    status='success'
                ).inc()
                
                return result
            
            except Exception as e:
                # Record failure
                tasks_processed.labels(
                    agent_id=self.agent_id,
                    task_type=task_type,
                    status='failure'
                ).inc()
                raise
            
            finally:
                # Record duration
                duration = time.time() - start
                task_duration.labels(
                    agent_id=self.agent_id,
                    task_type=task_type
                ).observe(duration)
        
        return wrapper
    return decorator


def track_logicnode_extraction(language):
    """Decorator to track LogicNode extraction"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            start = time.time()
            
            result = func(self, *args, **kwargs)
            
            # Record extraction
            if result:
                logicnodes_extracted.labels(
                    agent_id=self.agent_id,
                    language=language,
                    domain=result.get('domain', 'unknown')
                ).inc()
            
            # Record duration
            duration = time.time() - start
            logicnode_extraction_duration.labels(
                agent_id=self.agent_id,
                language=language
            ).observe(duration)
            
            return result
        
        return wrapper
    return decorator


# ============================================================================
# METRICS SERVER
# ============================================================================

def start_metrics_server(port=9100):
    """Start Prometheus metrics HTTP server"""
    start_http_server(port)
    print(f"Metrics server started on port {port}")


# Usage example in agent
class PythonAgent:
    def __init__(self, agent_id):
        self.agent_id = agent_id
        
        # Start metrics server
        start_metrics_server(9100)
        
        # Set initial health
        agent_health.labels(agent_id=self.agent_id).set(1)
    
    @track_task_duration('extract_logicnodes')
    def process_task(self, task):
        """Process task with automatic metrics tracking"""
        # Task processing logic...
        pass
    
    @track_logicnode_extraction('python')
    def extract_logicnode(self, source_code):
        """Extract LogicNode with automatic metrics tracking"""
        # Extraction logic...
        return logicnode
```

### 2.4 Alert Rules

**File:** `monitoring/rules/alerts.yml`

```yaml
groups:
  - name: agent_alerts
    interval: 30s
    rules:
      # Agent health
      - alert: AgentDown
        expr: hgr_agent_health == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Agent {{ $labels.agent_id }} is down"
          description: "Agent has been unhealthy for more than 5 minutes"
      
      # Task processing
      - alert: HighTaskFailureRate
        expr: |
          rate(hgr_tasks_processed_total{status="failure"}[5m]) /
          rate(hgr_tasks_processed_total[5m]) > 0.05
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High task failure rate for {{ $labels.agent_id }}"
          description: "Task failure rate is {{ $value | humanizePercentage }}"
      
      # Performance
      - alert: SlowLogicNodeExtraction
        expr: |
          histogram_quantile(0.95,
            rate(hgr_logicnode_extraction_duration_seconds_bucket[5m])
          ) > 2.0
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Slow LogicNode extraction for {{ $labels.language }}"
          description: "P95 extraction time: {{ $value }}s"
      
      # Memory
      - alert: HighMemoryUsage
        expr: hgr_agent_memory_bytes > 1e9  # 1GB
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage for {{ $labels.agent_id }}"
          description: "Memory usage: {{ $value | humanize }}B"
  
  - name: infrastructure_alerts
    interval: 30s
    rules:
      # Database
      - alert: DatabaseConnectionPoolExhausted
        expr: hgr_db_connections_active >= 95
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Database connection pool nearly exhausted"
          description: "Active connections: {{ $value }}"
      
      # Redis
      - alert: RedisMemoryHigh
        expr: redis_memory_used_bytes / redis_memory_max_bytes > 0.9
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Redis memory usage high"
          description: "Memory usage: {{ $value | humanizePercentage }}"
      
      # Dead Letter Queue
      - alert: DeadLetterQueueGrowing
        expr: hgr_dead_letter_queue_size > 100
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Dead letter queue is growing"
          description: "DLQ size: {{ $value }}"
  
  - name: api_alerts
    interval: 30s
    rules:
      # Error rate
      - alert: HighAPIErrorRate
        expr: |
          rate(hgr_http_requests_total{status=~"5.."}[5m]) /
          rate(hgr_http_requests_total[5m]) > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High API error rate"
          description: "Error rate: {{ $value | humanizePercentage }}"
      
      # Latency
      - alert: HighAPILatency
        expr: |
          histogram_quantile(0.95,
            rate(hgr_http_request_duration_seconds_bucket[5m])
          ) > 1.0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High API latency"
          description: "P95 latency: {{ $value }}s"
```

---

## 3. LOG AGGREGATION (LOKI)

### 3.1 Loki Setup

**File:** `docker-compose.monitoring.yml` (add to previous)

```yaml
  loki:
    image: grafana/loki:latest
    container_name: hgr-loki
    restart: unless-stopped
    
    ports:
      - "3100:3100"
    
    volumes:
      - ./monitoring/loki.yml:/etc/loki/local-config.yaml
      - loki-data:/loki
    
    command: -config.file=/etc/loki/local-config.yaml
    
    networks:
      - hgr-network
  
  promtail:
    image: grafana/promtail:latest
    container_name: hgr-promtail
    restart: unless-stopped
    
    volumes:
      - ./monitoring/promtail.yml:/etc/promtail/config.yml
      - /var/log:/var/log
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
    
    command: -config.file=/etc/promtail/config.yml
    
    networks:
      - hgr-network

volumes:
  loki-data:
```

### 3.2 Structured Logging

**File:** `agents/base/logging_config.py`

```python
"""
Structured logging configuration for Holy Grail Refinery
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any

class StructuredLogger:
    """
    JSON structured logger for centralized log aggregation
    """
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.logger = logging.getLogger(agent_id)
        self.logger.setLevel(logging.INFO)
        
        # JSON formatter
        handler = logging.StreamHandler()
        handler.setFormatter(self._get_formatter())
        self.logger.addHandler(handler)
    
    def _get_formatter(self):
        """Custom JSON formatter"""
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": record.levelname,
                    "agent_id": record.name,
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno
                }
                
                # Add exception info if present
                if record.exc_info:
                    log_data["exception"] = self.formatException(record.exc_info)
                
                # Add custom fields
                if hasattr(record, 'extra_fields'):
                    log_data.update(record.extra_fields)
                
                return json.dumps(log_data)
        
        return JSONFormatter()
    
    def info(self, message: str, **kwargs):
        """Log info with extra fields"""
        extra = {'extra_fields': kwargs}
        self.logger.info(message, extra=extra)
    
    def warning(self, message: str, **kwargs):
        """Log warning with extra fields"""
        extra = {'extra_fields': kwargs}
        self.logger.warning(message, extra=extra)
    
    def error(self, message: str, **kwargs):
        """Log error with extra fields"""
        extra = {'extra_fields': kwargs}
        self.logger.error(message, extra=extra)
    
    def debug(self, message: str, **kwargs):
        """Log debug with extra fields"""
        extra = {'extra_fields': kwargs}
        self.logger.debug(message, extra=extra)


# Usage example
logger = StructuredLogger("AGENT-PY-001")

logger.info("Task started", 
    task_id="task-123",
    task_type="extract_logicnodes",
    priority=1
)

logger.error("LogicNode extraction failed",
    task_id="task-123",
    source_file="main.py",
    error_type="SyntaxError"
)
```

### 3.3 Log Queries (LogQL Examples)

```logql
# All logs from Python agent
{agent_id="AGENT-PY-001"}

# Error logs across all agents
{level="ERROR"}

# Task failures in last hour
{level="ERROR"} |= "Task failed" | json | __error__ = ""

# Slow LogicNode extractions
{agent_id=~"AGENT-.*"} 
  | json 
  | duration > 1s
  | line_format "{{.agent_id}}: {{.message}}"

# Aggregate error rate by agent
sum by (agent_id) (
  rate({level="ERROR"}[5m])
)
```

---

## 4. DISTRIBUTED TRACING (JAEGER)

### 4.1 Jaeger Setup

**File:** `docker-compose.monitoring.yml` (add to previous)

```yaml
  jaeger:
    image: jaegertracing/all-in-one:latest
    container_name: hgr-jaeger
    restart: unless-stopped
    
    ports:
      - "5775:5775/udp"  # Zipkin compact
      - "6831:6831/udp"  # Jaeger compact
      - "6832:6832/udp"  # Jaeger binary
      - "5778:5778"      # Configs
      - "16686:16686"    # UI
      - "14268:14268"    # Jaeger HTTP
    
    environment:
      - COLLECTOR_ZIPKIN_HOST_PORT=:9411
    
    networks:
      - hgr-network
```

### 4.2 OpenTelemetry Instrumentation

**File:** `agents/base/tracing.py`

```python
"""
OpenTelemetry tracing for Holy Grail Refinery
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import Resource
from functools import wraps
import time

# Initialize tracer
resource = Resource(attributes={
    "service.name": "holy-grail-refinery"
})

trace.set_tracer_provider(TracerProvider(resource=resource))

jaeger_exporter = JaegerExporter(
    agent_host_name="jaeger",
    agent_port=6831,
)

trace.get_tracer_provider().add_span_processor(
    BatchSpanProcessor(jaeger_exporter)
)

tracer = trace.get_tracer(__name__)


def trace_function(operation_name):
    """Decorator to trace function execution"""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            with tracer.start_as_current_span(operation_name) as span:
                # Add attributes
                span.set_attribute("agent.id", self.agent_id)
                span.set_attribute("function", func.__name__)
                
                # Execute function
                start = time.time()
                try:
                    result = func(self, *args, **kwargs)
                    span.set_attribute("status", "success")
                    return result
                except Exception as e:
                    span.set_attribute("status", "error")
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    raise
                finally:
                    span.set_attribute("duration_ms", (time.time() - start) * 1000)
        
        return wrapper
    return decorator


# Usage in agent
class PythonAgent:
    def __init__(self, agent_id):
        self.agent_id = agent_id
    
    @trace_function("extract_logicnode")
    def extract_logicnode(self, source_code):
        """Extract LogicNode with automatic tracing"""
        
        # Create child span for parsing
        with tracer.start_as_current_span("parse_ast") as parse_span:
            ast_tree = self.parse(source_code)
            parse_span.set_attribute("ast.nodes", len(ast_tree.body))
        
        # Create child span for extraction
        with tracer.start_as_current_span("extract_semantics") as extract_span:
            logicnode = self.analyze(ast_tree)
            extract_span.set_attribute("logicnode.domain", logicnode['domain'])
            extract_span.set_attribute("logicnode.concept", logicnode['concept'])
        
        return logicnode
```

---

## 5. VISUALIZATION (GRAFANA)

### 5.1 Grafana Setup

**File:** `docker-compose.monitoring.yml` (add to previous)

```yaml
  grafana:
    image: grafana/grafana:latest
    container_name: hgr-grafana
    restart: unless-stopped
    
    ports:
      - "3000:3000"
    
    volumes:
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - grafana-data:/var/lib/grafana
    
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD}
      - GF_USERS_ALLOW_SIGN_UP=false
    
    networks:
      - hgr-network

volumes:
  grafana-data:
```

### 5.2 Dashboard Configuration

**File:** `monitoring/grafana/dashboards/system_overview.json`

```json
{
  "dashboard": {
    "title": "Holy Grail Refinery - System Overview",
    "panels": [
      {
        "id": 1,
        "title": "Agent Health Status",
        "type": "stat",
        "targets": [{
          "expr": "sum(hgr_agent_health)",
          "legendFormat": "Healthy Agents"
        }],
        "fieldConfig": {
          "defaults": {
            "thresholds": {
              "steps": [
                {"value": 0, "color": "red"},
                {"value": 30, "color": "yellow"},
                {"value": 35, "color": "green"}
              ]
            }
          }
        }
      },
      {
        "id": 2,
        "title": "Task Processing Rate",
        "type": "graph",
        "targets": [{
          "expr": "rate(hgr_tasks_processed_total[5m])",
          "legendFormat": "{{agent_id}} - {{task_type}}"
        }]
      },
      {
        "id": 3,
        "title": "LogicNodes Extracted",
        "type": "graph",
        "targets": [{
          "expr": "sum by (language) (rate(hgr_logicnodes_extracted_total[5m]))",
          "legendFormat": "{{language}}"
        }]
      },
      {
        "id": 4,
        "title": "API Response Time (P95)",
        "type": "graph",
        "targets": [{
          "expr": "histogram_quantile(0.95, rate(hgr_http_request_duration_seconds_bucket[5m]))",
          "legendFormat": "{{endpoint}}"
        }]
      },
      {
        "id": 5,
        "title": "Error Rate",
        "type": "graph",
        "targets": [{
          "expr": "sum(rate(hgr_tasks_processed_total{status=\"failure\"}[5m])) / sum(rate(hgr_tasks_processed_total[5m]))",
          "legendFormat": "Error Rate"
        }]
      },
      {
        "id": 6,
        "title": "Memory Usage by Agent",
        "type": "graph",
        "targets": [{
          "expr": "hgr_agent_memory_bytes",
          "legendFormat": "{{agent_id}}"
        }]
      }
    ]
  }
}
```

---

## 6. ALERTING (ALERTMANAGER)

### 6.1 Alertmanager Configuration

**File:** `monitoring/alertmanager.yml`

```yaml
global:
  resolve_timeout: 5m
  slack_api_url: ${SLACK_WEBHOOK_URL}

route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'
  
  routes:
    # Critical alerts to PagerDuty
    - match:
        severity: critical
      receiver: 'pagerduty'
      continue: true
    
    # All alerts to Slack
    - match_re:
        severity: warning|critical
      receiver: 'slack'

receivers:
  - name: 'default'
    email_configs:
      - to: 'ops@example.com'
        from: 'alertmanager@hgr.local'
        smarthost: 'smtp.gmail.com:587'
        auth_username: '${SMTP_USER}'
        auth_password: '${SMTP_PASS}'
  
  - name: 'slack'
    slack_configs:
      - channel: '#hgr-alerts'
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
        color: '{{ if eq .Status "firing" }}danger{{ else }}good{{ end }}'
  
  - name: 'pagerduty'
    pagerduty_configs:
      - service_key: '${PAGERDUTY_SERVICE_KEY}'
        description: '{{ .GroupLabels.alertname }}'

inhibit_rules:
  # Inhibit warning if critical is firing
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'agent_id']
```

---

## 7. PERFORMANCE MONITORING

### 7.1 Performance Benchmarks

**File:** `monitoring/benchmarks.py`

```python
"""
Continuous performance benchmarking
"""

import time
import statistics
from agents.pod_a.python_agent import PythonAgent
from agents.base.metrics import logicnode_extraction_duration

class PerformanceBenchmark:
    """Run performance benchmarks and track trends"""
    
    def __init__(self):
        self.agent = PythonAgent("BENCH-001")
        self.results = []
    
    def benchmark_logicnode_extraction(self, samples=100):
        """Benchmark LogicNode extraction speed"""
        
        test_code = """
def example(x, y):
    if x > 0:
        return x + y
    else:
        return x - y
"""
        
        times = []
        for _ in range(samples):
            start = time.time()
            self.agent.extract_logicnode(test_code)
            duration = time.time() - start
            times.append(duration)
        
        return {
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "p95": self._percentile(times, 95),
            "p99": self._percentile(times, 99),
            "min": min(times),
            "max": max(times)
        }
    
    def _percentile(self, data, percentile):
        """Calculate percentile"""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[index]
    
    def run_continuous_benchmark(self, interval=3600):
        """Run benchmark every hour"""
        import schedule
        
        def job():
            results = self.benchmark_logicnode_extraction()
            print(f"Benchmark results: {results}")
            
            # Record to Prometheus
            logicnode_extraction_duration.labels(
                agent_id="BENCH-001",
                language="python"
            ).observe(results["median"])
        
        schedule.every(interval).seconds.do(job)
        
        while True:
            schedule.run_pending()
            time.sleep(60)
```

---

## 8. HEALTH CHECKS

### 8.1 Comprehensive Health Check

**File:** `api/health.py`

```python
"""
Health check endpoint with dependency checks
"""

from fastapi import APIRouter, status
from pydantic import BaseModel
from typing import Dict
import asyncio

router = APIRouter()


class HealthStatus(BaseModel):
    status: str  # healthy, degraded, unhealthy
    version: str
    uptime: int
    checks: Dict[str, Dict[str, any]]


async def check_database():
    """Check database connectivity"""
    try:
        # Test query
        db.execute("SELECT 1")
        return {"status": "healthy", "response_time_ms": 5}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_redis():
    """Check Redis connectivity"""
    try:
        redis.ping()
        return {"status": "healthy", "response_time_ms": 2}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


async def check_agents():
    """Check agent health"""
    # Query Prometheus for agent health
    healthy_agents = prometheus_query("sum(hgr_agent_health)")
    total_agents = 35
    
    if healthy_agents == total_agents:
        return {"status": "healthy", "healthy_agents": healthy_agents}
    elif healthy_agents >= total_agents * 0.8:
        return {"status": "degraded", "healthy_agents": healthy_agents}
    else:
        return {"status": "unhealthy", "healthy_agents": healthy_agents}


@router.get("/health", response_model=HealthStatus)
async def health_check():
    """
    Comprehensive health check
    Returns 200 if healthy, 503 if unhealthy
    """
    
    # Run all checks concurrently
    db_check, redis_check, agents_check = await asyncio.gather(
        check_database(),
        check_redis(),
        check_agents()
    )
    
    checks = {
        "database": db_check,
        "redis": redis_check,
        "agents": agents_check
    }
    
    # Determine overall status
    all_healthy = all(c["status"] == "healthy" for c in checks.values())
    any_unhealthy = any(c["status"] == "unhealthy" for c in checks.values())
    
    if all_healthy:
        overall_status = "healthy"
        status_code = status.HTTP_200_OK
    elif any_unhealthy:
        overall_status = "unhealthy"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    else:
        overall_status = "degraded"
        status_code = status.HTTP_200_OK
    
    return HealthStatus(
        status=overall_status,
        version="1.0.0",
        uptime=get_uptime(),
        checks=checks
    ), status_code
```

---

## 9. INCIDENT RESPONSE

### 9.1 Incident Runbook

**File:** `docs/runbooks/agent_down.md`

```markdown
# Runbook: Agent Down

**Alert:** AgentDown
**Severity:** Critical
**Response Time:** < 5 minutes

## Symptoms
- Agent health metric = 0
- No heartbeat received for 5 minutes
- Tasks timing out

## Investigation Steps

1. Check agent container status:
   ```bash
   docker ps -a | grep <agent_id>
   ```

2. View recent logs:
   ```bash
   docker logs --tail 100 <agent_container>
   ```

3. Check resource usage:
   ```bash
   docker stats <agent_container>
   ```

4. Query Prometheus for recent metrics:
   ```promql
   hgr_agent_health{agent_id="<agent_id>"}[30m]
   ```

## Resolution Steps

### If container crashed:
```bash
# Restart container
docker restart <agent_container>

# Verify health
curl http://localhost:9100/metrics | grep hgr_agent_health
```

### If OOM (Out of Memory):
```bash
# Increase memory limit in docker-compose.yml
# Then restart
docker-compose up -d <agent_service>
```

### If persistent failures:
```bash
# Check for code issues in recent deployments
git log --oneline -10

# Consider rollback
./scripts/rollback.sh
```

## Post-Incident

1. Update incident log
2. Review root cause
3. Update monitoring/alerts if needed
4. Document lessons learned
```

---

## 10. CAPACITY PLANNING

### 10.1 Resource Forecasting

**File:** `monitoring/capacity_planning.py`

```python
"""
Capacity planning and resource forecasting
"""

import pandas as pd
from prometheus_api_client import PrometheusConnect
from datetime import datetime, timedelta

class CapacityPlanner:
    """Forecast resource needs based on trends"""
    
    def __init__(self, prometheus_url):
        self.prom = PrometheusConnect(url=prometheus_url)
    
    def forecast_memory_usage(self, days_ahead=30):
        """Forecast memory usage trends"""
        
        # Get 90 days of memory data
        end_time = datetime.now()
        start_time = end_time - timedelta(days=90)
        
        query = 'sum(hgr_agent_memory_bytes)'
        data = self.prom.custom_query_range(
            query=query,
            start_time=start_time,
            end_time=end_time,
            step='1h'
        )
        
        # Convert to DataFrame
        df = pd.DataFrame(data[0]['values'], columns=['timestamp', 'value'])
        df['value'] = pd.to_numeric(df['value'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        
        # Linear regression forecast
        from sklearn.linear_model import LinearRegression
        
        X = (df['timestamp'] - df['timestamp'].min()).dt.total_seconds().values.reshape(-1, 1)
        y = df['value'].values
        
        model = LinearRegression()
        model.fit(X, y)
        
        # Forecast
        future_time = (end_time + timedelta(days=days_ahead) - df['timestamp'].min()).total_seconds()
        forecast = model.predict([[future_time]])[0]
        
        return {
            "current_gb": y[-1] / 1e9,
            "forecast_gb": forecast / 1e9,
            "growth_rate_mb_per_day": (model.coef_[0] * 86400) / 1e6,
            "days_until_capacity": self._days_until_capacity(model, X[-1][0], max_gb=28)
        }
    
    def _days_until_capacity(self, model, current_time, max_gb):
        """Calculate days until max capacity"""
        max_bytes = max_gb * 1e9
        days = (max_bytes - model.predict([[current_time]])[0]) / (model.coef_[0] * 86400)
        return max(0, days)
```

---

## DOCUMENT METADATA

**Document ID:** 25  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Owner:** Chief Architect  
**Dependencies:** Documents 22-24  
**Next Document:** 26 (Security Implementation & Hardening)

---

*End of Monitoring & Observability Implementation*
