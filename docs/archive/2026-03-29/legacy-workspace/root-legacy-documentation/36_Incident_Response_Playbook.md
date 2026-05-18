# DOCUMENT 36: INCIDENT RESPONSE PLAYBOOK

Document version: 2026.03.29
Last updated: 2026-03-29
Status: Archived Legacy
## Holy Grail Refinery - Operations & Deployment

**Document ID:** 36  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Operations & Deployment  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document provides **comprehensive incident response procedures** for the Holy Grail Refinery system. It defines incident classification, response protocols, escalation paths, communication procedures, and post-incident analysis to minimize downtime and ensure rapid recovery.

**Incident Response Philosophy:**
- **Rapid Detection:** Automated monitoring with < 1 minute detection
- **Clear Ownership:** Defined roles and responsibilities
- **Structured Response:** Repeatable playbooks for common incidents
- **Continuous Learning:** Post-mortem analysis and improvement

**Response Time Targets:**
- 🚨 **P0 (Critical):** 5-minute response, 30-minute resolution target
- ⚠️ **P1 (High):** 15-minute response, 2-hour resolution target
- 📋 **P2 (Medium):** 1-hour response, 8-hour resolution target
- 📝 **P3 (Low):** 4-hour response, 24-hour resolution target

---

## TABLE OF CONTENTS

1. [Incident Classification](#1-incident-classification)
2. [Response Team Structure](#2-response-team-structure)
3. [Detection & Alerting](#3-detection--alerting)
4. [Response Procedures](#4-response-procedures)
5. [Common Incident Playbooks](#5-common-incident-playbooks)
6. [Communication Protocols](#6-communication-protocols)
7. [Escalation Paths](#7-escalation-paths)
8. [Post-Incident Review](#8-post-incident-review)
9. [Runbook Library](#9-runbook-library)
10. [On-Call Guide](#10-on-call-guide)

---

## 1. INCIDENT CLASSIFICATION

### 1.1 Severity Definitions

| Severity | Impact | Response Time | Resolution Target | Examples |
|----------|--------|---------------|-------------------|----------|
| **P0 - Critical** | Complete system outage | 5 minutes | 30 minutes | All agents down, database unreachable |
| **P1 - High** | Major functionality impaired | 15 minutes | 2 hours | Single pod failure, high error rate |
| **P2 - Medium** | Degraded performance | 1 hour | 8 hours | Slow queries, memory pressure |
| **P3 - Low** | Minor issues | 4 hours | 24 hours | Non-critical errors, cosmetic issues |

### 1.2 Classification Decision Tree

```
Start: Incident Detected
  │
  ├─> All agents down? ──YES──> P0 (Critical)
  │   
  ├─> Database unavailable? ──YES──> P0 (Critical)
  │
  ├─> >1 pod completely down? ──YES──> P1 (High)
  │
  ├─> API error rate >5%? ──YES──> P1 (High)
  │
  ├─> Single agent down? ──YES──> P2 (Medium)
  │
  ├─> Performance degraded? ──YES──> P2 (Medium)
  │
  └─> Minor anomaly? ──YES──> P3 (Low)
```

---

## 2. RESPONSE TEAM STRUCTURE

### 2.1 Roles & Responsibilities

**Incident Commander (IC)**
- Overall incident coordination
- Decision-making authority
- Stakeholder communication
- Resource allocation

**Operations Lead**
- Technical troubleshooting
- Executes remediation steps
- Coordinates with engineers
- Implements fixes

**Communications Lead**
- Internal updates
- External communications
- Status page updates
- Stakeholder notifications

**Subject Matter Expert (SME)**
- Domain-specific expertise
- Technical guidance
- Root cause analysis
- Solution design

### 2.2 On-Call Rotation

**File:** `docs/oncall_schedule.md`

```markdown
# On-Call Schedule

## Primary On-Call
- **Week 1-2:** Engineer A
- **Week 3-4:** Engineer B
- **Week 5-6:** Engineer C

## Secondary On-Call
- **Week 1-2:** Engineer D
- **Week 3-4:** Engineer E
- **Week 5-6:** Engineer F

## Escalation Contacts
- **Manager:** [Phone]
- **CTO:** [Phone]
- **CEO:** [Phone]

## On-Call Phone Numbers
- Primary: +1-XXX-XXX-XXXX
- Secondary: +1-XXX-XXX-XXXX
- PagerDuty: incidents@hgr.pagerduty.com
```

---

## 3. DETECTION & ALERTING

### 3.1 Alert Routing

**File:** `monitoring/alert_routes.yml`

```yaml
# Alert routing configuration

routes:
  # P0 Alerts → Page immediately
  - match:
      severity: critical
    receiver: pagerduty_critical
    group_wait: 10s
    group_interval: 5m
    repeat_interval: 5m
  
  # P1 Alerts → Page during business hours, email off-hours
  - match:
      severity: high
    receiver: pagerduty_high
    group_wait: 30s
    group_interval: 10m
    repeat_interval: 30m
  
  # P2/P3 Alerts → Email only
  - match_re:
      severity: warning|info
    receiver: email_ops
    group_wait: 5m
    group_interval: 30m
    repeat_interval: 4h

receivers:
  - name: pagerduty_critical
    pagerduty_configs:
      - service_key: ${PAGERDUTY_CRITICAL_KEY}
        severity: critical
  
  - name: pagerduty_high
    pagerduty_configs:
      - service_key: ${PAGERDUTY_HIGH_KEY}
        severity: high
  
  - name: email_ops
    email_configs:
      - to: ops-team@company.com
        from: alerts@hgr.local
```

### 3.2 Alert Response Checklist

```
☐ Acknowledge alert within SLA
☐ Assess severity and impact
☐ Declare incident if necessary
☐ Assemble response team
☐ Begin investigation
☐ Communicate status
☐ Implement mitigation
☐ Verify resolution
☐ Update stakeholders
☐ Schedule post-mortem
```

---

## 4. RESPONSE PROCEDURES

### 4.1 Incident Declaration

**File:** `scripts/incident/declare_incident.sh`

```bash
#!/bin/bash
# Declare an incident

set -e

SEVERITY=$1
DESCRIPTION=$2

if [ -z "$SEVERITY" ] || [ -z "$DESCRIPTION" ]; then
    echo "Usage: $0 <P0|P1|P2|P3> <description>"
    exit 1
fi

INCIDENT_ID="INC-$(date +%Y%m%d-%H%M%S)"

echo "Declaring Incident: $INCIDENT_ID"
echo "Severity: $SEVERITY"
echo "Description: $DESCRIPTION"

# Create incident record
cat > incidents/${INCIDENT_ID}.json <<EOF
{
  "incident_id": "$INCIDENT_ID",
  "severity": "$SEVERITY",
  "description": "$DESCRIPTION",
  "declared_at": "$(date -Iseconds)",
  "declared_by": "$(whoami)",
  "status": "investigating",
  "timeline": [
    {
      "timestamp": "$(date -Iseconds)",
      "event": "Incident declared",
      "actor": "$(whoami)"
    }
  ]
}
EOF

# Send notifications
case $SEVERITY in
    P0)
        # Page on-call immediately
        curl -X POST https://events.pagerduty.com/v2/enqueue \
            -H "Content-Type: application/json" \
            -d "{
                \"routing_key\": \"$PAGERDUTY_KEY\",
                \"event_action\": \"trigger\",
                \"payload\": {
                    \"summary\": \"P0: $DESCRIPTION\",
                    \"severity\": \"critical\",
                    \"source\": \"HGR System\"
                }
            }"
        
        # Post to Slack
        curl -X POST $SLACK_WEBHOOK \
            -H "Content-Type: application/json" \
            -d "{
                \"text\": \"🚨 *P0 INCIDENT DECLARED* 🚨\",
                \"attachments\": [{
                    \"color\": \"danger\",
                    \"fields\": [
                        {\"title\": \"ID\", \"value\": \"$INCIDENT_ID\", \"short\": true},
                        {\"title\": \"Severity\", \"value\": \"$SEVERITY\", \"short\": true},
                        {\"title\": \"Description\", \"value\": \"$DESCRIPTION\"}
                    ]
                }]
            }"
        ;;
    
    P1)
        # Email + Slack
        echo "P1: $DESCRIPTION" | mail -s "Incident $INCIDENT_ID" ops-team@company.com
        ;;
esac

echo "✓ Incident declared: $INCIDENT_ID"
echo "Response team should assemble immediately"
```

### 4.2 Incident Response Workflow

```
1. DETECT
   - Alert fired or issue reported
   - On-call engineer paged
   
2. ASSESS
   - Determine severity
   - Identify impact scope
   - Declare incident if necessary
   
3. ASSEMBLE
   - Notify response team
   - Assign roles (IC, Ops Lead, Comms)
   - Start incident channel
   
4. INVESTIGATE
   - Check monitoring dashboards
   - Review logs
   - Reproduce issue
   - Identify root cause
   
5. MITIGATE
   - Implement temporary fix
   - Restore service if possible
   - Monitor for stability
   
6. RESOLVE
   - Implement permanent fix
   - Verify resolution
   - Close incident
   
7. LEARN
   - Schedule post-mortem
   - Document lessons
   - Implement improvements
```

---

## 5. COMMON INCIDENT PLAYBOOKS

### 5.1 P0: Complete System Outage

**Playbook:** `playbooks/P0_system_outage.md`

```markdown
# P0: Complete System Outage

## Symptoms
- All API requests failing
- Zero agents responding
- Health checks failing

## Initial Response (First 5 minutes)
1. Declare P0 incident
2. Page primary and secondary on-call
3. Check infrastructure status:
   ```bash
   docker ps
   systemctl status docker
   ```

## Investigation Steps
1. Check Docker daemon:
   ```bash
   systemctl status docker
   journalctl -u docker -n 50
   ```

2. Check system resources:
   ```bash
   free -h
   df -h
   top -n 1
   ```

3. Check network connectivity:
   ```bash
   ping 8.8.8.8
   curl http://localhost:8000/health
   ```

## Mitigation Options

### Option 1: Docker Daemon Restart
```bash
sudo systemctl restart docker
sleep 30
docker-compose up -d
```

### Option 2: System Reboot (Last Resort)
```bash
# After approval from IC
sudo reboot
# Wait 2 minutes, then:
ssh user@host
cd /opt/hgr
docker-compose up -d
```

### Option 3: Restore from Backup
```bash
./scripts/recovery/full_restore.sh /opt/hgr/backups/latest.tar.gz
```

## Verification
1. Check all containers running:
   ```bash
   docker ps | grep hgr- | wc -l
   # Should be 40
   ```

2. Check API health:
   ```bash
   curl http://localhost:8000/health
   ```

3. Run smoke tests:
   ```bash
   ./scripts/smoke_test.sh
   ```

## Communication Template
```
STATUS UPDATE: P0 Incident - Complete System Outage

Current Status: [Investigating/Mitigating/Resolved]
Impact: All HGR services unavailable
ETA to Resolution: [Time estimate]
Root Cause: [Brief description if known]
Next Update: [Time]
```
```

### 5.2 P1: Pod Failure

**Playbook:** `playbooks/P1_pod_failure.md`

```markdown
# P1: Pod Failure

## Symptoms
- All agents in a pod (e.g., Pod A) not responding
- Pod-specific errors in logs
- Missions failing for specific languages

## Initial Response
1. Identify affected pod
2. Check pod manager status
3. Check specialist agents status

## Investigation
```bash
# Check pod manager
docker logs hgr-manager-pod-a-001 --tail 100

# Check all agents in pod
for AGENT in hgr-agent-py-001 hgr-agent-js-001 hgr-agent-ruby-001 hgr-agent-php-001; do
    echo "=== $AGENT ==="
    docker inspect $AGENT | jq '.[0].State'
done
```

## Mitigation
```bash
# Restart entire pod
docker-compose restart \
    manager-pod-a-001 \
    agent-py-001 \
    agent-js-001 \
    agent-ruby-001 \
    agent-php-001

# Verify health
sleep 30
./scripts/check_pod_health.sh A
```

## If Restart Fails
```bash
# Stop pod
docker-compose stop \
    manager-pod-a-001 \
    agent-py-001 \
    agent-js-001 \
    agent-ruby-001 \
    agent-php-001

# Check for resource constraints
docker system df
df -h

# Clear logs if disk full
./scripts/maintenance/rotate_logs.sh

# Start pod
docker-compose up -d \
    manager-pod-a-001 \
    agent-py-001 \
    agent-js-001 \
    agent-ruby-001 \
    agent-php-001
```
```

### 5.3 P1: Database Connection Failure

**Playbook:** `playbooks/P1_database_failure.md`

```markdown
# P1: Database Connection Failure

## Symptoms
- Agents reporting database connection errors
- High rate of database connection timeouts
- Connection pool exhausted alerts

## Investigation
```bash
# Check PostgreSQL status
docker exec hgr-postgres pg_isready -U hgr_admin

# Check active connections
docker exec hgr-postgres psql -U hgr_admin -c \
    "SELECT count(*) FROM pg_stat_activity;"

# Check connection pool
docker exec hgr-postgres psql -U hgr_admin -c \
    "SELECT * FROM pg_stat_database;"
```

## Common Causes & Solutions

### Cause 1: Connection Pool Exhausted
```sql
-- Check max connections
SHOW max_connections;

-- Check current connections by database
SELECT datname, count(*) 
FROM pg_stat_activity 
GROUP BY datname;

-- Kill idle connections
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE state = 'idle'
AND state_change < NOW() - INTERVAL '10 minutes';
```

### Cause 2: Long-Running Queries
```sql
-- Find long-running queries
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes';

-- Kill problematic query
SELECT pg_terminate_backend(pid);
```

### Cause 3: Database Disk Full
```bash
# Check disk usage
docker exec hgr-postgres df -h

# Clear old WAL files if needed
docker exec hgr-postgres pg_archivecleanup /var/lib/postgresql/data/pg_wal 000000010000000000000001
```

## Mitigation
```bash
# Restart PostgreSQL if necessary
docker restart hgr-postgres

# Wait for ready
sleep 10
docker exec hgr-postgres pg_isready -U hgr_admin

# Restart affected agents
docker-compose restart $(docker ps --filter "name=hgr-agent-" --format "{{.Names}}")
```
```

---

## 6. COMMUNICATION PROTOCOLS

### 6.1 Status Updates

**Update Frequency by Severity:**
- **P0:** Every 15 minutes
- **P1:** Every 30 minutes
- **P2:** Every 2 hours
- **P3:** Every 8 hours

**Update Template:**

```
INCIDENT UPDATE: [ID]
Time: [Timestamp]
Status: [Investigating/Identified/Monitoring/Resolved]

Current Situation:
[Brief description of what's happening]

Impact:
[Who/what is affected]

Actions Taken:
[What we've done so far]

Next Steps:
[What we're doing next]

ETA to Resolution:
[Best estimate]

Next Update: [Time]
```

### 6.2 Internal Communication Channels

**Slack Channels:**
- `#incidents` - All incident notifications
- `#incidents-critical` - P0/P1 incidents only
- `#ops-team` - Operations team coordination
- `#engineering-oncall` - On-call engineers

**Email Lists:**
- `incidents@company.com` - Incident notifications
- `ops-team@company.com` - Operations team
- `engineering@company.com` - All engineering

---

## 7. ESCALATION PATHS

### 7.1 Escalation Triggers

**Escalate to Manager when:**
- Incident severity P0 or P1
- No progress after 1 hour
- Additional resources needed
- Customer impact significant

**Escalate to CTO when:**
- Prolonged P0 outage (>1 hour)
- Data loss risk
- Security incident
- Public-facing impact

**Escalate to CEO when:**
- Extended outage (>4 hours)
- Major data loss
- Severe security breach
- Regulatory implications

### 7.2 Escalation Script

**File:** `scripts/incident/escalate.sh`

```bash
#!/bin/bash
# Escalate incident to next level

INCIDENT_ID=$1
ESCALATION_LEVEL=$2  # manager, cto, ceo

if [ -z "$INCIDENT_ID" ] || [ -z "$ESCALATION_LEVEL" ]; then
    echo "Usage: $0 <incident_id> <manager|cto|ceo>"
    exit 1
fi

# Read incident details
INCIDENT=$(cat incidents/${INCIDENT_ID}.json)
SEVERITY=$(echo $INCIDENT | jq -r '.severity')
DESCRIPTION=$(echo $INCIDENT | jq -r '.description')

case $ESCALATION_LEVEL in
    manager)
        PHONE="+1-XXX-XXX-XXXX"
        EMAIL="manager@company.com"
        ;;
    cto)
        PHONE="+1-XXX-XXX-XXXX"
        EMAIL="cto@company.com"
        ;;
    ceo)
        PHONE="+1-XXX-XXX-XXXX"
        EMAIL="ceo@company.com"
        ;;
esac

echo "Escalating incident $INCIDENT_ID to $ESCALATION_LEVEL"

# Send email
mail -s "ESCALATION: $INCIDENT_ID ($SEVERITY)" $EMAIL <<EOF
An incident has been escalated to your attention.

Incident ID: $INCIDENT_ID
Severity: $SEVERITY
Description: $DESCRIPTION

Please join the incident channel: #incident-$INCIDENT_ID

Dashboard: http://grafana.hgr.local/incidents/$INCIDENT_ID
EOF

# Log escalation
jq ".timeline += [{
    \"timestamp\": \"$(date -Iseconds)\",
    \"event\": \"Escalated to $ESCALATION_LEVEL\",
    \"actor\": \"$(whoami)\"
}]" incidents/${INCIDENT_ID}.json > incidents/${INCIDENT_ID}.json.tmp

mv incidents/${INCIDENT_ID}.json.tmp incidents/${INCIDENT_ID}.json

echo "✓ Escalation complete"
```

---

## 8. POST-INCIDENT REVIEW

### 8.1 Post-Mortem Template

**File:** `templates/postmortem_template.md`

```markdown
# Post-Mortem: [Incident ID]

## Incident Summary
- **Date:** [YYYY-MM-DD]
- **Duration:** [X hours Y minutes]
- **Severity:** [P0/P1/P2/P3]
- **Impact:** [Brief description]

## Timeline
| Time | Event |
|------|-------|
| 14:30 | Alert fired: High error rate |
| 14:32 | On-call engineer acknowledged |
| 14:35 | Incident declared (P1) |
| 14:40 | Root cause identified |
| 15:00 | Mitigation deployed |
| 15:15 | Service restored |
| 15:30 | Incident resolved |

## Root Cause
[Detailed explanation of what caused the incident]

## Impact
- **Users Affected:** [Number/percentage]
- **Services Affected:** [List of services]
- **Duration:** [Time]
- **Data Loss:** [None/Description]

## What Went Well
- Alert fired within 2 minutes
- Team assembled quickly
- Clear communication maintained

## What Went Wrong
- Initial investigation delayed by lack of logs
- Rollback took longer than expected
- Missing runbook for this scenario

## Action Items
| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| Add missing logs | Engineer A | 2026-02-15 | Open |
| Update runbook | Engineer B | 2026-02-10 | Open |
| Improve monitoring | Engineer C | 2026-02-20 | Open |

## Lessons Learned
1. Need better logging for database connections
2. Rollback procedure should be tested regularly
3. Runbooks must be kept up to date
```

### 8.2 Post-Mortem Meeting

**Agenda:**
1. Timeline review (5 min)
2. Root cause discussion (10 min)
3. What went well (5 min)
4. What went wrong (10 min)
5. Action items (10 min)

**Rules:**
- Blameless
- Focus on systems, not people
- Action-oriented
- Time-boxed

---

## 9. RUNBOOK LIBRARY

### 9.1 Quick Reference

| Symptom | Likely Cause | First Action |
|---------|-------------|--------------|
| All agents down | Docker daemon crash | `systemctl restart docker` |
| High CPU | Runaway process | Check `docker stats`, restart agent |
| High memory | Memory leak | Check `docker stats`, restart agent |
| Slow queries | Database issues | Check `pg_stat_activity` |
| Connection errors | Pool exhausted | Check connection count |
| Disk full | Logs or backups | Clear old logs/backups |

---

## 10. ON-CALL GUIDE

### 10.1 On-Call Checklist

**Before Your Shift:**
- [ ] Test pager/phone
- [ ] Review recent incidents
- [ ] Check system status
- [ ] Ensure laptop charged
- [ ] VPN credentials updated

**During Your Shift:**
- [ ] Acknowledge alerts within 5 min
- [ ] Keep phone nearby
- [ ] Stay within coverage area
- [ ] Document all actions
- [ ] Update incident status regularly

**After Your Shift:**
- [ ] Handoff summary to next on-call
- [ ] Document any ongoing issues
- [ ] Schedule post-mortems
- [ ] Update runbooks if needed

---

## DOCUMENT METADATA

**Document ID:** 36  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Operations & Deployment  
**Owner:** Operations Lead  
**Dependencies:** Documents 25 (Monitoring), 33 (Maintenance)  
**Next Document:** 37 (System Monitoring Dashboard Configuration)

---

*End of Incident Response Playbook*
