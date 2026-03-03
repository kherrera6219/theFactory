# DOCUMENT 37: SYSTEM MONITORING DASHBOARD CONFIGURATION
## Holy Grail Refinery - Operations & Deployment

**Document ID:** 37  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Operations & Deployment  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document provides **complete configuration specifications** for the Holy Grail Refinery monitoring dashboards using Grafana. It includes pre-configured dashboards for system health, agent performance, resource utilization, mission tracking, and business metrics. All dashboards are production-ready with proper alerting integration.

**Key Components:**
- 🎯 **System Overview Dashboard:** Complete system health at a glance
- 🤖 **Agent Performance Dashboard:** Individual agent metrics and status
- 📊 **Resource Utilization Dashboard:** CPU, memory, disk, network
- 🚀 **Mission Tracking Dashboard:** Active missions and throughput
- 💰 **Cost & Efficiency Dashboard:** API usage and cost tracking
- 🔔 **Alert Management Dashboard:** Active alerts and escalations

**Technology Stack:**
- **Grafana:** Dashboard visualization (v10.2+)
- **Prometheus:** Metrics collection
- **Loki:** Log aggregation
- **Tempo:** Distributed tracing
- **PostgreSQL:** TimescaleDB for historical metrics

---

## TABLE OF CONTENTS

1. [Grafana Installation & Configuration](#1-grafana-installation--configuration)
2. [Data Source Configuration](#2-data-source-configuration)
3. [System Overview Dashboard](#3-system-overview-dashboard)
4. [Agent Performance Dashboard](#4-agent-performance-dashboard)
5. [Resource Utilization Dashboard](#5-resource-utilization-dashboard)
6. [Mission Tracking Dashboard](#6-mission-tracking-dashboard)
7. [Cost & Efficiency Dashboard](#7-cost--efficiency-dashboard)
8. [Alert Management Dashboard](#8-alert-management-dashboard)
9. [Custom Panel Library](#9-custom-panel-library)
10. [Dashboard Automation & Provisioning](#10-dashboard-automation--provisioning)

---

## 1. GRAFANA INSTALLATION & CONFIGURATION

### 1.1 Docker Compose Configuration

**File:** `monitoring/docker-compose.grafana.yml`

```yaml
version: '3.8'

services:
  grafana:
    image: grafana/grafana:10.2.3
    container_name: hgr-grafana
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      # Admin credentials
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD}
      
      # Server configuration
      GF_SERVER_ROOT_URL: http://localhost:3000
      GF_SERVER_DOMAIN: localhost
      
      # Authentication
      GF_AUTH_ANONYMOUS_ENABLED: false
      GF_AUTH_BASIC_ENABLED: true
      
      # Feature toggles
      GF_FEATURE_TOGGLES_ENABLE: tempoSearch,tempoBackendSearch
      
      # Alerting
      GF_ALERTING_ENABLED: true
      GF_UNIFIED_ALERTING_ENABLED: true
      
      # Plugins
      GF_INSTALL_PLUGINS: >-
        grafana-clock-panel,
        grafana-simple-json-datasource,
        grafana-piechart-panel,
        grafana-worldmap-panel
    
    volumes:
      - ./grafana/data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
      - ./grafana/dashboards:/var/lib/grafana/dashboards
    
    networks:
      - monitoring
    
    depends_on:
      - prometheus
      - loki
      - tempo

networks:
  monitoring:
    external: true
```

### 1.2 Grafana Configuration File

**File:** `monitoring/grafana/grafana.ini`

```ini
[server]
protocol = http
http_port = 3000
domain = localhost
root_url = %(protocol)s://%(domain)s:%(http_port)s/

[security]
admin_user = admin
admin_password = ${GRAFANA_ADMIN_PASSWORD}
secret_key = ${GRAFANA_SECRET_KEY}

[users]
allow_sign_up = false
allow_org_create = false
auto_assign_org = true
auto_assign_org_role = Viewer

[auth]
disable_login_form = false
oauth_auto_login = false

[auth.anonymous]
enabled = false

[dashboards]
default_home_dashboard_path = /var/lib/grafana/dashboards/system_overview.json

[alerting]
enabled = true
execute_alerts = true

[unified_alerting]
enabled = true
min_interval = 10s

[smtp]
enabled = true
host = smtp.gmail.com:587
user = ${SMTP_USER}
password = ${SMTP_PASSWORD}
from_address = alerts@holygrain.ai
from_name = Holy Grail Refinery

[log]
mode = console file
level = info
```

---

## 2. DATA SOURCE CONFIGURATION

### 2.1 Prometheus Data Source

**File:** `monitoring/grafana/provisioning/datasources/prometheus.yml`

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      timeInterval: "15s"
      queryTimeout: "60s"
      httpMethod: POST
    version: 1
```

### 2.2 Loki Data Source

**File:** `monitoring/grafana/provisioning/datasources/loki.yml`

```yaml
apiVersion: 1

datasources:
  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100
    editable: false
    jsonData:
      maxLines: 1000
      derivedFields:
        - datasourceUid: tempo
          matcherRegex: "trace_id=(\\w+)"
          name: TraceID
          url: "$${__value.raw}"
    version: 1
```

### 2.3 Tempo Data Source

**File:** `monitoring/grafana/provisioning/datasources/tempo.yml`

```yaml
apiVersion: 1

datasources:
  - name: Tempo
    type: tempo
    access: proxy
    url: http://tempo:3200
    editable: false
    jsonData:
      tracesToLogs:
        datasourceUid: loki
        tags: ['job', 'instance', 'pod', 'namespace']
        mappedTags: [{ key: 'service.name', value: 'service' }]
        mapTagNamesEnabled: true
        spanStartTimeShift: '1h'
        spanEndTimeShift: '1h'
        filterByTraceID: true
        filterBySpanID: true
      serviceMap:
        datasourceUid: prometheus
      nodeGraph:
        enabled: true
    version: 1
```

### 2.4 PostgreSQL (TimescaleDB) Data Source

**File:** `monitoring/grafana/provisioning/datasources/timescaledb.yml`

```yaml
apiVersion: 1

datasources:
  - name: TimescaleDB
    type: postgres
    access: proxy
    url: postgres:5432
    database: hgr_metrics
    user: grafana_reader
    secureJsonData:
      password: ${TIMESCALEDB_PASSWORD}
    jsonData:
      sslmode: disable
      postgresVersion: 1400
      timescaledb: true
    editable: false
    version: 1
```

---

## 3. SYSTEM OVERVIEW DASHBOARD

### 3.1 Dashboard JSON Configuration

**File:** `monitoring/grafana/dashboards/system_overview.json`

```json
{
  "dashboard": {
    "title": "Holy Grail Refinery - System Overview",
    "uid": "hgr-system-overview",
    "tags": ["holy-grail", "overview"],
    "timezone": "browser",
    "schemaVersion": 36,
    "version": 1,
    "refresh": "10s",
    
    "panels": [
      {
        "id": 1,
        "title": "System Health Score",
        "type": "stat",
        "gridPos": {"x": 0, "y": 0, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "sum(up{job=~\"hgr-.*\"}) / count(up{job=~\"hgr-.*\"}) * 100",
            "refId": "A"
          }
        ],
        "options": {
          "graphMode": "area",
          "colorMode": "background",
          "textMode": "value_and_name",
          "reduceOptions": {
            "values": false,
            "calcs": ["lastNotNull"]
          }
        },
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "min": 0,
            "max": 100,
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"value": 0, "color": "red"},
                {"value": 80, "color": "yellow"},
                {"value": 95, "color": "green"}
              ]
            }
          }
        }
      },
      
      {
        "id": 2,
        "title": "Active Agents",
        "type": "stat",
        "gridPos": {"x": 6, "y": 0, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "count(up{job=~\"hgr-agent-.*\"} == 1)",
            "refId": "A"
          }
        ],
        "options": {
          "graphMode": "none",
          "colorMode": "value",
          "textMode": "value_and_name"
        },
        "fieldConfig": {
          "defaults": {
            "unit": "short",
            "thresholds": {
              "mode": "absolute",
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
        "id": 3,
        "title": "Active Missions",
        "type": "stat",
        "gridPos": {"x": 12, "y": 0, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "count(hgr_mission_status{status=\"in_progress\"})",
            "refId": "A"
          }
        ],
        "options": {
          "graphMode": "area",
          "colorMode": "value"
        },
        "fieldConfig": {
          "defaults": {
            "unit": "short",
            "color": {"mode": "thresholds"},
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"value": 0, "color": "green"},
                {"value": 50, "color": "yellow"},
                {"value": 100, "color": "red"}
              ]
            }
          }
        }
      },
      
      {
        "id": 4,
        "title": "CPU Usage",
        "type": "gauge",
        "gridPos": {"x": 18, "y": 0, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "100 - (avg(rate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
            "refId": "A"
          }
        ],
        "options": {
          "showThresholdLabels": false,
          "showThresholdMarkers": true
        },
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "min": 0,
            "max": 100,
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"value": 0, "color": "green"},
                {"value": 70, "color": "yellow"},
                {"value": 85, "color": "red"}
              ]
            }
          }
        }
      },
      
      {
        "id": 5,
        "title": "Agent Status Map",
        "type": "status-history",
        "gridPos": {"x": 0, "y": 4, "w": 24, "h": 6},
        "targets": [
          {
            "expr": "up{job=~\"hgr-agent-.*\"}",
            "legendFormat": "{{instance}}",
            "refId": "A"
          }
        ],
        "options": {
          "showValue": "never",
          "rowHeight": 0.9,
          "colWidth": 0.9
        },
        "fieldConfig": {
          "defaults": {
            "custom": {
              "fillOpacity": 70
            }
          }
        }
      },
      
      {
        "id": 6,
        "title": "Message Throughput (Semantic Bus)",
        "type": "timeseries",
        "gridPos": {"x": 0, "y": 10, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "sum(rate(hgr_semantic_bus_messages_total[5m]))",
            "legendFormat": "Messages/sec",
            "refId": "A"
          }
        ],
        "options": {
          "legend": {
            "displayMode": "list",
            "placement": "bottom",
            "showLegend": true
          },
          "tooltip": {
            "mode": "multi"
          }
        },
        "fieldConfig": {
          "defaults": {
            "unit": "short",
            "custom": {
              "drawStyle": "line",
              "lineInterpolation": "smooth",
              "fillOpacity": 20
            }
          }
        }
      },
      
      {
        "id": 7,
        "title": "Memory Usage by Pod",
        "type": "timeseries",
        "gridPos": {"x": 12, "y": 10, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "sum by (pod) (container_memory_usage_bytes{pod=~\"hgr-pod-.*\"})",
            "legendFormat": "{{pod}}",
            "refId": "A"
          }
        ],
        "options": {
          "legend": {
            "displayMode": "table",
            "placement": "right",
            "showLegend": true,
            "calcs": ["lastNotNull", "max"]
          }
        },
        "fieldConfig": {
          "defaults": {
            "unit": "bytes",
            "custom": {
              "drawStyle": "line",
              "lineInterpolation": "smooth",
              "fillOpacity": 0,
              "stacking": {
                "mode": "normal"
              }
            }
          }
        }
      },
      
      {
        "id": 8,
        "title": "Recent Alerts",
        "type": "table",
        "gridPos": {"x": 0, "y": 18, "w": 24, "h": 6},
        "targets": [
          {
            "expr": "ALERTS{alertstate=\"firing\"}",
            "format": "table",
            "instant": true,
            "refId": "A"
          }
        ],
        "options": {
          "showHeader": true,
          "sortBy": [
            {
              "displayName": "Time",
              "desc": true
            }
          ]
        },
        "fieldConfig": {
          "defaults": {
            "custom": {
              "align": "left",
              "displayMode": "auto"
            }
          },
          "overrides": [
            {
              "matcher": {"id": "byName", "options": "severity"},
              "properties": [
                {
                  "id": "custom.displayMode",
                  "value": "color-background"
                },
                {
                  "id": "thresholds",
                  "value": {
                    "mode": "absolute",
                    "steps": [
                      {"value": null, "color": "green"},
                      {"value": "warning", "color": "yellow"},
                      {"value": "critical", "color": "red"}
                    ]
                  }
                }
              ]
            }
          ]
        },
        "transformations": [
          {
            "id": "organize",
            "options": {
              "excludeByName": {
                "__name__": true,
                "job": true
              },
              "renameByName": {
                "alertname": "Alert",
                "severity": "Severity",
                "instance": "Instance",
                "description": "Description"
              }
            }
          }
        ]
      }
    ],
    
    "templating": {
      "list": [
        {
          "name": "datasource",
          "type": "datasource",
          "query": "prometheus",
          "current": {
            "selected": true,
            "text": "Prometheus",
            "value": "Prometheus"
          }
        },
        {
          "name": "pod",
          "type": "query",
          "datasource": "Prometheus",
          "query": "label_values(up{job=~\"hgr-.*\"}, pod)",
          "multi": true,
          "includeAll": true,
          "refresh": 1
        }
      ]
    },
    
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    
    "timepicker": {
      "refresh_intervals": ["5s", "10s", "30s", "1m", "5m", "15m", "30m", "1h"]
    }
  }
}
```

---

## 4. AGENT PERFORMANCE DASHBOARD

### 4.1 Agent Metrics Panel Configuration

**File:** `monitoring/grafana/dashboards/agent_performance.json`

```json
{
  "dashboard": {
    "title": "Holy Grail Refinery - Agent Performance",
    "uid": "hgr-agent-performance",
    "tags": ["holy-grail", "agents"],
    "refresh": "30s",
    
    "panels": [
      {
        "id": 1,
        "title": "Agent Response Times",
        "type": "heatmap",
        "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "histogram_quantile(0.95, sum(rate(hgr_agent_request_duration_seconds_bucket[5m])) by (agent, le))",
            "legendFormat": "{{agent}} - p95",
            "refId": "A"
          }
        ],
        "options": {
          "calculate": false,
          "cellGap": 2,
          "cellRadius": 0,
          "color": {
            "exponent": 0.5,
            "fill": "dark-orange",
            "mode": "spectrum",
            "scheme": "Spectral",
            "steps": 128
          },
          "exemplars": {
            "color": "rgba(255,0,255,0.7)"
          },
          "yAxis": {
            "axisPlacement": "left",
            "reverse": false,
            "unit": "s"
          }
        }
      },
      
      {
        "id": 2,
        "title": "Agent CPU Usage",
        "type": "timeseries",
        "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "sum by (agent) (rate(container_cpu_usage_seconds_total{container=~\"hgr-agent-.*\"}[5m])) * 100",
            "legendFormat": "{{agent}}",
            "refId": "A"
          }
        ],
        "options": {
          "legend": {
            "displayMode": "table",
            "placement": "right",
            "showLegend": true,
            "calcs": ["mean", "max", "last"]
          }
        },
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "min": 0,
            "max": 100,
            "custom": {
              "drawStyle": "line",
              "lineWidth": 1,
              "fillOpacity": 10
            }
          }
        }
      },
      
      {
        "id": 3,
        "title": "Agent Memory Usage",
        "type": "timeseries",
        "gridPos": {"x": 0, "y": 8, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "sum by (agent) (container_memory_usage_bytes{container=~\"hgr-agent-.*\"})",
            "legendFormat": "{{agent}}",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "bytes",
            "custom": {
              "drawStyle": "line",
              "lineWidth": 1,
              "fillOpacity": 10
            }
          }
        }
      },
      
      {
        "id": 4,
        "title": "Agent Task Completion Rate",
        "type": "bargauge",
        "gridPos": {"x": 12, "y": 8, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "sum by (agent) (rate(hgr_agent_tasks_completed_total[5m]))",
            "legendFormat": "{{agent}}",
            "refId": "A"
          }
        ],
        "options": {
          "orientation": "horizontal",
          "displayMode": "gradient",
          "showUnfilled": true
        },
        "fieldConfig": {
          "defaults": {
            "unit": "tasks/sec",
            "color": {
              "mode": "continuous-GrYlRd"
            },
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"value": 0, "color": "red"},
                {"value": 1, "color": "yellow"},
                {"value": 5, "color": "green"}
              ]
            }
          }
        }
      },
      
      {
        "id": 5,
        "title": "Agent Error Rates",
        "type": "timeseries",
        "gridPos": {"x": 0, "y": 16, "w": 24, "h": 8},
        "targets": [
          {
            "expr": "sum by (agent) (rate(hgr_agent_errors_total[5m]))",
            "legendFormat": "{{agent}}",
            "refId": "A"
          }
        ],
        "alert": {
          "conditions": [
            {
              "evaluator": {
                "params": [0.1],
                "type": "gt"
              },
              "operator": {
                "type": "and"
              },
              "query": {
                "params": ["A", "5m", "now"]
              },
              "reducer": {
                "params": [],
                "type": "avg"
              },
              "type": "query"
            }
          ],
          "executionErrorState": "alerting",
          "for": "5m",
          "frequency": "1m",
          "name": "High Agent Error Rate",
          "noDataState": "no_data",
          "notifications": []
        },
        "fieldConfig": {
          "defaults": {
            "unit": "errors/sec",
            "custom": {
              "drawStyle": "line",
              "lineWidth": 2,
              "fillOpacity": 0
            },
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"value": 0, "color": "green"},
                {"value": 0.05, "color": "yellow"},
                {"value": 0.1, "color": "red"}
              ]
            }
          }
        }
      },
      
      {
        "id": 6,
        "title": "Context Window Utilization",
        "type": "timeseries",
        "gridPos": {"x": 0, "y": 24, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "(hgr_agent_context_tokens_used / hgr_agent_context_tokens_limit) * 100",
            "legendFormat": "{{agent}}",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "min": 0,
            "max": 100,
            "custom": {
              "drawStyle": "line",
              "fillOpacity": 20
            },
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"value": 0, "color": "green"},
                {"value": 70, "color": "yellow"},
                {"value": 90, "color": "red"}
              ]
            }
          }
        }
      },
      
      {
        "id": 7,
        "title": "API Key Usage by Agent",
        "type": "piechart",
        "gridPos": {"x": 12, "y": 24, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "sum by (agent) (hgr_agent_api_calls_total)",
            "legendFormat": "{{agent}}",
            "refId": "A"
          }
        ],
        "options": {
          "legend": {
            "displayMode": "table",
            "placement": "right",
            "values": ["value", "percent"]
          },
          "pieType": "donut",
          "displayLabels": ["percent"]
        }
      }
    ],
    
    "templating": {
      "list": [
        {
          "name": "agent",
          "type": "query",
          "datasource": "Prometheus",
          "query": "label_values(up{job=~\"hgr-agent-.*\"}, agent)",
          "multi": true,
          "includeAll": true,
          "refresh": 1
        },
        {
          "name": "pod",
          "type": "query",
          "datasource": "Prometheus",
          "query": "label_values(up{job=~\"hgr-agent-.*\"}, pod)",
          "multi": true,
          "includeAll": true,
          "refresh": 1
        }
      ]
    }
  }
}
```

---

## 5. RESOURCE UTILIZATION DASHBOARD

### 5.1 Infrastructure Metrics

**File:** `monitoring/grafana/dashboards/resource_utilization.json`

```json
{
  "dashboard": {
    "title": "Holy Grail Refinery - Resource Utilization",
    "uid": "hgr-resources",
    "tags": ["holy-grail", "infrastructure"],
    "refresh": "30s",
    
    "panels": [
      {
        "id": 1,
        "title": "CPU Usage by Core",
        "type": "timeseries",
        "gridPos": {"x": 0, "y": 0, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "100 - (avg by (cpu) (rate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
            "legendFormat": "Core {{cpu}}",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "min": 0,
            "max": 100,
            "custom": {
              "drawStyle": "line",
              "fillOpacity": 10,
              "stacking": {
                "mode": "none"
              }
            }
          }
        }
      },
      
      {
        "id": 2,
        "title": "Memory Usage",
        "type": "timeseries",
        "gridPos": {"x": 12, "y": 0, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes",
            "legendFormat": "Used",
            "refId": "A"
          },
          {
            "expr": "node_memory_MemAvailable_bytes",
            "legendFormat": "Available",
            "refId": "B"
          },
          {
            "expr": "node_memory_MemTotal_bytes",
            "legendFormat": "Total",
            "refId": "C"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "bytes",
            "custom": {
              "drawStyle": "line",
              "fillOpacity": 10
            }
          }
        }
      },
      
      {
        "id": 3,
        "title": "Disk Usage",
        "type": "gauge",
        "gridPos": {"x": 0, "y": 8, "w": 6, "h": 6},
        "targets": [
          {
            "expr": "(node_filesystem_size_bytes{mountpoint=\"/\"} - node_filesystem_free_bytes{mountpoint=\"/\"}) / node_filesystem_size_bytes{mountpoint=\"/\"} * 100",
            "refId": "A"
          }
        ],
        "options": {
          "showThresholdLabels": true,
          "showThresholdMarkers": true
        },
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "min": 0,
            "max": 100,
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"value": 0, "color": "green"},
                {"value": 70, "color": "yellow"},
                {"value": 85, "color": "red"}
              ]
            }
          }
        }
      },
      
      {
        "id": 4,
        "title": "Disk I/O",
        "type": "timeseries",
        "gridPos": {"x": 6, "y": 8, "w": 18, "h": 6},
        "targets": [
          {
            "expr": "rate(node_disk_read_bytes_total[5m])",
            "legendFormat": "Read",
            "refId": "A"
          },
          {
            "expr": "rate(node_disk_written_bytes_total[5m])",
            "legendFormat": "Write",
            "refId": "B"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "Bps",
            "custom": {
              "drawStyle": "line",
              "fillOpacity": 10
            }
          }
        }
      },
      
      {
        "id": 5,
        "title": "Network Traffic",
        "type": "timeseries",
        "gridPos": {"x": 0, "y": 14, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "rate(node_network_receive_bytes_total[5m])",
            "legendFormat": "RX {{device}}",
            "refId": "A"
          },
          {
            "expr": "rate(node_network_transmit_bytes_total[5m])",
            "legendFormat": "TX {{device}}",
            "refId": "B"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "Bps",
            "custom": {
              "drawStyle": "line",
              "fillOpacity": 10
            }
          }
        }
      },
      
      {
        "id": 6,
        "title": "Docker Container Count",
        "type": "stat",
        "gridPos": {"x": 12, "y": 14, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "count(container_last_seen)",
            "refId": "A"
          }
        ],
        "options": {
          "graphMode": "area",
          "colorMode": "value"
        },
        "fieldConfig": {
          "defaults": {
            "unit": "short",
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"value": 0, "color": "red"},
                {"value": 35, "color": "yellow"},
                {"value": 40, "color": "green"}
              ]
            }
          }
        }
      },
      
      {
        "id": 7,
        "title": "Redis Memory Usage",
        "type": "gauge",
        "gridPos": {"x": 18, "y": 14, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "(redis_memory_used_bytes / redis_memory_max_bytes) * 100",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "min": 0,
            "max": 100,
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"value": 0, "color": "green"},
                {"value": 70, "color": "yellow"},
                {"value": 85, "color": "red"}
              ]
            }
          }
        }
      },
      
      {
        "id": 8,
        "title": "PostgreSQL Connections",
        "type": "timeseries",
        "gridPos": {"x": 12, "y": 18, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "pg_stat_database_numbackends",
            "legendFormat": "{{datname}}",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "short",
            "custom": {
              "drawStyle": "line",
              "fillOpacity": 0
            }
          }
        }
      }
    ]
  }
}
```

---

## 6. MISSION TRACKING DASHBOARD

### 6.1 Mission Metrics Configuration

**File:** `monitoring/grafana/dashboards/mission_tracking.json`

```json
{
  "dashboard": {
    "title": "Holy Grail Refinery - Mission Tracking",
    "uid": "hgr-missions",
    "tags": ["holy-grail", "missions"],
    "refresh": "30s",
    
    "panels": [
      {
        "id": 1,
        "title": "Active Missions",
        "type": "stat",
        "gridPos": {"x": 0, "y": 0, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "count(hgr_mission_status{status=\"in_progress\"})",
            "refId": "A"
          }
        ],
        "options": {
          "graphMode": "area",
          "colorMode": "background"
        },
        "fieldConfig": {
          "defaults": {
            "unit": "short",
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"value": 0, "color": "green"},
                {"value": 50, "color": "yellow"},
                {"value": 100, "color": "red"}
              ]
            }
          }
        }
      },
      
      {
        "id": 2,
        "title": "Mission Success Rate (24h)",
        "type": "gauge",
        "gridPos": {"x": 6, "y": 0, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "(sum(increase(hgr_mission_status{status=\"completed\"}[24h])) / sum(increase(hgr_mission_status[24h]))) * 100",
            "refId": "A"
          }
        ],
        "options": {
          "showThresholdLabels": false,
          "showThresholdMarkers": true
        },
        "fieldConfig": {
          "defaults": {
            "unit": "percent",
            "min": 0,
            "max": 100,
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"value": 0, "color": "red"},
                {"value": 90, "color": "yellow"},
                {"value": 95, "color": "green"}
              ]
            }
          }
        }
      },
      
      {
        "id": 3,
        "title": "Average Mission Duration",
        "type": "stat",
        "gridPos": {"x": 12, "y": 0, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "avg(hgr_mission_duration_seconds{status=\"completed\"})",
            "refId": "A"
          }
        ],
        "options": {
          "graphMode": "area"
        },
        "fieldConfig": {
          "defaults": {
            "unit": "s",
            "decimals": 1
          }
        }
      },
      
      {
        "id": 4,
        "title": "Missions Completed (24h)",
        "type": "stat",
        "gridPos": {"x": 18, "y": 0, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "sum(increase(hgr_mission_status{status=\"completed\"}[24h]))",
            "refId": "A"
          }
        ],
        "options": {
          "graphMode": "area",
          "colorMode": "value"
        },
        "fieldConfig": {
          "defaults": {
            "unit": "short",
            "color": {"mode": "palette-classic"}
          }
        }
      },
      
      {
        "id": 5,
        "title": "Mission Timeline",
        "type": "timeseries",
        "gridPos": {"x": 0, "y": 4, "w": 24, "h": 8},
        "targets": [
          {
            "expr": "sum by (status) (rate(hgr_mission_status[5m]))",
            "legendFormat": "{{status}}",
            "refId": "A"
          }
        ],
        "options": {
          "legend": {
            "displayMode": "table",
            "placement": "right",
            "showLegend": true,
            "calcs": ["mean", "max", "last"]
          }
        },
        "fieldConfig": {
          "defaults": {
            "unit": "missions/sec",
            "custom": {
              "drawStyle": "line",
              "lineWidth": 2,
              "fillOpacity": 20,
              "stacking": {
                "mode": "normal"
              }
            }
          }
        }
      },
      
      {
        "id": 6,
        "title": "LogicNodes Generated",
        "type": "timeseries",
        "gridPos": {"x": 0, "y": 12, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "sum(rate(hgr_logicnodes_generated_total[5m]))",
            "legendFormat": "LogicNodes/sec",
            "refId": "A"
          }
        ],
        "options": {
          "legend": {
            "showLegend": true
          }
        },
        "fieldConfig": {
          "defaults": {
            "unit": "short",
            "custom": {
              "drawStyle": "line",
              "lineWidth": 2,
              "fillOpacity": 20
            }
          }
        }
      },
      
      {
        "id": 7,
        "title": "Missions by Language",
        "type": "barchart",
        "gridPos": {"x": 12, "y": 12, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "sum by (language) (hgr_mission_status)",
            "legendFormat": "{{language}}",
            "refId": "A"
          }
        ],
        "options": {
          "orientation": "horizontal",
          "showValue": "always",
          "xTickLabelRotation": 0
        },
        "fieldConfig": {
          "defaults": {
            "unit": "short",
            "custom": {
              "fillOpacity": 80
            }
          }
        }
      },
      
      {
        "id": 8,
        "title": "Mission Queue Depth",
        "type": "timeseries",
        "gridPos": {"x": 0, "y": 20, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "hgr_mission_queue_depth",
            "legendFormat": "Pending Missions",
            "refId": "A"
          }
        ],
        "alert": {
          "conditions": [
            {
              "evaluator": {
                "params": [50],
                "type": "gt"
              },
              "query": {
                "params": ["A", "5m", "now"]
              },
              "reducer": {
                "params": [],
                "type": "avg"
              },
              "type": "query"
            }
          ],
          "executionErrorState": "alerting",
          "for": "10m",
          "frequency": "1m",
          "name": "High Mission Queue Depth",
          "noDataState": "no_data"
        },
        "fieldConfig": {
          "defaults": {
            "unit": "short",
            "custom": {
              "drawStyle": "line",
              "lineWidth": 2,
              "fillOpacity": 20
            },
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"value": 0, "color": "green"},
                {"value": 30, "color": "yellow"},
                {"value": 50, "color": "red"}
              ]
            }
          }
        }
      },
      
      {
        "id": 9,
        "title": "Recent Mission Failures",
        "type": "table",
        "gridPos": {"x": 12, "y": 20, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "hgr_mission_status{status=\"failed\"}",
            "format": "table",
            "instant": true,
            "refId": "A"
          }
        ],
        "options": {
          "showHeader": true,
          "sortBy": [
            {
              "displayName": "Time",
              "desc": true
            }
          ]
        },
        "transformations": [
          {
            "id": "organize",
            "options": {
              "renameByName": {
                "mission_id": "Mission ID",
                "language": "Language",
                "error_message": "Error",
                "agent": "Agent"
              }
            }
          }
        ]
      }
    ],
    
    "templating": {
      "list": [
        {
          "name": "language",
          "type": "query",
          "datasource": "Prometheus",
          "query": "label_values(hgr_mission_status, language)",
          "multi": true,
          "includeAll": true,
          "refresh": 1
        }
      ]
    }
  }
}
```

---

## 7. COST & EFFICIENCY DASHBOARD

### 7.1 API Cost Tracking

**File:** `monitoring/grafana/dashboards/cost_efficiency.json`

```json
{
  "dashboard": {
    "title": "Holy Grail Refinery - Cost & Efficiency",
    "uid": "hgr-cost",
    "tags": ["holy-grail", "cost", "efficiency"],
    "refresh": "1m",
    
    "panels": [
      {
        "id": 1,
        "title": "Total API Cost (24h)",
        "type": "stat",
        "gridPos": {"x": 0, "y": 0, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "sum(increase(hgr_api_cost_usd_total[24h]))",
            "refId": "A"
          }
        ],
        "options": {
          "graphMode": "area",
          "colorMode": "background"
        },
        "fieldConfig": {
          "defaults": {
            "unit": "currencyUSD",
            "decimals": 2,
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"value": 0, "color": "green"},
                {"value": 100, "color": "yellow"},
                {"value": 200, "color": "red"}
              ]
            }
          }
        }
      },
      
      {
        "id": 2,
        "title": "Cost per Mission",
        "type": "stat",
        "gridPos": {"x": 6, "y": 0, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "sum(increase(hgr_api_cost_usd_total[24h])) / sum(increase(hgr_mission_status{status=\"completed\"}[24h]))",
            "refId": "A"
          }
        ],
        "options": {
          "graphMode": "none"
        },
        "fieldConfig": {
          "defaults": {
            "unit": "currencyUSD",
            "decimals": 4
          }
        }
      },
      
      {
        "id": 3,
        "title": "Token Usage (24h)",
        "type": "stat",
        "gridPos": {"x": 12, "y": 0, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "sum(increase(hgr_api_tokens_total[24h]))",
            "refId": "A"
          }
        ],
        "options": {
          "graphMode": "area"
        },
        "fieldConfig": {
          "defaults": {
            "unit": "short",
            "decimals": 0
          }
        }
      },
      
      {
        "id": 4,
        "title": "Efficiency Score",
        "type": "gauge",
        "gridPos": {"x": 18, "y": 0, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "(sum(hgr_logicnodes_generated_total) / sum(hgr_api_tokens_total)) * 1000000",
            "refId": "A"
          }
        ],
        "options": {
          "showThresholdLabels": false,
          "showThresholdMarkers": true
        },
        "fieldConfig": {
          "defaults": {
            "unit": "short",
            "decimals": 2,
            "min": 0,
            "max": 100,
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"value": 0, "color": "red"},
                {"value": 30, "color": "yellow"},
                {"value": 50, "color": "green"}
              ]
            }
          }
        }
      },
      
      {
        "id": 5,
        "title": "API Cost Trend",
        "type": "timeseries",
        "gridPos": {"x": 0, "y": 4, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "sum(rate(hgr_api_cost_usd_total[1h]))",
            "legendFormat": "Cost/hour",
            "refId": "A"
          }
        ],
        "options": {
          "legend": {
            "showLegend": true
          }
        },
        "fieldConfig": {
          "defaults": {
            "unit": "currencyUSD",
            "custom": {
              "drawStyle": "line",
              "lineWidth": 2,
              "fillOpacity": 20
            }
          }
        }
      },
      
      {
        "id": 6,
        "title": "Cost by Agent",
        "type": "piechart",
        "gridPos": {"x": 12, "y": 4, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "sum by (agent) (increase(hgr_api_cost_usd_total[24h]))",
            "legendFormat": "{{agent}}",
            "refId": "A"
          }
        ],
        "options": {
          "legend": {
            "displayMode": "table",
            "placement": "right",
            "values": ["value", "percent"]
          },
          "pieType": "donut"
        }
      },
      
      {
        "id": 7,
        "title": "Token Usage by Model",
        "type": "timeseries",
        "gridPos": {"x": 0, "y": 12, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "sum by (model) (rate(hgr_api_tokens_total[5m]))",
            "legendFormat": "{{model}}",
            "refId": "A"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "unit": "tokens/sec",
            "custom": {
              "drawStyle": "line",
              "fillOpacity": 10,
              "stacking": {
                "mode": "normal"
              }
            }
          }
        }
      },
      
      {
        "id": 8,
        "title": "Cost Projection (30 days)",
        "type": "stat",
        "gridPos": {"x": 12, "y": 12, "w": 12, "h": 8},
        "targets": [
          {
            "expr": "(sum(increase(hgr_api_cost_usd_total[24h])) / 24) * 720",
            "refId": "A"
          }
        ],
        "options": {
          "graphMode": "area",
          "colorMode": "value"
        },
        "fieldConfig": {
          "defaults": {
            "unit": "currencyUSD",
            "decimals": 2
          }
        }
      }
    ]
  }
}
```

---

## 8. ALERT MANAGEMENT DASHBOARD

### 8.1 Alert Overview Configuration

**File:** `monitoring/grafana/dashboards/alert_management.json`

```json
{
  "dashboard": {
    "title": "Holy Grail Refinery - Alert Management",
    "uid": "hgr-alerts",
    "tags": ["holy-grail", "alerts"],
    "refresh": "10s",
    
    "panels": [
      {
        "id": 1,
        "title": "Active Alerts",
        "type": "stat",
        "gridPos": {"x": 0, "y": 0, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "count(ALERTS{alertstate=\"firing\"})",
            "refId": "A"
          }
        ],
        "options": {
          "graphMode": "none",
          "colorMode": "background"
        },
        "fieldConfig": {
          "defaults": {
            "unit": "short",
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"value": 0, "color": "green"},
                {"value": 1, "color": "yellow"},
                {"value": 5, "color": "red"}
              ]
            }
          }
        }
      },
      
      {
        "id": 2,
        "title": "Critical Alerts",
        "type": "stat",
        "gridPos": {"x": 6, "y": 0, "w": 6, "h": 4},
        "targets": [
          {
            "expr": "count(ALERTS{alertstate=\"firing\",severity=\"critical\"})",
            "refId": "A"
          }
        ],
        "options": {
          "colorMode": "background"
        },
        "fieldConfig": {
          "defaults": {
            "unit": "short",
            "thresholds": {
              "mode": "absolute",
              "steps": [
                {"value": 0, "color": "green"},
                {"value": 1, "color": "red"}
              ]
            }
          }
        }
      },
      
      {
        "id": 3,
        "title": "Alerts by Severity",
        "type": "piechart",
        "gridPos": {"x": 12, "y": 0, "w": 6, "h": 8},
        "targets": [
          {
            "expr": "count by (severity) (ALERTS{alertstate=\"firing\"})",
            "legendFormat": "{{severity}}",
            "refId": "A"
          }
        ],
        "options": {
          "legend": {
            "displayMode": "list",
            "placement": "bottom"
          },
          "pieType": "pie"
        }
      },
      
      {
        "id": 4,
        "title": "Alert Timeline",
        "type": "timeseries",
        "gridPos": {"x": 0, "y": 8, "w": 24, "h": 8},
        "targets": [
          {
            "expr": "count by (alertname) (ALERTS{alertstate=\"firing\"})",
            "legendFormat": "{{alertname}}",
            "refId": "A"
          }
        ],
        "options": {
          "legend": {
            "displayMode": "table",
            "placement": "right",
            "showLegend": true
          }
        },
        "fieldConfig": {
          "defaults": {
            "unit": "short",
            "custom": {
              "drawStyle": "line",
              "lineWidth": 2,
              "fillOpacity": 0,
              "stacking": {
                "mode": "normal"
              }
            }
          }
        }
      },
      
      {
        "id": 5,
        "title": "Active Alerts Table",
        "type": "table",
        "gridPos": {"x": 0, "y": 16, "w": 24, "h": 12},
        "targets": [
          {
            "expr": "ALERTS{alertstate=\"firing\"}",
            "format": "table",
            "instant": true,
            "refId": "A"
          }
        ],
        "options": {
          "showHeader": true,
          "sortBy": [
            {
              "displayName": "Severity",
              "desc": true
            }
          ]
        },
        "fieldConfig": {
          "overrides": [
            {
              "matcher": {"id": "byName", "options": "severity"},
              "properties": [
                {
                  "id": "custom.displayMode",
                  "value": "color-background"
                },
                {
                  "id": "thresholds",
                  "value": {
                    "mode": "absolute",
                    "steps": [
                      {"value": null, "color": "green"},
                      {"value": "warning", "color": "yellow"},
                      {"value": "critical", "color": "red"}
                    ]
                  }
                }
              ]
            }
          ]
        },
        "transformations": [
          {
            "id": "organize",
            "options": {
              "excludeByName": {
                "__name__": true,
                "job": false
              },
              "renameByName": {
                "alertname": "Alert",
                "severity": "Severity",
                "instance": "Instance",
                "description": "Description",
                "summary": "Summary"
              }
            }
          }
        ]
      }
    ]
  }
}
```

---

## 9. CUSTOM PANEL LIBRARY

### 9.1 Reusable Panel Templates

**File:** `monitoring/grafana/panels/library_panels.json`

```json
{
  "panels": [
    {
      "name": "Agent Health Check",
      "type": "stat",
      "description": "Shows agent UP/DOWN status",
      "targets": [
        {
          "expr": "up{job=\"$agent\"}",
          "refId": "A"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "mappings": [
            {"type": "value", "value": 1, "text": "UP", "color": "green"},
            {"type": "value", "value": 0, "text": "DOWN", "color": "red"}
          ]
        }
      }
    },
    
    {
      "name": "API Response Time Histogram",
      "type": "heatmap",
      "description": "API latency distribution",
      "targets": [
        {
          "expr": "histogram_quantile(0.95, sum(rate(hgr_api_duration_seconds_bucket[5m])) by (le))",
          "refId": "A"
        }
      ],
      "options": {
        "calculate": true,
        "yAxis": {"unit": "s"}
      }
    },
    
    {
      "name": "Error Rate Gauge",
      "type": "gauge",
      "description": "Shows error rate percentage",
      "targets": [
        {
          "expr": "(sum(rate(hgr_errors_total[5m])) / sum(rate(hgr_requests_total[5m]))) * 100",
          "refId": "A"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "unit": "percent",
          "thresholds": {
            "steps": [
              {"value": 0, "color": "green"},
              {"value": 1, "color": "yellow"},
              {"value": 5, "color": "red"}
            ]
          }
        }
      }
    }
  ]
}
```

---

## 10. DASHBOARD AUTOMATION & PROVISIONING

### 10.1 Automated Dashboard Provisioning

**File:** `monitoring/grafana/provisioning/dashboards/dashboards.yml`

```yaml
apiVersion: 1

providers:
  - name: 'Holy Grail Refinery'
    orgId: 1
    folder: 'HGR'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: true
```

### 10.2 Dashboard Export Script

**File:** `scripts/export_dashboards.sh`

```bash
#!/bin/bash
# Export all Grafana dashboards to JSON files

set -e

GRAFANA_URL="http://localhost:3000"
GRAFANA_USER="admin"
GRAFANA_PASSWORD="${GRAFANA_ADMIN_PASSWORD}"
OUTPUT_DIR="./monitoring/grafana/dashboards"

echo "Exporting Grafana dashboards..."

# Get all dashboard UIDs
DASHBOARD_UIDS=$(curl -s -u "$GRAFANA_USER:$GRAFANA_PASSWORD" \
    "$GRAFANA_URL/api/search?type=dash-db" | \
    jq -r '.[].uid')

# Export each dashboard
for uid in $DASHBOARD_UIDS; do
    echo "Exporting dashboard: $uid"
    
    curl -s -u "$GRAFANA_USER:$GRAFANA_PASSWORD" \
        "$GRAFANA_URL/api/dashboards/uid/$uid" | \
        jq '.dashboard' > "$OUTPUT_DIR/${uid}.json"
done

echo "✓ All dashboards exported to $OUTPUT_DIR"
```

### 10.3 Dashboard Import Script

**File:** `scripts/import_dashboards.sh`

```bash
#!/bin/bash
# Import all dashboard JSON files into Grafana

set -e

GRAFANA_URL="http://localhost:3000"
GRAFANA_USER="admin"
GRAFANA_PASSWORD="${GRAFANA_ADMIN_PASSWORD}"
DASHBOARD_DIR="./monitoring/grafana/dashboards"

echo "Importing Grafana dashboards..."

for dashboard in "$DASHBOARD_DIR"/*.json; do
    echo "Importing: $(basename $dashboard)"
    
    curl -X POST -u "$GRAFANA_USER:$GRAFANA_PASSWORD" \
        -H "Content-Type: application/json" \
        "$GRAFANA_URL/api/dashboards/db" \
        -d @"$dashboard"
done

echo "✓ All dashboards imported"
```

---

## DOCUMENT METADATA

**Document ID:** 37  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Operations & Deployment  
**Owner:** Monitoring Lead  
**Dependencies:** Documents 25 (Monitoring & Observability), 36 (Incident Response)  
**Next Document:** 38 (Log Aggregation & Analysis Setup)

---

*End of System Monitoring Dashboard Configuration*
