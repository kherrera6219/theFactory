# DOCUMENT 24: CI/CD PIPELINE CONFIGURATION
## Holy Grail Refinery - Development Specifications

**Document ID:** 24  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

The Holy Grail Refinery implements a **fully automated CI/CD pipeline** to ensure rapid, reliable deployment of the 35-agent system while maintaining the 99.9999% reliability target. The pipeline automates testing, building, security scanning, and deployment across development, staging, and production environments.

**Pipeline Architecture:**
- **Source Control:** Git with GitHub (or GitLab/Bitbucket alternatives)
- **CI Platform:** GitHub Actions (primary), Jenkins (backup)
- **Container Registry:** Docker Hub (private registry)
- **Deployment Target:** Local AW1 hardware with Docker Compose
- **Monitoring:** Integrated health checks and rollback mechanisms

**Key Features:**
- 🔄 Automated testing on every commit
- 🔒 Security scanning before deployment
- 📦 Multi-architecture Docker builds
- 🚀 Zero-downtime deployments
- ↩️ Automatic rollback on failures

---

## TABLE OF CONTENTS

1. [Pipeline Architecture](#1-pipeline-architecture)
2. [GitHub Actions Workflows](#2-github-actions-workflows)
3. [Build & Package Stage](#3-build--package-stage)
4. [Testing & Validation Stage](#4-testing--validation-stage)
5. [Security Scanning Stage](#5-security-scanning-stage)
6. [Deployment Strategies](#6-deployment-strategies)
7. [Environment Management](#7-environment-management)
8. [Rollback Procedures](#8-rollback-procedures)
9. [Pipeline Monitoring](#9-pipeline-monitoring)
10. [Best Practices](#10-best-practices)

---

## 1. PIPELINE ARCHITECTURE

### 1.1 Pipeline Stages Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     SOURCE CONTROL                           │
│              (GitHub Repository - main branch)               │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    STAGE 1: BUILD                            │
│  • Checkout code                                             │
│  • Install dependencies                                      │
│  • Compile code                                              │
│  • Build Docker images                                       │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                   STAGE 2: TEST                              │
│  • Lint & format checks                                      │
│  • Unit tests (90% coverage)                                 │
│  • Integration tests                                         │
│  • System tests                                              │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  STAGE 3: SECURITY                           │
│  • Dependency vulnerability scan                             │
│  • Container image scan                                      │
│  • SAST (Static Application Security Testing)                │
│  • License compliance check                                  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  STAGE 4: PACKAGE                            │
│  • Tag Docker images                                         │
│  • Push to registry                                          │
│  • Generate release notes                                    │
│  • Create deployment artifacts                               │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  STAGE 5: DEPLOY                             │
│  • Deploy to staging (automatic)                             │
│  • Run smoke tests                                           │
│  • Deploy to production (manual approval)                    │
│  • Health check validation                                   │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  STAGE 6: VERIFY                             │
│  • Post-deployment tests                                     │
│  • Performance benchmarks                                    │
│  • Monitoring integration                                    │
│  • Rollback if failures detected                             │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Pipeline Triggers

| Trigger | Action | Stages Executed |
|---------|--------|-----------------|
| **Push to main** | Full pipeline | All stages → Deploy to staging |
| **Push to develop** | Test pipeline | Build + Test + Security |
| **Pull Request** | Validation pipeline | Build + Test |
| **Manual trigger** | Selective deployment | Deploy to production |
| **Scheduled (nightly)** | Full test suite | All tests + Security scan |
| **Tag release** | Release pipeline | All stages → Deploy to production |

---

## 2. GITHUB ACTIONS WORKFLOWS

### 2.1 Main CI/CD Workflow

**File:** `.github/workflows/main.yml`

```yaml
name: Main CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  workflow_dispatch:
    inputs:
      environment:
        description: 'Deployment environment'
        required: true
        type: choice
        options:
          - staging
          - production

env:
  REGISTRY: docker.io
  IMAGE_PREFIX: hgr

jobs:
  # ============================================================================
  # JOB 1: BUILD
  # ============================================================================
  build:
    name: Build & Compile
    runs-on: ubuntu-latest
    
    outputs:
      version: ${{ steps.version.outputs.version }}
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for versioning
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'
      
      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Generate version
        id: version
        run: |
          VERSION=$(git describe --tags --always --dirty)
          echo "version=${VERSION}" >> $GITHUB_OUTPUT
          echo "Version: ${VERSION}"
      
      - name: Compile Python bytecode
        run: |
          python -m compileall agents/ api/ database/
      
      - name: Cache build artifacts
        uses: actions/cache@v3
        with:
          path: |
            ~/.cache/pip
            __pycache__
          key: ${{ runner.os }}-build-${{ hashFiles('**/requirements.txt') }}
  
  # ============================================================================
  # JOB 2: LINT & FORMAT
  # ============================================================================
  lint:
    name: Lint & Format Checks
    runs-on: ubuntu-latest
    needs: build
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install linting tools
        run: |
          pip install black flake8 isort mypy pylint
      
      - name: Run Black (format check)
        run: |
          black --check --diff agents/ api/ database/
      
      - name: Run Flake8 (style check)
        run: |
          flake8 agents/ api/ database/ \
            --max-line-length=100 \
            --ignore=E203,W503 \
            --count --statistics
      
      - name: Run isort (import order)
        run: |
          isort --check-only --diff agents/ api/ database/
      
      - name: Run mypy (type checking)
        run: |
          mypy agents/ api/ database/ \
            --ignore-missing-imports \
            --no-strict-optional
      
      - name: Run pylint (code quality)
        run: |
          pylint agents/ api/ database/ \
            --disable=C0111,R0903 \
            --min-similarity-lines=10 \
            --fail-under=9.0
  
  # ============================================================================
  # JOB 3: UNIT TESTS
  # ============================================================================
  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    needs: lint
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Run unit tests
        run: |
          pytest tests/unit/ \
            -v \
            --cov=agents \
            --cov=api \
            --cov=database \
            --cov-report=xml \
            --cov-report=html \
            --cov-fail-under=90 \
            --junitxml=junit/test-results.xml
      
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          flags: unittests
          name: codecov-unit
          fail_ci_if_error: true
      
      - name: Publish test results
        uses: EnricoMi/publish-unit-test-result-action@v2
        if: always()
        with:
          files: junit/test-results.xml
  
  # ============================================================================
  # JOB 4: INTEGRATION TESTS
  # ============================================================================
  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    needs: unit-tests
    
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: test_user
          POSTGRES_PASSWORD: test_pass
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7.2
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Run integration tests
        env:
          DATABASE_URL: postgresql://test_user:test_pass@localhost/test_db
          REDIS_URL: redis://localhost:6379
        run: |
          pytest tests/integration/ \
            -v \
            --junitxml=junit/integration-results.xml
      
      - name: Publish integration test results
        uses: EnricoMi/publish-unit-test-result-action@v2
        if: always()
        with:
          files: junit/integration-results.xml
  
  # ============================================================================
  # JOB 5: SECURITY SCANNING
  # ============================================================================
  security:
    name: Security Scanning
    runs-on: ubuntu-latest
    needs: build
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install security tools
        run: |
          pip install bandit safety
      
      - name: Run Bandit (SAST)
        run: |
          bandit -r agents/ api/ database/ \
            -f json \
            -o bandit-report.json
      
      - name: Run Safety (dependency scan)
        run: |
          safety check \
            --json \
            --output safety-report.json \
            || true
      
      - name: Upload security reports
        uses: actions/upload-artifact@v3
        with:
          name: security-reports
          path: |
            bandit-report.json
            safety-report.json
      
      - name: Check for critical vulnerabilities
        run: |
          # Fail if critical vulnerabilities found
          CRITICAL=$(jq '.[] | select(.severity == "CRITICAL")' safety-report.json)
          if [ ! -z "$CRITICAL" ]; then
            echo "Critical vulnerabilities found!"
            exit 1
          fi
  
  # ============================================================================
  # JOB 6: BUILD DOCKER IMAGES
  # ============================================================================
  docker-build:
    name: Build Docker Images
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests, security]
    if: github.ref == 'refs/heads/main'
    
    strategy:
      matrix:
        image:
          - api
          - agent-python
          - agent-javascript
          - agent-rust
          - agent-java
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Log in to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}
      
      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}-${{ matrix.image }}
          tags: |
            type=ref,event=branch
            type=sha,prefix={{branch}}-
            type=semver,pattern={{version}}
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./docker/${{ matrix.image }}/Dockerfile
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
      
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}-${{ matrix.image }}:${{ github.sha }}
          format: 'sarif'
          output: 'trivy-results-${{ matrix.image }}.sarif'
      
      - name: Upload Trivy results
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: 'trivy-results-${{ matrix.image }}.sarif'
  
  # ============================================================================
  # JOB 7: DEPLOY TO STAGING
  # ============================================================================
  deploy-staging:
    name: Deploy to Staging
    runs-on: ubuntu-latest
    needs: docker-build
    if: github.ref == 'refs/heads/main'
    environment:
      name: staging
      url: http://staging.hgr.local
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up SSH
        run: |
          mkdir -p ~/.ssh
          echo "${{ secrets.SSH_PRIVATE_KEY }}" > ~/.ssh/id_rsa
          chmod 600 ~/.ssh/id_rsa
          ssh-keyscan -H ${{ secrets.STAGING_HOST }} >> ~/.ssh/known_hosts
      
      - name: Deploy to staging server
        run: |
          ssh ${{ secrets.STAGING_USER }}@${{ secrets.STAGING_HOST }} << 'EOF'
            cd /opt/holy-grail-refinery
            
            # Pull latest code
            git pull origin main
            
            # Pull Docker images
            docker-compose pull
            
            # Rolling update
            docker-compose up -d --no-deps --build
            
            # Wait for health checks
            sleep 30
            
            # Verify deployment
            docker-compose ps
          EOF
      
      - name: Run smoke tests
        run: |
          # Wait for services to be ready
          sleep 60
          
          # Run basic health checks
          curl -f http://staging.hgr.local/health || exit 1
          curl -f http://staging.hgr.local/api/v1/agents || exit 1
      
      - name: Notify deployment
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          text: 'Staging deployment completed'
          webhook_url: ${{ secrets.SLACK_WEBHOOK }}
        if: always()
  
  # ============================================================================
  # JOB 8: DEPLOY TO PRODUCTION
  # ============================================================================
  deploy-production:
    name: Deploy to Production
    runs-on: ubuntu-latest
    needs: deploy-staging
    if: github.event_name == 'workflow_dispatch' || startsWith(github.ref, 'refs/tags/')
    environment:
      name: production
      url: http://localhost:8000
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Deploy to production (AW1)
        run: |
          # This assumes GitHub Actions runner has access to AW1
          # Alternative: Use self-hosted runner on AW1
          
          cd /opt/holy-grail-refinery
          
          # Backup current state
          docker-compose ps > deployment-backup-$(date +%Y%m%d-%H%M%S).txt
          
          # Pull latest images
          docker-compose pull
          
          # Rolling update with health checks
          docker-compose up -d --no-deps --build --scale api=2
          
          # Wait and verify
          sleep 60
          docker-compose ps | grep -v "Up (healthy)" && exit 1 || true
          
          # Scale back to normal
          docker-compose up -d --scale api=1
      
      - name: Post-deployment verification
        run: |
          # Health checks
          curl -f http://localhost:8000/health || exit 1
          
          # Performance benchmark
          ab -n 100 -c 10 http://localhost:8000/api/v1/agents
      
      - name: Rollback on failure
        if: failure()
        run: |
          cd /opt/holy-grail-refinery
          docker-compose down
          git checkout HEAD~1
          docker-compose up -d
      
      - name: Notify production deployment
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          text: 'Production deployment completed'
          webhook_url: ${{ secrets.SLACK_WEBHOOK }}
        if: always()
```

---

## 3. BUILD & PACKAGE STAGE

### 3.1 Multi-Stage Dockerfile

**File:** `docker/api/Dockerfile`

```dockerfile
# ============================================================================
# Stage 1: Builder
# ============================================================================
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ============================================================================
# Stage 2: Runtime
# ============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY api/ ./api/
COPY database/ ./database/
COPY semantic_bus/ ./semantic_bus/

# Create non-root user
RUN useradd -m -u 1000 hgr && chown -R hgr:hgr /app
USER hgr

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 3.2 Docker Compose for Production

**File:** `docker-compose.prod.yml`

```yaml
version: '3.8'

services:
  # API Gateway
  api:
    image: ${REGISTRY}/hgr-api:${VERSION}
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
    depends_on:
      - postgres
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
  
  # Agent containers (35 total)
  agent-python:
    image: ${REGISTRY}/hgr-agent-python:${VERSION}
    restart: unless-stopped
    environment:
      - AGENT_ID=AGENT-PY-001
      - REDIS_URL=${REDIS_URL}
      - DATABASE_URL=${DATABASE_URL}
    depends_on:
      - redis
      - postgres
  
  # Infrastructure
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    volumes:
      - postgres-data:/var/lib/postgresql/data
    environment:
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
  
  redis:
    image: redis:7.2-alpine
    restart: unless-stopped
    volumes:
      - redis-data:/data

volumes:
  postgres-data:
  redis-data:

networks:
  default:
    name: hgr-network
```

---

## 4. TESTING & VALIDATION STAGE

### 4.1 Automated Test Execution

**File:** `scripts/run_tests.sh`

```bash
#!/bin/bash
set -e

echo "=========================================="
echo "Holy Grail Refinery - Test Suite"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test results
UNIT_RESULT=0
INTEGRATION_RESULT=0
SYSTEM_RESULT=0

# 1. Unit Tests
echo ""
echo "Running Unit Tests..."
pytest tests/unit/ \
  -v \
  --cov=agents \
  --cov=api \
  --cov-report=term-missing \
  --cov-fail-under=90 \
  || UNIT_RESULT=$?

if [ $UNIT_RESULT -eq 0 ]; then
  echo -e "${GREEN}✓ Unit tests passed${NC}"
else
  echo -e "${RED}✗ Unit tests failed${NC}"
fi

# 2. Integration Tests
echo ""
echo "Running Integration Tests..."
pytest tests/integration/ -v || INTEGRATION_RESULT=$?

if [ $INTEGRATION_RESULT -eq 0 ]; then
  echo -e "${GREEN}✓ Integration tests passed${NC}"
else
  echo -e "${RED}✗ Integration tests failed${NC}"
fi

# 3. System Tests
echo ""
echo "Running System Tests..."
pytest tests/system/ -v || SYSTEM_RESULT=$?

if [ $SYSTEM_RESULT -eq 0 ]; then
  echo -e "${GREEN}✓ System tests passed${NC}"
else
  echo -e "${RED}✗ System tests failed${NC}"
fi

# Summary
echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Unit Tests:        $([ $UNIT_RESULT -eq 0 ] && echo -e "${GREEN}PASS${NC}" || echo -e "${RED}FAIL${NC}")"
echo "Integration Tests: $([ $INTEGRATION_RESULT -eq 0 ] && echo -e "${GREEN}PASS${NC}" || echo -e "${RED}FAIL${NC}")"
echo "System Tests:      $([ $SYSTEM_RESULT -eq 0 ] && echo -e "${GREEN}PASS${NC}" || echo -e "${RED}FAIL${NC}")"

# Exit with failure if any test failed
if [ $UNIT_RESULT -ne 0 ] || [ $INTEGRATION_RESULT -ne 0 ] || [ $SYSTEM_RESULT -ne 0 ]; then
  exit 1
fi

exit 0
```

---

## 5. SECURITY SCANNING STAGE

### 5.1 Comprehensive Security Pipeline

**File:** `.github/workflows/security-scan.yml`

```yaml
name: Security Scan

on:
  push:
    branches: [main, develop]
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

jobs:
  security-scan:
    name: Security Analysis
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      # SAST - Static Application Security Testing
      - name: Run Bandit
        run: |
          pip install bandit
          bandit -r agents/ api/ database/ \
            -f json \
            -o bandit-report.json
          
          # Check for high severity issues
          HIGH_COUNT=$(jq '[.results[] | select(.issue_severity == "HIGH")] | length' bandit-report.json)
          if [ $HIGH_COUNT -gt 0 ]; then
            echo "Found $HIGH_COUNT high severity issues"
            exit 1
          fi
      
      # Dependency vulnerabilities
      - name: Run Safety
        run: |
          pip install safety
          safety check --json > safety-report.json || true
          
          # Fail on critical vulnerabilities
          CRITICAL=$(jq '[.[] | select(.severity == "CRITICAL")] | length' safety-report.json)
          if [ $CRITICAL -gt 0 ]; then
            echo "Found $CRITICAL critical vulnerabilities"
            exit 1
          fi
      
      # Container scanning
      - name: Build test image
        run: docker build -t hgr-api:scan ./docker/api
      
      - name: Run Trivy
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'hgr-api:scan'
          format: 'table'
          exit-code: '1'
          severity: 'CRITICAL,HIGH'
      
      # Secret scanning
      - name: Run Gitleaks
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      
      # License compliance
      - name: Check licenses
        run: |
          pip install pip-licenses
          pip-licenses --format=json > licenses.json
          
          # Fail on GPL/AGPL licenses (if policy requires)
          BANNED=$(jq '[.[] | select(.License | contains("GPL"))] | length' licenses.json)
          if [ $BANNED -gt 0 ]; then
            echo "Found $BANNED packages with GPL licenses"
            # exit 1  # Uncomment if GPL is banned
          fi
      
      # Upload results
      - name: Upload security reports
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: security-reports
          path: |
            bandit-report.json
            safety-report.json
            licenses.json
```

---

## 6. DEPLOYMENT STRATEGIES

### 6.1 Blue-Green Deployment

**File:** `scripts/deploy_blue_green.sh`

```bash
#!/bin/bash
set -e

# Blue-Green Deployment Script
# Maintains two identical production environments
# Switches traffic between them for zero-downtime deployments

BLUE_PORT=8000
GREEN_PORT=8001
CURRENT_ENV=$(cat /opt/hgr/current_env.txt)

echo "Current environment: $CURRENT_ENV"

# Determine target environment
if [ "$CURRENT_ENV" == "blue" ]; then
  TARGET_ENV="green"
  TARGET_PORT=$GREEN_PORT
else
  TARGET_ENV="blue"
  TARGET_PORT=$BLUE_PORT
fi

echo "Deploying to: $TARGET_ENV (port $TARGET_PORT)"

# 1. Deploy to target environment
cd /opt/holy-grail-refinery
docker-compose -f docker-compose.$TARGET_ENV.yml pull
docker-compose -f docker-compose.$TARGET_ENV.yml up -d

# 2. Wait for health checks
echo "Waiting for $TARGET_ENV environment to be healthy..."
RETRIES=30
while [ $RETRIES -gt 0 ]; do
  if curl -f http://localhost:$TARGET_PORT/health; then
    echo "✓ $TARGET_ENV is healthy"
    break
  fi
  echo "Waiting... ($RETRIES attempts remaining)"
  sleep 10
  RETRIES=$((RETRIES - 1))
done

if [ $RETRIES -eq 0 ]; then
  echo "✗ $TARGET_ENV failed health checks"
  exit 1
fi

# 3. Switch traffic (update nginx/load balancer)
echo "Switching traffic to $TARGET_ENV..."
cat > /etc/nginx/sites-available/hgr.conf <<EOF
upstream hgr_backend {
  server localhost:$TARGET_PORT;
}

server {
  listen 80;
  location / {
    proxy_pass http://hgr_backend;
  }
}
EOF

nginx -s reload

# 4. Update current environment marker
echo "$TARGET_ENV" > /opt/hgr/current_env.txt

# 5. Keep old environment running for quick rollback
echo "✓ Deployment complete. Old environment still running for rollback."
echo "To rollback: ./rollback.sh"
echo "To stop old environment: docker-compose -f docker-compose.$CURRENT_ENV.yml down"
```

### 6.2 Rolling Deployment

**File:** `scripts/deploy_rolling.sh`

```bash
#!/bin/bash
set -e

# Rolling Deployment
# Updates containers one at a time to maintain availability

SERVICES=(
  "api"
  "agent-python"
  "agent-javascript"
  "agent-rust"
  "agent-java"
)

echo "Starting rolling deployment..."

for SERVICE in "${SERVICES[@]}"; do
  echo ""
  echo "Updating $SERVICE..."
  
  # Get current replicas
  REPLICAS=$(docker-compose ps -q $SERVICE | wc -l)
  
  # Scale up
  docker-compose up -d --scale $SERVICE=$((REPLICAS + 1)) --no-recreate
  
  # Wait for new container to be healthy
  sleep 30
  
  # Remove old containers
  docker-compose up -d --scale $SERVICE=$REPLICAS --no-recreate
  
  echo "✓ $SERVICE updated"
done

echo ""
echo "✓ Rolling deployment complete"
```

---

## 7. ENVIRONMENT MANAGEMENT

### 7.1 Environment Configuration

**File:** `config/environments.yml`

```yaml
# Environment configurations for CI/CD

development:
  database_url: postgresql://dev_user:dev_pass@localhost/hgr_dev
  redis_url: redis://localhost:6379
  log_level: DEBUG
  debug_mode: true
  test_mode: true

staging:
  database_url: postgresql://staging_user:${STAGING_DB_PASS}@staging-db.local/hgr_staging
  redis_url: redis://staging-redis.local:6379
  log_level: INFO
  debug_mode: false
  test_mode: false
  monitoring_enabled: true

production:
  database_url: postgresql://prod_user:${PROD_DB_PASS}@postgres-main/hgr_prod
  redis_url: redis://redis-semantic-bus:6379
  log_level: WARNING
  debug_mode: false
  test_mode: false
  monitoring_enabled: true
  backup_enabled: true
  high_availability: true
```

### 7.2 Secret Management

**File:** `scripts/manage_secrets.sh`

```bash
#!/bin/bash

# Secret Management Script
# Uses GitHub Secrets for CI/CD

case $1 in
  encrypt)
    # Encrypt secrets for storage
    echo -n "$2" | openssl enc -aes-256-cbc -pbkdf2 -out secrets.enc
    ;;
  
  decrypt)
    # Decrypt secrets
    openssl enc -d -aes-256-cbc -pbkdf2 -in secrets.enc
    ;;
  
  rotate)
    # Rotate secrets (e.g., JWT keys, DB passwords)
    NEW_JWT_SECRET=$(openssl rand -hex 32)
    echo "New JWT secret: $NEW_JWT_SECRET"
    # Update in GitHub Secrets via API
    ;;
  
  *)
    echo "Usage: $0 {encrypt|decrypt|rotate} [value]"
    exit 1
    ;;
esac
```

---

## 8. ROLLBACK PROCEDURES

### 8.1 Automatic Rollback

**File:** `scripts/rollback.sh`

```bash
#!/bin/bash
set -e

echo "=========================================="
echo "Emergency Rollback Procedure"
echo "=========================================="

# Get previous version
CURRENT_VERSION=$(cat /opt/hgr/deployed_version.txt)
PREVIOUS_VERSION=$(git describe --abbrev=0 --tags $(git rev-list --tags --skip=1 --max-count=1))

echo "Current version: $CURRENT_VERSION"
echo "Rolling back to: $PREVIOUS_VERSION"

read -p "Confirm rollback? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "Rollback cancelled"
  exit 1
fi

# 1. Stop current deployment
docker-compose down

# 2. Checkout previous version
git checkout $PREVIOUS_VERSION

# 3. Pull previous images
docker-compose pull

# 4. Start previous version
docker-compose up -d

# 5. Wait for health checks
echo "Waiting for services to be healthy..."
sleep 60

# 6. Verify health
if curl -f http://localhost:8000/health; then
  echo "✓ Rollback successful"
  echo "$PREVIOUS_VERSION" > /opt/hgr/deployed_version.txt
else
  echo "✗ Rollback failed - manual intervention required"
  exit 1
fi

# 7. Notify team
curl -X POST $SLACK_WEBHOOK \
  -H 'Content-Type: application/json' \
  -d "{\"text\": \"🔴 Emergency rollback to $PREVIOUS_VERSION completed\"}"
```

### 8.2 Rollback Decision Matrix

| Condition | Action | Automatic? |
|-----------|--------|------------|
| **Health check fails** | Rollback immediately | Yes |
| **Error rate > 1%** | Rollback after 5 minutes | Yes |
| **Response time > 2x baseline** | Alert, manual decision | No |
| **Memory usage > 90%** | Alert, manual decision | No |
| **User reports critical bug** | Manual rollback | No |

---

## 9. PIPELINE MONITORING

### 9.1 Pipeline Metrics

**File:** `scripts/pipeline_metrics.sh`

```bash
#!/bin/bash

# Collect pipeline metrics

echo "Pipeline Metrics Report"
echo "======================="

# Build time
BUILD_TIME=$(gh run view --json timing --jq '.timing.build')
echo "Build time: ${BUILD_TIME}s"

# Test results
TEST_PASS_RATE=$(gh run view --json conclusion --jq '.conclusion')
echo "Test pass rate: $TEST_PASS_RATE"

# Deployment frequency
DEPLOY_COUNT=$(gh run list --workflow=main.yml --limit 100 --json conclusion | jq '[.[] | select(.conclusion == "success")] | length')
echo "Deployments (last 100): $DEPLOY_COUNT"

# Mean time to recovery
LAST_FAILURE=$(gh run list --workflow=main.yml --limit 1 --json createdAt,conclusion | jq -r '.[] | select(.conclusion == "failure") | .createdAt')
NEXT_SUCCESS=$(gh run list --workflow=main.yml --limit 1 --json createdAt,conclusion | jq -r '.[] | select(.conclusion == "success") | .createdAt')
# Calculate MTTR...

# Security scan results
VULN_COUNT=$(jq '[.[] | select(.severity == "HIGH" or .severity == "CRITICAL")] | length' safety-report.json)
echo "Security vulnerabilities: $VULN_COUNT"
```

### 9.2 Pipeline Dashboard

**Grafana Dashboard JSON** (snippet):

```json
{
  "dashboard": {
    "title": "CI/CD Pipeline Metrics",
    "panels": [
      {
        "title": "Build Success Rate",
        "targets": [{
          "expr": "sum(rate(ci_build_success_total[24h])) / sum(rate(ci_build_total[24h]))"
        }]
      },
      {
        "title": "Average Build Time",
        "targets": [{
          "expr": "avg(ci_build_duration_seconds)"
        }]
      },
      {
        "title": "Deployment Frequency",
        "targets": [{
          "expr": "sum(increase(deployments_total[7d]))"
        }]
      }
    ]
  }
}
```

---

## 10. BEST PRACTICES

### 10.1 Pipeline Optimization

**Speed Improvements:**
1. **Caching**: Cache dependencies between runs
2. **Parallel execution**: Run tests in parallel
3. **Incremental builds**: Only rebuild changed components
4. **Image layers**: Optimize Docker layer caching
5. **Test selection**: Run affected tests only

**Example: Cached Dependencies**

```yaml
- name: Cache dependencies
  uses: actions/cache@v3
  with:
    path: |
      ~/.cache/pip
      ~/.npm
    key: ${{ runner.os }}-deps-${{ hashFiles('**/requirements.txt', '**/package.json') }}
```

### 10.2 Deployment Checklist

**Pre-Deployment:**
- [ ] All tests passing (unit, integration, system)
- [ ] Security scans clear (no critical vulnerabilities)
- [ ] Code review approved
- [ ] Documentation updated
- [ ] Database migrations ready
- [ ] Rollback plan prepared
- [ ] Monitoring dashboards configured

**Post-Deployment:**
- [ ] Health checks passing
- [ ] Performance metrics normal
- [ ] Error rates within threshold
- [ ] Logs show no critical errors
- [ ] User acceptance testing passed
- [ ] Team notified
- [ ] Documentation updated with changes

### 10.3 Pipeline Maintenance

**Weekly:**
- Review failed builds and fix flaky tests
- Update dependencies to latest stable versions
- Check security scan results
- Review pipeline execution times

**Monthly:**
- Audit pipeline configuration
- Review and optimize caching strategies
- Update CI/CD documentation
- Test disaster recovery procedures

**Quarterly:**
- Full pipeline security audit
- Review deployment strategies
- Update rollback procedures
- Team training on new features

---

## DOCUMENT METADATA

**Document ID:** 24  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Owner:** Chief Architect  
**Dependencies:** Documents 22 (API), 23 (Testing)  
**Next Document:** 25 (Monitoring & Observability)

---

*End of CI/CD Pipeline Configuration*
