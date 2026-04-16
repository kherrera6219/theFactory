"""config.py — Environment configuration constants for the API Gateway.

All service-level env var reads are centralized here so that other modules
import from this file rather than calling os.getenv() directly.
"""
from __future__ import annotations

import logging
import os

LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Core service URLs
# ---------------------------------------------------------------------------
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8001")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
INTAKE_STREAM = os.getenv("INTAKE_STREAM", "missions.intake")
STATE_STREAM = os.getenv("STATE_STREAM", "missions.state")
INTAKE_TOPIC = os.getenv("INTAKE_TOPIC", "intake.feature_contract.created")
MAX_STREAM_LEN = int(os.getenv("MAX_STREAM_LEN", "20000"))
CORS_ALLOW_ORIGINS = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:3100")
INTERNAL_SERVICE_API_KEY = os.getenv("INTERNAL_SERVICE_API_KEY", "")

# ---------------------------------------------------------------------------
# Environment / auth mode
# ---------------------------------------------------------------------------
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()
AUTH_MODE_RAW = os.getenv("AUTH_MODE", "api_key").strip().lower()
VALID_AUTH_MODES = {"api_key", "hybrid", "oidc"}

# Validate AUTH_MODE at import time; fail-closed in production, log+fallback otherwise.
if AUTH_MODE_RAW not in VALID_AUTH_MODES:
    _invalid_msg = (
        f"Invalid AUTH_MODE '{AUTH_MODE_RAW}'. "
        f"Valid values: {', '.join(sorted(VALID_AUTH_MODES))}. "
        f"Falling back to api_key."
    )
    if ENVIRONMENT == "production":
        raise RuntimeError(
            f"Invalid AUTH_MODE '{AUTH_MODE_RAW}' in production. "
            f"Valid values: {', '.join(sorted(VALID_AUTH_MODES))}. "
            f"Set AUTH_MODE to a valid value before starting the service."
        )
    LOGGER.error(_invalid_msg)
    AUTH_MODE: str = "api_key"
else:
    AUTH_MODE = AUTH_MODE_RAW

LOGGER.info("api-gateway auth mode active: %s (environment=%s)", AUTH_MODE, ENVIRONMENT)

# ---------------------------------------------------------------------------
# OIDC configuration
# ---------------------------------------------------------------------------
OIDC_ISSUER_URL = os.getenv("OIDC_ISSUER_URL", "").strip()
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE", "").strip()
OIDC_JWKS_URL = os.getenv("OIDC_JWKS_URL", "").strip()
OIDC_SHARED_SECRET = os.getenv("OIDC_SHARED_SECRET", "").strip()
OIDC_REQUIRED_ROLE = os.getenv("OIDC_REQUIRED_ROLE", "mutate").strip().lower() or "mutate"
OIDC_OPERATOR_ROLE = os.getenv("OIDC_OPERATOR_ROLE", "observe").strip().lower() or "observe"
OIDC_ENFORCE_OPERATOR_ROUTES = (
    os.getenv("OIDC_ENFORCE_OPERATOR_ROUTES", "true").strip().lower()
    in {"1", "true", "yes", "on"}
)
OIDC_ROLE_CLAIMS = tuple(
    claim.strip()
    for claim in os.getenv("OIDC_ROLE_CLAIMS", "roles,role,permissions").split(",")
    if claim.strip()
)
OIDC_SCOPE_CLAIMS = tuple(
    claim.strip()
    for claim in os.getenv("OIDC_SCOPE_CLAIMS", "scope,scp").split(",")
    if claim.strip()
)
OIDC_ALLOWED_ALGORITHMS = [
    algorithm.strip()
    for algorithm in os.getenv("OIDC_ALLOWED_ALGORITHMS", "RS256,HS256").split(",")
    if algorithm.strip()
]
OIDC_LEEWAY_SECONDS = max(0.0, float(os.getenv("OIDC_LEEWAY_SECONDS", "60")))

# ---------------------------------------------------------------------------
# Rate limiting and idempotency
# ---------------------------------------------------------------------------
IDEMPOTENCY_TTL_SECONDS = int(os.getenv("IDEMPOTENCY_TTL_SECONDS", "86400"))
IDEMPOTENCY_KEY_PREFIX = "idempotency:missions"
API_RATE_LIMIT_PER_MINUTE = int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "120"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_KEY_PREFIX = "ratelimit:api-gateway"
RATE_LIMIT_HMAC_KEY = os.getenv("RATE_LIMIT_HMAC_KEY", "ratelimit-default").encode()

# ---------------------------------------------------------------------------
# SSE live stream
# ---------------------------------------------------------------------------
LIVE_STREAM_BLOCK_MS = int(os.getenv("LIVE_STREAM_BLOCK_MS", "5000"))
LIVE_STREAM_KEEPALIVE_SECONDS = float(os.getenv("LIVE_STREAM_KEEPALIVE_SECONDS", "15"))
LIVE_STREAM_COUNT = int(os.getenv("LIVE_STREAM_COUNT", "50"))

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS = [
    "Accept",
    "Authorization",
    "Content-Type",
    "Idempotency-Key",
    "X-API-Key",
]
CORS_EXPOSE_HEADERS = [
    "Retry-After",
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "X-Trace-Id",
]

# ---------------------------------------------------------------------------
# LLM provider configuration
# ---------------------------------------------------------------------------
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "offline").strip().lower()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.3-codex")
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "20"))
OPENAI_REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "medium").strip().lower()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1").rstrip("/")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip()
ANTHROPIC_TIMEOUT_SECONDS = float(os.getenv("ANTHROPIC_TIMEOUT_SECONDS", "20"))
ANTHROPIC_VERSION = os.getenv("ANTHROPIC_VERSION", "2023-06-01").strip()
ANTHROPIC_THINKING_MODE = os.getenv("ANTHROPIC_THINKING_MODE", "enabled").strip().lower()
ANTHROPIC_THINKING_BUDGET_TOKENS = int(os.getenv("ANTHROPIC_THINKING_BUDGET_TOKENS", "8192"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
).rstrip("/")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview").strip()
GEMINI_TIMEOUT_SECONDS = float(os.getenv("GEMINI_TIMEOUT_SECONDS", "20"))
GEMINI_THINKING_BUDGET = int(os.getenv("GEMINI_THINKING_BUDGET", "-1"))
GEMINI_THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "medium").strip().lower()

# ---------------------------------------------------------------------------
# Mission routing constants
# ---------------------------------------------------------------------------
PM_AGENT_ID = "AGENT-01-PM"
CEO_AGENT_ID = "AGENT-02-CEO"
DEFAULT_POD_MANAGER_AGENT_ID = "AGENT-12-PODA-MGR"
ROUTING_VERSION = "v1.1"

_POD_A_LANGUAGES = {"python", "javascript", "typescript", "ruby", "php"}
_POD_B_LANGUAGES = {"go", "rust", "c", "cpp", "zig"}
_POD_C_LANGUAGES = {"java", "csharp", "kotlin", "scala"}
_POD_D_LANGUAGES = {"matlab", "r", "julia", "mathematica", "haskell", "ocaml"}

POD_MANAGER_BY_LANGUAGE: dict[str, str] = {
    **{lang: "AGENT-12-PODA-MGR" for lang in _POD_A_LANGUAGES},
    **{lang: "AGENT-18-PODB-MGR" for lang in _POD_B_LANGUAGES},
    **{lang: "AGENT-24-PODC-MGR" for lang in _POD_C_LANGUAGES},
    **{lang: "AGENT-30-PODD-MGR" for lang in _POD_D_LANGUAGES},
}
