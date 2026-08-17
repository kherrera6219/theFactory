"""Contracts for remaining live proofs: injection, fallback, EDCP, spend, ZIP."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import prove_remaining_live as proof  # noqa: E402


def test_failure_injection_requires_visible_terminal_state() -> None:
    assert proof.failure_injection_passed("COMPLETE", 8) is True
    assert proof.failure_injection_passed("FAILED", 3) is True
    assert proof.failure_injection_passed("COMPLETE", 0) is False
    assert proof.failure_injection_passed("QUEUED", 4) is False


def test_provider_fallback_accepts_route_or_openai_provider() -> None:
    assert proof.provider_fallback_passed({"routing_sources": ["fallback"]}) is True
    assert proof.provider_fallback_passed({"by_provider": [{"provider": "openai"}]}) is True
    assert proof.provider_fallback_passed({}, "fallback") is True
    assert proof.provider_fallback_passed({"routing_sources": ["primary"], "by_provider": [{"provider": "gemini"}]}) is False


def test_edcp_requires_consumed_delta_prefix() -> None:
    assert proof.edcp_live_passed(
        "COMPLETE",
        {"audit_result": "pass", "correlation_id": "delta-mission-1-podA", "consumed_at": "t"},
    ) is True
    assert proof.edcp_live_passed("COMPLETE", {"correlation_id": "mission-1"}) is False
    assert proof.edcp_live_passed("COMPLETE", {}) is False
    assert proof.edcp_live_passed("COMPLETE", None) is False


def test_spend_cap_accepts_hit_or_pause_state() -> None:
    assert proof.spend_cap_passed("VERIFIED", {"spend_cap_hit": True}) is True
    assert proof.spend_cap_passed("VERIFIED", {"spend_cap": {"state": "pause"}}) is True
    assert proof.spend_cap_passed("COMPLETE", {"spend_cap": {"state": "ok"}}) is False


def test_chat_zip_requires_import_and_sow() -> None:
    assert proof.chat_zip_passed(True, "zip", "sow-1", 12) is True
    assert proof.chat_zip_passed(True, "", "sow-1", 40) is False
    assert proof.chat_zip_passed(True, "zip", "", 40) is False
    assert proof.chat_zip_passed(False, "zip", "sow-1", 40) is False
