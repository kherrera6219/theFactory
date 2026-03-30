# DOCUMENT 26: SECURITY IMPLEMENTATION & HARDENING
## Holy Grail Refinery - Development Specifications

**Document ID:** 26  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Status:** Specification Complete

---

## EXECUTIVE SUMMARY

The Holy Grail Refinery implements **defense-in-depth security** to protect the 35-agent system, sensitive data, and API access. This document provides comprehensive security implementation guidelines, hardening procedures, and threat mitigation strategies to maintain a secure production environment.

**Security Layers:**
- **Network Security:** Firewall rules, VPN, network segmentation
- **Application Security:** Input validation, authentication, authorization
- **Data Security:** Encryption at rest and in transit, secure key management
- **Container Security:** Image scanning, runtime protection, least privilege
- **Infrastructure Security:** OS hardening, patch management, access control
- **Monitoring Security:** Intrusion detection, security logging, SIEM

**Compliance Targets:**
- 🔒 OWASP Top 10 mitigation
- 🛡️ Zero critical vulnerabilities in production
- 🔐 End-to-end encryption for sensitive data
- 📋 Audit logging for all security events
- ⚡ < 24h security patch deployment

---

## TABLE OF CONTENTS

1. [Security Architecture](#1-security-architecture)
2. [Network Security](#2-network-security)
3. [Authentication & Authorization](#3-authentication--authorization)
4. [Data Encryption](#4-data-encryption)
5. [Container Security](#5-container-security)
6. [API Security](#6-api-security)
7. [Secrets Management](#7-secrets-management)
8. [Security Monitoring](#8-security-monitoring)
9. [Incident Response](#9-incident-response)
10. [Compliance & Auditing](#10-compliance--auditing)

---

## 1. SECURITY ARCHITECTURE

### 1.1 Defense-in-Depth Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 7: MONITORING                       │
│  • SIEM (Security Information & Event Management)            │
│  • Intrusion Detection (IDS/IPS)                             │
│  • Security Logging & Alerts                                 │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 6: APPLICATION                      │
│  • Input Validation                                          │
│  • Authentication (JWT, OAuth2)                              │
│  • Authorization (RBAC)                                      │
│  • Rate Limiting                                             │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 5: DATA                             │
│  • Encryption at Rest (AES-256)                              │
│  • Encryption in Transit (TLS 1.3)                           │
│  • Key Management (Vault)                                    │
│  • Data Masking                                              │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 4: CONTAINER                        │
│  • Image Scanning (Trivy)                                    │
│  • Runtime Security (Falco)                                  │
│  • Least Privilege                                           │
│  • Network Policies                                          │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 3: INFRASTRUCTURE                   │
│  • OS Hardening (CIS Benchmarks)                             │
│  • Patch Management                                          │
│  • Access Control (SSH keys only)                            │
│  • Audit Logging                                             │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 2: NETWORK                          │
│  • Firewall (iptables/nftables)                              │
│  • Network Segmentation                                      │
│  • VPN Access                                                │
│  • DDoS Protection                                           │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌─────────────────────────────────────────────────────────────┐
│                    LAYER 1: PHYSICAL                         │
│  • Hardware Security (AW1 local)                             │
│  • Physical Access Control                                   │
│  • Secure Boot                                               │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 Threat Model

| Threat | Impact | Likelihood | Mitigation |
|--------|--------|------------|------------|
| **Unauthorized API Access** | High | Medium | JWT auth, rate limiting, IP whitelist |
| **SQL Injection** | Critical | Low | Parameterized queries, ORM, input validation |
| **Container Escape** | Critical | Low | Minimal images, SELinux, AppArmor |
| **Secrets Exposure** | High | Medium | Vault, encrypted env vars, no hardcoding |
| **DDoS Attack** | High | Medium | Rate limiting, Cloudflare, failover |
| **Insider Threat** | High | Low | RBAC, audit logging, least privilege |
| **Supply Chain Attack** | Critical | Low | Image scanning, SBOMs, signed images |
| **Data Breach** | Critical | Low | Encryption, access control, monitoring |

---

## 2. NETWORK SECURITY

### 2.1 Firewall Configuration

**File:** `security/iptables.rules`

```bash
#!/bin/bash
# Firewall rules for Holy Grail Refinery

# Flush existing rules
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X
iptables -t mangle -F
iptables -t mangle -X

# Set default policies
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Allow loopback
iptables -A INPUT -i lo -j ACCEPT

# Allow established connections
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow SSH (only from specific IPs)
iptables -A INPUT -p tcp --dport 22 -s 192.168.1.0/24 -j ACCEPT

# Allow HTTP/HTTPS (API)
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# Allow Prometheus (internal only)
iptables -A INPUT -p tcp --dport 9090 -s 127.0.0.1 -j ACCEPT

# Allow Grafana (internal only)
iptables -A INPUT -p tcp --dport 3000 -s 127.0.0.1 -j ACCEPT

# Rate limiting for API
iptables -A INPUT -p tcp --dport 80 -m state --state NEW -m recent --set
iptables -A INPUT -p tcp --dport 80 -m state --state NEW -m recent --update --seconds 1 --hitcount 20 -j DROP

# Log dropped packets
iptables -A INPUT -m limit --limit 5/min -j LOG --log-prefix "iptables-dropped: " --log-level 7

# Save rules
iptables-save > /etc/iptables/rules.v4
```

### 2.2 Network Segmentation

**File:** `docker-compose.security.yml`

```yaml
version: '3.8'

# Network segmentation for security isolation
networks:
  frontend:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/24
  
  backend:
    driver: bridge
    internal: true  # No external access
    ipam:
      config:
        - subnet: 172.21.0.0/24
  
  database:
    driver: bridge
    internal: true  # No external access
    ipam:
      config:
        - subnet: 172.22.0.0/24

services:
  # API in frontend network (external access)
  api:
    networks:
      - frontend
      - backend
  
  # Agents in backend network (no direct external access)
  agent-python:
    networks:
      - backend
  
  # Database in isolated network
  postgres:
    networks:
      - database
  
  # Redis in backend network
  redis:
    networks:
      - backend
```

### 2.3 TLS Configuration

**File:** `nginx/ssl.conf`

```nginx
# Strong SSL configuration
ssl_protocols TLSv1.3 TLSv1.2;
ssl_ciphers 'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305';
ssl_prefer_server_ciphers on;

# SSL session settings
ssl_session_cache shared:SSL:10m;
ssl_session_timeout 10m;
ssl_session_tickets off;

# OCSP stapling
ssl_stapling on;
ssl_stapling_verify on;
resolver 8.8.8.8 8.8.4.4 valid=300s;
resolver_timeout 5s;

# Security headers
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Frame-Options DENY always;
add_header X-Content-Type-Options nosniff always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "no-referrer-when-downgrade" always;
add_header Content-Security-Policy "default-src 'self'" always;

# SSL certificates
ssl_certificate /etc/nginx/ssl/cert.pem;
ssl_certificate_key /etc/nginx/ssl/key.pem;
ssl_trusted_certificate /etc/nginx/ssl/chain.pem;
```

---

## 3. AUTHENTICATION & AUTHORIZATION

### 3.1 Enhanced JWT Implementation

**File:** `api/auth/secure_jwt.py`

```python
"""
Secure JWT implementation with additional protections
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import HTTPException, status
import secrets
import hashlib

# Security configuration
SECRET_KEY = secrets.token_urlsafe(32)  # Generate secure key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30  # Short-lived tokens
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Increased rounds for security
)


class SecureJWTHandler:
    """Enhanced JWT handler with security features"""
    
    def __init__(self):
        self.blacklist = set()  # Token blacklist for revocation
        self.token_family = {}  # Track token families for security
    
    def create_access_token(
        self,
        user_id: str,
        scopes: list,
        additional_claims: Optional[Dict] = None
    ) -> str:
        """
        Create secure access token
        
        Security features:
        - Short expiration (30 minutes)
        - Unique JTI (JWT ID) for tracking
        - Token family ID for refresh token rotation
        - IP address binding (optional)
        """
        jti = secrets.token_urlsafe(16)
        family_id = secrets.token_urlsafe(16)
        
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        claims = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "nbf": datetime.utcnow(),  # Not before
            "jti": jti,
            "scopes": scopes,
            "type": "access",
            "family": family_id
        }
        
        # Add additional claims if provided
        if additional_claims:
            claims.update(additional_claims)
        
        # Store token family
        self.token_family[jti] = family_id
        
        token = jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)
        return token
    
    def create_refresh_token(
        self,
        user_id: str,
        family_id: str
    ) -> str:
        """
        Create refresh token with rotation support
        """
        jti = secrets.token_urlsafe(16)
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        claims = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": jti,
            "type": "refresh",
            "family": family_id
        }
        
        token = jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)
        return token
    
    def verify_token(
        self,
        token: str,
        expected_type: str = "access"
    ) -> Dict[str, Any]:
        """
        Verify token with security checks
        
        Checks:
        - Signature validity
        - Expiration
        - Type matches expected
        - Not blacklisted
        - Token family valid
        """
        try:
            # Decode token
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            
            # Check type
            if payload.get("type") != expected_type:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type"
                )
            
            # Check blacklist
            jti = payload.get("jti")
            if jti in self.blacklist:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked"
                )
            
            # Check token family (detect token reuse)
            if expected_type == "refresh":
                family_id = payload.get("family")
                if family_id and family_id in self._get_invalidated_families():
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token family invalidated (possible security breach)"
                    )
            
            return payload
            
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}"
            )
    
    def revoke_token(self, jti: str):
        """Revoke token by adding to blacklist"""
        self.blacklist.add(jti)
    
    def invalidate_token_family(self, family_id: str):
        """Invalidate entire token family (on security breach)"""
        # Add to invalidated families
        # Implementation depends on persistent storage
        pass
    
    def _get_invalidated_families(self) -> set:
        """Get set of invalidated token families"""
        # Implementation depends on persistent storage
        return set()
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password with bcrypt"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(plain_password, hashed_password)


# Rate limiting for authentication attempts
class AuthRateLimiter:
    """Rate limiter for authentication attempts"""
    
    def __init__(self):
        self.attempts = {}  # user_id -> (count, timestamp)
        self.lockout_duration = 900  # 15 minutes
        self.max_attempts = 5
    
    def check_rate_limit(self, user_id: str) -> bool:
        """
        Check if user can attempt login
        
        Returns:
            True if allowed, False if rate limited
        """
        now = datetime.utcnow()
        
        if user_id in self.attempts:
            count, first_attempt = self.attempts[user_id]
            
            # Check if lockout period has passed
            if (now - first_attempt).total_seconds() > self.lockout_duration:
                # Reset counter
                self.attempts[user_id] = (1, now)
                return True
            
            # Check attempt count
            if count >= self.max_attempts:
                return False
            
            # Increment counter
            self.attempts[user_id] = (count + 1, first_attempt)
        else:
            # First attempt
            self.attempts[user_id] = (1, now)
        
        return True
    
    def reset_attempts(self, user_id: str):
        """Reset failed attempts (on successful login)"""
        if user_id in self.attempts:
            del self.attempts[user_id]
```

### 3.2 Role-Based Access Control (RBAC)

**File:** `api/auth/rbac.py`

```python
"""
Role-Based Access Control implementation
"""

from typing import List, Set
from enum import Enum
from fastapi import HTTPException, status


class Permission(str, Enum):
    """System permissions"""
    # LogicNodes
    READ_LOGICNODES = "read:logicnodes"
    WRITE_LOGICNODES = "write:logicnodes"
    DELETE_LOGICNODES = "delete:logicnodes"
    
    # Tasks
    READ_TASKS = "read:tasks"
    WRITE_TASKS = "write:tasks"
    
    # Agents
    READ_AGENTS = "read:agents"
    CONTROL_AGENTS = "control:agents"
    
    # Audit
    READ_AUDIT = "read:audit"
    
    # Admin
    ADMIN_ALL = "admin:all"


class Role(str, Enum):
    """User roles"""
    VIEWER = "viewer"
    DEVELOPER = "developer"
    MANAGER = "manager"
    ADMIN = "admin"


# Role-to-permissions mapping
ROLE_PERMISSIONS = {
    Role.VIEWER: {
        Permission.READ_LOGICNODES,
        Permission.READ_TASKS,
        Permission.READ_AGENTS
    },
    Role.DEVELOPER: {
        Permission.READ_LOGICNODES,
        Permission.WRITE_LOGICNODES,
        Permission.READ_TASKS,
        Permission.WRITE_TASKS,
        Permission.READ_AGENTS,
        Permission.READ_AUDIT
    },
    Role.MANAGER: {
        Permission.READ_LOGICNODES,
        Permission.WRITE_LOGICNODES,
        Permission.DELETE_LOGICNODES,
        Permission.READ_TASKS,
        Permission.WRITE_TASKS,
        Permission.READ_AGENTS,
        Permission.CONTROL_AGENTS,
        Permission.READ_AUDIT
    },
    Role.ADMIN: {
        Permission.ADMIN_ALL  # Grants all permissions
    }
}


class RBACManager:
    """RBAC manager for permission checking"""
    
    @staticmethod
    def get_permissions_for_role(role: Role) -> Set[Permission]:
        """Get permissions for a role"""
        return ROLE_PERMISSIONS.get(role, set())
    
    @staticmethod
    def has_permission(user_roles: List[Role], required_permission: Permission) -> bool:
        """
        Check if user has required permission
        
        Args:
            user_roles: List of user's roles
            required_permission: Permission to check
            
        Returns:
            True if user has permission
        """
        # Admin has all permissions
        if Role.ADMIN in user_roles:
            return True
        
        # Check each role
        for role in user_roles:
            role_perms = ROLE_PERMISSIONS.get(role, set())
            if required_permission in role_perms:
                return True
        
        return False
    
    @staticmethod
    def require_permission(required_permission: Permission):
        """
        Decorator to require specific permission
        
        Usage:
            @require_permission(Permission.WRITE_LOGICNODES)
            async def create_logicnode(...):
                pass
        """
        def decorator(func):
            async def wrapper(*args, **kwargs):
                # Get user from request context
                user = kwargs.get('user')
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required"
                    )
                
                # Get user roles
                user_roles = user.get('roles', [])
                
                # Check permission
                if not RBACManager.has_permission(user_roles, required_permission):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied: {required_permission}"
                    )
                
                return await func(*args, **kwargs)
            
            return wrapper
        return decorator
```

---

## 4. DATA ENCRYPTION

### 4.1 Encryption at Rest

**File:** `security/encryption.py`

```python
"""
Data encryption utilities
"""

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.backends import default_backend
import base64
import os


class DataEncryption:
    """Handle encryption/decryption of sensitive data"""
    
    def __init__(self, master_key: bytes = None):
        """
        Initialize encryption handler
        
        Args:
            master_key: Master encryption key (32 bytes)
                       If None, loads from environment
        """
        if master_key is None:
            master_key_b64 = os.getenv('MASTER_ENCRYPTION_KEY')
            if not master_key_b64:
                raise ValueError("MASTER_ENCRYPTION_KEY not set")
            master_key = base64.urlsafe_b64decode(master_key_b64)
        
        self.master_key = master_key
        self.fernet = Fernet(base64.urlsafe_b64encode(master_key))
    
    def encrypt(self, data: str) -> str:
        """
        Encrypt string data
        
        Args:
            data: Plain text data
            
        Returns:
            Base64-encoded encrypted data
        """
        encrypted = self.fernet.encrypt(data.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt string data
        
        Args:
            encrypted_data: Base64-encoded encrypted data
            
        Returns:
            Plain text data
        """
        encrypted = base64.urlsafe_b64decode(encrypted_data.encode())
        decrypted = self.fernet.decrypt(encrypted)
        return decrypted.decode()
    
    @staticmethod
    def generate_key() -> bytes:
        """Generate new encryption key"""
        return Fernet.generate_key()
    
    @staticmethod
    def derive_key_from_password(password: str, salt: bytes = None) -> tuple:
        """
        Derive encryption key from password
        
        Args:
            password: User password
            salt: Salt (generated if None)
            
        Returns:
            (key, salt) tuple
        """
        if salt is None:
            salt = os.urandom(16)
        
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        key = kdf.derive(password.encode())
        return key, salt


# Database field encryption
class EncryptedField:
    """
    Encrypt sensitive database fields
    
    Usage in SQLAlchemy model:
        class User(Base):
            ssn = Column(String, EncryptedField())
    """
    
    def __init__(self):
        self.encryptor = DataEncryption()
    
    def process_bind_param(self, value, dialect):
        """Encrypt before storing"""
        if value is not None:
            return self.encryptor.encrypt(value)
        return value
    
    def process_result_value(self, value, dialect):
        """Decrypt after retrieving"""
        if value is not None:
            return self.encryptor.decrypt(value)
        return value
```

### 4.2 PostgreSQL Encryption

**File:** `database/encryption_setup.sql`

```sql
-- Enable pgcrypto extension for database-level encryption
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Encrypt sensitive columns
ALTER TABLE users 
ADD COLUMN email_encrypted BYTEA;

-- Encrypt existing data
UPDATE users 
SET email_encrypted = pgp_sym_encrypt(email, current_setting('app.encryption_key'));

-- Create encrypted view
CREATE VIEW users_decrypted AS
SELECT 
    user_id,
    username,
    pgp_sym_decrypt(email_encrypted, current_setting('app.encryption_key')) AS email
FROM users;

-- Grant access to view only
REVOKE ALL ON users FROM app_user;
GRANT SELECT ON users_decrypted TO app_user;
```

---

## 5. CONTAINER SECURITY

### 5.1 Secure Dockerfile

**File:** `docker/secure-agent.Dockerfile`

```dockerfile
# ============================================================================
# Stage 1: Builder (minimal dependencies)
# ============================================================================
FROM python:3.11-slim AS builder

# Install only build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir --no-warn-script-location -r requirements.txt

# ============================================================================
# Stage 2: Runtime (minimal, hardened)
# ============================================================================
FROM python:3.11-slim

# Security: Run as non-root user
RUN groupadd -r hgr && useradd -r -g hgr -u 1000 hgr

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python packages from builder
COPY --from=builder /root/.local /home/hgr/.local

# Set up application
WORKDIR /app
COPY --chown=hgr:hgr agents/ ./agents/

# Security: Remove unnecessary files
RUN find /app -type f -name "*.pyc" -delete \
    && find /app -type d -name "__pycache__" -delete \
    && find /app -type f -name "*.md" -delete

# Security: Set read-only filesystem (where possible)
RUN chmod -R 555 /app/agents

# Security: Disable shell for hgr user
RUN usermod -s /usr/sbin/nologin hgr

# Switch to non-root user
USER hgr

# Set environment
ENV PATH=/home/hgr/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD python -c "import sys; sys.exit(0)"

# Run application
CMD ["python", "-m", "agents.specialists.python_agent"]
```

### 5.2 Container Runtime Security

**File:** `docker-compose.security.yml`

```yaml
version: '3.8'

services:
  agent-python:
    image: hgr-agent-python:secure
    
    # Security: Read-only root filesystem
    read_only: true
    
    # Security: Temporary filesystem for /tmp
    tmpfs:
      - /tmp:noexec,nosuid,size=100m
    
    # Security: Drop all capabilities, add only needed
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE  # Only if needed
    
    # Security: No new privileges
    security_opt:
      - no-new-privileges:true
    
    # Security: AppArmor profile
    security_opt:
      - apparmor=docker-default
    
    # Security: Seccomp profile
    security_opt:
      - seccomp=/etc/docker/seccomp-profile.json
    
    # Security: Resource limits
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
          pids: 100  # Limit process count
    
    # Security: Disable privileged mode
    privileged: false
    
    # Security: Network mode
    network_mode: bridge
    
    # Security: Environment variables from secrets
    env_file:
      - secrets.env
```

### 5.3 Image Scanning

**File:** `security/scan-images.sh`

```bash
#!/bin/bash
set -e

echo "Scanning Docker images for vulnerabilities..."

IMAGES=(
    "hgr-api:latest"
    "hgr-agent-python:latest"
    "hgr-agent-javascript:latest"
    "hgr-agent-rust:latest"
)

CRITICAL_COUNT=0

for IMAGE in "${IMAGES[@]}"; do
    echo ""
    echo "Scanning $IMAGE..."
    
    # Scan with Trivy
    trivy image \
        --severity HIGH,CRITICAL \
        --exit-code 1 \
        --no-progress \
        "$IMAGE" || CRITICAL_COUNT=$((CRITICAL_COUNT + 1))
done

if [ $CRITICAL_COUNT -gt 0 ]; then
    echo ""
    echo "❌ Found critical vulnerabilities in $CRITICAL_COUNT image(s)"
    exit 1
else
    echo ""
    echo "✓ All images passed security scan"
    exit 0
fi
```

---

## 6. API SECURITY

### 6.1 Input Validation

**File:** `api/security/input_validation.py`

```python
"""
Input validation and sanitization
"""

import re
from typing import Any
from fastapi import HTTPException, status
import bleach


class InputValidator:
    """Validate and sanitize user inputs"""
    
    @staticmethod
    def validate_agent_id(agent_id: str) -> str:
        """
        Validate agent ID format
        
        Args:
            agent_id: Agent ID to validate
            
        Returns:
            Validated agent ID
            
        Raises:
            HTTPException: If invalid
        """
        pattern = r'^[A-Z]+-[A-Z0-9]+-\d{3}$'
        if not re.match(pattern, agent_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid agent ID format: {agent_id}"
            )
        return agent_id
    
    @staticmethod
    def validate_task_id(task_id: str) -> str:
        """Validate task ID format"""
        pattern = r'^task-[a-f0-9]{12}$'
        if not re.match(pattern, task_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid task ID format: {task_id}"
            )
        return task_id
    
    @staticmethod
    def sanitize_html(html: str) -> str:
        """
        Sanitize HTML to prevent XSS
        
        Args:
            html: Raw HTML
            
        Returns:
            Sanitized HTML
        """
        allowed_tags = ['p', 'br', 'strong', 'em', 'ul', 'li', 'ol']
        allowed_attributes = {}
        
        return bleach.clean(
            html,
            tags=allowed_tags,
            attributes=allowed_attributes,
            strip=True
        )
    
    @staticmethod
    def validate_sql_safe(value: str) -> str:
        """
        Check for SQL injection patterns
        
        Note: This is defense-in-depth. Primary protection
        is parameterized queries.
        """
        dangerous_patterns = [
            r"('|(--)|;|/\*|\*/|xp_|sp_|0x)",
            r"(union|select|insert|update|delete|drop|create|alter|exec|execute)",
        ]
        
        value_lower = value.lower()
        for pattern in dangerous_patterns:
            if re.search(pattern, value_lower):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Input contains potentially dangerous patterns"
                )
        
        return value
    
    @staticmethod
    def validate_file_path(file_path: str) -> str:
        """
        Validate file path to prevent directory traversal
        
        Args:
            file_path: File path to validate
            
        Returns:
            Validated file path
            
        Raises:
            HTTPException: If path contains traversal attempts
        """
        # Check for path traversal
        if '..' in file_path or file_path.startswith('/'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file path"
            )
        
        # Only allow alphanumeric, dash, underscore, dot
        if not re.match(r'^[a-zA-Z0-9_\-./]+$', file_path):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File path contains invalid characters"
            )
        
        return file_path
```

### 6.2 CORS Configuration

**File:** `api/security/cors.py`

```python
"""
CORS (Cross-Origin Resource Sharing) configuration
"""

from fastapi.middleware.cors import CORSMiddleware

def configure_cors(app):
    """Configure CORS for production"""
    
    # Production: Strict CORS
    allowed_origins = [
        "https://hgr.example.com",
        "https://app.hgr.example.com"
    ]
    
    # Development: Allow localhost
    if app.debug:
        allowed_origins.extend([
            "http://localhost:3000",
            "http://localhost:8080"
        ])
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=3600  # Cache preflight requests
    )
```

---

## 7. SECRETS MANAGEMENT

### 7.1 HashiCorp Vault Integration

**File:** `security/vault.py`

```python
"""
HashiCorp Vault integration for secrets management
"""

import hvac
import os
from typing import Dict, Any


class VaultManager:
    """Manage secrets in HashiCorp Vault"""
    
    def __init__(self):
        """Initialize Vault client"""
        vault_addr = os.getenv('VAULT_ADDR', 'http://localhost:8200')
        vault_token = os.getenv('VAULT_TOKEN')
        
        if not vault_token:
            raise ValueError("VAULT_TOKEN not set")
        
        self.client = hvac.Client(
            url=vault_addr,
            token=vault_token
        )
        
        if not self.client.is_authenticated():
            raise ValueError("Vault authentication failed")
    
    def read_secret(self, path: str) -> Dict[str, Any]:
        """
        Read secret from Vault
        
        Args:
            path: Secret path (e.g., 'secret/data/hgr/db')
            
        Returns:
            Secret data
        """
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path
            )
            return response['data']['data']
        except Exception as e:
            raise ValueError(f"Failed to read secret {path}: {e}")
    
    def write_secret(self, path: str, data: Dict[str, Any]):
        """
        Write secret to Vault
        
        Args:
            path: Secret path
            data: Secret data
        """
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret=data
            )
        except Exception as e:
            raise ValueError(f"Failed to write secret {path}: {e}")
    
    def delete_secret(self, path: str):
        """Delete secret from Vault"""
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=path
            )
        except Exception as e:
            raise ValueError(f"Failed to delete secret {path}: {e}")
    
    def rotate_secret(self, path: str, new_value: str):
        """
        Rotate secret (create new version)
        
        Args:
            path: Secret path
            new_value: New secret value
        """
        current_secret = self.read_secret(path)
        current_secret['value'] = new_value
        self.write_secret(path, current_secret)


# Usage example
vault = VaultManager()

# Store database credentials
vault.write_secret('hgr/database', {
    'username': 'hgr_admin',
    'password': 'secure_password_here',
    'host': 'postgres-main',
    'port': 5432
})

# Retrieve credentials
db_creds = vault.read_secret('hgr/database')
```

### 7.2 Environment Variable Management

**File:** `.env.encrypted`

```bash
# Encrypted environment variables
# Decrypt with: gpg --decrypt .env.encrypted > .env

# Database
DATABASE_URL=postgresql://user:ENCRYPTED_PASSWORD@localhost/hgr
POSTGRES_PASSWORD=ENCRYPTED_PASSWORD

# Redis
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=ENCRYPTED_PASSWORD

# JWT
JWT_SECRET_KEY=ENCRYPTED_SECRET

# API Keys (per agent)
AGENT_PY_001_API_KEY=ENCRYPTED_KEY
AGENT_JS_001_API_KEY=ENCRYPTED_KEY

# Encryption
MASTER_ENCRYPTION_KEY=ENCRYPTED_KEY

# Vault
VAULT_ADDR=http://localhost:8200
VAULT_TOKEN=ENCRYPTED_TOKEN
```

**Encryption script:**

```bash
#!/bin/bash
# Encrypt sensitive environment variables

# Generate GPG key if needed
if ! gpg --list-keys "hgr-secrets" > /dev/null 2>&1; then
    gpg --batch --gen-key <<EOF
Key-Type: RSA
Key-Length: 4096
Name-Real: HGR Secrets
Name-Email: secrets@hgr.local
Expire-Date: 1y
%no-protection
%commit
EOF
fi

# Encrypt .env file
gpg --encrypt --recipient "hgr-secrets" .env > .env.encrypted

echo "✓ Environment variables encrypted"
echo "Decrypt with: gpg --decrypt .env.encrypted > .env"
```

---

## 8. SECURITY MONITORING

### 8.1 Intrusion Detection (Falco)

**File:** `security/falco-rules.yaml`

```yaml
# Custom Falco rules for Holy Grail Refinery

- rule: Unauthorized Container Access
  desc: Detect unauthorized access to sensitive containers
  condition: >
    container.name in (postgres-main, redis-semantic-bus)
    and not user.name in (hgr, postgres, redis)
  output: >
    Unauthorized access to sensitive container
    (user=%user.name container=%container.name command=%proc.cmdline)
  priority: CRITICAL

- rule: Suspicious File Access
  desc: Detect access to sensitive files
  condition: >
    open_read and
    fd.name in (/etc/shadow, /etc/passwd, /root/.ssh/id_rsa)
  output: >
    Suspicious file access
    (user=%user.name file=%fd.name command=%proc.cmdline)
  priority: CRITICAL

- rule: Container Drift Detection
  desc: Detect changes to running containers
  condition: >
    container and
    (proc.name in (apt, apt-get, yum, rpm) or
     spawned_process and proc.pname in (sh, bash))
  output: >
    Container drift detected
    (container=%container.name command=%proc.cmdline)
  priority: WARNING

- rule: Reverse Shell Detection
  desc: Detect potential reverse shell
  condition: >
    spawned_process and
    (proc.name in (nc, ncat, socat, telnet) or
     proc.cmdline contains "/bin/sh" or
     proc.cmdline contains "/bin/bash")
  output: >
    Potential reverse shell detected
    (user=%user.name command=%proc.cmdline)
  priority: CRITICAL
```

### 8.2 Security Event Logging

**File:** `security/security_logger.py`

```python
"""
Security event logging
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any


class SecurityLogger:
    """Log security-relevant events"""
    
    def __init__(self):
        self.logger = logging.getLogger('security')
        self.logger.setLevel(logging.INFO)
        
        # JSON formatter for structured logging
        handler = logging.FileHandler('/var/log/hgr/security.log')
        handler.setFormatter(self._get_json_formatter())
        self.logger.addHandler(handler)
    
    def log_authentication_success(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str
    ):
        """Log successful authentication"""
        self.logger.info(json.dumps({
            'event_type': 'authentication_success',
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'ip_address': ip_address,
            'user_agent': user_agent
        }))
    
    def log_authentication_failure(
        self,
        username: str,
        ip_address: str,
        reason: str
    ):
        """Log failed authentication attempt"""
        self.logger.warning(json.dumps({
            'event_type': 'authentication_failure',
            'timestamp': datetime.utcnow().isoformat(),
            'username': username,
            'ip_address': ip_address,
            'reason': reason
        }))
    
    def log_authorization_failure(
        self,
        user_id: str,
        resource: str,
        action: str,
        reason: str
    ):
        """Log authorization failure"""
        self.logger.warning(json.dumps({
            'event_type': 'authorization_failure',
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'resource': resource,
            'action': action,
            'reason': reason
        }))
    
    def log_suspicious_activity(
        self,
        user_id: str,
        activity: str,
        details: Dict[str, Any]
    ):
        """Log suspicious activity"""
        self.logger.error(json.dumps({
            'event_type': 'suspicious_activity',
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'activity': activity,
            'details': details
        }))
    
    def log_data_access(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str
    ):
        """Log sensitive data access"""
        self.logger.info(json.dumps({
            'event_type': 'data_access',
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'action': action
        }))
    
    @staticmethod
    def _get_json_formatter():
        """Get JSON log formatter"""
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                return record.getMessage()
        
        return JSONFormatter()
```

---

## 9. INCIDENT RESPONSE

### 9.1 Security Incident Playbook

**File:** `docs/security/incident-response.md`

```markdown
# Security Incident Response Playbook

## Severity Levels

| Level | Description | Response Time |
|-------|-------------|---------------|
| **P0 - Critical** | Active breach, data exfiltration | < 15 minutes |
| **P1 - High** | Unauthorized access, privilege escalation | < 1 hour |
| **P2 - Medium** | Suspicious activity, failed attacks | < 4 hours |
| **P3 - Low** | Policy violations, minor issues | < 24 hours |

## Incident Response Steps

### 1. Detection & Triage (0-15 minutes)

**Actions:**
- Alert received via monitoring system
- Assign severity level
- Notify security team
- Begin evidence collection

**Commands:**
```bash
# Check security logs
tail -f /var/log/hgr/security.log

# Check active connections
netstat -tulpn

# Check running processes
docker ps -a
```

### 2. Containment (15-60 minutes)

**For Active Breach (P0):**
```bash
# Immediate actions
# 1. Isolate affected systems
iptables -A INPUT -j DROP
iptables -A OUTPUT -j DROP

# 2. Stop affected containers
docker stop <compromised_container>

# 3. Capture evidence
docker logs <compromised_container> > /evidence/logs_$(date +%s).txt
docker inspect <compromised_container> > /evidence/inspect_$(date +%s).json

# 4. Block attacker IP
iptables -A INPUT -s <attacker_ip> -j DROP
```

**For Unauthorized Access (P1):**
```bash
# 1. Revoke user access
# Via API
curl -X POST https://api.hgr.local/auth/revoke \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"user_id": "<compromised_user>"}'

# 2. Invalidate sessions
redis-cli DEL "session:<user_id>:*"

# 3. Change credentials
vault write hgr/database password="$(openssl rand -base64 32)"
```

### 3. Eradication (1-4 hours)

**Actions:**
- Identify root cause
- Remove malicious code/backdoors
- Patch vulnerabilities
- Update security rules

```bash
# Scan for malware
clamscan -r /app --infected --log=/evidence/scan.log

# Check for backdoors
find /app -name "*.php" -exec grep -l "eval" {} \;
find /app -name "*.py" -exec grep -l "__import__('os').system" {} \;

# Update and rebuild images
docker build -t hgr-api:secure-$(date +%s) .
docker-compose up -d
```

### 4. Recovery (4-24 hours)

**Actions:**
- Restore from clean backups
- Rebuild compromised systems
- Verify system integrity
- Resume normal operations

```bash
# Restore from backup
./scripts/restore_backup.sh /backups/clean_backup.tar.gz

# Verify integrity
sha256sum -c /backups/checksums.txt

# Restart services
docker-compose up -d

# Verify health
curl https://api.hgr.local/health
```

### 5. Post-Incident (24-72 hours)

**Actions:**
- Write incident report
- Update security procedures
- Conduct lessons learned session
- Implement preventive measures
```

### 9.2 Automated Incident Response

**File:** `security/auto_response.py`

```python
"""
Automated incident response actions
"""

import subprocess
from typing import List


class AutoResponse:
    """Automated incident response"""
    
    @staticmethod
    def block_ip(ip_address: str):
        """Block IP address at firewall"""
        subprocess.run([
            'iptables', '-A', 'INPUT',
            '-s', ip_address,
            '-j', 'DROP'
        ])
        print(f"Blocked IP: {ip_address}")
    
    @staticmethod
    def isolate_container(container_name: str):
        """Isolate container from network"""
        subprocess.run([
            'docker', 'network', 'disconnect',
            'hgr-network', container_name
        ])
        print(f"Isolated container: {container_name}")
    
    @staticmethod
    def revoke_user_access(user_id: str):
        """Revoke all user access"""
        # Invalidate JWT tokens
        from api.auth.secure_jwt import SecureJWTHandler
        jwt_handler = SecureJWTHandler()
        
        # Get all tokens for user and blacklist them
        # Implementation depends on token storage
        
        print(f"Revoked access for user: {user_id}")
    
    @staticmethod
    def trigger_backup():
        """Trigger emergency backup"""
        subprocess.run(['/scripts/emergency_backup.sh'])
        print("Emergency backup triggered")
```

---

## 10. COMPLIANCE & AUDITING

### 10.1 Audit Logging

**File:** `security/audit_log.py`

```python
"""
Comprehensive audit logging
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any


class AuditLogger:
    """Log all security-relevant actions for compliance"""
    
    def __init__(self):
        self.logger = logging.getLogger('audit')
        handler = logging.FileHandler('/var/log/hgr/audit.log')
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_action(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        result: str,
        details: Dict[str, Any] = None
    ):
        """
        Log security-relevant action
        
        Args:
            user_id: User performing action
            action: Action type (create, read, update, delete)
            resource_type: Type of resource (logicnode, task, etc.)
            resource_id: Resource identifier
            result: Result (success, failure)
            details: Additional details
        """
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'action': action,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'result': result,
            'details': details or {}
        }
        
        self.logger.info(json.dumps(log_entry))


# Usage in API endpoints
audit = AuditLogger()

@app.delete("/api/v1/logicnodes/{logicnode_id}")
async def delete_logicnode(logicnode_id: str, user: dict = Depends(get_current_user)):
    # Delete logicnode
    result = db.delete(logicnode_id)
    
    # Audit log
    audit.log_action(
        user_id=user['sub'],
        action='delete',
        resource_type='logicnode',
        resource_id=logicnode_id,
        result='success' if result else 'failure'
    )
    
    return {"status": "deleted"}
```

### 10.2 Compliance Checks

**File:** `security/compliance_check.sh`

```bash
#!/bin/bash
# Compliance verification script

echo "Running compliance checks..."

# Check 1: All containers running as non-root
echo "Checking container users..."
for container in $(docker ps --format "{{.Names}}"); do
    USER=$(docker exec $container whoami 2>/dev/null)
    if [ "$USER" == "root" ]; then
        echo "❌ $container running as root"
    else
        echo "✓ $container running as $USER"
    fi
done

# Check 2: TLS enabled
echo "Checking TLS configuration..."
if curl -k https://localhost:443/health > /dev/null 2>&1; then
    echo "✓ TLS enabled"
else
    echo "❌ TLS not configured"
fi

# Check 3: Audit logging enabled
echo "Checking audit logs..."
if [ -f /var/log/hgr/audit.log ]; then
    ENTRIES=$(wc -l < /var/log/hgr/audit.log)
    echo "✓ Audit log active ($ENTRIES entries)"
else
    echo "❌ Audit log not found"
fi

# Check 4: Password policy
echo "Checking password policy..."
# Implementation depends on authentication system

# Check 5: Backup encryption
echo "Checking backup encryption..."
if gpg --list-packets /backups/latest.tar.gz.gpg > /dev/null 2>&1; then
    echo "✓ Backups encrypted"
else
    echo "❌ Backups not encrypted"
fi

echo "Compliance check complete"
```

---

## DOCUMENT METADATA

**Document ID:** 26  
**Version:** 1.0  
**Created:** February 5, 2026  
**Category:** Development & Implementation  
**Owner:** Chief Security Officer  
**Dependencies:** Documents 19-25  
**Next Document:** 27 (Agent Deployment & Operations Guide)

---

*End of Security Implementation & Hardening*
