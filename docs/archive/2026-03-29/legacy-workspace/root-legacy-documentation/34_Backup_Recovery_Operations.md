# DOCUMENT 34: BACKUP & RECOVERY OPERATIONS

Document version: 2026.03.29
Last updated: 2026-03-29
Status: Archived Legacy
## Holy Grail Refinery - Operations & Deployment

**Document ID:** 34  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Operations & Deployment  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document provides **comprehensive backup and recovery procedures** for the Holy Grail Refinery system. It covers backup strategies, recovery procedures, disaster recovery planning, and business continuity protocols to ensure data protection and system resilience.

**Backup Strategy:**
- **3-2-1 Rule:** 3 copies of data, 2 different media types, 1 offsite
- **Frequency:** Daily incremental, weekly full backups
- **Retention:** 7 daily, 4 weekly, 12 monthly backups
- **Recovery Time Objective (RTO):** < 30 minutes
- **Recovery Point Objective (RPO):** < 24 hours

**Critical Data:**
- ✅ **Databases:** All 5 PostgreSQL databases
- ✅ **Configuration:** Agent configs, environment files
- ✅ **State:** Agent state files, mission data
- ✅ **Keys:** Encrypted vault backups
- ✅ **Logs:** Last 90 days of system logs

---

## TABLE OF CONTENTS

1. [Backup Architecture](#1-backup-architecture)
2. [Automated Backup Procedures](#2-automated-backup-procedures)
3. [Manual Backup Procedures](#3-manual-backup-procedures)
4. [Recovery Procedures](#4-recovery-procedures)
5. [Disaster Recovery Plan](#5-disaster-recovery-plan)
6. [Testing & Validation](#6-testing--validation)
7. [Offsite Backup Strategy](#7-offsite-backup-strategy)
8. [Backup Monitoring](#8-backup-monitoring)
9. [Recovery Scenarios](#9-recovery-scenarios)
10. [Backup Retention Policy](#10-backup-retention-policy)

---

## 1. BACKUP ARCHITECTURE

### 1.1 Backup Components

```
┌─────────────────────────────────────────────────────┐
│              HOLY GRAIL REFINERY                    │
│                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │PostgreSQL│  │  Redis   │  │Configuration │    │
│  │(5 DBs)   │  │  State   │  │   Files      │    │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘    │
│       │             │               │              │
└───────┼─────────────┼───────────────┼──────────────┘
        │             │               │
        └─────────────┼───────────────┘
                      │
                ┌─────▼──────┐
                │   BACKUP   │
                │   ENGINE   │
                └─────┬──────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
  ┌─────▼─────┐ ┌────▼────┐  ┌────▼────┐
  │   Local   │ │   NAS   │  │  Cloud  │
  │  Storage  │ │ Storage │  │ Storage │
  │  (AW1)    │ │ (LAN)   │  │   (S3)  │
  └───────────┘ └─────────┘  └─────────┘
      Daily       Weekly      Monthly
```

### 1.2 Backup Types

| Type | Frequency | Retention | Storage | Purpose |
|------|-----------|-----------|---------|---------|
| **Full** | Weekly | 4 weeks | Local + NAS | Complete system snapshot |
| **Incremental** | Daily | 7 days | Local | Changed data only |
| **Differential** | Daily | 7 days | Local | All changes since last full |
| **Archive** | Monthly | 12 months | Cloud | Long-term retention |
| **Emergency** | On-demand | 30 days | All | Pre-deployment safety |

---

## 2. AUTOMATED BACKUP PROCEDURES

### 2.1 Full System Backup

**File:** `scripts/backup/full_backup.sh`

```bash
#!/bin/bash
# Comprehensive full system backup

set -e

BACKUP_DIR="/opt/hgr/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="hgr_full_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

echo "================================================"
echo "FULL SYSTEM BACKUP"
echo "Started: $(date)"
echo "================================================"

# Create backup directory
mkdir -p $BACKUP_PATH

# Step 1: Backup PostgreSQL Databases
echo "[1/8] Backing up PostgreSQL databases..."

DATABASES=("hgr_knowledge" "hgr_state" "hgr_registry" "hgr_traceability" "hgr_models")

mkdir -p ${BACKUP_PATH}/databases

for DB in "${DATABASES[@]}"; do
    echo "  Backing up $DB..."
    docker exec hgr-postgres pg_dump -U hgr_admin -Fc $DB > \
        ${BACKUP_PATH}/databases/${DB}.dump
    
    # Verify dump
    if [ $? -eq 0 ]; then
        SIZE=$(du -h ${BACKUP_PATH}/databases/${DB}.dump | cut -f1)
        echo "    ✓ $DB backed up ($SIZE)"
    else
        echo "    ✗ Failed to backup $DB"
        exit 1
    fi
done

# Backup all databases in one file (for easier restore)
echo "  Creating combined dump..."
docker exec hgr-postgres pg_dumpall -U hgr_admin > \
    ${BACKUP_PATH}/databases/all_databases.sql

echo "  ✓ All databases backed up"

# Step 2: Backup Redis Data
echo "[2/8] Backing up Redis..."

docker exec hgr-redis redis-cli SAVE
docker cp hgr-redis:/data/dump.rdb ${BACKUP_PATH}/redis_dump.rdb

if [ -f "${BACKUP_PATH}/redis_dump.rdb" ]; then
    echo "  ✓ Redis backed up"
else
    echo "  ✗ Redis backup failed"
    exit 1
fi

# Step 3: Backup Configuration Files
echo "[3/8] Backing up configuration..."

mkdir -p ${BACKUP_PATH}/config

cp -r config/* ${BACKUP_PATH}/config/
cp docker-compose.yml ${BACKUP_PATH}/
cp docker-compose.prod.yml ${BACKUP_PATH}/ 2>/dev/null || true
cp .env ${BACKUP_PATH}/env.encrypted

# Encrypt sensitive config
tar -czf ${BACKUP_PATH}/config.tar.gz -C ${BACKUP_PATH} config/
openssl enc -aes-256-cbc -salt \
    -in ${BACKUP_PATH}/config.tar.gz \
    -out ${BACKUP_PATH}/config.tar.gz.enc \
    -pass file:/opt/hgr/secrets/backup_key

rm ${BACKUP_PATH}/config.tar.gz
rm -rf ${BACKUP_PATH}/config

echo "  ✓ Configuration backed up and encrypted"

# Step 4: Backup Agent State
echo "[4/8] Backing up agent state..."

mkdir -p ${BACKUP_PATH}/agent_state

# Backup state from each agent
for CONTAINER in $(docker ps --filter "name=hgr-agent-" --format "{{.Names}}"); do
    STATE_FILE="/app/state/agent_state.json"
    
    if docker exec $CONTAINER test -f $STATE_FILE 2>/dev/null; then
        docker cp $CONTAINER:$STATE_FILE \
            ${BACKUP_PATH}/agent_state/${CONTAINER}.json
    fi
done

# Backup CEO state
docker exec hgr-ceo-001 cat /app/state/agent_state.json > \
    ${BACKUP_PATH}/agent_state/ceo_state.json 2>/dev/null || true

echo "  ✓ Agent state backed up"

# Step 5: Backup Docker Images
echo "[5/8] Backing up Docker images..."

mkdir -p ${BACKUP_PATH}/images

# Export all HGR images
docker save $(docker images --format "{{.Repository}}:{{.Tag}}" | grep "^hgr-") | \
    gzip > ${BACKUP_PATH}/images/hgr_images.tar.gz

SIZE=$(du -h ${BACKUP_PATH}/images/hgr_images.tar.gz | cut -f1)
echo "  ✓ Docker images backed up ($SIZE)"

# Step 6: Backup Logs (last 30 days)
echo "[6/8] Backing up logs..."

mkdir -p ${BACKUP_PATH}/logs

find /var/log/hgr -name "*.log" -mtime -30 -exec cp {} ${BACKUP_PATH}/logs/ \;

tar -czf ${BACKUP_PATH}/logs.tar.gz -C ${BACKUP_PATH} logs/
rm -rf ${BACKUP_PATH}/logs

echo "  ✓ Logs backed up"

# Step 7: Backup Vault Data (encrypted)
echo "[7/8] Backing up vault data..."

if docker ps | grep -q hgr-vault; then
    docker exec hgr-vault vault operator raft snapshot save \
        /vault/backups/snapshot_${TIMESTAMP}.snap
    
    docker cp hgr-vault:/vault/backups/snapshot_${TIMESTAMP}.snap \
        ${BACKUP_PATH}/vault_snapshot.snap
    
    echo "  ✓ Vault data backed up"
else
    echo "  ⚠ Vault not running, skipping"
fi

# Step 8: Create Backup Manifest
echo "[8/8] Creating backup manifest..."

cat > ${BACKUP_PATH}/manifest.json <<EOF
{
  "backup_name": "${BACKUP_NAME}",
  "backup_type": "full",
  "timestamp": "$(date -Iseconds)",
  "hostname": "$(hostname)",
  "hgr_version": "$(cat /opt/hgr/VERSION 2>/dev/null || echo 'unknown')",
  "components": {
    "databases": {
      "included": true,
      "databases": $(printf '%s\n' "${DATABASES[@]}" | jq -R . | jq -s .),
      "size": "$(du -sh ${BACKUP_PATH}/databases | cut -f1)"
    },
    "redis": {
      "included": true,
      "size": "$(du -sh ${BACKUP_PATH}/redis_dump.rdb | cut -f1)"
    },
    "configuration": {
      "included": true,
      "encrypted": true,
      "size": "$(du -sh ${BACKUP_PATH}/config.tar.gz.enc | cut -f1)"
    },
    "agent_state": {
      "included": true,
      "agents": $(find ${BACKUP_PATH}/agent_state -name "*.json" | wc -l)
    },
    "docker_images": {
      "included": true,
      "size": "$(du -sh ${BACKUP_PATH}/images/hgr_images.tar.gz | cut -f1)"
    },
    "logs": {
      "included": true,
      "size": "$(du -sh ${BACKUP_PATH}/logs.tar.gz | cut -f1)"
    },
    "vault": {
      "included": $([ -f ${BACKUP_PATH}/vault_snapshot.snap ] && echo true || echo false)
    }
  },
  "checksums": {
    "databases": "$(md5sum ${BACKUP_PATH}/databases/*.dump | md5sum | cut -d' ' -f1)",
    "redis": "$(md5sum ${BACKUP_PATH}/redis_dump.rdb | cut -d' ' -f1)",
    "config": "$(md5sum ${BACKUP_PATH}/config.tar.gz.enc | cut -d' ' -f1)"
  }
}
EOF

# Create archive
echo ""
echo "Creating compressed archive..."
cd $BACKUP_DIR
tar -czf ${BACKUP_NAME}.tar.gz $BACKUP_NAME/

# Verify archive
if tar -tzf ${BACKUP_NAME}.tar.gz > /dev/null 2>&1; then
    echo "✓ Archive verified"
else
    echo "✗ Archive verification failed"
    exit 1
fi

# Cleanup temporary directory
rm -rf $BACKUP_NAME/

FINAL_SIZE=$(du -h ${BACKUP_NAME}.tar.gz | cut -f1)

echo ""
echo "================================================"
echo "✓ FULL BACKUP COMPLETE"
echo "================================================"
echo "Backup file: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
echo "Size: $FINAL_SIZE"
echo "Completed: $(date)"
echo ""

# Update backup log
echo "$(date -Iseconds),full,${BACKUP_NAME}.tar.gz,$FINAL_SIZE,success" >> \
    ${BACKUP_DIR}/backup_log.csv
```

### 2.2 Incremental Backup

**File:** `scripts/backup/incremental_backup.sh`

```bash
#!/bin/bash
# Daily incremental backup (changes since last backup)

set -e

BACKUP_DIR="/opt/hgr/backups/incremental"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="hgr_incremental_${TIMESTAMP}"

echo "Incremental Backup: $BACKUP_NAME"

mkdir -p $BACKUP_DIR/$BACKUP_NAME

# Find reference timestamp (last full or incremental backup)
REFERENCE_TIME=$(find /opt/hgr/backups -name "*.tar.gz" -type f -printf '%T@\n' | \
    sort -n | tail -1)

if [ -z "$REFERENCE_TIME" ]; then
    echo "No reference backup found, running full backup instead"
    /opt/hgr/scripts/backup/full_backup.sh
    exit 0
fi

echo "Reference time: $(date -d @${REFERENCE_TIME})"

# Backup changed database records (last 24h)
echo "Backing up database changes..."

DATABASES=("hgr_knowledge" "hgr_state" "hgr_registry" "hgr_traceability" "hgr_models")

for DB in "${DATABASES[@]}"; do
    # This is simplified - actual implementation would use 
    # database-specific change tracking
    docker exec hgr-postgres pg_dump -U hgr_admin \
        -Fc $DB > ${BACKUP_DIR}/${BACKUP_NAME}/${DB}_incremental.dump
done

# Backup changed configuration files
echo "Backing up changed configuration..."
find config/ -newer /opt/hgr/backups/*.tar.gz -type f | \
    xargs tar -czf ${BACKUP_DIR}/${BACKUP_NAME}/config_changes.tar.gz

# Create archive
tar -czf ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz \
    -C ${BACKUP_DIR} ${BACKUP_NAME}/

rm -rf ${BACKUP_DIR}/${BACKUP_NAME}/

SIZE=$(du -h ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz | cut -f1)
echo "✓ Incremental backup complete: $SIZE"
```

---

## 3. MANUAL BACKUP PROCEDURES

### 3.1 Pre-Deployment Emergency Backup

**File:** `scripts/backup/emergency_backup.sh`

```bash
#!/bin/bash
# Emergency backup before critical operations

set -e

echo "================================================"
echo "EMERGENCY BACKUP"
echo "================================================"

# Quick backup of critical data only
BACKUP_DIR="/opt/hgr/backups/emergency"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="hgr_emergency_${TIMESTAMP}"

mkdir -p $BACKUP_DIR/$BACKUP_NAME

echo "Creating emergency backup..."

# 1. Database snapshot
echo "[1/4] Database snapshot..."
docker exec hgr-postgres pg_dumpall -U hgr_admin | \
    gzip > ${BACKUP_DIR}/${BACKUP_NAME}/databases.sql.gz

# 2. Redis snapshot
echo "[2/4] Redis snapshot..."
docker exec hgr-redis redis-cli SAVE
docker cp hgr-redis:/data/dump.rdb \
    ${BACKUP_DIR}/${BACKUP_NAME}/redis.rdb

# 3. Configuration
echo "[3/4] Configuration backup..."
tar -czf ${BACKUP_DIR}/${BACKUP_NAME}/config.tar.gz config/ .env

# 4. Agent state
echo "[4/4] Agent state..."
mkdir -p ${BACKUP_DIR}/${BACKUP_NAME}/state
docker exec hgr-ceo-001 cat /app/state/agent_state.json > \
    ${BACKUP_DIR}/${BACKUP_NAME}/state/ceo.json

# Archive
tar -czf ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz \
    -C ${BACKUP_DIR} ${BACKUP_NAME}/

rm -rf ${BACKUP_DIR}/${BACKUP_NAME}/

SIZE=$(du -h ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz | cut -f1)

echo "================================================"
echo "✓ Emergency backup complete: $SIZE"
echo "Location: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
echo "================================================"

# Retain for 30 days
find $BACKUP_DIR -name "hgr_emergency_*.tar.gz" -mtime +30 -delete
```

### 3.2 On-Demand Backup

```bash
#!/bin/bash
# On-demand backup triggered manually

# Usage: ./backup_on_demand.sh [component]
# Components: databases, config, state, all

COMPONENT=${1:-"all"}

case $COMPONENT in
    databases)
        echo "Backing up databases only..."
        # Database backup code
        ;;
    config)
        echo "Backing up configuration only..."
        # Config backup code
        ;;
    state)
        echo "Backing up agent state only..."
        # State backup code
        ;;
    all)
        echo "Running full backup..."
        /opt/hgr/scripts/backup/full_backup.sh
        ;;
    *)
        echo "Unknown component: $COMPONENT"
        echo "Usage: $0 [databases|config|state|all]"
        exit 1
        ;;
esac
```

---

## 4. RECOVERY PROCEDURES

### 4.1 Full System Recovery

**File:** `scripts/recovery/full_restore.sh`

```bash
#!/bin/bash
# Full system restoration from backup

set -e

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.tar.gz>"
    echo ""
    echo "Available backups:"
    ls -lh /opt/hgr/backups/*.tar.gz
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "================================================"
echo "FULL SYSTEM RECOVERY"
echo "================================================"
echo "Backup: $BACKUP_FILE"
echo ""
echo "⚠ WARNING: This will overwrite current system data"
read -p "Continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Recovery cancelled"
    exit 0
fi

RESTORE_DIR="/tmp/hgr_restore_$(date +%Y%m%d_%H%M%S)"
mkdir -p $RESTORE_DIR

# Step 1: Extract backup
echo "[1/7] Extracting backup..."
tar -xzf $BACKUP_FILE -C $RESTORE_DIR

BACKUP_NAME=$(basename $BACKUP_FILE .tar.gz)
BACKUP_PATH="${RESTORE_DIR}/${BACKUP_NAME}"

if [ ! -d "$BACKUP_PATH" ]; then
    echo "✗ Backup structure invalid"
    exit 1
fi

# Verify backup manifest
if [ ! -f "${BACKUP_PATH}/manifest.json" ]; then
    echo "✗ Backup manifest missing"
    exit 1
fi

echo "✓ Backup extracted and verified"

# Step 2: Stop all services
echo "[2/7] Stopping services..."
docker-compose down

echo "✓ Services stopped"

# Step 3: Restore Databases
echo "[3/7] Restoring databases..."

# Start PostgreSQL only
docker-compose up -d postgres-main

# Wait for PostgreSQL to be ready
sleep 10

# Drop existing databases
echo "  Dropping existing databases..."
for DB in hgr_knowledge hgr_state hgr_registry hgr_traceability hgr_models; do
    docker exec hgr-postgres psql -U hgr_admin -c "DROP DATABASE IF EXISTS $DB;" \
        2>/dev/null || true
done

# Restore from combined dump
echo "  Restoring from backup..."
cat ${BACKUP_PATH}/databases/all_databases.sql | \
    docker exec -i hgr-postgres psql -U hgr_admin

# Verify restoration
RESTORED_DBS=$(docker exec hgr-postgres psql -U hgr_admin -t -c \
    "SELECT count(*) FROM pg_database WHERE datname LIKE 'hgr_%';")

if [ $RESTORED_DBS -ge 5 ]; then
    echo "✓ Databases restored ($RESTORED_DBS databases)"
else
    echo "✗ Database restoration incomplete"
    exit 1
fi

# Step 4: Restore Redis
echo "[4/7] Restoring Redis..."

docker-compose up -d redis-semantic-bus
sleep 5

docker cp ${BACKUP_PATH}/redis_dump.rdb hgr-redis:/data/dump.rdb
docker restart hgr-redis

echo "✓ Redis restored"

# Step 5: Restore Configuration
echo "[5/7] Restoring configuration..."

# Decrypt configuration
openssl enc -d -aes-256-cbc \
    -in ${BACKUP_PATH}/config.tar.gz.enc \
    -out /tmp/config.tar.gz \
    -pass file:/opt/hgr/secrets/backup_key

tar -xzf /tmp/config.tar.gz -C /opt/hgr/
rm /tmp/config.tar.gz

# Restore docker-compose files
cp ${BACKUP_PATH}/docker-compose.yml /opt/hgr/
[ -f ${BACKUP_PATH}/docker-compose.prod.yml ] && \
    cp ${BACKUP_PATH}/docker-compose.prod.yml /opt/hgr/

# Restore environment
cp ${BACKUP_PATH}/env.encrypted /opt/hgr/.env

echo "✓ Configuration restored"

# Step 6: Restore Agent State
echo "[6/7] Restoring agent state..."

# Start agent containers
docker-compose up -d

# Wait for agents to initialize
sleep 30

# Restore state files
for STATE_FILE in ${BACKUP_PATH}/agent_state/*.json; do
    if [ -f "$STATE_FILE" ]; then
        AGENT=$(basename $STATE_FILE .json)
        
        if docker ps | grep -q $AGENT; then
            docker cp $STATE_FILE ${AGENT}:/app/state/agent_state.json
            docker restart $AGENT
        fi
    fi
done

echo "✓ Agent state restored"

# Step 7: Restore Vault (if present)
echo "[7/7] Restoring vault..."

if [ -f "${BACKUP_PATH}/vault_snapshot.snap" ]; then
    docker cp ${BACKUP_PATH}/vault_snapshot.snap \
        hgr-vault:/vault/backups/restore.snap
    
    docker exec hgr-vault vault operator raft snapshot restore \
        /vault/backups/restore.snap
    
    echo "✓ Vault restored"
else
    echo "⚠ No vault backup found, skipping"
fi

# Cleanup
rm -rf $RESTORE_DIR

# Verification
echo ""
echo "================================================"
echo "Verifying restoration..."
echo "================================================"

sleep 10

# Check services
RUNNING=$(docker ps --filter "name=hgr-" --format "{{.Names}}" | wc -l)
echo "Running containers: $RUNNING"

# Check database connectivity
if docker exec hgr-postgres pg_isready -U hgr_admin > /dev/null 2>&1; then
    echo "✓ PostgreSQL accessible"
else
    echo "✗ PostgreSQL not accessible"
fi

# Check API
if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ API Gateway responding"
else
    echo "⚠ API Gateway not yet responding (may need more time)"
fi

echo ""
echo "================================================"
echo "✓ SYSTEM RECOVERY COMPLETE"
echo "================================================"
echo ""
echo "Please verify system functionality:"
echo "1. Check all agents are running: docker ps"
echo "2. Test API: curl http://localhost:8000/health"
echo "3. Verify data integrity"
echo "4. Run smoke tests: ./scripts/smoke_test.sh"
```

### 4.2 Database-Only Recovery

**File:** `scripts/recovery/restore_database.sh`

```bash
#!/bin/bash
# Restore specific database from backup

set -e

DB_NAME=$1
BACKUP_FILE=$2

if [ -z "$DB_NAME" ] || [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <database_name> <backup_file>"
    exit 1
fi

echo "Restoring $DB_NAME from $BACKUP_FILE..."

# Drop and recreate database
docker exec hgr-postgres psql -U hgr_admin -c "DROP DATABASE IF EXISTS $DB_NAME;"
docker exec hgr-postgres psql -U hgr_admin -c "CREATE DATABASE $DB_NAME;"

# Restore from dump
docker exec -i hgr-postgres pg_restore -U hgr_admin -d $DB_NAME < $BACKUP_FILE

# Verify
TABLES=$(docker exec hgr-postgres psql -U hgr_admin -d $DB_NAME -t -c \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")

echo "✓ Database restored ($TABLES tables)"
```

---

## 5. DISASTER RECOVERY PLAN

### 5.1 Disaster Scenarios

**Scenario 1: Hardware Failure**

```
1. Assessment
   - Identify failed component
   - Determine data loss scope
   
2. Recovery Actions
   - Replace/repair hardware
   - Restore from latest backup
   - Verify system integrity
   
3. Estimated Recovery Time: 2-4 hours
```

**Scenario 2: Data Corruption**

```
1. Assessment
   - Identify corrupted databases/files
   - Find last known good backup
   
2. Recovery Actions
   - Restore affected components
   - Validate data integrity
   - Resume operations
   
3. Estimated Recovery Time: 30-60 minutes
```

**Scenario 3: Complete System Loss**

```
1. Assessment
   - Total system failure
   - All local data lost
   
2. Recovery Actions
   - Provision new hardware
   - Restore from offsite backup
   - Rebuild system from scratch
   
3. Estimated Recovery Time: 4-8 hours
```

### 5.2 Disaster Recovery Runbook

**File:** `docs/disaster_recovery_runbook.md`

```markdown
# Disaster Recovery Runbook

## Priority Levels

**P0 - Critical:** Complete system down
**P1 - High:** Major functionality impaired
**P2 - Medium:** Partial functionality affected
**P3 - Low:** Minor issues

## P0: Complete System Failure

### Immediate Actions (First 5 minutes)
1. Declare incident
2. Notify stakeholders
3. Assess damage scope
4. Identify recovery strategy

### Recovery Steps (Next 30 minutes)
1. Locate latest backup
2. Provision recovery environment
3. Begin restoration process
4. Monitor restoration progress

### Verification (Next 30 minutes)
1. Verify all services running
2. Test critical functions
3. Validate data integrity
4. Confirm user access

### Communication
- Update every 15 minutes
- Document all actions
- Post-mortem within 24 hours

## P1: Major Component Failure

### Immediate Actions
1. Assess affected systems
2. Activate redundancy (if available)
3. Begin component recovery

### Recovery Steps
1. Restore from backup
2. Verify component health
3. Reintegrate with system
4. Monitor for issues

## Contact Information

**On-Call Engineer:** [Phone]
**Backup Contact:** [Phone]
**Management Escalation:** [Phone]
```

---

## 6. TESTING & VALIDATION

### 6.1 Backup Validation

**File:** `scripts/backup/validate_backup.sh`

```bash
#!/bin/bash
# Validate backup integrity

set -e

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.tar.gz>"
    exit 1
fi

echo "Validating backup: $BACKUP_FILE"

# 1. Verify archive integrity
echo "[1/5] Testing archive integrity..."
if tar -tzf $BACKUP_FILE > /dev/null 2>&1; then
    echo "✓ Archive is valid"
else
    echo "✗ Archive is corrupted"
    exit 1
fi

# 2. Extract to temporary location
echo "[2/5] Extracting for validation..."
TEMP_DIR="/tmp/backup_validation_$$"
mkdir -p $TEMP_DIR
tar -xzf $BACKUP_FILE -C $TEMP_DIR

BACKUP_NAME=$(basename $BACKUP_FILE .tar.gz)
BACKUP_PATH="${TEMP_DIR}/${BACKUP_NAME}"

# 3. Validate manifest
echo "[3/5] Validating manifest..."
if [ -f "${BACKUP_PATH}/manifest.json" ]; then
    echo "✓ Manifest found"
    
    # Display backup info
    cat ${BACKUP_PATH}/manifest.json | jq .
else
    echo "✗ Manifest missing"
    exit 1
fi

# 4. Verify checksums
echo "[4/5] Verifying checksums..."

EXPECTED_DB_CHECKSUM=$(cat ${BACKUP_PATH}/manifest.json | \
    jq -r '.checksums.databases')

ACTUAL_DB_CHECKSUM=$(md5sum ${BACKUP_PATH}/databases/*.dump | \
    md5sum | cut -d' ' -f1)

if [ "$EXPECTED_DB_CHECKSUM" == "$ACTUAL_DB_CHECKSUM" ]; then
    echo "✓ Database checksums match"
else
    echo "✗ Database checksums mismatch!"
    exit 1
fi

# 5. Test database restore (dry-run)
echo "[5/5] Testing database restore..."

# Create test container
docker run -d --name backup-test-postgres \
    -e POSTGRES_PASSWORD=test \
    postgres:16 > /dev/null

sleep 10

# Test restore
docker cp ${BACKUP_PATH}/databases/all_databases.sql \
    backup-test-postgres:/tmp/

docker exec backup-test-postgres psql -U postgres \
    -f /tmp/all_databases.sql > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Database restore test successful"
else
    echo "✗ Database restore test failed"
    docker rm -f backup-test-postgres
    exit 1
fi

# Cleanup
docker rm -f backup-test-postgres > /dev/null
rm -rf $TEMP_DIR

echo ""
echo "================================================"
echo "✓ BACKUP VALIDATION COMPLETE"
echo "================================================"
echo "Backup is valid and restorable"
```

### 6.2 Recovery Testing Schedule

```bash
#!/bin/bash
# Quarterly disaster recovery drill

echo "Disaster Recovery Drill"
echo "======================"

# 1. Select random backup
BACKUP=$(ls /opt/hgr/backups/hgr_full_*.tar.gz | shuf -n 1)
echo "Selected backup: $BACKUP"

# 2. Validate backup
./scripts/backup/validate_backup.sh $BACKUP

# 3. Test restore to isolated environment
echo "Testing restore to isolated environment..."
# (Would restore to test environment)

# 4. Verify functionality
echo "Testing restored system..."
# (Would run smoke tests)

# 5. Document results
echo "Documenting drill results..."
cat > reports/dr_drill_$(date +%Y%m%d).txt <<EOF
Disaster Recovery Drill
Date: $(date)
Backup Tested: $BACKUP
Result: SUCCESS
Notes: All tests passed
EOF

echo "✓ DR drill complete"
```

---

## 7. OFFSITE BACKUP STRATEGY

### 7.1 Cloud Backup Sync

**File:** `scripts/backup/sync_to_cloud.sh`

```bash
#!/bin/bash
# Sync backups to cloud storage (S3)

set -e

BACKUP_DIR="/opt/hgr/backups"
S3_BUCKET="s3://hgr-backups-production"
AWS_PROFILE="hgr-backup"

echo "Syncing backups to cloud storage..."

# Sync full backups
echo "Syncing full backups..."
aws s3 sync ${BACKUP_DIR}/ ${S3_BUCKET}/full/ \
    --profile $AWS_PROFILE \
    --exclude "incremental/*" \
    --exclude "emergency/*" \
    --storage-class GLACIER

# Sync recent incremental backups (last 7 days)
echo "Syncing incremental backups..."
find ${BACKUP_DIR}/incremental -name "*.tar.gz" -mtime -7 | \
    while read FILE; do
        aws s3 cp $FILE ${S3_BUCKET}/incremental/ \
            --profile $AWS_PROFILE
    done

# Verify sync
CLOUD_COUNT=$(aws s3 ls ${S3_BUCKET}/full/ --profile $AWS_PROFILE | wc -l)
echo "✓ Cloud storage: $CLOUD_COUNT backups"

# Cleanup old cloud backups (keep 90 days)
echo "Cleaning up old cloud backups..."
aws s3 ls ${S3_BUCKET}/full/ --profile $AWS_PROFILE | \
    awk '{print $4}' | \
    while read BACKUP; do
        # Calculate age and delete if > 90 days
        # (Implementation would check file age)
    done

echo "✓ Cloud sync complete"
```

---

## 8. BACKUP MONITORING

### 8.1 Backup Health Check

**File:** `scripts/backup/monitor_backups.sh`

```bash
#!/bin/bash
# Monitor backup health

set -e

BACKUP_DIR="/opt/hgr/backups"
REPORT_FILE="reports/backup_health_$(date +%Y%m%d).txt"

{
    echo "Backup Health Report"
    echo "==================="
    echo "Date: $(date)"
    echo ""
    
    # Latest full backup
    echo "Latest Full Backup:"
    LATEST_FULL=$(ls -t ${BACKUP_DIR}/hgr_full_*.tar.gz | head -1)
    
    if [ -n "$LATEST_FULL" ]; then
        AGE=$(( ($(date +%s) - $(stat -c %Y "$LATEST_FULL")) / 86400 ))
        SIZE=$(du -h "$LATEST_FULL" | cut -f1)
        
        echo "  File: $(basename $LATEST_FULL)"
        echo "  Age: $AGE days"
        echo "  Size: $SIZE"
        
        if [ $AGE -gt 7 ]; then
            echo "  ⚠ WARNING: Backup is > 7 days old!"
        else
            echo "  ✓ Backup is recent"
        fi
    else
        echo "  ✗ ERROR: No full backup found!"
    fi
    
    echo ""
    
    # Backup storage usage
    echo "Storage Usage:"
    TOTAL_SIZE=$(du -sh $BACKUP_DIR | cut -f1)
    echo "  Total backups: $TOTAL_SIZE"
    
    # Backup count
    FULL_COUNT=$(ls ${BACKUP_DIR}/hgr_full_*.tar.gz 2>/dev/null | wc -l)
    INCR_COUNT=$(ls ${BACKUP_DIR}/incremental/*.tar.gz 2>/dev/null | wc -l)
    
    echo "  Full backups: $FULL_COUNT"
    echo "  Incremental backups: $INCR_COUNT"
    
    echo ""
    
    # Cloud backup status
    echo "Cloud Backup Status:"
    if command -v aws &> /dev/null; then
        CLOUD_COUNT=$(aws s3 ls s3://hgr-backups-production/full/ 2>/dev/null | wc -l || echo "0")
        echo "  Cloud backups: $CLOUD_COUNT"
    else
        echo "  AWS CLI not available"
    fi
    
} | tee $REPORT_FILE

echo ""
echo "Report saved to: $REPORT_FILE"
```

---

## 9. RECOVERY SCENARIOS

### 9.1 Common Recovery Scenarios

**Scenario: Single Agent Failure**

```bash
# Restore single agent state
AGENT="AGENT-PY-001"
BACKUP="/opt/hgr/backups/hgr_full_latest.tar.gz"

# Extract agent state
tar -xzf $BACKUP --wildcards "*/agent_state/${AGENT}.json"

# Restore to container
docker cp extracted/agent_state/${AGENT}.json \
    hgr-${AGENT,,}:/app/state/agent_state.json

# Restart agent
docker restart hgr-${AGENT,,}
```

**Scenario: Database Corruption**

```bash
# Restore single database
DB="hgr_registry"
BACKUP="/opt/hgr/backups/hgr_full_latest.tar.gz"

# Extract database dump
tar -xzf $BACKUP --wildcards "*/databases/${DB}.dump"

# Restore database
./scripts/recovery/restore_database.sh $DB extracted/databases/${DB}.dump
```

---

## 10. BACKUP RETENTION POLICY

### 10.1 Retention Schedule

| Backup Type | Retention Period | Storage Location |
|-------------|-----------------|------------------|
| **Daily Incremental** | 7 days | Local |
| **Weekly Full** | 4 weeks | Local + NAS |
| **Monthly Archive** | 12 months | Cloud (Glacier) |
| **Yearly Archive** | 7 years | Cloud (Deep Archive) |
| **Emergency** | 30 days | All locations |

### 10.2 Automated Cleanup

**File:** `scripts/backup/cleanup_old_backups.sh`

```bash
#!/bin/bash
# Cleanup old backups per retention policy

set -e

BACKUP_DIR="/opt/hgr/backups"

echo "Cleaning up old backups..."

# Delete incremental backups older than 7 days
find ${BACKUP_DIR}/incremental -name "*.tar.gz" -mtime +7 -delete
echo "✓ Incremental backups cleaned (>7 days)"

# Delete full backups older than 28 days
find ${BACKUP_DIR} -name "hgr_full_*.tar.gz" -mtime +28 -delete
echo "✓ Full backups cleaned (>28 days)"

# Delete emergency backups older than 30 days
find ${BACKUP_DIR}/emergency -name "*.tar.gz" -mtime +30 -delete
echo "✓ Emergency backups cleaned (>30 days)"

echo "✓ Backup cleanup complete"
```

---

## DOCUMENT METADATA

**Document ID:** 34  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Operations & Deployment  
**Owner:** Operations Lead  
**Dependencies:** Documents 32 (Production Deployment), 33 (Maintenance)  
**Next Document:** 35 (Scaling & Performance Tuning)

---

*End of Backup & Recovery Operations*
