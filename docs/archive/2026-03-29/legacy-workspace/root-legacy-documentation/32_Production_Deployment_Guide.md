# DOCUMENT 32: PRODUCTION DEPLOYMENT GUIDE
## Holy Grail Refinery - Operations & Deployment

**Document ID:** 32  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Operations & Deployment  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

This document provides **comprehensive production deployment procedures** for the Holy Grail Refinery system on the AW1 hardware platform. It covers pre-deployment validation, deployment execution, verification procedures, rollback strategies, and post-deployment monitoring.

**Deployment Characteristics:**
- **Platform:** Local AW1 hardware (Docker containerized)
- **Strategy:** Blue-green deployment with zero downtime
- **Rollback Time:** < 5 minutes to previous stable state
- **Validation:** Automated smoke tests + manual verification
- **Monitoring:** 48-hour enhanced observation period

**Target Metrics:**
- 🎯 **Deployment Success Rate:** > 99%
- ⚡ **Deployment Duration:** < 30 minutes
- 🔄 **Recovery Time Objective (RTO):** < 5 minutes
- 📊 **Availability During Deployment:** 100%

---

## TABLE OF CONTENTS

1. [Pre-Deployment Checklist](#1-pre-deployment-checklist)
2. [Deployment Preparation](#2-deployment-preparation)
3. [Blue-Green Deployment Strategy](#3-blue-green-deployment-strategy)
4. [Deployment Execution](#4-deployment-execution)
5. [Smoke Testing & Validation](#5-smoke-testing--validation)
6. [Rollback Procedures](#6-rollback-procedures)
7. [Post-Deployment Monitoring](#7-post-deployment-monitoring)
8. [Deployment Scenarios](#8-deployment-scenarios)
9. [Emergency Procedures](#9-emergency-procedures)
10. [Deployment Checklists](#10-deployment-checklists)

---

## 1. PRE-DEPLOYMENT CHECKLIST

### 1.1 System Health Verification

**File:** `scripts/pre_deployment_check.sh`

```bash
#!/bin/bash
# Pre-deployment health check for Holy Grail Refinery

set -e

CHECKS_PASSED=0
CHECKS_TOTAL=10

echo "================================================"
echo "HOLY GRAIL REFINERY - PRE-DEPLOYMENT CHECK"
echo "================================================"
echo ""

# Check 1: Docker daemon running
echo "[1/10] Checking Docker daemon..."
if systemctl is-active --quiet docker; then
    echo "✓ Docker daemon is running"
    ((CHECKS_PASSED++))
else
    echo "✗ Docker daemon is not running"
fi

# Check 2: Disk space
echo "[2/10] Checking disk space..."
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -lt 80 ]; then
    echo "✓ Disk usage: ${DISK_USAGE}% (< 80%)"
    ((CHECKS_PASSED++))
else
    echo "✗ Disk usage critical: ${DISK_USAGE}%"
fi

# Check 3: Available memory
echo "[3/10] Checking available memory..."
AVAILABLE_MEM=$(free -g | awk 'NR==2 {print $7}')
if [ $AVAILABLE_MEM -gt 5 ]; then
    echo "✓ Available memory: ${AVAILABLE_MEM}GB (> 5GB)"
    ((CHECKS_PASSED++))
else
    echo "✗ Insufficient memory: ${AVAILABLE_MEM}GB"
fi

# Check 4: PostgreSQL connectivity
echo "[4/10] Checking PostgreSQL..."
if docker exec hgr-postgres pg_isready -U hgr_admin > /dev/null 2>&1; then
    echo "✓ PostgreSQL is ready"
    ((CHECKS_PASSED++))
else
    echo "✗ PostgreSQL is not accessible"
fi

# Check 5: Redis connectivity
echo "[5/10] Checking Redis..."
if docker exec hgr-redis redis-cli ping > /dev/null 2>&1; then
    echo "✓ Redis is responding"
    ((CHECKS_PASSED++))
else
    echo "✗ Redis is not accessible"
fi

# Check 6: All agent containers running
echo "[6/10] Checking agent containers..."
EXPECTED_AGENTS=35
RUNNING_AGENTS=$(docker ps --filter "name=hgr-agent-" --format "{{.Names}}" | wc -l)
if [ $RUNNING_AGENTS -eq $EXPECTED_AGENTS ]; then
    echo "✓ All $EXPECTED_AGENTS agents running"
    ((CHECKS_PASSED++))
else
    echo "✗ Expected $EXPECTED_AGENTS agents, found $RUNNING_AGENTS"
fi

# Check 7: No failed containers
echo "[7/10] Checking for failed containers..."
FAILED=$(docker ps -a --filter "status=exited" --filter "name=hgr-" --format "{{.Names}}" | wc -l)
if [ $FAILED -eq 0 ]; then
    echo "✓ No failed containers"
    ((CHECKS_PASSED++))
else
    echo "✗ $FAILED failed containers detected"
fi

# Check 8: API gateway health
echo "[8/10] Checking API gateway..."
if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ API gateway is healthy"
    ((CHECKS_PASSED++))
else
    echo "✗ API gateway health check failed"
fi

# Check 9: Backup exists
echo "[9/10] Checking recent backup..."
LATEST_BACKUP=$(ls -t backups/*.tar.gz 2>/dev/null | head -1)
if [ -n "$LATEST_BACKUP" ]; then
    BACKUP_AGE=$(( ($(date +%s) - $(stat -c %Y "$LATEST_BACKUP")) / 86400 ))
    if [ $BACKUP_AGE -lt 7 ]; then
        echo "✓ Recent backup found: $LATEST_BACKUP ($BACKUP_AGE days old)"
        ((CHECKS_PASSED++))
    else
        echo "⚠ Backup is $BACKUP_AGE days old"
    fi
else
    echo "✗ No backup found"
fi

# Check 10: Network connectivity
echo "[10/10] Checking network connectivity..."
if docker network inspect hgr-network > /dev/null 2>&1; then
    echo "✓ Docker network exists"
    ((CHECKS_PASSED++))
else
    echo "✗ Docker network missing"
fi

echo ""
echo "================================================"
echo "RESULTS: $CHECKS_PASSED/$CHECKS_TOTAL checks passed"
echo "================================================"

if [ $CHECKS_PASSED -eq $CHECKS_TOTAL ]; then
    echo "✓ System ready for deployment"
    exit 0
else
    echo "✗ System not ready for deployment"
    exit 1
fi
```

### 1.2 Configuration Validation

**File:** `scripts/validate_config.py`

```python
#!/usr/bin/env python3
"""
Validate configuration files before deployment
"""

import os
import yaml
import json
import sys
from typing import Dict, List, Tuple

class ConfigValidator:
    """Validate system configuration"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
    
    def validate_all(self) -> bool:
        """Run all validation checks"""
        print("Validating configuration files...")
        
        self.validate_docker_compose()
        self.validate_env_files()
        self.validate_agent_configs()
        self.validate_database_configs()
        
        return self.print_results()
    
    def validate_docker_compose(self):
        """Validate docker-compose.yml"""
        try:
            with open('docker-compose.yml', 'r') as f:
                compose = yaml.safe_load(f)
            
            # Check required services
            required_services = [
                'postgres-main',
                'redis-semantic-bus',
                'api-gateway'
            ]
            
            services = compose.get('services', {})
            
            for service in required_services:
                if service not in services:
                    self.errors.append(
                        f"Missing required service: {service}"
                    )
            
            # Check agent services
            agent_services = [
                name for name in services
                if name.startswith('agent-')
            ]
            
            if len(agent_services) < 35:
                self.warnings.append(
                    f"Expected 35 agents, found {len(agent_services)}"
                )
            
            # Validate resource limits
            for name, service in services.items():
                if 'deploy' in service:
                    resources = service['deploy'].get('resources', {})
                    limits = resources.get('limits', {})
                    
                    if 'cpus' not in limits:
                        self.warnings.append(
                            f"{name}: No CPU limit specified"
                        )
                    
                    if 'memory' not in limits:
                        self.warnings.append(
                            f"{name}: No memory limit specified"
                        )
            
            print("✓ docker-compose.yml validated")
            
        except Exception as e:
            self.errors.append(f"docker-compose.yml error: {e}")
    
    def validate_env_files(self):
        """Validate environment variable files"""
        env_files = [
            '.env',
            '.env.production'
        ]
        
        required_vars = [
            'POSTGRES_USER',
            'POSTGRES_PASSWORD',
            'POSTGRES_DB',
            'REDIS_PASSWORD',
            'JWT_SECRET',
            'ANTHROPIC_API_KEY'
        ]
        
        for env_file in env_files:
            if not os.path.exists(env_file):
                self.errors.append(f"Missing env file: {env_file}")
                continue
            
            with open(env_file, 'r') as f:
                lines = f.readlines()
            
            env_vars = {}
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key] = value
            
            # Check required variables
            for var in required_vars:
                if var not in env_vars:
                    self.errors.append(
                        f"{env_file}: Missing variable {var}"
                    )
                elif not env_vars[var]:
                    self.errors.append(
                        f"{env_file}: Empty value for {var}"
                    )
            
            print(f"✓ {env_file} validated")
    
    def validate_agent_configs(self):
        """Validate agent configuration files"""
        config_dir = 'config/agents'
        
        if not os.path.exists(config_dir):
            self.errors.append(f"Agent config directory missing: {config_dir}")
            return
        
        expected_agents = [
            'PM-001', 'CEO-001', 'IS-001',
            # ... all 35 agents
        ]
        
        config_files = os.listdir(config_dir)
        
        for agent in expected_agents:
            config_file = f"{agent.lower()}.json"
            
            if config_file not in config_files:
                self.errors.append(
                    f"Missing config for {agent}"
                )
                continue
            
            # Validate JSON structure
            with open(os.path.join(config_dir, config_file), 'r') as f:
                try:
                    config = json.load(f)
                    
                    required_fields = [
                        'agent_id',
                        'agent_type',
                        'context_window',
                        'protocols'
                    ]
                    
                    for field in required_fields:
                        if field not in config:
                            self.errors.append(
                                f"{agent}: Missing field {field}"
                            )
                
                except json.JSONDecodeError as e:
                    self.errors.append(
                        f"{agent}: Invalid JSON: {e}"
                    )
        
        print(f"✓ Agent configs validated")
    
    def validate_database_configs(self):
        """Validate database schemas and migrations"""
        schema_dir = 'database/schemas'
        
        if not os.path.exists(schema_dir):
            self.errors.append(f"Schema directory missing: {schema_dir}")
            return
        
        required_schemas = [
            'knowledge_lake.sql',
            'state_graph.sql',
            'logicnode_registry.sql',
            'traceability_ledger.sql',
            'model_store.sql'
        ]
        
        for schema in required_schemas:
            schema_path = os.path.join(schema_dir, schema)
            
            if not os.path.exists(schema_path):
                self.errors.append(f"Missing schema: {schema}")
            else:
                # Validate SQL syntax (basic check)
                with open(schema_path, 'r') as f:
                    sql = f.read()
                    
                    if 'CREATE TABLE' not in sql:
                        self.warnings.append(
                            f"{schema}: No CREATE TABLE statements found"
                        )
        
        print(f"✓ Database schemas validated")
    
    def print_results(self) -> bool:
        """Print validation results"""
        print("\n" + "="*50)
        print("CONFIGURATION VALIDATION RESULTS")
        print("="*50)
        
        if self.errors:
            print(f"\n✗ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  - {error}")
        
        if self.warnings:
            print(f"\n⚠ WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        if not self.errors and not self.warnings:
            print("\n✓ All configuration files valid")
        
        print("="*50)
        
        return len(self.errors) == 0


if __name__ == "__main__":
    validator = ConfigValidator()
    success = validator.validate_all()
    sys.exit(0 if success else 1)
```

---

## 2. DEPLOYMENT PREPARATION

### 2.1 Pre-Deployment Backup

**File:** `scripts/backup_system.sh`

```bash
#!/bin/bash
# Create complete system backup before deployment

set -e

BACKUP_DIR="backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="hgr_backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

echo "Creating system backup: $BACKUP_NAME"

# Create backup directory
mkdir -p $BACKUP_PATH

# Backup databases
echo "Backing up databases..."

# PostgreSQL dump
docker exec hgr-postgres pg_dumpall -U hgr_admin > \
    ${BACKUP_PATH}/postgres_dump.sql

# Redis snapshot
docker exec hgr-redis redis-cli SAVE
docker cp hgr-redis:/data/dump.rdb ${BACKUP_PATH}/redis_dump.rdb

# Backup configuration
echo "Backing up configuration..."
cp -r config ${BACKUP_PATH}/
cp docker-compose.yml ${BACKUP_PATH}/
cp .env ${BACKUP_PATH}/

# Backup agent state
echo "Backing up agent state..."
mkdir -p ${BACKUP_PATH}/agent_state
docker exec hgr-ceo-001 cat /app/state/agent_state.json > \
    ${BACKUP_PATH}/agent_state/ceo_state.json

# Create tarball
echo "Creating archive..."
cd $BACKUP_DIR
tar -czf ${BACKUP_NAME}.tar.gz $BACKUP_NAME/
rm -rf $BACKUP_NAME/

BACKUP_SIZE=$(du -h ${BACKUP_NAME}.tar.gz | cut -f1)

echo "✓ Backup created: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz (${BACKUP_SIZE})"

# Cleanup old backups (keep last 7)
echo "Cleaning up old backups..."
ls -t ${BACKUP_DIR}/*.tar.gz | tail -n +8 | xargs -r rm

echo "✓ Backup complete"
```

### 2.2 Deployment Package Preparation

**File:** `scripts/prepare_deployment.sh`

```bash
#!/bin/bash
# Prepare deployment package

set -e

VERSION=$1

if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 v1.2.0"
    exit 1
fi

DEPLOY_DIR="deploy/${VERSION}"

echo "Preparing deployment package: $VERSION"

# Create deployment directory
mkdir -p $DEPLOY_DIR

# Copy application files
echo "Copying application files..."
cp -r src ${DEPLOY_DIR}/
cp -r config ${DEPLOY_DIR}/
cp docker-compose.yml ${DEPLOY_DIR}/
cp docker-compose.prod.yml ${DEPLOY_DIR}/

# Build Docker images
echo "Building Docker images..."
docker-compose -f docker-compose.yml build

# Tag images with version
echo "Tagging images..."
for service in $(docker-compose config --services); do
    IMAGE_NAME="hgr-${service}"
    docker tag ${IMAGE_NAME}:latest ${IMAGE_NAME}:${VERSION}
done

# Export images
echo "Exporting images..."
mkdir -p ${DEPLOY_DIR}/images
docker save $(docker-compose config --services | sed 's/^/hgr-/') | \
    gzip > ${DEPLOY_DIR}/images/hgr_images_${VERSION}.tar.gz

# Create deployment manifest
cat > ${DEPLOY_DIR}/manifest.json <<EOF
{
  "version": "${VERSION}",
  "created_at": "$(date -Iseconds)",
  "services": $(docker-compose config --services | jq -R . | jq -s .),
  "images": $(docker images --format '{{.Repository}}:{{.Tag}}' | \
              grep "^hgr-" | jq -R . | jq -s .),
  "checksums": {
    "docker_compose": "$(md5sum docker-compose.yml | cut -d' ' -f1)",
    "images": "$(md5sum ${DEPLOY_DIR}/images/hgr_images_${VERSION}.tar.gz | \
                cut -d' ' -f1)"
  }
}
EOF

# Create deployment instructions
cat > ${DEPLOY_DIR}/DEPLOY.md <<EOF
# Holy Grail Refinery - Deployment Instructions
## Version: ${VERSION}

### Pre-Deployment
1. Run pre-deployment checks: \`./scripts/pre_deployment_check.sh\`
2. Create system backup: \`./scripts/backup_system.sh\`
3. Validate configuration: \`./scripts/validate_config.py\`

### Deployment
1. Load images: \`docker load < images/hgr_images_${VERSION}.tar.gz\`
2. Update configuration: \`cp config/* /opt/hgr/config/\`
3. Deploy: \`./scripts/deploy.sh ${VERSION}\`

### Verification
1. Run smoke tests: \`./scripts/smoke_test.sh\`
2. Check agent health: \`./scripts/check_health.sh\`
3. Verify API: \`curl http://localhost:8000/health\`

### Rollback (if needed)
\`./scripts/rollback.sh\`
EOF

echo "✓ Deployment package ready: $DEPLOY_DIR"
```

---

## 3. BLUE-GREEN DEPLOYMENT STRATEGY

### 3.1 Blue-Green Architecture

```
┌─────────────────────────────────────────────────┐
│              LOAD BALANCER / NGINX              │
│           (Routes traffic to active)            │
└─────────────┬───────────────────────┬───────────┘
              │                       │
      ┌───────▼────────┐      ┌──────▼─────────┐
      │  BLUE (Active) │      │ GREEN (Standby)│
      │                │      │                │
      │  35 Agents     │      │  35 Agents     │
      │  Databases     │      │  Databases     │
      │  API Gateway   │      │  API Gateway   │
      └────────────────┘      └────────────────┘
           Current                  New
          Version                 Version
```

### 3.2 Blue-Green Deployment Script

**File:** `scripts/blue_green_deploy.sh`

```bash
#!/bin/bash
# Blue-green deployment for Holy Grail Refinery

set -e

VERSION=$1
ACTIVE_ENV=${ACTIVE_ENV:-"blue"}

if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>"
    exit 1
fi

echo "Starting blue-green deployment: $VERSION"
echo "Active environment: $ACTIVE_ENV"

# Determine inactive environment
if [ "$ACTIVE_ENV" == "blue" ]; then
    INACTIVE_ENV="green"
else
    INACTIVE_ENV="blue"
fi

echo "Deploying to: $INACTIVE_ENV"

# Step 1: Deploy to inactive environment
echo "[1/5] Deploying to $INACTIVE_ENV environment..."
docker-compose \
    -f docker-compose.yml \
    -f docker-compose.${INACTIVE_ENV}.yml \
    up -d

# Step 2: Wait for health checks
echo "[2/5] Waiting for health checks..."
sleep 30

HEALTH_CHECK_MAX_ATTEMPTS=30
HEALTH_CHECK_INTERVAL=10

for i in $(seq 1 $HEALTH_CHECK_MAX_ATTEMPTS); do
    if curl -sf http://localhost:800${INACTIVE_ENV}/health > /dev/null 2>&1; then
        echo "✓ $INACTIVE_ENV environment healthy"
        break
    fi
    
    if [ $i -eq $HEALTH_CHECK_MAX_ATTEMPTS ]; then
        echo "✗ Health check failed after $((HEALTH_CHECK_MAX_ATTEMPTS * HEALTH_CHECK_INTERVAL))s"
        exit 1
    fi
    
    echo "Waiting for health check... ($i/$HEALTH_CHECK_MAX_ATTEMPTS)"
    sleep $HEALTH_CHECK_INTERVAL
done

# Step 3: Run smoke tests
echo "[3/5] Running smoke tests on $INACTIVE_ENV..."
./scripts/smoke_test.sh http://localhost:800${INACTIVE_ENV}

if [ $? -ne 0 ]; then
    echo "✗ Smoke tests failed"
    exit 1
fi

echo "✓ Smoke tests passed"

# Step 4: Switch traffic
echo "[4/5] Switching traffic to $INACTIVE_ENV..."

# Update nginx configuration
sudo sed -i "s/proxy_pass http:\/\/hgr-${ACTIVE_ENV}/proxy_pass http:\/\/hgr-${INACTIVE_ENV}/" \
    /etc/nginx/sites-available/hgr

# Reload nginx
sudo nginx -t && sudo systemctl reload nginx

echo "✓ Traffic switched to $INACTIVE_ENV"

# Step 5: Verify production traffic
echo "[5/5] Verifying production traffic..."
sleep 10

RESPONSE=$(curl -s http://localhost/health | jq -r '.environment')

if [ "$RESPONSE" == "$INACTIVE_ENV" ]; then
    echo "✓ Production traffic verified on $INACTIVE_ENV"
else
    echo "✗ Traffic verification failed"
    # Automatic rollback
    ./scripts/rollback.sh
    exit 1
fi

# Update active environment marker
echo "$INACTIVE_ENV" > .active_env
export ACTIVE_ENV=$INACTIVE_ENV

echo "✓ Deployment complete"
echo "  New active environment: $INACTIVE_ENV"
echo "  Old environment ($ACTIVE_ENV) is now standby"
echo ""
echo "Monitor for 15 minutes, then shutdown old environment:"
echo "  docker-compose -f docker-compose.${ACTIVE_ENV}.yml down"
```

---

## 4. DEPLOYMENT EXECUTION

### 4.1 Standard Deployment Script

**File:** `scripts/deploy.sh`

```bash
#!/bin/bash
# Standard deployment script

set -e

VERSION=$1

if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>"
    exit 1
fi

echo "================================================"
echo "HOLY GRAIL REFINERY - DEPLOYMENT"
echo "Version: $VERSION"
echo "================================================"
echo ""

# Step 1: Pre-deployment checks
echo "Step 1: Pre-deployment checks"
./scripts/pre_deployment_check.sh

if [ $? -ne 0 ]; then
    echo "✗ Pre-deployment checks failed"
    exit 1
fi

# Step 2: Backup
echo ""
echo "Step 2: Creating backup"
./scripts/backup_system.sh

# Step 3: Load new images
echo ""
echo "Step 3: Loading Docker images"
docker load < deploy/${VERSION}/images/hgr_images_${VERSION}.tar.gz

# Step 4: Update configuration
echo ""
echo "Step 4: Updating configuration"
cp -r deploy/${VERSION}/config/* config/

# Step 5: Blue-green deployment
echo ""
echo "Step 5: Executing blue-green deployment"
./scripts/blue_green_deploy.sh $VERSION

# Step 6: Post-deployment verification
echo ""
echo "Step 6: Post-deployment verification"
./scripts/smoke_test.sh

if [ $? -ne 0 ]; then
    echo "✗ Post-deployment verification failed"
    echo "Initiating rollback..."
    ./scripts/rollback.sh
    exit 1
fi

echo ""
echo "================================================"
echo "✓ DEPLOYMENT SUCCESSFUL"
echo "================================================"
echo ""
echo "Version $VERSION is now live"
echo "Monitor dashboard: http://localhost:3000"
```

---

## 5. SMOKE TESTING & VALIDATION

### 5.1 Comprehensive Smoke Test Suite

**File:** `scripts/smoke_test.sh`

```bash
#!/bin/bash
# Comprehensive smoke tests for deployment validation

set -e

BASE_URL=${1:-"http://localhost:8000"}

echo "Running smoke tests against: $BASE_URL"

TESTS_PASSED=0
TESTS_TOTAL=15

# Test 1: API Gateway Health
echo "[1/15] Testing API gateway health..."
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $BASE_URL/health)
if [ "$RESPONSE" -eq 200 ]; then
    echo "✓ API gateway healthy"
    ((TESTS_PASSED++))
else
    echo "✗ API gateway unhealthy (HTTP $RESPONSE)"
fi

# Test 2: Authentication
echo "[2/15] Testing authentication..."
TOKEN=$(curl -s -X POST $BASE_URL/api/v1/auth/token \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"test123"}' | jq -r '.access_token')

if [ -n "$TOKEN" ] && [ "$TOKEN" != "null" ]; then
    echo "✓ Authentication successful"
    ((TESTS_PASSED++))
else
    echo "✗ Authentication failed"
fi

# Test 3: PM Agent Status
echo "[3/15] Testing PM Agent..."
RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" \
    $BASE_URL/api/v1/agents/PM-001/status | jq -r '.status')

if [ "$RESPONSE" == "active" ]; then
    echo "✓ PM Agent active"
    ((TESTS_PASSED++))
else
    echo "✗ PM Agent status: $RESPONSE"
fi

# Test 4: CEO Agent Status
echo "[4/15] Testing CEO Agent..."
RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" \
    $BASE_URL/api/v1/agents/CEO-001/status | jq -r '.status')

if [ "$RESPONSE" == "active" ]; then
    echo "✓ CEO Agent active"
    ((TESTS_PASSED++))
else
    echo "✗ CEO Agent status: $RESPONSE"
fi

# Test 5: Knowledge Lake Query
echo "[5/15] Testing Knowledge Lake..."
RESPONSE=$(curl -s -X POST $BASE_URL/api/v1/knowledge/search \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"query":"Python list operations","top_k":5}' | \
    jq -r '.total_results')

if [ "$RESPONSE" -gt 0 ]; then
    echo "✓ Knowledge Lake responsive ($RESPONSE results)"
    ((TESTS_PASSED++))
else
    echo "✗ Knowledge Lake returned no results"
fi

# Test 6: LogicNode Registry
echo "[6/15] Testing LogicNode Registry..."
RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" \
    $BASE_URL/api/v1/registry/statistics | jq -r '.total_logicnodes')

if [ "$RESPONSE" != "null" ]; then
    echo "✓ LogicNode Registry accessible ($RESPONSE nodes)"
    ((TESTS_PASSED++))
else
    echo "✗ LogicNode Registry error"
fi

# Test 7: Language Specialist (Python)
echo "[7/15] Testing Python Specialist..."
RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" \
    $BASE_URL/api/v1/agents/AGENT-PY-001/status | jq -r '.status')

if [ "$RESPONSE" == "active" ]; then
    echo "✓ Python Specialist active"
    ((TESTS_PASSED++))
else
    echo "✗ Python Specialist status: $RESPONSE"
fi

# Test 8: Audit Agent
echo "[8/15] Testing Audit Agent..."
RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" \
    $BASE_URL/api/v1/agents/AUDIT-LEAD-001/status | jq -r '.status')

if [ "$RESPONSE" == "active" ]; then
    echo "✓ Audit Lead active"
    ((TESTS_PASSED++))
else
    echo "✗ Audit Lead status: $RESPONSE"
fi

# Test 9: Support Agent
echo "[9/15] Testing Support Agent..."
RESPONSE=$(curl -s -H "Authorization: Bearer $TOKEN" \
    $BASE_URL/api/v1/agents/SUPPORT-DEVOPS-001/status | jq -r '.status')

if [ "$RESPONSE" == "active" ]; then
    echo "✓ DevOps Support active"
    ((TESTS_PASSED++))
else
    echo "✗ DevOps Support status: $RESPONSE"
fi

# Test 10: Mission Creation
echo "[10/15] Testing mission creation..."
MISSION_ID=$(curl -s -X POST $BASE_URL/api/v1/missions \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{
        "description":"Smoke test mission",
        "type":"test",
        "requirements":{"languages":["python"]}
    }' | jq -r '.mission_id')

if [ -n "$MISSION_ID" ] && [ "$MISSION_ID" != "null" ]; then
    echo "✓ Mission created: $MISSION_ID"
    ((TESTS_PASSED++))
else
    echo "✗ Mission creation failed"
fi

# Test 11: Database Connectivity
echo "[11/15] Testing database connectivity..."
if docker exec hgr-postgres pg_isready -U hgr_admin > /dev/null 2>&1; then
    echo "✓ PostgreSQL connected"
    ((TESTS_PASSED++))
else
    echo "✗ PostgreSQL connection failed"
fi

# Test 12: Redis Connectivity
echo "[12/15] Testing Redis connectivity..."
if docker exec hgr-redis redis-cli ping > /dev/null 2>&1; then
    echo "✓ Redis connected"
    ((TESTS_PASSED++))
else
    echo "✗ Redis connection failed"
fi

# Test 13: Semantic Bus
echo "[13/15] Testing Semantic Bus..."
RESPONSE=$(docker exec hgr-redis redis-cli PUBSUB CHANNELS "hgr:*" | wc -l)

if [ "$RESPONSE" -gt 0 ]; then
    echo "✓ Semantic Bus active ($RESPONSE channels)"
    ((TESTS_PASSED++))
else
    echo "⚠ Semantic Bus has no active channels"
fi

# Test 14: Container Health
echo "[14/15] Testing container health..."
UNHEALTHY=$(docker ps --filter "health=unhealthy" --filter "name=hgr-" \
    --format "{{.Names}}" | wc -l)

if [ "$UNHEALTHY" -eq 0 ]; then
    echo "✓ All containers healthy"
    ((TESTS_PASSED++))
else
    echo "✗ $UNHEALTHY unhealthy containers"
fi

# Test 15: Resource Usage
echo "[15/15] Testing resource usage..."
CPU_USAGE=$(docker stats --no-stream --format "table {{.CPUPerc}}" | \
    tail -n +2 | sed 's/%//' | awk '{s+=$1} END {print s}')

if (( $(echo "$CPU_USAGE < 80" | bc -l) )); then
    echo "✓ CPU usage: ${CPU_USAGE}%"
    ((TESTS_PASSED++))
else
    echo "⚠ High CPU usage: ${CPU_USAGE}%"
fi

echo ""
echo "================================================"
echo "SMOKE TEST RESULTS: $TESTS_PASSED/$TESTS_TOTAL passed"
echo "================================================"

if [ $TESTS_PASSED -eq $TESTS_TOTAL ]; then
    echo "✓ All smoke tests passed"
    exit 0
elif [ $TESTS_PASSED -ge $((TESTS_TOTAL * 80 / 100)) ]; then
    echo "⚠ Some tests failed, but system operational"
    exit 0
else
    echo "✗ Too many tests failed"
    exit 1
fi
```

---

## 6. ROLLBACK PROCEDURES

### 6.1 Automatic Rollback Script

**File:** `scripts/rollback.sh`

```bash
#!/bin/bash
# Automatic rollback to previous stable version

set -e

echo "================================================"
echo "INITIATING ROLLBACK"
echo "================================================"

# Get current active environment
ACTIVE_ENV=$(cat .active_env 2>/dev/null || echo "blue")

# Determine previous environment
if [ "$ACTIVE_ENV" == "blue" ]; then
    PREVIOUS_ENV="green"
else
    PREVIOUS_ENV="blue"
fi

echo "Rolling back from $ACTIVE_ENV to $PREVIOUS_ENV"

# Step 1: Verify previous environment is running
echo "[1/4] Checking $PREVIOUS_ENV environment..."
if ! curl -sf http://localhost:800${PREVIOUS_ENV}/health > /dev/null 2>&1; then
    echo "✗ Previous environment not available"
    echo "Starting previous environment..."
    
    # Load previous backup
    LATEST_BACKUP=$(ls -t backups/*.tar.gz | head -1)
    if [ -z "$LATEST_BACKUP" ]; then
        echo "✗ No backup available for rollback"
        exit 1
    fi
    
    echo "Restoring from backup: $LATEST_BACKUP"
    tar -xzf $LATEST_BACKUP -C /tmp/
    
    # Restore configuration
    cp -r /tmp/hgr_backup_*/config/* config/
    
    # Restore databases
    cat /tmp/hgr_backup_*/postgres_dump.sql | \
        docker exec -i hgr-postgres psql -U hgr_admin
    
    docker cp /tmp/hgr_backup_*/redis_dump.rdb hgr-redis:/data/dump.rdb
    docker exec hgr-redis redis-cli SHUTDOWN NOSAVE
    docker restart hgr-redis
    
    # Cleanup
    rm -rf /tmp/hgr_backup_*
fi

# Step 2: Switch traffic back
echo "[2/4] Switching traffic to $PREVIOUS_ENV..."
sudo sed -i "s/proxy_pass http:\/\/hgr-${ACTIVE_ENV}/proxy_pass http:\/\/hgr-${PREVIOUS_ENV}/" \
    /etc/nginx/sites-available/hgr

sudo nginx -t && sudo systemctl reload nginx

# Step 3: Verify rollback
echo "[3/4] Verifying rollback..."
sleep 5

RESPONSE=$(curl -s http://localhost/health | jq -r '.environment')

if [ "$RESPONSE" == "$PREVIOUS_ENV" ]; then
    echo "✓ Rollback successful - traffic on $PREVIOUS_ENV"
else
    echo "✗ Rollback verification failed"
    exit 1
fi

# Step 4: Shutdown failed environment
echo "[4/4] Shutting down failed environment..."
docker-compose -f docker-compose.${ACTIVE_ENV}.yml down

# Update active marker
echo "$PREVIOUS_ENV" > .active_env

echo ""
echo "================================================"
echo "✓ ROLLBACK COMPLETE"
echo "================================================"
echo "System reverted to previous stable state"
echo "Environment: $PREVIOUS_ENV"
```

---

## 7. POST-DEPLOYMENT MONITORING

### 7.1 Enhanced Monitoring Period

**File:** `scripts/monitor_deployment.sh`

```bash
#!/bin/bash
# Enhanced monitoring for 48 hours post-deployment

DURATION_HOURS=48
INTERVAL_SECONDS=300  # 5 minutes

echo "Starting enhanced monitoring (${DURATION_HOURS}h)"

END_TIME=$(($(date +%s) + DURATION_HOURS * 3600))

while [ $(date +%s) -lt $END_TIME ]; do
    TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")
    
    echo "[$TIMESTAMP] Monitoring check..."
    
    # Check error rates
    ERROR_COUNT=$(docker logs hgr-api-gateway --since 5m 2>&1 | \
        grep -c "ERROR" || true)
    
    if [ $ERROR_COUNT -gt 10 ]; then
        echo "⚠ High error rate: $ERROR_COUNT errors in last 5 min"
        # Send alert
        ./scripts/send_alert.sh "High error rate detected: $ERROR_COUNT"
    fi
    
    # Check response times
    RESPONSE_TIME=$(curl -s -w "%{time_total}" -o /dev/null \
        http://localhost:8000/health)
    
    if (( $(echo "$RESPONSE_TIME > 1.0" | bc -l) )); then
        echo "⚠ Slow response time: ${RESPONSE_TIME}s"
    fi
    
    # Check container restarts
    RESTARTS=$(docker ps --format "{{.Names}} {{.Status}}" | \
        grep -c "Restarting" || true)
    
    if [ $RESTARTS -gt 0 ]; then
        echo "⚠ $RESTARTS containers restarting"
    fi
    
    sleep $INTERVAL_SECONDS
done

echo "✓ Enhanced monitoring period complete"
```

---

## 8. DEPLOYMENT SCENARIOS

### 8.1 Zero-Downtime Agent Update

```bash
#!/bin/bash
# Update a single agent without downtime

AGENT_NAME=$1
NEW_VERSION=$2

echo "Updating $AGENT_NAME to version $NEW_VERSION"

# Get current replica count
CURRENT_REPLICAS=$(docker ps --filter "name=$AGENT_NAME" \
    --format "{{.Names}}" | wc -l)

# Deploy new version alongside old
docker-compose up -d --scale $AGENT_NAME=$((CURRENT_REPLICAS * 2)) \
    --no-recreate

# Wait for new replicas to be healthy
sleep 30

# Remove old replicas
docker ps --filter "name=$AGENT_NAME" --format "{{.ID}}" | \
    head -n $CURRENT_REPLICAS | xargs docker stop

echo "✓ Agent updated with zero downtime"
```

### 8.2 Emergency Hotfix Deployment

```bash
#!/bin/bash
# Emergency hotfix deployment procedure

HOTFIX_VERSION=$1

echo "EMERGENCY HOTFIX DEPLOYMENT: $HOTFIX_VERSION"

# Skip normal checks for speed
# Load hotfix image
docker load < hotfix/$HOTFIX_VERSION.tar.gz

# Apply immediately
docker-compose up -d --no-deps [affected-service]

# Verify
./scripts/smoke_test.sh

echo "✓ Hotfix applied"
```

---

## 9. EMERGENCY PROCEDURES

### 9.1 System Recovery

**In case of complete system failure:**

```bash
#!/bin/bash
# Emergency system recovery

echo "EMERGENCY SYSTEM RECOVERY"

# 1. Stop all containers
docker-compose down

# 2. Clear corrupted data (if needed)
# docker volume rm hgr_postgres_data  # DANGEROUS

# 3. Restore from backup
LATEST_BACKUP=$(ls -t backups/*.tar.gz | head -1)
tar -xzf $LATEST_BACKUP -C /tmp/

# 4. Restore databases
cat /tmp/hgr_backup_*/postgres_dump.sql | \
    docker exec -i hgr-postgres psql -U hgr_admin

# 5. Restart system
docker-compose up -d

# 6. Verify
./scripts/smoke_test.sh

echo "✓ System recovered"
```

---

## 10. DEPLOYMENT CHECKLISTS

### 10.1 Pre-Deployment Checklist

- [ ] All tests passing in CI/CD
- [ ] Code review completed and approved
- [ ] Security scan passed
- [ ] Performance benchmarks met
- [ ] Database migrations tested
- [ ] Configuration validated
- [ ] Backup created
- [ ] Rollback plan ready
- [ ] Stakeholders notified
- [ ] Deployment window confirmed

### 10.2 Deployment Checklist

- [ ] Pre-deployment checks passed
- [ ] Backup completed
- [ ] Blue-green deployment executed
- [ ] Health checks passed
- [ ] Smoke tests passed
- [ ] Traffic switched successfully
- [ ] Production verified
- [ ] Monitoring enhanced
- [ ] Team notified of success

### 10.3 Post-Deployment Checklist

- [ ] All agents running
- [ ] No error spikes
- [ ] Performance metrics normal
- [ ] User feedback positive
- [ ] Documentation updated
- [ ] Release notes published
- [ ] Old environment shut down
- [ ] Post-mortem scheduled (if issues)

---

## DOCUMENT METADATA

**Document ID:** 32  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Operations & Deployment  
**Owner:** DevOps Lead  
**Dependencies:** Documents 17 (Docker), 27 (Agent Deployment)  
**Next Document:** 33 (System Maintenance Procedures)

---

*End of Production Deployment Guide*
