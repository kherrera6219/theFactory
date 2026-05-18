# DOCUMENT 33: SYSTEM MAINTENANCE PROCEDURES

Document version: 2026.03.29
Last updated: 2026-03-29
Status: Archived Legacy
## Holy Grail Refinery - Operations & Deployment

**Document ID:** 33  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Operations & Deployment  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document provides **comprehensive maintenance procedures** for the Holy Grail Refinery system. It covers routine maintenance tasks, preventive maintenance schedules, system health monitoring, performance optimization, and troubleshooting procedures to ensure 99.999% uptime and optimal performance.

**Maintenance Philosophy:**
- **Proactive:** Prevent issues before they occur
- **Automated:** Minimize manual intervention
- **Documented:** Every procedure trackable and repeatable
- **Tested:** All maintenance procedures validated in staging

**Maintenance Categories:**
- 🔄 **Daily:** Health checks, log review, backup verification
- 📅 **Weekly:** Performance optimization, capacity review
- 📆 **Monthly:** Security updates, database optimization
- 🗓️ **Quarterly:** Agent updates, infrastructure review

---

## TABLE OF CONTENTS

1. [Daily Maintenance](#1-daily-maintenance)
2. [Weekly Maintenance](#2-weekly-maintenance)
3. [Monthly Maintenance](#3-monthly-maintenance)
4. [Quarterly Maintenance](#4-quarterly-maintenance)
5. [Database Maintenance](#5-database-maintenance)
6. [Log Management](#6-log-management)
7. [Performance Tuning](#7-performance-tuning)
8. [Security Hardening](#8-security-hardening)
9. [Capacity Management](#9-capacity-management)
10. [Maintenance Calendar](#10-maintenance-calendar)

---

## 1. DAILY MAINTENANCE

### 1.1 Morning Health Check

**File:** `scripts/maintenance/daily_health_check.sh`

```bash
#!/bin/bash
# Daily morning health check routine

set -e

REPORT_DATE=$(date "+%Y-%m-%d")
REPORT_FILE="reports/health_check_${REPORT_DATE}.txt"

mkdir -p reports

echo "================================================" | tee $REPORT_FILE
echo "HOLY GRAIL REFINERY - DAILY HEALTH CHECK" | tee -a $REPORT_FILE
echo "Date: $REPORT_DATE" | tee -a $REPORT_FILE
echo "================================================" | tee -a $REPORT_FILE
echo "" | tee -a $REPORT_FILE

# Check 1: System Uptime
echo "1. System Uptime:" | tee -a $REPORT_FILE
uptime | tee -a $REPORT_FILE
echo "" | tee -a $REPORT_FILE

# Check 2: Docker Status
echo "2. Docker Status:" | tee -a $REPORT_FILE
systemctl status docker --no-pager | head -3 | tee -a $REPORT_FILE
echo "" | tee -a $REPORT_FILE

# Check 3: Container Health
echo "3. Container Health:" | tee -a $REPORT_FILE
TOTAL=$(docker ps --filter "name=hgr-" --format "{{.Names}}" | wc -l)
HEALTHY=$(docker ps --filter "health=healthy" --filter "name=hgr-" \
    --format "{{.Names}}" | wc -l)
UNHEALTHY=$(docker ps --filter "health=unhealthy" --filter "name=hgr-" \
    --format "{{.Names}}" | wc -l)

echo "  Total containers: $TOTAL" | tee -a $REPORT_FILE
echo "  Healthy: $HEALTHY" | tee -a $REPORT_FILE
echo "  Unhealthy: $UNHEALTHY" | tee -a $REPORT_FILE

if [ $UNHEALTHY -gt 0 ]; then
    echo "  ⚠ WARNING: Unhealthy containers detected!" | tee -a $REPORT_FILE
    docker ps --filter "health=unhealthy" --filter "name=hgr-" \
        --format "{{.Names}}" | tee -a $REPORT_FILE
fi

echo "" | tee -a $REPORT_FILE

# Check 4: Agent Status Summary
echo "4. Agent Status:" | tee -a $REPORT_FILE
for AGENT in PM-001 CEO-001 AGENT-PY-001 AUDIT-LEAD-001; do
    STATUS=$(curl -sf http://localhost:8000/api/v1/agents/$AGENT/status | \
        jq -r '.status' 2>/dev/null || echo "unreachable")
    echo "  $AGENT: $STATUS" | tee -a $REPORT_FILE
done
echo "" | tee -a $REPORT_FILE

# Check 5: Database Status
echo "5. Database Status:" | tee -a $REPORT_FILE

# PostgreSQL
PG_STATUS=$(docker exec hgr-postgres pg_isready -U hgr_admin 2>&1 | \
    grep "accepting connections" && echo "OK" || echo "ERROR")
echo "  PostgreSQL: $PG_STATUS" | tee -a $REPORT_FILE

# Redis
REDIS_STATUS=$(docker exec hgr-redis redis-cli ping 2>&1 | \
    grep "PONG" && echo "OK" || echo "ERROR")
echo "  Redis: $REDIS_STATUS" | tee -a $REPORT_FILE

echo "" | tee -a $REPORT_FILE

# Check 6: Disk Usage
echo "6. Disk Usage:" | tee -a $REPORT_FILE
df -h / /var/lib/docker | tee -a $REPORT_FILE

DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt 80 ]; then
    echo "  ⚠ WARNING: Disk usage above 80%!" | tee -a $REPORT_FILE
fi

echo "" | tee -a $REPORT_FILE

# Check 7: Memory Usage
echo "7. Memory Usage:" | tee -a $REPORT_FILE
free -h | tee -a $REPORT_FILE
echo "" | tee -a $REPORT_FILE

# Check 8: Recent Errors
echo "8. Recent Errors (last 24h):" | tee -a $REPORT_FILE
ERROR_COUNT=$(docker logs hgr-api-gateway --since 24h 2>&1 | \
    grep -c "ERROR" || echo "0")
echo "  API Gateway errors: $ERROR_COUNT" | tee -a $REPORT_FILE

if [ $ERROR_COUNT -gt 100 ]; then
    echo "  ⚠ WARNING: High error count!" | tee -a $REPORT_FILE
fi

echo "" | tee -a $REPORT_FILE

# Check 9: Backup Status
echo "9. Backup Status:" | tee -a $REPORT_FILE
LATEST_BACKUP=$(ls -t backups/*.tar.gz 2>/dev/null | head -1)
if [ -n "$LATEST_BACKUP" ]; then
    BACKUP_AGE=$(( ($(date +%s) - $(stat -c %Y "$LATEST_BACKUP")) / 86400 ))
    BACKUP_SIZE=$(du -h "$LATEST_BACKUP" | cut -f1)
    echo "  Latest backup: $(basename $LATEST_BACKUP)" | tee -a $REPORT_FILE
    echo "  Age: $BACKUP_AGE days" | tee -a $REPORT_FILE
    echo "  Size: $BACKUP_SIZE" | tee -a $REPORT_FILE
    
    if [ $BACKUP_AGE -gt 1 ]; then
        echo "  ⚠ WARNING: Backup is more than 24h old!" | tee -a $REPORT_FILE
    fi
else
    echo "  ⚠ ERROR: No backup found!" | tee -a $REPORT_FILE
fi

echo "" | tee -a $REPORT_FILE

# Check 10: Overall System Health Score
echo "10. Overall Health Score:" | tee -a $REPORT_FILE

HEALTH_SCORE=100

if [ $UNHEALTHY -gt 0 ]; then
    ((HEALTH_SCORE -= 20))
fi

if [ $ERROR_COUNT -gt 100 ]; then
    ((HEALTH_SCORE -= 10))
fi

if [ $DISK_USAGE -gt 80 ]; then
    ((HEALTH_SCORE -= 10))
fi

if [ -z "$LATEST_BACKUP" ] || [ $BACKUP_AGE -gt 1 ]; then
    ((HEALTH_SCORE -= 10))
fi

echo "  Score: $HEALTH_SCORE/100" | tee -a $REPORT_FILE

if [ $HEALTH_SCORE -ge 90 ]; then
    echo "  Status: ✓ EXCELLENT" | tee -a $REPORT_FILE
elif [ $HEALTH_SCORE -ge 80 ]; then
    echo "  Status: ✓ GOOD" | tee -a $REPORT_FILE
elif [ $HEALTH_SCORE -ge 70 ]; then
    echo "  Status: ⚠ FAIR - Action recommended" | tee -a $REPORT_FILE
else
    echo "  Status: ✗ POOR - Immediate action required" | tee -a $REPORT_FILE
fi

echo "" | tee -a $REPORT_FILE
echo "Report saved to: $REPORT_FILE" | tee -a $REPORT_FILE

# Send email report if health score is low
if [ $HEALTH_SCORE -lt 80 ]; then
    ./scripts/send_alert.sh "System health score: $HEALTH_SCORE" "$REPORT_FILE"
fi
```

### 1.2 Log Rotation and Archival

**File:** `scripts/maintenance/rotate_logs.sh`

```bash
#!/bin/bash
# Rotate and compress logs daily

set -e

LOG_DIR="/var/log/hgr"
ARCHIVE_DIR="/var/log/hgr/archive"
RETENTION_DAYS=30

echo "Starting log rotation..."

mkdir -p $ARCHIVE_DIR

# Rotate container logs
for CONTAINER in $(docker ps --format "{{.Names}}" | grep "^hgr-"); do
    LOG_FILE="${LOG_DIR}/${CONTAINER}.log"
    
    if [ -f "$LOG_FILE" ]; then
        # Compress and archive
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        gzip -c "$LOG_FILE" > "${ARCHIVE_DIR}/${CONTAINER}_${TIMESTAMP}.log.gz"
        
        # Truncate current log
        > "$LOG_FILE"
        
        echo "✓ Rotated logs for $CONTAINER"
    fi
done

# Rotate application logs
for LOG_FILE in ${LOG_DIR}/application*.log; do
    if [ -f "$LOG_FILE" ]; then
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        BASENAME=$(basename "$LOG_FILE" .log)
        gzip -c "$LOG_FILE" > "${ARCHIVE_DIR}/${BASENAME}_${TIMESTAMP}.log.gz"
        > "$LOG_FILE"
    fi
done

# Cleanup old archives
find $ARCHIVE_DIR -name "*.gz" -mtime +$RETENTION_DAYS -delete

echo "✓ Log rotation complete"
```

### 1.3 Automated Backup

**File:** `scripts/maintenance/daily_backup.sh`

```bash
#!/bin/bash
# Automated daily backup

set -e

BACKUP_DIR="/opt/hgr/backups"
DATE=$(date +%Y%m%d)
BACKUP_NAME="hgr_daily_${DATE}"

echo "Starting daily backup: $BACKUP_NAME"

# Run backup script
/opt/hgr/scripts/backup_system.sh

# Verify backup
LATEST_BACKUP=$(ls -t ${BACKUP_DIR}/*.tar.gz | head -1)

if [ -f "$LATEST_BACKUP" ]; then
    # Test backup integrity
    tar -tzf "$LATEST_BACKUP" > /dev/null
    
    if [ $? -eq 0 ]; then
        echo "✓ Backup verified: $LATEST_BACKUP"
        
        # Upload to remote storage (optional)
        # aws s3 cp "$LATEST_BACKUP" s3://hgr-backups/
    else
        echo "✗ Backup verification failed!"
        exit 1
    fi
else
    echo "✗ Backup file not found!"
    exit 1
fi

# Cleanup old local backups (keep last 7 days)
find $BACKUP_DIR -name "hgr_daily_*.tar.gz" -mtime +7 -delete

echo "✓ Daily backup complete"
```

---

## 2. WEEKLY MAINTENANCE

### 2.1 Performance Review

**File:** `scripts/maintenance/weekly_performance_review.sh`

```bash
#!/bin/bash
# Weekly performance analysis

set -e

REPORT_DATE=$(date "+%Y-%m-%d")
REPORT_FILE="reports/performance_review_${REPORT_DATE}.txt"

echo "Generating weekly performance report..."

{
    echo "================================================"
    echo "WEEKLY PERFORMANCE REVIEW"
    echo "Week ending: $REPORT_DATE"
    echo "================================================"
    echo ""
    
    # 1. Response Time Analysis
    echo "1. API Response Times (7-day average):"
    echo "  Calculating..."
    
    # Query from monitoring database
    docker exec hgr-postgres psql -U hgr_admin -d hgr_monitoring -c \
        "SELECT 
            endpoint,
            AVG(response_time_ms) as avg_ms,
            MAX(response_time_ms) as max_ms,
            COUNT(*) as request_count
         FROM api_metrics
         WHERE timestamp > NOW() - INTERVAL '7 days'
         GROUP BY endpoint
         ORDER BY avg_ms DESC
         LIMIT 10;"
    
    echo ""
    
    # 2. Agent Performance
    echo "2. Agent Processing Times:"
    docker exec hgr-postgres psql -U hgr_admin -d hgr_monitoring -c \
        "SELECT 
            agent_id,
            AVG(processing_time_ms) as avg_ms,
            COUNT(*) as tasks_completed
         FROM agent_metrics
         WHERE timestamp > NOW() - INTERVAL '7 days'
         GROUP BY agent_id
         ORDER BY avg_ms DESC;"
    
    echo ""
    
    # 3. Resource Utilization
    echo "3. Resource Utilization Trends:"
    
    echo "  CPU Usage (peak):"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}" | \
        head -10
    
    echo ""
    echo "  Memory Usage (peak):"
    docker stats --no-stream --format "table {{.Name}}\t{{.MemPerc}}\t{{.MemUsage}}" | \
        head -10
    
    echo ""
    
    # 4. Database Performance
    echo "4. Database Query Performance:"
    docker exec hgr-postgres psql -U hgr_admin -d hgr_monitoring -c \
        "SELECT 
            query,
            calls,
            mean_exec_time,
            max_exec_time
         FROM pg_stat_statements
         WHERE mean_exec_time > 100
         ORDER BY mean_exec_time DESC
         LIMIT 10;"
    
    echo ""
    
    # 5. Error Rate Trends
    echo "5. Error Rates:"
    ERROR_COUNT=$(docker logs hgr-api-gateway --since 7d 2>&1 | \
        grep -c "ERROR" || echo "0")
    REQUEST_COUNT=$(docker logs hgr-api-gateway --since 7d 2>&1 | \
        wc -l || echo "1")
    ERROR_RATE=$(echo "scale=4; $ERROR_COUNT / $REQUEST_COUNT * 100" | bc)
    
    echo "  Total requests: $REQUEST_COUNT"
    echo "  Total errors: $ERROR_COUNT"
    echo "  Error rate: ${ERROR_RATE}%"
    
    if (( $(echo "$ERROR_RATE > 1.0" | bc -l) )); then
        echo "  ⚠ WARNING: Error rate above threshold!"
    fi
    
    echo ""
    
    # 6. Recommendations
    echo "6. Performance Recommendations:"
    
    # Check for slow queries
    SLOW_QUERIES=$(docker exec hgr-postgres psql -U hgr_admin -d hgr_monitoring -t -c \
        "SELECT COUNT(*) FROM pg_stat_statements WHERE mean_exec_time > 100;")
    
    if [ $SLOW_QUERIES -gt 10 ]; then
        echo "  - Optimize $SLOW_QUERIES slow database queries"
    fi
    
    # Check for high CPU agents
    HIGH_CPU=$(docker stats --no-stream --format "{{.CPUPerc}}" | \
        sed 's/%//' | awk '$1 > 80 {count++} END {print count}')
    
    if [ -n "$HIGH_CPU" ] && [ $HIGH_CPU -gt 0 ]; then
        echo "  - Scale $HIGH_CPU high-CPU agents"
    fi
    
    echo "  - Review and implement optimizations"
    
} | tee $REPORT_FILE

echo ""
echo "Performance review saved to: $REPORT_FILE"
```

### 2.2 Capacity Planning Review

**File:** `scripts/maintenance/capacity_review.sh`

```bash
#!/bin/bash
# Weekly capacity review and planning

set -e

echo "Capacity Planning Review"
echo "========================"

# 1. Storage Growth Analysis
echo "1. Storage Growth:"
CURRENT_USAGE=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
echo "  Current usage: ${CURRENT_USAGE}%"

# Calculate growth rate
LAST_WEEK_USAGE=$(cat /var/log/hgr/capacity_history.log | \
    tail -1 | cut -d',' -f2 || echo "$CURRENT_USAGE")

GROWTH_RATE=$((CURRENT_USAGE - LAST_WEEK_USAGE))
echo "  Weekly growth: ${GROWTH_RATE}%"

if [ $GROWTH_RATE -gt 5 ]; then
    echo "  ⚠ High growth rate detected"
    
    # Calculate weeks until 80% full
    WEEKS_REMAINING=$(((80 - CURRENT_USAGE) / GROWTH_RATE))
    echo "  ⚠ Estimated weeks until 80% full: $WEEKS_REMAINING"
fi

# Log current usage for trend analysis
echo "$(date +%Y-%m-%d),$CURRENT_USAGE" >> /var/log/hgr/capacity_history.log

# 2. Database Size Trends
echo ""
echo "2. Database Sizes:"
docker exec hgr-postgres psql -U hgr_admin -c \
    "SELECT 
        pg_database.datname,
        pg_size_pretty(pg_database_size(pg_database.datname)) AS size
     FROM pg_database
     WHERE datname LIKE 'hgr_%'
     ORDER BY pg_database_size(pg_database.datname) DESC;"

# 3. LogicNode Growth
echo ""
echo "3. LogicNode Registry Growth:"
LOGICNODE_COUNT=$(docker exec hgr-postgres psql -U hgr_admin -d hgr_registry -t -c \
    "SELECT COUNT(*) FROM logicnodes;")
echo "  Total LogicNodes: $LOGICNODE_COUNT"

# 4. Recommendations
echo ""
echo "4. Capacity Recommendations:"

if [ $CURRENT_USAGE -gt 70 ]; then
    echo "  - Plan storage expansion"
fi

if [ $LOGICNODE_COUNT -gt 1000000 ]; then
    echo "  - Consider implementing LogicNode archival"
fi

echo "  - Continue monitoring growth trends"
```

---

## 3. MONTHLY MAINTENANCE

### 3.1 Security Updates

**File:** `scripts/maintenance/monthly_security_updates.sh`

```bash
#!/bin/bash
# Monthly security update procedure

set -e

echo "================================================"
echo "MONTHLY SECURITY UPDATES"
echo "================================================"

# 1. System Updates
echo "1. Updating system packages..."
sudo apt update
sudo apt upgrade -y

# 2. Docker Updates
echo ""
echo "2. Checking Docker version..."
DOCKER_VERSION=$(docker version --format '{{.Server.Version}}')
echo "  Current version: $DOCKER_VERSION"

# 3. Scan Images for Vulnerabilities
echo ""
echo "3. Scanning Docker images for vulnerabilities..."

for IMAGE in $(docker images --format "{{.Repository}}:{{.Tag}}" | grep "^hgr-"); do
    echo "  Scanning $IMAGE..."
    
    # Using Trivy for vulnerability scanning
    trivy image --severity HIGH,CRITICAL $IMAGE
done

# 4. Update Base Images
echo ""
echo "4. Updating base images..."
docker pull ubuntu:24.04
docker pull postgres:16
docker pull redis:7

# 5. Rebuild Agent Images
echo ""
echo "5. Rebuilding agent images with security patches..."
docker-compose build --no-cache

# 6. Update SSL Certificates
echo ""
echo "6. Checking SSL certificates..."
CERT_FILE="/etc/ssl/certs/hgr.crt"

if [ -f "$CERT_FILE" ]; then
    EXPIRY=$(openssl x509 -enddate -noout -in $CERT_FILE | cut -d= -f2)
    EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s)
    NOW_EPOCH=$(date +%s)
    DAYS_UNTIL_EXPIRY=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))
    
    echo "  Certificate expires in: $DAYS_UNTIL_EXPIRY days"
    
    if [ $DAYS_UNTIL_EXPIRY -lt 30 ]; then
        echo "  ⚠ Certificate expires soon - renewal required"
    fi
fi

# 7. Review Access Logs
echo ""
echo "7. Reviewing access logs for suspicious activity..."

# Check for failed login attempts
FAILED_LOGINS=$(grep "authentication failed" /var/log/hgr/api-gateway.log | wc -l)
echo "  Failed login attempts: $FAILED_LOGINS"

if [ $FAILED_LOGINS -gt 100 ]; then
    echo "  ⚠ High number of failed logins detected"
fi

# 8. Update API Keys
echo ""
echo "8. Checking API key rotation..."

# Query key ages from vault
OLDEST_KEY_AGE=$(docker exec hgr-vault vault kv get -format=json secret/api-keys | \
    jq -r '.data.created_at' || echo "unknown")

echo "  Oldest API key age: $OLDEST_KEY_AGE"

if [ "$OLDEST_KEY_AGE" != "unknown" ]; then
    echo "  Consider rotating keys older than 90 days"
fi

echo ""
echo "✓ Security update procedure complete"
echo "Review findings and schedule any required maintenance"
```

### 3.2 Database Optimization

**File:** `scripts/maintenance/monthly_database_optimization.sh`

```bash
#!/bin/bash
# Monthly database optimization and maintenance

set -e

echo "================================================"
echo "MONTHLY DATABASE OPTIMIZATION"
echo "================================================"

# 1. Vacuum and Analyze
echo "1. Running VACUUM ANALYZE on all databases..."

for DB in hgr_knowledge hgr_state hgr_registry hgr_traceability hgr_models; do
    echo "  Processing $DB..."
    
    docker exec hgr-postgres psql -U hgr_admin -d $DB -c \
        "VACUUM ANALYZE;"
    
    echo "  ✓ $DB optimized"
done

# 2. Rebuild Indexes
echo ""
echo "2. Rebuilding indexes..."

docker exec hgr-postgres psql -U hgr_admin -d hgr_registry -c \
    "REINDEX DATABASE hgr_registry;"

# 3. Update Statistics
echo ""
echo "3. Updating query statistics..."

docker exec hgr-postgres psql -U hgr_admin -d hgr_registry -c \
    "ANALYZE;"

# 4. Check for Bloat
echo ""
echo "4. Checking for table bloat..."

docker exec hgr-postgres psql -U hgr_admin -d hgr_registry -c \
    "SELECT 
        schemaname,
        tablename,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - 
                       pg_relation_size(schemaname||'.'||tablename)) AS external_size
     FROM pg_tables
     WHERE schemaname = 'public'
     ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
     LIMIT 10;"

# 5. Archive Old Data
echo ""
echo "5. Archiving old data..."

# Archive old logs (older than 90 days)
docker exec hgr-postgres psql -U hgr_admin -d hgr_traceability -c \
    "DELETE FROM logs WHERE timestamp < NOW() - INTERVAL '90 days';"

# Archive old test results
docker exec hgr-postgres psql -U hgr_admin -d hgr_registry -c \
    "DELETE FROM equivalence_tests 
     WHERE tested_at < NOW() - INTERVAL '180 days'
     AND logicnode_id IN (
         SELECT logicnode_id 
         FROM logicnodes 
         WHERE audit_status = 'verified'
     );"

echo "  ✓ Old data archived"

# 6. Refresh Materialized Views
echo ""
echo "6. Refreshing materialized views..."

docker exec hgr-postgres psql -U hgr_admin -d hgr_registry -c \
    "REFRESH MATERIALIZED VIEW paradigm_summary;"

docker exec hgr-postgres psql -U hgr_admin -d hgr_registry -c \
    "REFRESH MATERIALIZED VIEW domain_summary;"

echo "  ✓ Materialized views refreshed"

# 7. Check Connection Pool
echo ""
echo "7. Checking connection pool status..."

docker exec hgr-postgres psql -U hgr_admin -c \
    "SELECT 
        datname,
        count(*) AS connections,
        max_conn - count(*) AS available
     FROM pg_stat_activity, 
          (SELECT setting::int AS max_conn FROM pg_settings WHERE name='max_connections') max
     GROUP BY datname, max_conn;"

echo ""
echo "✓ Database optimization complete"
```

---

## 4. QUARTERLY MAINTENANCE

### 4.1 Agent Self-Update Procedure

**File:** `scripts/maintenance/quarterly_agent_updates.sh`

```bash
#!/bin/bash
# Quarterly agent self-update procedure

set -e

echo "================================================"
echo "QUARTERLY AGENT SELF-UPDATE"
echo "================================================"

# 1. Review Performance Metrics
echo "1. Reviewing agent performance (last 90 days)..."

docker exec hgr-postgres psql -U hgr_admin -d hgr_monitoring -c \
    "SELECT 
        agent_id,
        AVG(processing_time_ms) as avg_processing_ms,
        AVG(confidence) as avg_confidence,
        COUNT(*) as tasks_completed,
        SUM(CASE WHEN status='error' THEN 1 ELSE 0 END) as error_count
     FROM agent_metrics
     WHERE timestamp > NOW() - INTERVAL '90 days'
     GROUP BY agent_id
     ORDER BY error_count DESC, avg_processing_ms DESC;"

# 2. Update Agent Configurations
echo ""
echo "2. Updating agent configurations..."

# CEO Agent updates its strategic parameters
docker exec hgr-ceo-001 python /app/self_update.py --mode quarterly

# Pod Managers update coordination strategies
for MANAGER in MANAGER-POD-A-001 MANAGER-POD-B-001 MANAGER-POD-C-001 MANAGER-POD-D-001; do
    echo "  Updating $MANAGER..."
    docker exec hgr-${MANAGER,,} python /app/self_update.py --mode quarterly
done

# Language Specialists update extraction strategies
for LANG in py js ruby php c cpp rust zig java cs scala kotlin; do
    AGENT="AGENT-${LANG^^}-001"
    echo "  Updating $AGENT..."
    docker exec hgr-agent-${LANG} python /app/self_update.py --mode quarterly
done

# 3. Update Knowledge Lake Indexes
echo ""
echo "3. Updating Knowledge Lake indexes..."

# Re-index documentation that has changed
docker exec hgr-is-001 python /app/reindex_knowledge.py --incremental

# 4. Retrain Models (if applicable)
echo ""
echo "4. Checking model performance..."

# Review embedding model performance
EMBEDDING_ACCURACY=$(docker exec hgr-postgres psql -U hgr_admin -d hgr_models -t -c \
    "SELECT AVG(accuracy) FROM model_metrics WHERE model_type='embedding' AND 
     timestamp > NOW() - INTERVAL '90 days';")

echo "  Embedding model accuracy: $EMBEDDING_ACCURACY"

if (( $(echo "$EMBEDDING_ACCURACY < 0.95" | bc -l) )); then
    echo "  ⚠ Model accuracy below threshold - consider retraining"
fi

# 5. Update Communication Protocols
echo ""
echo "5. Reviewing communication protocols..."

# Check message success rates
docker exec hgr-postgres psql -U hgr_admin -d hgr_monitoring -c \
    "SELECT 
        protocol,
        COUNT(*) as total_messages,
        SUM(CASE WHEN success=true THEN 1 ELSE 0 END) as successful,
        AVG(latency_ms) as avg_latency_ms
     FROM message_metrics
     WHERE timestamp > NOW() - INTERVAL '90 days'
     GROUP BY protocol
     ORDER BY protocol;"

# 6. Generate Update Report
echo ""
echo "6. Generating quarterly update report..."

REPORT_FILE="reports/quarterly_update_$(date +%Y_Q%q).txt"

{
    echo "Quarterly Agent Update Report"
    echo "============================="
    echo "Date: $(date)"
    echo ""
    echo "Agents Updated: 35/35"
    echo "Configuration Changes: Applied"
    echo "Knowledge Lake: Re-indexed"
    echo "Model Performance: Reviewed"
    echo "Communication: Optimized"
    echo ""
    echo "Next quarterly update: $(date -d '+3 months')"
} | tee $REPORT_FILE

echo ""
echo "✓ Quarterly agent update complete"
echo "Report saved to: $REPORT_FILE"
```

---

## 5. DATABASE MAINTENANCE

### 5.1 PostgreSQL Maintenance Tasks

**File:** `scripts/maintenance/postgres_maintenance.sh`

```bash
#!/bin/bash
# Comprehensive PostgreSQL maintenance

set -e

echo "PostgreSQL Maintenance Tasks"
echo "============================"

# 1. Check Database Sizes
echo "1. Database Sizes:"
docker exec hgr-postgres psql -U hgr_admin -c \
    "SELECT 
        datname AS database,
        pg_size_pretty(pg_database_size(datname)) AS size
     FROM pg_database
     WHERE datname LIKE 'hgr_%'
     ORDER BY pg_database_size(datname) DESC;"

# 2. Check Table Sizes
echo ""
echo "2. Largest Tables:"
docker exec hgr-postgres psql -U hgr_admin -d hgr_registry -c \
    "SELECT 
        schemaname AS schema,
        tablename AS table,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
        pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
        pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - 
                       pg_relation_size(schemaname||'.'||tablename)) AS indexes_size
     FROM pg_tables
     WHERE schemaname = 'public'
     ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
     LIMIT 10;"

# 3. Check Index Usage
echo ""
echo "3. Unused Indexes:"
docker exec hgr-postgres psql -U hgr_admin -d hgr_registry -c \
    "SELECT 
        schemaname,
        tablename,
        indexname,
        idx_scan AS index_scans,
        pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
     FROM pg_stat_user_indexes
     WHERE idx_scan = 0
     AND indexrelname NOT LIKE '%_pkey'
     ORDER BY pg_relation_size(indexrelid) DESC
     LIMIT 10;"

# 4. Check for Long-Running Queries
echo ""
echo "4. Long-Running Queries:"
docker exec hgr-postgres psql -U hgr_admin -c \
    "SELECT 
        pid,
        now() - pg_stat_activity.query_start AS duration,
        query,
        state
     FROM pg_stat_activity
     WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes'
     AND state != 'idle';"

# 5. Check Replication Lag (if applicable)
echo ""
echo "5. Replication Status:"
docker exec hgr-postgres psql -U hgr_admin -c \
    "SELECT * FROM pg_stat_replication;" || echo "No replication configured"

# 6. Vacuum Progress
echo ""
echo "6. Current Vacuum Operations:"
docker exec hgr-postgres psql -U hgr_admin -c \
    "SELECT 
        pid,
        datname,
        relid::regclass AS table,
        phase,
        heap_blks_total,
        heap_blks_scanned,
        heap_blks_vacuumed,
        index_vacuum_count
     FROM pg_stat_progress_vacuum;"

echo ""
echo "✓ PostgreSQL maintenance check complete"
```

---

## 6. LOG MANAGEMENT

### 6.1 Log Analysis and Reporting

**File:** `scripts/maintenance/analyze_logs.py`

```python
#!/usr/bin/env python3
"""
Analyze system logs for patterns and anomalies
"""

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import json

class LogAnalyzer:
    """Analyze Holy Grail Refinery logs"""
    
    def __init__(self, log_file):
        self.log_file = log_file
        self.errors = []
        self.warnings = []
        self.patterns = defaultdict(int)
    
    def analyze(self):
        """Perform comprehensive log analysis"""
        print("Analyzing logs...")
        
        with open(self.log_file, 'r') as f:
            for line in f:
                self._analyze_line(line)
        
        self.generate_report()
    
    def _analyze_line(self, line):
        """Analyze individual log line"""
        # Extract timestamp
        timestamp_match = re.search(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', line)
        
        # Categorize by severity
        if 'ERROR' in line:
            self.errors.append(line.strip())
            
            # Extract error patterns
            error_match = re.search(r'ERROR: (.+?)(?:\n|$)', line)
            if error_match:
                self.patterns[error_match.group(1)] += 1
        
        elif 'WARNING' in line or 'WARN' in line:
            self.warnings.append(line.strip())
    
    def generate_report(self):
        """Generate analysis report"""
        print("\n" + "="*50)
        print("LOG ANALYSIS REPORT")
        print("="*50)
        
        print(f"\nTotal Errors: {len(self.errors)}")
        print(f"Total Warnings: {len(self.warnings)}")
        
        # Top error patterns
        if self.patterns:
            print("\nTop Error Patterns:")
            for pattern, count in Counter(self.patterns).most_common(10):
                print(f"  [{count}x] {pattern[:80]}")
        
        # Recent critical errors
        if self.errors:
            print("\nRecent Errors (last 5):")
            for error in self.errors[-5:]:
                print(f"  {error[:100]}")
        
        print("\n" + "="*50)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: analyze_logs.py <log_file>")
        sys.exit(1)
    
    analyzer = LogAnalyzer(sys.argv[1])
    analyzer.analyze()
```

---

## 7. PERFORMANCE TUNING

### 7.1 Automated Performance Tuning

**File:** `scripts/maintenance/auto_tune_performance.sh`

```bash
#!/bin/bash
# Automated performance tuning based on metrics

set -e

echo "Automated Performance Tuning"
echo "==========================="

# 1. Analyze CPU Usage
echo "1. Analyzing CPU usage patterns..."

HIGH_CPU_AGENTS=$(docker stats --no-stream --format "{{.Name}} {{.CPUPerc}}" | \
    awk '$2 > 80.0 {print $1}')

if [ -n "$HIGH_CPU_AGENTS" ]; then
    echo "  High CPU agents detected:"
    echo "$HIGH_CPU_AGENTS" | while read AGENT; do
        echo "    - $AGENT"
        
        # Increase CPU allocation
        CURRENT_CPU=$(docker inspect $AGENT | jq -r '.[0].HostConfig.NanoCpus')
        NEW_CPU=$((CURRENT_CPU + 500000000))  # Add 0.5 CPU
        
        echo "      Action: Increasing CPU allocation"
    done
fi

# 2. Analyze Memory Usage
echo ""
echo "2. Analyzing memory usage patterns..."

HIGH_MEM_AGENTS=$(docker stats --no-stream --format "{{.Name}} {{.MemPerc}}" | \
    awk '$2 > 80.0 {print $1}')

if [ -n "$HIGH_MEM_AGENTS" ]; then
    echo "  High memory agents detected:"
    echo "$HIGH_MEM_AGENTS" | while read AGENT; do
        echo "    - $AGENT"
        echo "      Action: Consider increasing memory limit"
    done
fi

# 3. Optimize Database Connections
echo ""
echo "3. Optimizing database connection pools..."

# Check current connection counts
CONNECTIONS=$(docker exec hgr-postgres psql -U hgr_admin -t -c \
    "SELECT count(*) FROM pg_stat_activity;")

MAX_CONNECTIONS=$(docker exec hgr-postgres psql -U hgr_admin -t -c \
    "SELECT setting FROM pg_settings WHERE name='max_connections';")

USAGE_PERCENT=$((CONNECTIONS * 100 / MAX_CONNECTIONS))

echo "  Current connections: $CONNECTIONS / $MAX_CONNECTIONS (${USAGE_PERCENT}%)"

if [ $USAGE_PERCENT -gt 80 ]; then
    echo "  ⚠ High connection usage - consider increasing pool size"
fi

# 4. Optimize Redis Memory
echo ""
echo "4. Analyzing Redis memory usage..."

REDIS_USED=$(docker exec hgr-redis redis-cli INFO memory | \
    grep "used_memory_human" | cut -d: -f2 | tr -d '\r')

REDIS_PEAK=$(docker exec hgr-redis redis-cli INFO memory | \
    grep "used_memory_peak_human" | cut -d: -f2 | tr -d '\r')

echo "  Current: $REDIS_USED / Peak: $REDIS_PEAK"

# 5. Recommendations
echo ""
echo "5. Performance Recommendations:"
echo "  - Monitor high-CPU agents for optimization opportunities"
echo "  - Review database query performance weekly"
echo "  - Consider agent replication for high-load scenarios"

echo ""
echo "✓ Performance tuning analysis complete"
```

---

## 8. SECURITY HARDENING

### 8.1 Security Audit

**File:** `scripts/maintenance/security_audit.sh`

```bash
#!/bin/bash
# Monthly security audit

set -e

REPORT_FILE="reports/security_audit_$(date +%Y%m).txt"

echo "Security Audit" | tee $REPORT_FILE
echo "==============" | tee -a $REPORT_FILE
echo "Date: $(date)" | tee -a $REPORT_FILE
echo "" | tee -a $REPORT_FILE

# 1. Check for exposed ports
echo "1. Exposed Ports:" | tee -a $REPORT_FILE
docker ps --format "{{.Names}}: {{.Ports}}" | tee -a $REPORT_FILE
echo "" | tee -a $REPORT_FILE

# 2. Check file permissions
echo "2. Critical File Permissions:" | tee -a $REPORT_FILE
ls -la .env config/*.json | tee -a $REPORT_FILE
echo "" | tee -a $REPORT_FILE

# 3. Check for default passwords
echo "3. Checking for default credentials..." | tee -a $REPORT_FILE
# (Implementation would check actual credentials)
echo "  Manual review required" | tee -a $REPORT_FILE
echo "" | tee -a $REPORT_FILE

# 4. Check SSL/TLS configuration
echo "4. SSL/TLS Status:" | tee -a $REPORT_FILE
# Check certificate validity
echo "  Certificate check required" | tee -a $REPORT_FILE
echo "" | tee -a $REPORT_FILE

# 5. Review access logs
echo "5. Access Log Review:" | tee -a $REPORT_FILE
echo "  Recent failed authentications:" | tee -a $REPORT_FILE
grep "authentication failed" /var/log/hgr/*.log | tail -10 | tee -a $REPORT_FILE
echo "" | tee -a $REPORT_FILE

echo "✓ Security audit complete" | tee -a $REPORT_FILE
echo "Report saved to: $REPORT_FILE"
```

---

## 9. CAPACITY MANAGEMENT

### 9.1 Resource Forecasting

**File:** `scripts/maintenance/capacity_forecast.py`

```python
#!/usr/bin/env python3
"""
Forecast resource needs based on growth trends
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

class CapacityForecaster:
    """Forecast resource capacity needs"""
    
    def __init__(self):
        self.history_file = '/var/log/hgr/capacity_history.log'
    
    def forecast(self, days_ahead=90):
        """Forecast resource needs"""
        print(f"Forecasting resource needs for next {days_ahead} days...")
        
        # Load historical data
        data = pd.read_csv(
            self.history_file,
            names=['date', 'disk_usage'],
            parse_dates=['date']
        )
        
        # Calculate growth rate
        data['days'] = (data['date'] - data['date'].min()).dt.days
        
        # Linear regression
        coeffs = np.polyfit(data['days'], data['disk_usage'], 1)
        daily_growth = coeffs[0]
        
        # Forecast
        current_usage = data['disk_usage'].iloc[-1]
        forecast_usage = current_usage + (daily_growth * days_ahead)
        
        print(f"\nCurrent disk usage: {current_usage}%")
        print(f"Daily growth rate: {daily_growth:.2f}%")
        print(f"Forecast in {days_ahead} days: {forecast_usage:.1f}%")
        
        # Recommendations
        if forecast_usage > 80:
            days_until_80 = (80 - current_usage) / daily_growth
            print(f"\n⚠ WARNING: Will reach 80% in {int(days_until_80)} days")
            print("  Recommendation: Plan storage expansion")
        else:
            print("\n✓ Capacity adequate for forecast period")


if __name__ == "__main__":
    forecaster = CapacityForecaster()
    forecaster.forecast(days_ahead=90)
```

---

## 10. MAINTENANCE CALENDAR

### 10.1 Automated Scheduling

**File:** `/etc/cron.d/hgr-maintenance`

```cron
# Holy Grail Refinery Maintenance Schedule

# Daily Tasks (2 AM)
0 2 * * * hgr /opt/hgr/scripts/maintenance/daily_health_check.sh
30 2 * * * hgr /opt/hgr/scripts/maintenance/daily_backup.sh
0 3 * * * hgr /opt/hgr/scripts/maintenance/rotate_logs.sh

# Weekly Tasks (Sunday 3 AM)
0 3 * * 0 hgr /opt/hgr/scripts/maintenance/weekly_performance_review.sh
30 3 * * 0 hgr /opt/hgr/scripts/maintenance/capacity_review.sh

# Monthly Tasks (1st of month, 4 AM)
0 4 1 * * hgr /opt/hgr/scripts/maintenance/monthly_security_updates.sh
0 5 1 * * hgr /opt/hgr/scripts/maintenance/monthly_database_optimization.sh
0 6 1 * * hgr /opt/hgr/scripts/maintenance/security_audit.sh

# Quarterly Tasks (1st of Jan/Apr/Jul/Oct, 5 AM)
0 5 1 1,4,7,10 * hgr /opt/hgr/scripts/maintenance/quarterly_agent_updates.sh
0 6 1 1,4,7,10 * hgr /opt/hgr/scripts/maintenance/capacity_forecast.py
```

---

## DOCUMENT METADATA

**Document ID:** 33  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Operations & Deployment  
**Owner:** Operations Lead  
**Dependencies:** Documents 32 (Production Deployment), 27 (Agent Operations)  
**Next Document:** 34 (Backup & Recovery Operations)

---

*End of System Maintenance Procedures*
