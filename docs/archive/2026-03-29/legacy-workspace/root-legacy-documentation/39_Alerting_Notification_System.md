# DOCUMENT 39: ALERTING & NOTIFICATION SYSTEM
## Holy Grail Refinery - Operations & Deployment

**Document ID:** 39  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Operations & Deployment  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document provides **complete specifications** for the Holy Grail Refinery alerting and notification system using Prometheus AlertManager with multi-channel notification (PagerDuty, Slack, Email) and intelligent alert routing with escalation policies.

**Key Components:**
- 🚨 **AlertManager:** Central alert management and routing
- 📱 **PagerDuty:** On-call escalation for critical alerts
- 💬 **Slack:** Team notifications and incident channels
- 📧 **Email:** Detailed alert notifications
- 🔄 **Escalation Policies:** Automatic escalation for unacknowledged alerts
- 🤖 **Auto-Remediation:** Automated responses to common issues

**Alert Categories:**
- **P0 (Critical):** System down, data loss imminent
- **P1 (High):** Major degradation, immediate attention required
- **P2 (Medium):** Minor issues, requires investigation
- **P3 (Low):** Informational, review during business hours

**Response Times:**
- P0: Immediate page, 5-minute acknowledgment SLA
- P1: Immediate notification, 15-minute acknowledgment
- P2: Notification during business hours, 1-hour acknowledgment
- P3: Email digest, next-day review

---

## TABLE OF CONTENTS

1. [AlertManager Installation & Configuration](#1-alertmanager-installation--configuration)
2. [Alert Rule Definitions](#2-alert-rule-definitions)
3. [Notification Channels](#3-notification-channels)
4. [Escalation Policies](#4-escalation-policies)
5. [Alert Routing Logic](#5-alert-routing-logic)
6. [Alert Templates](#6-alert-templates)
7. [Silence & Maintenance Windows](#7-silence--maintenance-windows)
8. [Auto-Remediation Workflows](#8-auto-remediation-workflows)
9. [Alert Testing & Validation](#9-alert-testing--validation)
10. [On-Call Procedures](#10-on-call-procedures)

---

## 1. ALERTMANAGER INSTALLATION & CONFIGURATION

### 1.1 Docker Compose Configuration

**File:** `alerting/docker-compose.alertmanager.yml`

```yaml
version: '3.8'

services:
  alertmanager:
    image: prom/alertmanager:v0.26.0
    container_name: hgr-alertmanager
    restart: unless-stopped
    ports:
      - "9093:9093"
    volumes:
      - ./alertmanager/config.yml:/etc/alertmanager/config.yml
      - ./alertmanager/templates:/etc/alertmanager/templates
      - alertmanager-data:/alertmanager
    command:
      - '--config.file=/etc/alertmanager/config.yml'
      - '--storage.path=/alertmanager'
      - '--web.external-url=http://localhost:9093'
      - '--cluster.advertise-address=0.0.0.0:9093'
    networks:
      - monitoring
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:9093/-/healthy"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  alertmanager-data:

networks:
  monitoring:
    external: true
```

### 1.2 AlertManager Configuration

**File:** `alerting/alertmanager/config.yml`

```yaml
global:
  resolve_timeout: 5m
  
  # Slack configuration
  slack_api_url: '${SLACK_WEBHOOK_URL}'
  
  # PagerDuty configuration
  pagerduty_url: 'https://events.pagerduty.com/v2/enqueue'
  
  # SMTP configuration
  smtp_smarthost: 'smtp.gmail.com:587'
  smtp_from: 'alerts@holygrail.ai'
  smtp_auth_username: '${SMTP_USER}'
  smtp_auth_password: '${SMTP_PASSWORD}'
  smtp_require_tls: true

# Templates for notifications
templates:
  - '/etc/alertmanager/templates/*.tmpl'

# Alert routing tree
route:
  # Default receiver
  receiver: 'default'
  
  # Group alerts by these labels
  group_by: ['alertname', 'cluster', 'service']
  
  # Wait before sending notification to allow grouping
  group_wait: 30s
  
  # Wait before sending notification about new alerts in group
  group_interval: 5m
  
  # Wait before sending repeat notification
  repeat_interval: 4h
  
  # Child routes
  routes:
    # Critical alerts (P0)
    - match:
        severity: critical
      receiver: 'pagerduty-critical'
      continue: true  # Also send to other receivers
      group_wait: 10s
      group_interval: 1m
      repeat_interval: 5m
      routes:
        - match:
            alertname: 'SystemDown'
          receiver: 'pagerduty-critical-escalation'
    
    # High severity alerts (P1)
    - match:
        severity: high
      receiver: 'slack-high'
      group_wait: 30s
      group_interval: 5m
      repeat_interval: 1h
    
    # Warning alerts (P2)
    - match:
        severity: warning
      receiver: 'slack-warnings'
      group_wait: 5m
      group_interval: 10m
      repeat_interval: 4h
    
    # Info alerts (P3)
    - match:
        severity: info
      receiver: 'email-digest'
      group_wait: 10m
      group_interval: 1h
      repeat_interval: 24h
    
    # Agent-specific alerts
    - match_re:
        alertname: 'Agent.*'
      receiver: 'slack-agents'
      routes:
        - match:
            pod: 'A'
          receiver: 'email-pod-a-team'
        - match:
            pod: 'B'
          receiver: 'email-pod-b-team'
        - match:
            pod: 'C'
          receiver: 'email-pod-c-team'
        - match:
            pod: 'D'
          receiver: 'email-pod-d-team'
    
    # Database alerts
    - match_re:
        alertname: '(Postgres|Redis).*'
      receiver: 'slack-database'
    
    # Infrastructure alerts
    - match_re:
        alertname: '(Node|Docker|Disk).*'
      receiver: 'slack-infrastructure'

# Alert inhibition rules
inhibit_rules:
  # If system is down, suppress other alerts
  - source_match:
      alertname: 'SystemDown'
    target_match_re:
      alertname: '.*'
    equal: ['cluster']
  
  # If agent is down, suppress performance alerts
  - source_match:
      alertname: 'AgentDown'
    target_match_re:
      alertname: 'Agent(HighLatency|HighMemory|HighCPU)'
    equal: ['agent_id']
  
  # If pod is down, suppress agent alerts
  - source_match:
      alertname: 'PodDown'
    target_match_re:
      alertname: 'Agent.*'
    equal: ['pod']

# Notification receivers
receivers:
  # Default receiver
  - name: 'default'
    email_configs:
      - to: 'ops-team@holygrail.ai'
        send_resolved: true
  
  # PagerDuty for critical alerts
  - name: 'pagerduty-critical'
    pagerduty_configs:
      - service_key: '${PAGERDUTY_SERVICE_KEY_CRITICAL}'
        severity: 'critical'
        description: '{{ .CommonAnnotations.summary }}'
        details:
          firing: '{{ .Alerts.Firing | len }}'
          resolved: '{{ .Alerts.Resolved | len }}'
          alerts: '{{ range .Alerts }}{{ .Labels.alertname }}: {{ .Annotations.description }}\n{{ end }}'
        send_resolved: true
  
  # PagerDuty escalation
  - name: 'pagerduty-critical-escalation'
    pagerduty_configs:
      - service_key: '${PAGERDUTY_SERVICE_KEY_ESCALATION}'
        severity: 'critical'
        description: 'ESCALATED: {{ .CommonAnnotations.summary }}'
        send_resolved: true
  
  # Slack for high severity
  - name: 'slack-high'
    slack_configs:
      - channel: '#holy-grail-alerts-high'
        username: 'AlertManager'
        icon_emoji: ':rotating_light:'
        title: '🚨 High Severity Alert'
        text: '{{ template "slack.default.text" . }}'
        send_resolved: true
        actions:
          - type: button
            text: 'View in Grafana'
            url: '{{ .ExternalURL }}'
          - type: button
            text: 'Acknowledge'
            url: '{{ .ExternalURL }}/#/alerts?receiver=slack-high'
  
  # Slack for warnings
  - name: 'slack-warnings'
    slack_configs:
      - channel: '#holy-grail-alerts-warnings'
        username: 'AlertManager'
        icon_emoji: ':warning:'
        title: '⚠️  Warning Alert'
        text: '{{ template "slack.default.text" . }}'
        send_resolved: true
  
  # Slack for agent alerts
  - name: 'slack-agents'
    slack_configs:
      - channel: '#holy-grail-agents'
        username: 'AlertManager'
        icon_emoji: ':robot_face:'
        title: '🤖 Agent Alert'
        text: '{{ template "slack.agents.text" . }}'
        send_resolved: true
  
  # Slack for database
  - name: 'slack-database'
    slack_configs:
      - channel: '#holy-grail-database'
        username: 'AlertManager'
        icon_emoji: ':database:'
        title: '💾 Database Alert'
        text: '{{ template "slack.default.text" . }}'
        send_resolved: true
  
  # Slack for infrastructure
  - name: 'slack-infrastructure'
    slack_configs:
      - channel: '#holy-grail-infrastructure'
        username: 'AlertManager'
        icon_emoji: ':gear:'
        title: '⚙️  Infrastructure Alert'
        text: '{{ template "slack.default.text" . }}'
        send_resolved: true
  
  # Email digest for info
  - name: 'email-digest'
    email_configs:
      - to: 'ops-team@holygrail.ai'
        subject: 'Daily Digest: Holy Grail Refinery Alerts'
        html: '{{ template "email.digest.html" . }}'
        send_resolved: false
  
  # Pod team emails
  - name: 'email-pod-a-team'
    email_configs:
      - to: 'pod-a-team@holygrail.ai'
        subject: 'Pod A Alert: {{ .CommonAnnotations.summary }}'
        html: '{{ template "email.default.html" . }}'
  
  - name: 'email-pod-b-team'
    email_configs:
      - to: 'pod-b-team@holygrail.ai'
        subject: 'Pod B Alert: {{ .CommonAnnotations.summary }}'
        html: '{{ template "email.default.html" . }}'
  
  - name: 'email-pod-c-team'
    email_configs:
      - to: 'pod-c-team@holygrail.ai'
        subject: 'Pod C Alert: {{ .CommonAnnotations.summary }}'
        html: '{{ template "email.default.html" . }}'
  
  - name: 'email-pod-d-team'
    email_configs:
      - to: 'pod-d-team@holygrail.ai'
        subject: 'Pod D Alert: {{ .CommonAnnotations.summary }}'
        html: '{{ template "email.default.html" . }}'
```

---

## 2. ALERT RULE DEFINITIONS

### 2.1 Critical Alerts (P0)

**File:** `monitoring/prometheus/rules/critical_alerts.yml`

```yaml
groups:
  - name: critical_alerts
    interval: 15s
    rules:
      # System completely down
      - alert: SystemDown
        expr: up{job="hgr-api"} == 0
        for: 1m
        labels:
          severity: critical
          category: infrastructure
        annotations:
          summary: "Holy Grail Refinery system is DOWN"
          description: "API gateway is unreachable for 1 minute"
          runbook_url: "https://docs.holygrail.ai/runbooks/system-down"
      
      # Database connection failure
      - alert: DatabaseConnectionFailure
        expr: pg_up == 0 or redis_up == 0
        for: 30s
        labels:
          severity: critical
          category: database
        annotations:
          summary: "Database connection failure"
          description: "Cannot connect to {{ $labels.job }} database"
          runbook_url: "https://docs.holygrail.ai/runbooks/database-failure"
      
      # Critical agent pod completely down
      - alert: PodDown
        expr: sum by (pod) (up{job=~"hgr-agent-.*"}) / count by (pod) (up{job=~"hgr-agent-.*"}) < 0.5
        for: 2m
        labels:
          severity: critical
          category: agents
        annotations:
          summary: "Pod {{ $labels.pod }} is down"
          description: "More than 50% of agents in Pod {{ $labels.pod }} are down"
          runbook_url: "https://docs.holygrail.ai/runbooks/pod-failure"
      
      # Disk almost full
      - alert: DiskAlmostFull
        expr: (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) * 100 < 5
        for: 5m
        labels:
          severity: critical
          category: infrastructure
        annotations:
          summary: "Disk space critically low"
          description: "Only {{ $value | humanize }}% disk space remaining"
          runbook_url: "https://docs.holygrail.ai/runbooks/disk-full"
      
      # Memory exhaustion
      - alert: MemoryExhausted
        expr: (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100 < 5
        for: 2m
        labels:
          severity: critical
          category: infrastructure
        annotations:
          summary: "Memory critically low"
          description: "Only {{ $value | humanize }}% memory available"
          runbook_url: "https://docs.holygrail.ai/runbooks/memory-exhausted"
```

### 2.2 High Severity Alerts (P1)

**File:** `monitoring/prometheus/rules/high_severity_alerts.yml`

```yaml
groups:
  - name: high_severity_alerts
    interval: 30s
    rules:
      # Agent down
      - alert: AgentDown
        expr: up{job=~"hgr-agent-.*"} == 0
        for: 5m
        labels:
          severity: high
          category: agents
        annotations:
          summary: "Agent {{ $labels.agent_id }} is down"
          description: "Agent has been unreachable for 5 minutes"
          runbook_url: "https://docs.holygrail.ai/runbooks/agent-down"
      
      # High error rate
      - alert: HighErrorRate
        expr: sum(rate(hgr_errors_total[5m])) / sum(rate(hgr_requests_total[5m])) > 0.05
        for: 10m
        labels:
          severity: high
          category: performance
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }} (threshold: 5%)"
          runbook_url: "https://docs.holygrail.ai/runbooks/high-error-rate"
      
      # High API latency
      - alert: HighAPILatency
        expr: histogram_quantile(0.95, sum(rate(hgr_api_duration_seconds_bucket[5m])) by (le)) > 5
        for: 10m
        labels:
          severity: high
          category: performance
        annotations:
          summary: "API latency is high"
          description: "p95 latency is {{ $value }}s (threshold: 5s)"
          runbook_url: "https://docs.holygrail.ai/runbooks/high-latency"
      
      # Mission queue backed up
      - alert: MissionQueueBacklog
        expr: hgr_mission_queue_depth > 100
        for: 15m
        labels:
          severity: high
          category: operations
        annotations:
          summary: "Mission queue is backed up"
          description: "{{ $value }} missions are queued (threshold: 100)"
          runbook_url: "https://docs.holygrail.ai/runbooks/queue-backlog"
      
      # Database connections saturated
      - alert: DatabaseConnectionsSaturated
        expr: pg_stat_database_numbackends / pg_settings_max_connections > 0.8
        for: 10m
        labels:
          severity: high
          category: database
        annotations:
          summary: "Database connections near limit"
          description: "{{ $value | humanizePercentage }} of connections in use"
          runbook_url: "https://docs.holygrail.ai/runbooks/db-connections"
```

### 2.3 Warning Alerts (P2)

**File:** `monitoring/prometheus/rules/warning_alerts.yml`

```yaml
groups:
  - name: warning_alerts
    interval: 1m
    rules:
      # High CPU usage
      - alert: HighCPUUsage
        expr: 100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 15m
        labels:
          severity: warning
          category: infrastructure
        annotations:
          summary: "CPU usage is high"
          description: "CPU usage is {{ $value | humanize }}% (threshold: 80%)"
      
      # High memory usage
      - alert: HighMemoryUsage
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 80
        for: 15m
        labels:
          severity: warning
          category: infrastructure
        annotations:
          summary: "Memory usage is high"
          description: "Memory usage is {{ $value | humanize }}% (threshold: 80%)"
      
      # Agent high latency
      - alert: AgentHighLatency
        expr: histogram_quantile(0.95, sum by (agent_id, le) (rate(hgr_agent_request_duration_seconds_bucket[5m]))) > 10
        for: 15m
        labels:
          severity: warning
          category: performance
        annotations:
          summary: "Agent {{ $labels.agent_id }} has high latency"
          description: "p95 latency is {{ $value }}s (threshold: 10s)"
      
      # Context window filling up
      - alert: ContextWindowHigh
        expr: (hgr_agent_context_tokens_used / hgr_agent_context_tokens_limit) * 100 > 80
        for: 10m
        labels:
          severity: warning
          category: agents
        annotations:
          summary: "Agent {{ $labels.agent_id }} context window nearly full"
          description: "Context window is {{ $value | humanize }}% full"
      
      # High API costs
      - alert: HighAPICosts
        expr: rate(hgr_api_cost_usd_total[1h]) * 24 > 100
        for: 1h
        labels:
          severity: warning
          category: cost
        annotations:
          summary: "API costs are high"
          description: "Projected daily cost is ${{ $value | humanize }}"
```

### 2.4 Info Alerts (P3)

**File:** `monitoring/prometheus/rules/info_alerts.yml`

```yaml
groups:
  - name: info_alerts
    interval: 5m
    rules:
      # Container restarted
      - alert: ContainerRestarted
        expr: increase(kube_pod_container_status_restarts_total[1h]) > 0
        labels:
          severity: info
          category: infrastructure
        annotations:
          summary: "Container {{ $labels.container }} restarted"
          description: "Container has restarted {{ $value }} times in the last hour"
      
      # New agent version deployed
      - alert: AgentVersionChanged
        expr: changes(hgr_agent_version[1h]) > 0
        labels:
          severity: info
          category: deployment
        annotations:
          summary: "Agent {{ $labels.agent_id }} version changed"
          description: "Agent updated to version {{ $labels.version }}"
      
      # High mission completion rate
      - alert: HighMissionCompletionRate
        expr: rate(hgr_mission_status{status="completed"}[1h]) > 10
        labels:
          severity: info
          category: operations
        annotations:
          summary: "High mission completion rate"
          description: "Completing {{ $value }} missions per second"
```

---

## 3. NOTIFICATION CHANNELS

### 3.1 Slack Integration

**Setup script:**

```bash
#!/bin/bash
# Setup Slack webhooks

echo "Setting up Slack integration..."

# Create Slack app at https://api.slack.com/apps
# Enable Incoming Webhooks
# Add webhooks for each channel

# Store webhook URLs in environment
cat >> .env << EOF
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
EOF

echo "✓ Slack configured"
```

### 3.2 PagerDuty Integration

**Setup script:**

```bash
#!/bin/bash
# Setup PagerDuty integration

echo "Setting up PagerDuty integration..."

# Create PagerDuty service at https://pagerduty.com
# Get integration key

# Store keys in environment
cat >> .env << EOF
PAGERDUTY_SERVICE_KEY_CRITICAL=your-critical-service-key
PAGERDUTY_SERVICE_KEY_ESCALATION=your-escalation-service-key
EOF

echo "✓ PagerDuty configured"
```

### 3.3 Email Configuration

**Setup script:**

```bash
#!/bin/bash
# Setup email notifications

echo "Setting up email notifications..."

# For Gmail, create app password at:
# https://myaccount.google.com/apppasswords

cat >> .env << EOF
SMTP_USER=alerts@holygrail.ai
SMTP_PASSWORD=your-app-password
EOF

echo "✓ Email configured"
```

---

## 4. ESCALATION POLICIES

### 4.1 PagerDuty Escalation Policy

**Configuration:**

```yaml
# PagerDuty escalation policy
name: "Holy Grail Refinery Critical Alerts"

escalation_rules:
  - escalation_delay_in_minutes: 5
    targets:
      - type: user
        id: PRIMARY_ON_CALL
  
  - escalation_delay_in_minutes: 10
    targets:
      - type: user
        id: SECONDARY_ON_CALL
  
  - escalation_delay_in_minutes: 15
    targets:
      - type: schedule
        id: ENGINEERING_MANAGER_SCHEDULE
  
  - escalation_delay_in_minutes: 30
    targets:
      - type: user
        id: CTO

repeat:
  enabled: true
  repeat_delay_in_minutes: 60
```

### 4.2 Alert Escalation Script

**File:** `scripts/escalate_alert.sh`

```bash
#!/bin/bash
# Escalate unacknowledged critical alerts

set -e

ALERTMANAGER_URL="http://localhost:9093"
ESCALATION_DELAY_MINUTES=15

echo "Checking for unacknowledged critical alerts..."

# Get firing critical alerts
CRITICAL_ALERTS=$(curl -s "$ALERTMANAGER_URL/api/v2/alerts?filter=severity=critical&filter=alertstate=active" | \
    jq -r '.[] | select(.status.state == "active") | .fingerprint')

if [ -z "$CRITICAL_ALERTS" ]; then
    echo "No critical alerts to escalate"
    exit 0
fi

# Check each alert's age
for fingerprint in $CRITICAL_ALERTS; do
    ALERT_START=$(curl -s "$ALERTMANAGER_URL/api/v2/alerts?filter=fingerprint=$fingerprint" | \
        jq -r '.[0].startsAt')
    
    START_EPOCH=$(date -d "$ALERT_START" +%s)
    NOW_EPOCH=$(date +%s)
    AGE_MINUTES=$(( (NOW_EPOCH - START_EPOCH) / 60 ))
    
    if [ $AGE_MINUTES -gt $ESCALATION_DELAY_MINUTES ]; then
        echo "Escalating alert: $fingerprint (age: ${AGE_MINUTES}m)"
        
        # Trigger escalation webhook
        curl -X POST "$ALERTMANAGER_URL/api/v2/alerts" \
            -H "Content-Type: application/json" \
            -d "{
                \"labels\": {
                    \"alertname\": \"EscalatedAlert\",
                    \"severity\": \"critical\",
                    \"original_fingerprint\": \"$fingerprint\"
                },
                \"annotations\": {
                    \"summary\": \"ESCALATED: Unacknowledged critical alert\",
                    \"description\": \"Alert has been active for ${AGE_MINUTES} minutes without acknowledgment\"
                }
            }"
    fi
done

echo "✓ Escalation check complete"
```

---

## 5. ALERT ROUTING LOGIC

### 5.1 Routing Decision Tree

```
Alert Triggered
│
├─ severity = critical
│  ├─ PagerDuty (immediate page)
│  ├─ Slack #alerts-high (immediate)
│  └─ Email (immediate)
│
├─ severity = high
│  ├─ Slack #alerts-high (immediate)
│  └─ Email (immediate)
│
├─ severity = warning
│  ├─ Slack #alerts-warnings (5min delay)
│  └─ Email (4hr batch)
│
└─ severity = info
   └─ Email (24hr digest)
```

### 5.2 Alert Grouping Strategy

```yaml
# Group by these labels to reduce noise
group_by:
  - alertname
  - cluster
  - service
  - pod

# Example: Multiple agents down in same pod
# Instead of 6 separate alerts:
#   AgentDown (AGENT-PY-001)
#   AgentDown (AGENT-JS-001)
#   AgentDown (AGENT-RUBY-001)
#   ...
# Send single grouped alert:
#   AgentDown (Pod A): 6 agents affected
```

---

## 6. ALERT TEMPLATES

### 6.1 Slack Template

**File:** `alerting/alertmanager/templates/slack.tmpl`

```go
{{ define "slack.default.title" }}
[{{ .Status | toUpper }}{{ if eq .Status "firing" }}:{{ .Alerts.Firing | len }}{{ end }}] {{ .GroupLabels.SortedPairs.Values | join " " }}
{{ end }}

{{ define "slack.default.text" }}
{{ range .Alerts }}
*Alert:* {{ .Labels.alertname }}
*Severity:* {{ .Labels.severity }}
*Summary:* {{ .Annotations.summary }}
*Description:* {{ .Annotations.description }}
{{ if .Labels.pod }}*Pod:* {{ .Labels.pod }}{{ end }}
{{ if .Labels.agent_id }}*Agent:* {{ .Labels.agent_id }}{{ end }}
*Runbook:* {{ .Annotations.runbook_url }}
*Started:* {{ .StartsAt.Format "2006-01-02 15:04:05 MST" }}
{{ if .EndsAt }}*Ended:* {{ .EndsAt.Format "2006-01-02 15:04:05 MST" }}{{ end }}
---
{{ end }}
{{ end }}

{{ define "slack.agents.text" }}
{{ if eq .Status "firing" }}
🚨 *Agent Alert Firing*
{{ range .Alerts }}
• *{{ .Labels.agent_id }}* in Pod {{ .Labels.pod }}
  {{ .Annotations.summary }}
  _{{ .Annotations.description }}_
{{ end }}
{{ else }}
✅ *Agent Alert Resolved*
{{ range .Alerts }}
• *{{ .Labels.agent_id }}* in Pod {{ .Labels.pod }} is now healthy
{{ end }}
{{ end }}
{{ end }}
```

### 6.2 Email Template

**File:** `alerting/alertmanager/templates/email.tmpl`

```html
{{ define "email.default.html" }}
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; }
        .alert { border: 1px solid #ddd; padding: 15px; margin: 10px 0; }
        .critical { background-color: #ffebee; border-color: #f44336; }
        .high { background-color: #fff3e0; border-color: #ff9800; }
        .warning { background-color: #fff9c4; border-color: #fdd835; }
        .info { background-color: #e3f2fd; border-color: #2196f3; }
        .resolved { background-color: #e8f5e9; border-color: #4caf50; }
        h2 { margin-top: 0; }
        .metadata { color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <h1>Holy Grail Refinery - Alert Notification</h1>
    
    {{ if eq .Status "firing" }}
        <p><strong>Status:</strong> 🚨 FIRING ({{ .Alerts.Firing | len }} alerts)</p>
    {{ else }}
        <p><strong>Status:</strong> ✅ RESOLVED</p>
    {{ end }}
    
    {{ range .Alerts }}
    <div class="alert {{ .Labels.severity }}{{ if eq .Status "resolved" }} resolved{{ end }}">
        <h2>{{ .Labels.alertname }}</h2>
        
        <p><strong>Severity:</strong> {{ .Labels.severity | toUpper }}</p>
        <p><strong>Summary:</strong> {{ .Annotations.summary }}</p>
        <p><strong>Description:</strong> {{ .Annotations.description }}</p>
        
        {{ if .Labels.pod }}
        <p><strong>Pod:</strong> {{ .Labels.pod }}</p>
        {{ end }}
        
        {{ if .Labels.agent_id }}
        <p><strong>Agent:</strong> {{ .Labels.agent_id }}</p>
        {{ end }}
        
        <p><strong>Started:</strong> {{ .StartsAt.Format "2006-01-02 15:04:05 MST" }}</p>
        {{ if .EndsAt }}
        <p><strong>Ended:</strong> {{ .EndsAt.Format "2006-01-02 15:04:05 MST" }}</p>
        <p><strong>Duration:</strong> {{ .EndsAt.Sub .StartsAt }}</p>
        {{ end }}
        
        <p><a href="{{ .GeneratorURL }}">View in Prometheus</a> | 
           <a href="{{ .Annotations.runbook_url }}">Runbook</a></p>
        
        <div class="metadata">
            <p>Fingerprint: {{ .Fingerprint }}</p>
        </div>
    </div>
    {{ end }}
    
    <p><a href="http://localhost:9093">View in AlertManager</a></p>
</body>
</html>
{{ end }}

{{ define "email.digest.html" }}
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h1>Daily Alert Digest - {{ now.Format "2006-01-02" }}</h1>
    
    <h2>Summary</h2>
    <ul>
        <li>Total alerts: {{ .Alerts | len }}</li>
        <li>Critical: {{ .Alerts | len "severity" "critical" }}</li>
        <li>High: {{ .Alerts | len "severity" "high" }}</li>
        <li>Warning: {{ .Alerts | len "severity" "warning" }}</li>
        <li>Info: {{ .Alerts | len "severity" "info" }}</li>
    </ul>
    
    <h2>Alert Details</h2>
    <table>
        <thead>
            <tr>
                <th>Time</th>
                <th>Alert</th>
                <th>Severity</th>
                <th>Summary</th>
            </tr>
        </thead>
        <tbody>
            {{ range .Alerts }}
            <tr>
                <td>{{ .StartsAt.Format "15:04:05" }}</td>
                <td>{{ .Labels.alertname }}</td>
                <td>{{ .Labels.severity }}</td>
                <td>{{ .Annotations.summary }}</td>
            </tr>
            {{ end }}
        </tbody>
    </table>
</body>
</html>
{{ end }}
```

---

## 7. SILENCE & MAINTENANCE WINDOWS

### 7.1 Create Silence

**Script:** `scripts/create_silence.sh`

```bash
#!/bin/bash
# Create alert silence for maintenance window

set -e

ALERTMANAGER_URL="http://localhost:9093"

# Parse arguments
DURATION_HOURS=${1:-2}
COMMENT=${2:-"Scheduled maintenance"}

# Calculate end time
END_TIME=$(date -u -d "+${DURATION_HOURS} hours" --rfc-3339=seconds | sed 's/ /T/')

# Create silence
curl -X POST "$ALERTMANAGER_URL/api/v2/silences" \
    -H "Content-Type: application/json" \
    -d "{
        \"matchers\": [
            {
                \"name\": \"alertname\",
                \"value\": \".*\",
                \"isRegex\": true
            }
        ],
        \"startsAt\": \"$(date -u --rfc-3339=seconds | sed 's/ /T/')\",
        \"endsAt\": \"$END_TIME\",
        \"createdBy\": \"$(whoami)\",
        \"comment\": \"$COMMENT\"
    }"

echo "✓ Silence created for ${DURATION_HOURS} hours"
```

### 7.2 List Active Silences

**Script:** `scripts/list_silences.sh`

```bash
#!/bin/bash
# List all active silences

ALERTMANAGER_URL="http://localhost:9093"

echo "Active silences:"
curl -s "$ALERTMANAGER_URL/api/v2/silences" | \
    jq -r '.[] | select(.status.state == "active") | 
        "ID: \(.id)\nCreated by: \(.createdBy)\nComment: \(.comment)\nExpires: \(.endsAt)\n---"'
```

### 7.3 Delete Silence

**Script:** `scripts/delete_silence.sh`

```bash
#!/bin/bash
# Delete a silence by ID

ALERTMANAGER_URL="http://localhost:9093"
SILENCE_ID=$1

if [ -z "$SILENCE_ID" ]; then
    echo "Usage: $0 <silence_id>"
    exit 1
fi

curl -X DELETE "$ALERTMANAGER_URL/api/v2/silence/$SILENCE_ID"

echo "✓ Silence $SILENCE_ID deleted"
```

---

## 8. AUTO-REMEDIATION WORKFLOWS

### 8.1 Webhook Receiver for Auto-Remediation

**File:** `alerting/webhook_receiver.py`

```python
"""
Webhook receiver for alert auto-remediation
"""

from fastapi import FastAPI, Request
import subprocess
import logging

app = FastAPI()
logger = logging.getLogger(__name__)

@app.post("/webhook/alertmanager")
async def handle_alert(request: Request):
    """
    Receive alerts from AlertManager and trigger remediation
    """
    payload = await request.json()
    
    for alert in payload.get('alerts', []):
        alertname = alert['labels'].get('alertname')
        status = alert['status']
        
        if status == 'firing':
            logger.info(f"Received alert: {alertname}")
            
            # Dispatch to remediation handler
            if alertname == 'DiskAlmostFull':
                cleanup_disk()
            elif alertname == 'AgentDown':
                restart_agent(alert['labels'].get('agent_id'))
            elif alertname == 'HighMemoryUsage':
                restart_high_memory_containers()
    
    return {"status": "ok"}

def cleanup_disk():
    """Clean up disk space automatically"""
    logger.info("Running disk cleanup...")
    subprocess.run(['/scripts/cleanup_disk.sh'])

def restart_agent(agent_id: str):
    """Restart a specific agent"""
    logger.info(f"Restarting agent: {agent_id}")
    subprocess.run(['docker', 'restart', f'hgr-{agent_id.lower()}'])

def restart_high_memory_containers():
    """Restart containers using excessive memory"""
    logger.info("Restarting high memory containers...")
    subprocess.run(['/scripts/restart_high_memory.sh'])
```

### 8.2 Disk Cleanup Script

**File:** `scripts/cleanup_disk.sh`

```bash
#!/bin/bash
# Automatic disk cleanup

set -e

echo "Starting disk cleanup..."

# Clean Docker
echo "1. Cleaning Docker resources..."
docker system prune -af --volumes

# Clean old logs
echo "2. Cleaning old logs..."
find /var/log -name "*.log" -mtime +30 -delete

# Clean old Loki chunks
echo "3. Cleaning old Loki chunks..."
find /loki/chunks -mtime +90 -delete

# Clean temp files
echo "4. Cleaning temp files..."
find /tmp -mtime +7 -delete

echo "✓ Disk cleanup complete"
df -h /
```

---

## 9. ALERT TESTING & VALIDATION

### 9.1 Test Alert Generation

**Script:** `scripts/test_alert.sh`

```bash
#!/bin/bash
# Generate test alerts

ALERTMANAGER_URL="http://localhost:9093"

# Send test critical alert
curl -X POST "$ALERTMANAGER_URL/api/v2/alerts" \
    -H "Content-Type: application/json" \
    -d '[
        {
            "labels": {
                "alertname": "TestCriticalAlert",
                "severity": "critical",
                "category": "test"
            },
            "annotations": {
                "summary": "This is a test critical alert",
                "description": "Testing alert routing and notifications"
            },
            "startsAt": "'"$(date -u --rfc-3339=seconds)"'",
            "endsAt": "'"$(date -u -d '+5 minutes' --rfc-3339=seconds)"'"
        }
    ]'

echo "✓ Test alert sent"
```

### 9.2 Alert Validation Checklist

```yaml
validation_checklist:
  - name: "Critical Alert Routing"
    steps:
      - Generate test critical alert
      - Verify PagerDuty page received within 30s
      - Verify Slack notification in #alerts-high
      - Verify email received
    
  - name: "Alert Grouping"
    steps:
      - Generate 5 similar alerts
      - Verify single grouped notification sent
      - Verify all 5 alerts visible in group
    
  - name: "Alert Resolution"
    steps:
      - Generate test alert
      - Send resolution
      - Verify resolved notification sent
    
  - name: "Silence Functionality"
    steps:
      - Create silence
      - Generate test alert
      - Verify alert is silenced
      - Delete silence
```

---

## 10. ON-CALL PROCEDURES

### 10.1 On-Call Rotation

**PagerDuty Schedule:**

```yaml
schedule:
  name: "Holy Grail Refinery On-Call"
  timezone: "America/Los_Angeles"
  
  layers:
    - name: "Primary"
      rotation_virtual_start: "2026-01-01T00:00:00"
      rotation_turn_length_seconds: 604800  # 1 week
      users:
        - user1@holygrail.ai
        - user2@holygrail.ai
        - user3@holygrail.ai
    
    - name: "Secondary"
      rotation_virtual_start: "2026-01-01T00:00:00"
      rotation_turn_length_seconds: 604800
      users:
        - user4@holygrail.ai
        - user5@holygrail.ai
        - user6@holygrail.ai
```

### 10.2 On-Call Runbook

**Critical Alert Response:**

1. **Acknowledge within 5 minutes**
2. **Assess severity** - Is system down? Data at risk?
3. **Check runbook** - Follow documented procedures
4. **Investigate logs** - Use Grafana/Loki to find root cause
5. **Apply fix** - Use auto-remediation or manual intervention
6. **Monitor recovery** - Ensure system stabilizes
7. **Document** - Update incident log
8. **Post-mortem** - Schedule if P0/P1

### 10.3 Escalation Contacts

```yaml
escalation_chain:
  - level: 1
    role: On-Call Engineer
    response_time: 5 minutes
    contact: PagerDuty primary
  
  - level: 2
    role: Secondary On-Call
    response_time: 10 minutes
    contact: PagerDuty secondary
  
  - level: 3
    role: Engineering Manager
    response_time: 15 minutes
    contact: manager@holygrail.ai
  
  - level: 4
    role: CTO
    response_time: 30 minutes
    contact: cto@holygrail.ai
```

---

## DOCUMENT METADATA

**Document ID:** 39  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Operations & Deployment  
**Owner:** SRE Lead  
**Dependencies:** Documents 25 (Monitoring), 37 (Dashboards), 38 (Logging)  
**Next Document:** 40 (Disaster Recovery Testing Procedures)

---

*End of Alerting & Notification System*
