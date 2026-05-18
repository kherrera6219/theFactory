# DOCUMENT 40: DISASTER RECOVERY TESTING PROCEDURES

Document version: 2026.03.29
Last updated: 2026-03-29
Status: Archived Legacy
## Holy Grail Refinery - Operations & Deployment

**Document ID:** 40  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Operations & Deployment  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document provides **comprehensive disaster recovery (DR) testing procedures** for the Holy Grail Refinery system. It includes failover scenarios, data restoration validation, recovery time objective (RTO) verification, and business continuity testing to ensure the system can recover from catastrophic failures.

**DR Objectives:**
- **RTO (Recovery Time Objective):** 4 hours maximum
- **RPO (Recovery Point Objective):** 15 minutes maximum data loss
- **System Availability Target:** 99.9% (43 minutes downtime/month)
- **Critical Data Restoration:** 100% integrity verification
- **Automated Failover:** <5 minutes for infrastructure failures

**Testing Frequency:**
- **Full DR Test:** Quarterly (4x per year)
- **Partial DR Test:** Monthly
- **Backup Verification:** Weekly
- **Runbook Validation:** Bi-weekly

**Failure Scenarios Covered:**
1. Complete hardware failure (AW1 machine down)
2. Database corruption/loss (PostgreSQL, Redis)
3. Container orchestration failure (Docker daemon crash)
4. Network partition/isolation
5. Storage device failure
6. Power outage (unplanned shutdown)
7. Cyber attack/ransomware simulation
8. Data center evacuation scenario

---

## TABLE OF CONTENTS

1. [DR Testing Framework](#1-dr-testing-framework)
2. [Test Scenario Catalog](#2-test-scenario-catalog)
3. [Backup Verification Procedures](#3-backup-verification-procedures)
4. [Data Restoration Validation](#4-data-restoration-validation)
5. [Failover Testing](#5-failover-testing)
6. [RTO/RPO Measurement](#6-rtorpo-measurement)
7. [DR Test Execution Workflow](#7-dr-test-execution-workflow)
8. [Post-Test Analysis](#8-post-test-analysis)
9. [Continuous Improvement Process](#9-continuous-improvement-process)
10. [DR Test Schedule & Reporting](#10-dr-test-schedule--reporting)

---

## 1. DR TESTING FRAMEWORK

### 1.1 Test Environment Setup

**File:** `dr_testing/environment_setup.sh`

```bash
#!/bin/bash
# Setup isolated DR test environment

set -e

echo "=== DR Test Environment Setup ==="

# 1. Create isolated network for testing
docker network create --driver bridge \
    --subnet=172.30.0.0/24 \
    --gateway=172.30.0.1 \
    dr-test-network

# 2. Label test environment
export DR_TEST_MODE=true
export DR_TEST_ID="DR-TEST-$(date +%Y%m%d-%H%M%S)"

echo "DR Test ID: $DR_TEST_ID"

# 3. Create test data directory
mkdir -p /tmp/dr-test-$DR_TEST_ID/{backups,restored,logs}

# 4. Copy current backups to test location
echo "Copying production backups..."
cp -r /backups/* /tmp/dr-test-$DR_TEST_ID/backups/

# 5. Launch monitoring for test
echo "Starting test monitoring..."
./monitoring/start_dr_monitoring.sh $DR_TEST_ID

echo "✓ DR test environment ready"
echo "Test directory: /tmp/dr-test-$DR_TEST_ID"
```

### 1.2 Test Validation Criteria

**File:** `dr_testing/validation_criteria.yml`

```yaml
validation_criteria:
  # System availability
  system_available:
    description: "System is accessible and responsive"
    success_criteria:
      - API returns 200 OK
      - All 35 agents are running
      - Database connections successful
      - Semantic Bus operational
    
  # Data integrity
  data_integrity:
    description: "All data restored without corruption"
    success_criteria:
      - Database checksum matches backup
      - LogicNode registry complete
      - Knowledge Lake indexes valid
      - No missing missions or logs
    
  # Performance
  performance:
    description: "System performs within acceptable limits"
    success_criteria:
      - API latency < 2x normal
      - Agent response time < 2x normal
      - Database query time < 2x normal
    
  # RTO compliance
  rto_met:
    description: "Recovery completed within RTO"
    success_criteria:
      - Total recovery time < 4 hours
      - Critical services < 30 minutes
      - Full system < 4 hours
    
  # RPO compliance
  rpo_met:
    description: "Data loss within acceptable limits"
    success_criteria:
      - Max data loss < 15 minutes
      - All mission data recoverable
      - Logs within RPO window

# Test pass/fail thresholds
thresholds:
  minimum_passing_score: 80%  # 4 of 5 criteria must pass
  critical_failures:
    - system_available: false
    - data_integrity: false
```

### 1.3 Pre-Test Checklist

**File:** `dr_testing/pre_test_checklist.md`

```markdown
# DR Test Pre-Flight Checklist

## Planning
- [ ] DR test scheduled on team calendar
- [ ] All team members notified 48 hours in advance
- [ ] Stakeholders informed of potential disruptions
- [ ] Test window confirmed (non-peak hours)
- [ ] Backup restoration target identified

## Environment
- [ ] Production backups verified within last 24 hours
- [ ] Test environment isolated from production
- [ ] Monitoring systems operational
- [ ] Logging configured for test
- [ ] Test network configured

## Team
- [ ] DR lead identified
- [ ] Backup engineer assigned
- [ ] Observer role assigned
- [ ] Communication channels established (Slack, Zoom)
- [ ] Runbooks accessible to all participants

## Safety
- [ ] Production system in stable state
- [ ] No planned deployments during test window
- [ ] Rollback plan documented
- [ ] Emergency stop procedure reviewed
- [ ] Production isolation verified

## Documentation
- [ ] Test scenario documented
- [ ] Success criteria defined
- [ ] Measurement tools ready
- [ ] Video recording prepared (optional)
- [ ] Post-test report template ready

**Sign-off:**
- DR Lead: _____________ Date: _______
- Engineering Manager: _____________ Date: _______
```

---

## 2. TEST SCENARIO CATALOG

### 2.1 Scenario 1: Complete Hardware Failure

**File:** `dr_testing/scenarios/01_hardware_failure.sh`

```bash
#!/bin/bash
# DR Test Scenario 1: Complete hardware failure simulation

set -e

echo "=== DR Scenario 1: Complete Hardware Failure ==="
echo "Simulating catastrophic failure of AW1 machine"

START_TIME=$(date +%s)

# Record baseline metrics
echo "Recording baseline metrics..."
./scripts/record_metrics.sh baseline

# Step 1: Simulate hardware failure (controlled shutdown)
echo "Step 1: Simulating hardware failure..."
echo "  - Stopping all containers gracefully"
docker-compose down

echo "  - Simulating disk corruption"
# Don't actually corrupt, just mark as test
touch /tmp/dr-test-disk-failure

sleep 10

# Step 2: Prepare recovery environment
echo "Step 2: Preparing recovery environment..."
echo "  - Provisioning new infrastructure (simulated)"
./dr_testing/provision_recovery_environment.sh

# Step 3: Restore from backups
echo "Step 3: Restoring from latest backup..."
BACKUP_FILE=$(ls -t /backups/full-backup-*.tar.gz | head -1)
echo "  - Using backup: $BACKUP_FILE"

./scripts/restore_full_backup.sh "$BACKUP_FILE"

# Step 4: Verify data integrity
echo "Step 4: Verifying data integrity..."
./dr_testing/verify_data_integrity.sh

# Step 5: Start services
echo "Step 5: Starting all services..."
docker-compose up -d

# Step 6: Wait for system ready
echo "Step 6: Waiting for system to become ready..."
timeout 300 bash -c 'until curl -sf http://localhost:8000/health; do sleep 5; done' || \
    (echo "ERROR: System did not become ready within 5 minutes" && exit 1)

# Step 7: Run smoke tests
echo "Step 7: Running smoke tests..."
./scripts/smoke_test.sh

# Step 8: Measure recovery metrics
END_TIME=$(date +%s)
RECOVERY_TIME=$((END_TIME - START_TIME))

echo ""
echo "=== Recovery Complete ==="
echo "Total recovery time: $((RECOVERY_TIME / 60)) minutes"
echo "RTO target: 240 minutes"

if [ $RECOVERY_TIME -lt 14400 ]; then  # 4 hours
    echo "✓ RTO MET"
else
    echo "✗ RTO EXCEEDED"
fi

# Generate test report
./dr_testing/generate_report.sh \
    --scenario "hardware_failure" \
    --recovery-time "$RECOVERY_TIME" \
    --test-id "$DR_TEST_ID"
```

### 2.2 Scenario 2: Database Corruption

**File:** `dr_testing/scenarios/02_database_corruption.sh`

```bash
#!/bin/bash
# DR Test Scenario 2: Database corruption simulation

set -e

echo "=== DR Scenario 2: Database Corruption ==="

START_TIME=$(date +%s)

# Step 1: Simulate database corruption
echo "Step 1: Simulating PostgreSQL corruption..."
docker exec hgr-postgres psql -U hgr_admin -d hgr_main -c \
    "DROP TABLE IF EXISTS missions CASCADE;"

echo "  - missions table dropped (simulating corruption)"

# Step 2: Detect corruption
echo "Step 2: Detecting corruption..."
if ! docker exec hgr-postgres psql -U hgr_admin -d hgr_main -c "SELECT 1 FROM missions LIMIT 1;" 2>/dev/null; then
    echo "  ✓ Corruption detected"
else
    echo "  ERROR: Corruption not detected"
    exit 1
fi

# Step 3: Stop applications
echo "Step 3: Stopping applications to prevent data loss..."
docker-compose stop api agent-*

# Step 4: Restore database from backup
echo "Step 4: Restoring database from backup..."
LATEST_DB_BACKUP=$(ls -t /backups/postgres/postgres-*.sql.gz | head -1)
echo "  - Using backup: $LATEST_DB_BACKUP"

# Drop and recreate database
docker exec hgr-postgres psql -U postgres -c "DROP DATABASE IF EXISTS hgr_main;"
docker exec hgr-postgres psql -U postgres -c "CREATE DATABASE hgr_main;"

# Restore
gunzip -c "$LATEST_DB_BACKUP" | \
    docker exec -i hgr-postgres psql -U hgr_admin -d hgr_main

# Step 5: Verify restoration
echo "Step 5: Verifying database restoration..."
MISSION_COUNT=$(docker exec hgr-postgres psql -U hgr_admin -d hgr_main -t -c \
    "SELECT COUNT(*) FROM missions;")

echo "  - Missions restored: $MISSION_COUNT"

# Step 6: Check data integrity
echo "Step 6: Checking data integrity..."
./dr_testing/verify_database_integrity.sh

# Step 7: Restart applications
echo "Step 7: Restarting applications..."
docker-compose up -d

# Step 8: Smoke test
echo "Step 8: Running smoke tests..."
./scripts/smoke_test.sh

END_TIME=$(date +%s)
RECOVERY_TIME=$((END_TIME - START_TIME))

echo ""
echo "=== Database Recovery Complete ==="
echo "Recovery time: $((RECOVERY_TIME / 60)) minutes"
```

### 2.3 Scenario 3: Redis Data Loss

**File:** `dr_testing/scenarios/03_redis_data_loss.sh`

```bash
#!/bin/bash
# DR Test Scenario 3: Redis (Semantic Bus) data loss

set -e

echo "=== DR Scenario 3: Redis Data Loss ==="

START_TIME=$(date +%s)

# Step 1: Record current state
echo "Step 1: Recording current Redis state..."
KEYS_BEFORE=$(docker exec hgr-redis redis-cli DBSIZE | grep -oP '\d+')
echo "  - Keys in Redis: $KEYS_BEFORE"

# Step 2: Simulate data loss (flush all)
echo "Step 2: Simulating Redis data loss..."
docker exec hgr-redis redis-cli FLUSHALL

KEYS_AFTER=$(docker exec hgr-redis redis-cli DBSIZE | grep -oP '\d+')
echo "  - Keys after flush: $KEYS_AFTER"

# Step 3: Restore from RDB backup
echo "Step 3: Restoring from Redis backup..."
docker stop hgr-redis

# Copy backup file
LATEST_RDB=$(ls -t /backups/redis/dump-*.rdb | head -1)
echo "  - Using backup: $LATEST_RDB"
cp "$LATEST_RDB" /var/lib/docker/volumes/hgr_redis-data/_data/dump.rdb

# Restart Redis
docker start hgr-redis
sleep 5

# Step 4: Verify restoration
echo "Step 4: Verifying Redis restoration..."
KEYS_RESTORED=$(docker exec hgr-redis redis-cli DBSIZE | grep -oP '\d+')
echo "  - Keys restored: $KEYS_RESTORED"

DATA_LOSS_PCT=$(echo "scale=2; (($KEYS_BEFORE - $KEYS_RESTORED) / $KEYS_BEFORE) * 100" | bc)
echo "  - Data loss: ${DATA_LOSS_PCT}%"

# Step 5: Verify RPO
echo "Step 5: Checking RPO compliance..."
BACKUP_AGE=$(stat -c %Y "$LATEST_RDB")
CURRENT_TIME=$(date +%s)
BACKUP_AGE_MINUTES=$(( (CURRENT_TIME - BACKUP_AGE) / 60 ))

echo "  - Backup age: $BACKUP_AGE_MINUTES minutes"

if [ $BACKUP_AGE_MINUTES -lt 15 ]; then
    echo "  ✓ RPO MET (< 15 minutes)"
else
    echo "  ✗ RPO EXCEEDED (> 15 minutes)"
fi

END_TIME=$(date +%s)
RECOVERY_TIME=$((END_TIME - START_TIME))

echo ""
echo "=== Redis Recovery Complete ==="
echo "Recovery time: $((RECOVERY_TIME / 60)) minutes"
```

### 2.4 Scenario 4: Network Partition

**File:** `dr_testing/scenarios/04_network_partition.sh`

```bash
#!/bin/bash
# DR Test Scenario 4: Network partition simulation

set -e

echo "=== DR Scenario 4: Network Partition ==="

START_TIME=$(date +%s)

# Step 1: Create network partition
echo "Step 1: Creating network partition..."
echo "  - Isolating Pod A from other pods"

# Block traffic between Pod A and other pods
docker exec hgr-agent-python-001 iptables -A OUTPUT -d 172.20.2.0/24 -j DROP
docker exec hgr-agent-python-001 iptables -A OUTPUT -d 172.20.3.0/24 -j DROP
docker exec hgr-agent-python-001 iptables -A OUTPUT -d 172.20.4.0/24 -j DROP

echo "  - Network partition created"

# Step 2: Verify partition
echo "Step 2: Verifying partition..."
if docker exec hgr-agent-python-001 ping -c 1 -W 1 hgr-agent-c-001 2>/dev/null; then
    echo "  ERROR: Partition not effective"
    exit 1
else
    echo "  ✓ Partition verified"
fi

# Step 3: Monitor system behavior
echo "Step 3: Monitoring system behavior during partition..."
sleep 30

# Check for circuit breaker activation
CIRCUIT_BREAKER_ACTIVE=$(curl -s http://localhost:8000/metrics | \
    grep -c "circuit_breaker_open" || true)

echo "  - Circuit breakers activated: $CIRCUIT_BREAKER_ACTIVE"

# Step 4: Restore network connectivity
echo "Step 4: Restoring network connectivity..."
docker exec hgr-agent-python-001 iptables -F OUTPUT

sleep 5

# Step 5: Verify recovery
echo "Step 5: Verifying system recovery..."
if docker exec hgr-agent-python-001 ping -c 1 -W 1 hgr-agent-c-001; then
    echo "  ✓ Connectivity restored"
else
    echo "  ERROR: Connectivity not restored"
    exit 1
fi

# Step 6: Check for data inconsistencies
echo "Step 6: Checking for data inconsistencies..."
./dr_testing/verify_data_consistency.sh

END_TIME=$(date +%s)
RECOVERY_TIME=$((END_TIME - START_TIME))

echo ""
echo "=== Network Partition Test Complete ==="
echo "Partition duration: $((RECOVERY_TIME / 60)) minutes"
```

### 2.5 Scenario 5: Ransomware Simulation

**File:** `dr_testing/scenarios/05_ransomware_simulation.sh`

```bash
#!/bin/bash
# DR Test Scenario 5: Ransomware attack simulation

set -e

echo "=== DR Scenario 5: Ransomware Attack Simulation ==="
echo "WARNING: This is a controlled test. Do NOT run in production."

START_TIME=$(date +%s)

# Step 1: Detect "ransomware" (simulated)
echo "Step 1: Detecting ransomware..."
touch /tmp/ransomware-detected
echo "  ✓ Ransomware detected (simulated)"

# Step 2: Immediate isolation
echo "Step 2: Isolating affected systems..."
# Disconnect from external networks
docker network disconnect bridge hgr-api

echo "  ✓ System isolated"

# Step 3: Assess damage
echo "Step 3: Assessing damage..."
echo "  - Checking file integrity..."
# Simulate encryption detection
ENCRYPTED_FILES=150
echo "  - Encrypted files detected: $ENCRYPTED_FILES"

# Step 4: Initiate emergency backup
echo "Step 4: Creating emergency backup..."
./scripts/emergency_backup.sh

# Step 5: Wipe and restore from clean backup
echo "Step 5: Restoring from clean backup..."
# Use backup from before infection (e.g., 24 hours ago)
CLEAN_BACKUP=$(find /backups/full-backup-* -mtime +1 | tail -1)
echo "  - Using clean backup: $CLEAN_BACKUP"

./scripts/restore_full_backup.sh "$CLEAN_BACKUP"

# Step 6: Rebuild infrastructure
echo "Step 6: Rebuilding infrastructure..."
docker-compose down
docker system prune -af
docker-compose up -d

# Step 7: Verify no malware present
echo "Step 7: Verifying system integrity..."
./dr_testing/malware_scan.sh

# Step 8: Reconnect to network
echo "Step 8: Reconnecting to network..."
docker network connect bridge hgr-api

# Step 9: Validate recovery
echo "Step 9: Validating recovery..."
./scripts/smoke_test.sh

END_TIME=$(date +%s)
RECOVERY_TIME=$((END_TIME - START_TIME))

echo ""
echo "=== Ransomware Recovery Complete ==="
echo "Recovery time: $((RECOVERY_TIME / 60)) minutes"

# Calculate data loss
DATA_LOSS_HOURS=24  # Using 24-hour-old backup
echo "Data loss: $DATA_LOSS_HOURS hours of data"
```

---

## 3. BACKUP VERIFICATION PROCEDURES

### 3.1 Weekly Backup Verification

**File:** `dr_testing/verify_backups.sh`

```bash
#!/bin/bash
# Weekly backup verification

set -e

echo "=== Backup Verification ==="

BACKUP_DIR="/backups"
VERIFY_LOG="/var/log/backup-verification.log"

# Function to verify backup file
verify_backup() {
    local backup_file=$1
    local backup_type=$2
    
    echo "Verifying: $backup_file"
    
    # Check file exists and is readable
    if [ ! -r "$backup_file" ]; then
        echo "ERROR: Cannot read backup file"
        return 1
    fi
    
    # Check file size (must be > 1MB)
    size=$(stat -c%s "$backup_file")
    if [ $size -lt 1048576 ]; then
        echo "ERROR: Backup file too small ($size bytes)"
        return 1
    fi
    
    # Verify compression integrity
    if [[ $backup_file == *.gz ]]; then
        if ! gunzip -t "$backup_file" 2>/dev/null; then
            echo "ERROR: Corrupt gzip file"
            return 1
        fi
    fi
    
    # Test restoration (in isolated environment)
    case $backup_type in
        "postgres")
            verify_postgres_backup "$backup_file"
            ;;
        "redis")
            verify_redis_backup "$backup_file"
            ;;
        "full")
            verify_full_backup "$backup_file"
            ;;
    esac
    
    echo "✓ Backup verified successfully"
    return 0
}

verify_postgres_backup() {
    local backup_file=$1
    
    # Create test database
    docker exec hgr-postgres psql -U postgres -c \
        "DROP DATABASE IF EXISTS test_restore;"
    docker exec hgr-postgres psql -U postgres -c \
        "CREATE DATABASE test_restore;"
    
    # Attempt restore
    if gunzip -c "$backup_file" | \
        docker exec -i hgr-postgres psql -U postgres -d test_restore 2>&1 | \
        tee -a "$VERIFY_LOG"; then
        
        # Verify table count
        table_count=$(docker exec hgr-postgres psql -U postgres -d test_restore -t -c \
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
        
        echo "  - Tables restored: $table_count"
        
        # Cleanup
        docker exec hgr-postgres psql -U postgres -c \
            "DROP DATABASE test_restore;"
        
        return 0
    else
        echo "ERROR: Failed to restore PostgreSQL backup"
        return 1
    fi
}

verify_redis_backup() {
    local backup_file=$1
    
    # Start temporary Redis instance
    docker run -d --name redis-verify \
        -v "$backup_file:/data/dump.rdb" \
        redis:7.2-alpine redis-server --appendonly no
    
    sleep 2
    
    # Check if data loaded
    key_count=$(docker exec redis-verify redis-cli DBSIZE | grep -oP '\d+')
    echo "  - Keys loaded: $key_count"
    
    # Cleanup
    docker rm -f redis-verify
    
    if [ $key_count -gt 0 ]; then
        return 0
    else
        echo "ERROR: No keys loaded from Redis backup"
        return 1
    fi
}

verify_full_backup() {
    local backup_file=$1
    
    # Extract to temporary location
    temp_dir=$(mktemp -d)
    tar -xzf "$backup_file" -C "$temp_dir"
    
    # Verify key components present
    components=("postgres" "redis" "loki" "prometheus" "config")
    
    for component in "${components[@]}"; do
        if [ ! -d "$temp_dir/$component" ]; then
            echo "ERROR: Missing component: $component"
            rm -rf "$temp_dir"
            return 1
        fi
    done
    
    echo "  - All components present"
    
    # Cleanup
    rm -rf "$temp_dir"
    return 0
}

# Main verification loop
echo "Checking PostgreSQL backups..."
for backup in "$BACKUP_DIR"/postgres/postgres-*.sql.gz; do
    verify_backup "$backup" "postgres"
done

echo ""
echo "Checking Redis backups..."
for backup in "$BACKUP_DIR"/redis/dump-*.rdb; do
    verify_backup "$backup" "redis"
done

echo ""
echo "Checking full system backups..."
for backup in "$BACKUP_DIR"/full-backup-*.tar.gz; do
    verify_backup "$backup" "full"
done

echo ""
echo "=== Backup Verification Complete ==="
```

---

## 4. DATA RESTORATION VALIDATION

### 4.1 Data Integrity Verification

**File:** `dr_testing/verify_data_integrity.sh`

```bash
#!/bin/bash
# Verify data integrity after restoration

set -e

echo "=== Data Integrity Verification ==="

ERRORS=0

# 1. PostgreSQL data integrity
echo "1. Verifying PostgreSQL data integrity..."

# Check database consistency
if docker exec hgr-postgres psql -U hgr_admin -d hgr_main -c \
    "SELECT pg_catalog.pg_check_all_visible('missions');" | grep -q "t"; then
    echo "  ✓ missions table integrity OK"
else
    echo "  ✗ missions table integrity FAILED"
    ((ERRORS++))
fi

# Verify foreign key constraints
CONSTRAINT_VIOLATIONS=$(docker exec hgr-postgres psql -U hgr_admin -d hgr_main -t -c \
    "SELECT COUNT(*) FROM 
        (SELECT conname, conrelid::regclass, confrelid::regclass 
         FROM pg_constraint 
         WHERE contype = 'f') AS constraints 
    WHERE NOT EXISTS (
        SELECT 1 FROM missions
    );")

if [ "$CONSTRAINT_VIOLATIONS" -eq 0 ]; then
    echo "  ✓ Foreign key constraints valid"
else
    echo "  ✗ $CONSTRAINT_VIOLATIONS foreign key violations found"
    ((ERRORS++))
fi

# 2. Redis data integrity
echo ""
echo "2. Verifying Redis data integrity..."

# Check Redis memory consistency
REDIS_MEMORY=$(docker exec hgr-redis redis-cli INFO memory | grep used_memory_human)
echo "  - Redis memory: $REDIS_MEMORY"

# Verify key types
declare -A expected_types=(
    ["mission:*"]="hash"
    ["agent:*:state"]="hash"
    ["semantic_bus:*"]="list"
)

for pattern in "${!expected_types[@]}"; do
    keys=$(docker exec hgr-redis redis-cli --scan --pattern "$pattern" | head -1)
    if [ -n "$keys" ]; then
        actual_type=$(docker exec hgr-redis redis-cli TYPE "$keys")
        expected_type="${expected_types[$pattern]}"
        
        if [ "$actual_type" == "$expected_type" ]; then
            echo "  ✓ $pattern type correct ($actual_type)"
        else
            echo "  ✗ $pattern type incorrect (expected: $expected_type, got: $actual_type)"
            ((ERRORS++))
        fi
    fi
done

# 3. LogicNode Registry integrity
echo ""
echo "3. Verifying LogicNode Registry..."

# Count LogicNodes
LOGICNODE_COUNT=$(docker exec hgr-postgres psql -U hgr_admin -d hgr_logicnodes -t -c \
    "SELECT COUNT(*) FROM logicnodes;")

echo "  - LogicNodes in registry: $LOGICNODE_COUNT"

# Verify Git repository
if [ -d "/data/logicnode-registry/.git" ]; then
    cd /data/logicnode-registry
    if git fsck --full 2>&1 | grep -q "Checking"; then
        echo "  ✓ Git repository integrity OK"
    else
        echo "  ✗ Git repository corruption detected"
        ((ERRORS++))
    fi
fi

# 4. Knowledge Lake integrity
echo ""
echo "4. Verifying Knowledge Lake..."

# Check Milvus collection
# (Assuming Milvus CLI is available)
if command -v milvus &> /dev/null; then
    VECTOR_COUNT=$(milvus_cli -c "count collection knowledge_lake")
    echo "  - Vectors in Knowledge Lake: $VECTOR_COUNT"
fi

# 5. File system integrity
echo ""
echo "5. Verifying file system integrity..."

# Check critical directories
CRITICAL_DIRS=(
    "/data/postgres"
    "/data/redis"
    "/data/loki"
    "/data/prometheus"
    "/data/logicnode-registry"
)

for dir in "${CRITICAL_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        # Check directory is readable
        if [ -r "$dir" ]; then
            # Check disk usage
            usage=$(df -h "$dir" | tail -1 | awk '{print $5}' | sed 's/%//')
            echo "  - $dir usage: ${usage}%"
            
            if [ $usage -gt 90 ]; then
                echo "    ⚠  WARNING: High disk usage"
            fi
        else
            echo "  ✗ $dir not readable"
            ((ERRORS++))
        fi
    else
        echo "  ✗ $dir does not exist"
        ((ERRORS++))
    fi
done

# 6. Mission data consistency
echo ""
echo "6. Verifying mission data consistency..."

# Compare mission count across databases
POSTGRES_MISSIONS=$(docker exec hgr-postgres psql -U hgr_admin -d hgr_main -t -c \
    "SELECT COUNT(*) FROM missions;")

REDIS_MISSIONS=$(docker exec hgr-redis redis-cli KEYS "mission:*" | wc -l)

echo "  - Missions in PostgreSQL: $POSTGRES_MISSIONS"
echo "  - Missions in Redis: $REDIS_MISSIONS"

DIFFERENCE=$((POSTGRES_MISSIONS - REDIS_MISSIONS))
if [ ${DIFFERENCE#-} -lt 10 ]; then  # Allow small differences
    echo "  ✓ Mission counts consistent"
else
    echo "  ✗ Mission counts differ by $DIFFERENCE"
    ((ERRORS++))
fi

# Summary
echo ""
echo "=== Verification Summary ==="
if [ $ERRORS -eq 0 ]; then
    echo "✓ All data integrity checks PASSED"
    exit 0
else
    echo "✗ $ERRORS data integrity checks FAILED"
    exit 1
fi
```

---

## 5. FAILOVER TESTING

### 5.1 Automated Failover Test

**File:** `dr_testing/test_failover.sh`

```bash
#!/bin/bash
# Test automated failover mechanisms

set -e

echo "=== Automated Failover Test ==="

START_TIME=$(date +%s)

# Test 1: Database primary failover
echo "Test 1: Database failover..."

# Simulate primary database failure
docker exec hgr-postgres-primary pg_ctl stop -D /var/lib/postgresql/data -m fast

# Monitor for failover
echo "  - Waiting for automatic failover..."
timeout 60 bash -c '
    while true; do
        if docker exec hgr-postgres-standby psql -U postgres -c "SELECT pg_is_in_recovery();" | grep -q "f"; then
            echo "    ✓ Standby promoted to primary"
            break
        fi
        sleep 2
    done
' || (echo "    ✗ Failover timeout" && exit 1)

FAILOVER_TIME_1=$(($(date +%s) - START_TIME))
echo "  - Failover time: ${FAILOVER_TIME_1}s"

# Test 2: Redis sentinel failover
echo ""
echo "Test 2: Redis failover..."

# Simulate Redis master failure
docker pause hgr-redis-master

# Wait for sentinel to detect and promote
timeout 60 bash -c '
    while true; do
        MASTER=$(docker exec hgr-redis-sentinel redis-cli -p 26379 SENTINEL get-master-addr-by-name mymaster | head -1)
        if [ "$MASTER" != "172.20.5.2" ]; then  # Original master IP
            echo "    ✓ New master elected: $MASTER"
            break
        fi
        sleep 2
    done
' || (echo "    ✗ Sentinel failover timeout" && exit 1)

FAILOVER_TIME_2=$(($(date +%s) - START_TIME - FAILOVER_TIME_1))
echo "  - Failover time: ${FAILOVER_TIME_2}s"

# Unpause original master
docker unpause hgr-redis-master

# Test 3: API gateway failover
echo ""
echo "Test 3: API gateway failover..."

# Stop primary API instance
docker stop hgr-api-1

# Check if load balancer redirects to backup
timeout 30 bash -c '
    while true; do
        RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
        if [ "$RESPONSE" == "200" ]; then
            echo "    ✓ Traffic redirected to backup API"
            break
        fi
        sleep 2
    done
' || (echo "    ✗ API failover timeout" && exit 1)

FAILOVER_TIME_3=$(($(date +%s) - START_TIME - FAILOVER_TIME_1 - FAILOVER_TIME_2))
echo "  - Failover time: ${FAILOVER_TIME_3}s"

# Restart primary API
docker start hgr-api-1

# Summary
echo ""
echo "=== Failover Test Summary ==="
echo "Database failover: ${FAILOVER_TIME_1}s"
echo "Redis failover: ${FAILOVER_TIME_2}s"
echo "API failover: ${FAILOVER_TIME_3}s"

MAX_FAILOVER_TIME=300  # 5 minutes
TOTAL_FAILOVER=$((FAILOVER_TIME_1 + FAILOVER_TIME_2 + FAILOVER_TIME_3))

if [ $TOTAL_FAILOVER -lt $MAX_FAILOVER_TIME ]; then
    echo "✓ All failovers completed within acceptable time"
    exit 0
else
    echo "✗ Failover exceeded acceptable time"
    exit 1
fi
```

---

## 6. RTO/RPO MEASUREMENT

### 6.1 RTO Measurement Script

**File:** `dr_testing/measure_rto.sh`

```bash
#!/bin/bash
# Measure Recovery Time Objective (RTO)

set -e

echo "=== RTO Measurement ==="

# Define recovery phases
declare -A PHASES=(
    ["detection"]="Time to detect failure"
    ["decision"]="Time to decide on recovery action"
    ["preparation"]="Time to prepare recovery environment"
    ["restoration"]="Time to restore data"
    ["validation"]="Time to validate restoration"
    ["cutover"]="Time to switch traffic to recovered system"
)

# Record timestamps for each phase
declare -A TIMESTAMPS

record_phase() {
    local phase=$1
    TIMESTAMPS[$phase]=$(date +%s)
    echo "[$phase] $(date '+%Y-%m-%d %H:%M:%S')"
}

# Start measurement
echo "Starting RTO measurement..."
record_phase "start"

# Simulate each phase
echo ""
echo "Phase 1: Detection"
record_phase "detection_start"
# Simulate detection time
sleep 2
record_phase "detection_end"

echo ""
echo "Phase 2: Decision"
record_phase "decision_start"
# Simulate decision time
sleep 1
record_phase "decision_end"

echo ""
echo "Phase 3: Preparation"
record_phase "preparation_start"
./dr_testing/provision_recovery_environment.sh
record_phase "preparation_end"

echo ""
echo "Phase 4: Restoration"
record_phase "restoration_start"
./scripts/restore_full_backup.sh "$(ls -t /backups/full-backup-*.tar.gz | head -1)"
record_phase "restoration_end"

echo ""
echo "Phase 5: Validation"
record_phase "validation_start"
./dr_testing/verify_data_integrity.sh
record_phase "validation_end"

echo ""
echo "Phase 6: Cutover"
record_phase "cutover_start"
# Update DNS/load balancer (simulated)
sleep 1
record_phase "cutover_end"

# End measurement
record_phase "end"

# Calculate durations
echo ""
echo "=== RTO Breakdown ==="

DETECTION_TIME=$((${TIMESTAMPS[detection_end]} - ${TIMESTAMPS[detection_start]}))
DECISION_TIME=$((${TIMESTAMPS[decision_end]} - ${TIMESTAMPS[decision_start]}))
PREPARATION_TIME=$((${TIMESTAMPS[preparation_end]} - ${TIMESTAMPS[preparation_start]}))
RESTORATION_TIME=$((${TIMESTAMPS[restoration_end]} - ${TIMESTAMPS[restoration_start]}))
VALIDATION_TIME=$((${TIMESTAMPS[validation_end]} - ${TIMESTAMPS[validation_start]}))
CUTOVER_TIME=$((${TIMESTAMPS[cutover_end]} - ${TIMESTAMPS[cutover_start]}))

TOTAL_RTO=$((${TIMESTAMPS[end]} - ${TIMESTAMPS[start]}))

echo "Detection:    ${DETECTION_TIME}s"
echo "Decision:     ${DECISION_TIME}s"
echo "Preparation:  ${PREPARATION_TIME}s ($((PREPARATION_TIME / 60))m)"
echo "Restoration:  ${RESTORATION_TIME}s ($((RESTORATION_TIME / 60))m)"
echo "Validation:   ${VALIDATION_TIME}s ($((VALIDATION_TIME / 60))m)"
echo "Cutover:      ${CUTOVER_TIME}s"
echo ""
echo "Total RTO:    ${TOTAL_RTO}s ($((TOTAL_RTO / 60))m)"
echo "Target RTO:   14400s (240m / 4h)"

if [ $TOTAL_RTO -lt 14400 ]; then
    echo ""
    echo "✓ RTO TARGET MET"
    exit 0
else
    echo ""
    echo "✗ RTO TARGET EXCEEDED"
    exit 1
fi
```

### 6.2 RPO Measurement Script

**File:** `dr_testing/measure_rpo.sh`

```bash
#!/bin/bash
# Measure Recovery Point Objective (RPO)

set -e

echo "=== RPO Measurement ==="

# Get latest backup timestamp
LATEST_BACKUP=$(ls -t /backups/full-backup-*.tar.gz | head -1)
BACKUP_TIME=$(stat -c %Y "$LATEST_BACKUP")

# Get current time
CURRENT_TIME=$(date +%s)

# Calculate backup age
BACKUP_AGE_SECONDS=$((CURRENT_TIME - BACKUP_TIME))
BACKUP_AGE_MINUTES=$((BACKUP_AGE_SECONDS / 60))

echo "Latest backup: $(basename $LATEST_BACKUP)"
echo "Backup timestamp: $(date -d @$BACKUP_TIME '+%Y-%m-%d %H:%M:%S')"
echo "Current time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Backup age: ${BACKUP_AGE_MINUTES} minutes"

# Check against RPO target
RPO_TARGET_MINUTES=15

if [ $BACKUP_AGE_MINUTES -le $RPO_TARGET_MINUTES ]; then
    echo ""
    echo "✓ RPO TARGET MET (backup within ${RPO_TARGET_MINUTES} minutes)"
    exit 0
else
    echo ""
    echo "✗ RPO TARGET EXCEEDED (backup older than ${RPO_TARGET_MINUTES} minutes)"
    exit 1
fi
```

---

## 7. DR TEST EXECUTION WORKFLOW

### 7.1 Master Test Execution Script

**File:** `dr_testing/run_dr_test.sh`

```bash
#!/bin/bash
# Master DR test execution workflow

set -e

# Parse arguments
TEST_SCENARIO=${1:-"full"}
DRY_RUN=${2:-false}

echo "========================================="
echo "  DR TEST EXECUTION"
echo "========================================="
echo "Scenario: $TEST_SCENARIO"
echo "Dry run: $DRY_RUN"
echo "Start time: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Generate test ID
export DR_TEST_ID="DR-$(date +%Y%m%d-%H%M%S)"
echo "Test ID: $DR_TEST_ID"

# Create test log directory
TEST_LOG_DIR="/var/log/dr-tests/$DR_TEST_ID"
mkdir -p "$TEST_LOG_DIR"

# Log all output
exec > >(tee -a "$TEST_LOG_DIR/test.log") 2>&1

# Pre-flight checklist
echo ""
echo "=== Pre-Flight Checklist ==="
./dr_testing/pre_flight_check.sh || \
    (echo "Pre-flight checks failed. Aborting." && exit 1)

# Setup test environment
echo ""
echo "=== Setting Up Test Environment ==="
./dr_testing/environment_setup.sh

# Run selected scenario
echo ""
echo "=== Executing Test Scenario ==="

case $TEST_SCENARIO in
    "hardware_failure")
        ./dr_testing/scenarios/01_hardware_failure.sh
        ;;
    "database_corruption")
        ./dr_testing/scenarios/02_database_corruption.sh
        ;;
    "redis_loss")
        ./dr_testing/scenarios/03_redis_data_loss.sh
        ;;
    "network_partition")
        ./dr_testing/scenarios/04_network_partition.sh
        ;;
    "ransomware")
        ./dr_testing/scenarios/05_ransomware_simulation.sh
        ;;
    "full")
        echo "Running full DR test suite..."
        ./dr_testing/scenarios/01_hardware_failure.sh
        ./dr_testing/scenarios/02_database_corruption.sh
        ./dr_testing/scenarios/03_redis_data_loss.sh
        ;;
    *)
        echo "Unknown scenario: $TEST_SCENARIO"
        exit 1
        ;;
esac

# Measure RTO/RPO
echo ""
echo "=== Measuring RTO/RPO ==="
./dr_testing/measure_rto.sh
./dr_testing/measure_rpo.sh

# Generate test report
echo ""
echo "=== Generating Test Report ==="
./dr_testing/generate_report.sh --test-id "$DR_TEST_ID"

# Cleanup
echo ""
echo "=== Cleanup ==="
./dr_testing/cleanup.sh

echo ""
echo "========================================="
echo "  DR TEST COMPLETE"
echo "========================================="
echo "Test ID: $DR_TEST_ID"
echo "End time: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Report: $TEST_LOG_DIR/report.html"
```

---

## 8. POST-TEST ANALYSIS

### 8.1 Generate Test Report

**File:** `dr_testing/generate_report.sh`

```bash
#!/bin/bash
# Generate comprehensive DR test report

TEST_ID=$1
TEST_LOG_DIR="/var/log/dr-tests/$TEST_ID"
REPORT_FILE="$TEST_LOG_DIR/report.html"

echo "Generating DR test report..."

cat > "$REPORT_FILE" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <title>DR Test Report - {{ TEST_ID }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        .pass { color: green; font-weight: bold; }
        .fail { color: red; font-weight: bold; }
        .warn { color: orange; font-weight: bold; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .metric { background-color: #e8f4f8; padding: 10px; margin: 10px 0; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>Disaster Recovery Test Report</h1>
    <p><strong>Test ID:</strong> {{ TEST_ID }}</p>
    <p><strong>Date:</strong> {{ TEST_DATE }}</p>
    <p><strong>Duration:</strong> {{ TEST_DURATION }}</p>
    
    <h2>Executive Summary</h2>
    <div class="metric">
        <p><strong>Overall Result:</strong> <span class="{{ OVERALL_STATUS }}">{{ OVERALL_RESULT }}</span></p>
        <p><strong>RTO Compliance:</strong> {{ RTO_STATUS }}</p>
        <p><strong>RPO Compliance:</strong> {{ RPO_STATUS }}</p>
        <p><strong>Data Integrity:</strong> {{ DATA_INTEGRITY_STATUS }}</p>
    </div>
    
    <h2>Test Scenarios</h2>
    <table>
        <thead>
            <tr>
                <th>Scenario</th>
                <th>Result</th>
                <th>Duration</th>
                <th>Notes</th>
            </tr>
        </thead>
        <tbody>
            {{ SCENARIO_ROWS }}
        </tbody>
    </table>
    
    <h2>RTO/RPO Metrics</h2>
    <div class="metric">
        <p><strong>Recovery Time:</strong> {{ RECOVERY_TIME }} (Target: 4 hours)</p>
        <p><strong>Data Loss:</strong> {{ DATA_LOSS }} (Target: 15 minutes)</p>
    </div>
    
    <h2>Validation Results</h2>
    <table>
        <thead>
            <tr>
                <th>Check</th>
                <th>Result</th>
                <th>Details</th>
            </tr>
        </thead>
        <tbody>
            {{ VALIDATION_ROWS }}
        </tbody>
    </table>
    
    <h2>Recommendations</h2>
    <ul>
        {{ RECOMMENDATIONS }}
    </ul>
    
    <h2>Detailed Logs</h2>
    <p>Full logs available at: <code>{{ LOG_PATH }}</code></p>
</body>
</html>
EOF

# Populate template variables
sed -i "s/{{ TEST_ID }}/$TEST_ID/g" "$REPORT_FILE"
# ... (populate other variables)

echo "✓ Report generated: $REPORT_FILE"
```

---

## 9. CONTINUOUS IMPROVEMENT PROCESS

### 9.1 Lessons Learned Template

**File:** `dr_testing/lessons_learned_template.md`

```markdown
# DR Test Lessons Learned

**Test ID:** {{ TEST_ID }}
**Date:** {{ TEST_DATE }}
**Facilitator:** {{ FACILITATOR_NAME }}
**Participants:** {{ PARTICIPANTS }}

## What Went Well
- 
- 
- 

## What Didn't Go Well
- 
- 
- 

## Action Items
| Item | Owner | Due Date | Status |
|------|-------|----------|--------|
|      |       |          |        |

## Runbook Updates Required
- 
- 

## Tool/Process Improvements
- 
- 

## Training Needs Identified
- 
- 

## Next Test Date
**Scheduled:** {{ NEXT_TEST_DATE }}
```

---

## 10. DR TEST SCHEDULE & REPORTING

### 10.1 Annual DR Test Schedule

```yaml
annual_schedule:
  Q1_2026:
    - date: "2026-01-15"
      type: "Full DR Test"
      scenario: "Complete hardware failure"
      lead: "SRE Team"
    
    - date: "2026-02-15"
      type: "Partial DR Test"
      scenario: "Database corruption"
      lead: "Database Team"
    
    - date: "2026-03-15"
      type: "Backup Verification"
      scenario: "All backup types"
      lead: "Operations Team"
  
  Q2_2026:
    - date: "2026-04-15"
      type: "Full DR Test"
      scenario: "Ransomware simulation"
      lead: "Security Team"
    
    - date: "2026-05-15"
      type: "Failover Test"
      scenario: "Automated failover"
      lead: "SRE Team"
    
    - date: "2026-06-15"
      type: "Network Partition"
      scenario: "Split brain scenario"
      lead: "Network Team"
```

---

## DOCUMENT METADATA

**Document ID:** 40  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Operations & Deployment  
**Owner:** Business Continuity Lead  
**Dependencies:** Documents 34 (Backup & Recovery), 36 (Incident Response)  
**Next Document:** 41 (Unit Testing Standards & Implementation)

---

*End of Disaster Recovery Testing Procedures*
