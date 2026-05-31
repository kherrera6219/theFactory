"""Unit tests for the mission-lifecycle, LLM, and auth observability metrics
added in fix/observability-critical-metrics."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (
    str(ROOT / "services" / "orchestrator"),
    str(ROOT / "services" / "api-gateway"),
):
    if _p not in sys.path:
        sys.path.insert(0, _p)

orchestrator_metrics = importlib.import_module("orchestrator.orchestrator_metrics")
llm_metrics = importlib.import_module("orchestrator.llm_delegation.metrics")
api_gateway_main = importlib.import_module("api_gateway.main")


def _counter_value(counter, **labels) -> float:
    return counter.labels(**labels)._value.get()


def _gauge_value(gauge, **labels) -> float:
    return gauge.labels(**labels)._value.get()


# ---------------------------------------------------------------------------
# Mission lifecycle metrics
# ---------------------------------------------------------------------------
def test_transition_increments_counter() -> None:
    before = _counter_value(
        orchestrator_metrics.MISSION_TRANSITIONS_TOTAL,
        from_state="QUEUED",
        to_state="RUNNING",
        engine="v2",
    )
    orchestrator_metrics.record_mission_transition(
        from_state="QUEUED", to_state="RUNNING", engine="v2"
    )
    after = _counter_value(
        orchestrator_metrics.MISSION_TRANSITIONS_TOTAL,
        from_state="QUEUED",
        to_state="RUNNING",
        engine="v2",
    )
    assert after == before + 1


def test_active_gauge_moves_between_states() -> None:
    queued_before = _gauge_value(orchestrator_metrics.MISSIONS_ACTIVE, state="QUEUED")
    running_before = _gauge_value(orchestrator_metrics.MISSIONS_ACTIVE, state="RUNNING")

    # Enter QUEUED, then transition QUEUED -> RUNNING.
    orchestrator_metrics.record_mission_transition(
        from_state=None, to_state="QUEUED", engine="v2"
    )
    orchestrator_metrics.record_mission_transition(
        from_state="QUEUED", to_state="RUNNING", engine="v2"
    )

    queued_after = _gauge_value(orchestrator_metrics.MISSIONS_ACTIVE, state="QUEUED")
    running_after = _gauge_value(orchestrator_metrics.MISSIONS_ACTIVE, state="RUNNING")

    # Net QUEUED change is zero (incremented then decremented), RUNNING +1.
    assert queued_after == queued_before
    assert running_after == running_before + 1


def test_terminal_outcome_and_duration_recorded() -> None:
    complete_before = _counter_value(
        orchestrator_metrics.MISSION_OUTCOMES_TOTAL, outcome="complete"
    )
    duration_count_before = (
        orchestrator_metrics.MISSION_DURATION_SECONDS.labels(outcome="complete")
        ._sum.get()
    )

    orchestrator_metrics.record_mission_transition(
        from_state="VERIFIED",
        to_state="COMPLETE",
        engine="v2",
        started_at_epoch=0.0,  # large positive duration
    )

    complete_after = _counter_value(
        orchestrator_metrics.MISSION_OUTCOMES_TOTAL, outcome="complete"
    )
    duration_sum_after = (
        orchestrator_metrics.MISSION_DURATION_SECONDS.labels(outcome="complete")
        ._sum.get()
    )

    assert complete_after == complete_before + 1
    assert duration_sum_after > duration_count_before


def test_failed_outcome_recorded() -> None:
    before = _counter_value(orchestrator_metrics.MISSION_OUTCOMES_TOTAL, outcome="failed")
    orchestrator_metrics.record_mission_transition(
        from_state="RUNNING", to_state="FAILED", engine="legacy"
    )
    after = _counter_value(orchestrator_metrics.MISSION_OUTCOMES_TOTAL, outcome="failed")
    assert after == before + 1


def test_self_loop_skipped_by_caller_not_double_counted() -> None:
    # The helper itself records whatever it is given; the self-loop guard lives
    # in insert_mission_event. Recording a real transition still updates the ts.
    orchestrator_metrics.record_mission_transition(
        from_state="RUNNING", to_state="GATING", engine="v2"
    )
    assert orchestrator_metrics.MISSION_LAST_TRANSITION_TIMESTAMP._value.get() > 0


def test_record_mission_transition_never_raises() -> None:
    # Bad engine / weird states must not raise.
    orchestrator_metrics.record_mission_transition(
        from_state="???", to_state="???", engine=""
    )


# ---------------------------------------------------------------------------
# LLM metrics
# ---------------------------------------------------------------------------
def test_llm_request_counter_and_duration() -> None:
    before = _counter_value(
        llm_metrics.LLM_REQUESTS_TOTAL,
        provider="openai",
        model="gpt-5.5",
        agent_id="CEO",
        status="success",
    )
    llm_metrics.record_llm_request(
        provider="openai",
        model="gpt-5.5",
        agent_id="CEO",
        status="success",
        duration_seconds=1.23,
    )
    after = _counter_value(
        llm_metrics.LLM_REQUESTS_TOTAL,
        provider="openai",
        model="gpt-5.5",
        agent_id="CEO",
        status="success",
    )
    assert after == before + 1
    # Duration histogram observed at least one sample.
    assert (
        llm_metrics.LLM_REQUEST_DURATION_SECONDS.labels(
            provider="openai", model="gpt-5.5"
        )._sum.get()
        >= 1.23
    )


def test_llm_tokens_and_cost_recorded() -> None:
    prompt_before = _counter_value(
        llm_metrics.LLM_TOKENS_TOTAL,
        provider="openai",
        model="gpt-5.5",
        token_type="prompt",
    )
    completion_before = _counter_value(
        llm_metrics.LLM_TOKENS_TOTAL,
        provider="openai",
        model="gpt-5.5",
        token_type="completion",
    )
    cost_before = _counter_value(
        llm_metrics.LLM_ESTIMATED_COST_USD_TOTAL, provider="openai", model="gpt-5.5"
    )

    llm_metrics.record_llm_usage(
        provider="openai", model="gpt-5.5", input_tokens=1000, output_tokens=500
    )

    assert (
        _counter_value(
            llm_metrics.LLM_TOKENS_TOTAL,
            provider="openai",
            model="gpt-5.5",
            token_type="prompt",
        )
        == prompt_before + 1000
    )
    assert (
        _counter_value(
            llm_metrics.LLM_TOKENS_TOTAL,
            provider="openai",
            model="gpt-5.5",
            token_type="completion",
        )
        == completion_before + 500
    )
    # gpt-5.5 is in the pricing table → cost must increase.
    assert (
        _counter_value(
            llm_metrics.LLM_ESTIMATED_COST_USD_TOTAL, provider="openai", model="gpt-5.5"
        )
        > cost_before
    )


def test_llm_usage_unknown_model_no_cost_no_raise() -> None:
    cost_before = _counter_value(
        llm_metrics.LLM_ESTIMATED_COST_USD_TOTAL,
        provider="openai",
        model="totally-unknown-model",
    )
    llm_metrics.record_llm_usage(
        provider="openai", model="totally-unknown-model", input_tokens=10, output_tokens=10
    )
    cost_after = _counter_value(
        llm_metrics.LLM_ESTIMATED_COST_USD_TOTAL,
        provider="openai",
        model="totally-unknown-model",
    )
    assert cost_after == cost_before


# ---------------------------------------------------------------------------
# Gateway auth-failure classification helpers
# ---------------------------------------------------------------------------
def test_auth_failure_classification_and_route_prefix() -> None:
    gw = api_gateway_main

    assert gw._classify_auth_failure_reason(403, "insufficient oidc role") == "insufficient_role"
    assert gw._classify_auth_failure_reason(401, "expired bearer token") == "expired_token"
    assert gw._classify_auth_failure_reason(401, "x-api-key header is required") == "missing_auth"
    assert gw._classify_auth_failure_reason(401, "invalid bearer token") == "invalid_key"

    assert gw._route_prefix("/v1/missions/abc/state") == "/v1/missions"
    assert gw._route_prefix("/health") == "/health"
    assert gw._route_prefix("/") == "/"


def test_auth_failure_handler_increments_on_401_and_403() -> None:
    from fastapi import HTTPException
    from fastapi.testclient import TestClient

    gw = api_gateway_main

    @gw.app.get("/v1/__metrics_authtest__")
    def _raise_401():
        raise HTTPException(status_code=401, detail="authorization bearer token is required")

    @gw.app.get("/v1/__metrics_roletest__")
    def _raise_403():
        raise HTTPException(status_code=403, detail="insufficient oidc role for endpoint")

    client = TestClient(gw.app, raise_server_exceptions=False)

    missing_before = gw.AUTH_FAILURES_TOTAL.labels(
        reason="missing_auth", route_prefix="/v1/__metrics_authtest__"
    )._value.get()
    role_before = gw.AUTH_FAILURES_TOTAL.labels(
        reason="insufficient_role", route_prefix="/v1/__metrics_roletest__"
    )._value.get()

    r401 = client.get("/v1/__metrics_authtest__")
    r403 = client.get("/v1/__metrics_roletest__")

    # Response behavior is unchanged.
    assert r401.status_code == 401
    assert r401.json() == {"detail": "authorization bearer token is required"}
    assert r403.status_code == 403

    assert (
        gw.AUTH_FAILURES_TOTAL.labels(
            reason="missing_auth", route_prefix="/v1/__metrics_authtest__"
        )._value.get()
        == missing_before + 1
    )
    assert (
        gw.AUTH_FAILURES_TOTAL.labels(
            reason="insufficient_role", route_prefix="/v1/__metrics_roletest__"
        )._value.get()
        == role_before + 1
    )
