"""Tests for agent_runtime circuit breaker — Phase 3."""
from __future__ import annotations

import importlib
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "agent-runtime"))
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

# agent_runtime.main requires SERVICE_API_KEY to be set (no default credential
# is allowed) — provide a test-only value for the duration of the import only,
# so this doesn't leak into other test files' processes (module import is
# process-wide, not per-test-scoped, so monkeypatch can't cover this).
_PRIOR_SERVICE_API_KEY = os.environ.get("SERVICE_API_KEY")
os.environ["SERVICE_API_KEY"] = "test-service-key"
try:
    # Import the class directly (not the module-level singleton)
    _CircuitBreaker = importlib.import_module("agent_runtime.main")._CircuitBreaker
finally:
    if _PRIOR_SERVICE_API_KEY is None:
        os.environ.pop("SERVICE_API_KEY", None)
    else:
        os.environ["SERVICE_API_KEY"] = _PRIOR_SERVICE_API_KEY

# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------

class TestCircuitBreakerClosed:
    def test_initial_state_is_closed(self):
        cb = _CircuitBreaker()
        assert cb.state == _CircuitBreaker.CLOSED

    def test_not_open_when_closed(self):
        cb = _CircuitBreaker()
        assert cb.is_open() is False

    def test_failure_below_threshold_stays_closed(self):
        cb = _CircuitBreaker()
        for _ in range(cb.FAILURE_THRESHOLD - 1):
            cb.record_failure()
        assert cb.state == _CircuitBreaker.CLOSED
        assert cb.is_open() is False

    def test_success_resets_failure_count(self):
        cb = _CircuitBreaker()
        for _ in range(cb.FAILURE_THRESHOLD - 1):
            cb.record_failure()
        cb.record_success()
        assert cb._failures == 0
        assert cb.state == _CircuitBreaker.CLOSED


class TestCircuitBreakerOpens:
    def test_opens_after_threshold_failures(self):
        cb = _CircuitBreaker()
        for _ in range(cb.FAILURE_THRESHOLD):
            cb.record_failure()
        assert cb.state == _CircuitBreaker.OPEN

    def test_is_open_returns_true_when_open(self):
        cb = _CircuitBreaker()
        for _ in range(cb.FAILURE_THRESHOLD):
            cb.record_failure()
        assert cb.is_open() is True

    def test_additional_failures_keep_open(self):
        cb = _CircuitBreaker()
        for _ in range(cb.FAILURE_THRESHOLD + 10):
            cb.record_failure()
        assert cb.state == _CircuitBreaker.OPEN
        assert cb.is_open() is True

    def test_opened_at_timestamp_set(self):
        cb = _CircuitBreaker()
        before = time.time()
        for _ in range(cb.FAILURE_THRESHOLD):
            cb.record_failure()
        assert cb._opened_at >= before


class TestCircuitBreakerHalfOpen:
    def test_transitions_to_half_after_recovery_seconds(self):
        cb = _CircuitBreaker()
        for _ in range(cb.FAILURE_THRESHOLD):
            cb.record_failure()
        # Backdate the opened_at to simulate recovery time elapsed
        cb._opened_at = time.time() - cb.RECOVERY_SECONDS - 1.0
        # is_open() should return False (enters HALF)
        assert cb.is_open() is False
        assert cb.state == _CircuitBreaker.HALF

    def test_half_open_closes_on_success(self):
        cb = _CircuitBreaker()
        for _ in range(cb.FAILURE_THRESHOLD):
            cb.record_failure()
        cb._opened_at = time.time() - cb.RECOVERY_SECONDS - 1.0
        cb.is_open()  # transitions to HALF
        cb.record_success()
        assert cb.state == _CircuitBreaker.CLOSED

    def test_half_open_reopens_on_failure(self):
        cb = _CircuitBreaker()
        for _ in range(cb.FAILURE_THRESHOLD):
            cb.record_failure()
        cb._opened_at = time.time() - cb.RECOVERY_SECONDS - 1.0
        cb.is_open()  # transitions to HALF
        cb.record_failure()  # probe fails → reopen
        assert cb.state == _CircuitBreaker.OPEN

    def test_half_state_not_open(self):
        cb = _CircuitBreaker()
        cb.state = _CircuitBreaker.HALF
        # HALF is not open (probe is allowed)
        assert cb.is_open() is False


class TestCircuitBreakerReset:
    def test_success_after_open_closes(self):
        cb = _CircuitBreaker()
        for _ in range(cb.FAILURE_THRESHOLD):
            cb.record_failure()
        assert cb.state == _CircuitBreaker.OPEN
        cb.record_success()
        assert cb.state == _CircuitBreaker.CLOSED
        assert cb._failures == 0

    def test_multiple_cycles(self):
        cb = _CircuitBreaker()
        # First cycle: open
        for _ in range(cb.FAILURE_THRESHOLD):
            cb.record_failure()
        assert cb.state == _CircuitBreaker.OPEN
        # Reset
        cb.record_success()
        assert cb.state == _CircuitBreaker.CLOSED
        # Second cycle: open again
        for _ in range(cb.FAILURE_THRESHOLD):
            cb.record_failure()
        assert cb.state == _CircuitBreaker.OPEN
