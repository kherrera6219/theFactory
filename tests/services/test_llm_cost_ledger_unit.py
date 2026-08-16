import asyncio
import importlib
import sys
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

ledger = importlib.import_module("orchestrator.llm_cost_ledger")


def _make_fake_db(fetch_rows: list | None = None):
    """Return (db_connect_stub, cursor) where db_connect_stub mimics the
    `with db_connect(settings) as conn: with conn.cursor() as cur:` protocol."""
    cursor = MagicMock()
    cursor.fetchall.return_value = fetch_rows or []

    @contextmanager
    def _cursor_cm():
        yield cursor

    conn = MagicMock()
    conn.cursor.side_effect = _cursor_cm

    @contextmanager
    def _connect(_settings):
        yield conn

    return _connect, cursor


# ---------------------------------------------------------------------------
# _estimate_cost
# ---------------------------------------------------------------------------
def test_estimate_cost_known_model() -> None:
    cost, known = ledger._estimate_cost("openai", "gpt-5.5", 1000, 1000)
    # (1000*0.005 + 1000*0.015) / 1000 = 0.02
    assert known is True
    assert cost == 0.02


def test_estimate_cost_prefix_match() -> None:
    # "gpt-5.5-turbo" is not an exact key but starts with "gpt-5.5"
    cost, known = ledger._estimate_cost("openai", "gpt-5.5-turbo", 1000, 0)
    assert known is True
    assert cost == 0.005


def test_estimate_cost_unknown_provider() -> None:
    cost, known = ledger._estimate_cost("nonsense", "model-x", 1000, 1000)
    assert known is False
    assert cost is None


def test_estimate_cost_unknown_model() -> None:
    cost, known = ledger._estimate_cost("openai", "totally-unknown-9000", 100, 100)
    assert known is False
    assert cost is None


def test_estimate_cost_gemini_known() -> None:
    cost, known = ledger._estimate_cost("gemini", "gemini-3.5-flash", 1000, 1000)
    # (1000*0.00150 + 1000*0.009) / 1000 = 0.0105
    assert known is True
    assert round(cost, 6) == 0.0105


def test_estimate_cost_gemini_3_7_flash() -> None:
    cost, known = ledger._estimate_cost("gemini", "gemini-3.7-flash", 1000, 1000)
    # (1000*0.00075 + 1000*0.00375) / 1000 = 0.0045
    assert known is True
    assert round(cost, 6) == 0.0045


# ---------------------------------------------------------------------------
# record_llm_usage
# ---------------------------------------------------------------------------
def test_record_llm_usage_inserts(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_insert(settings, mission_id, agent_id, provider, model,
                     input_tokens, output_tokens, total, cost, pricing_known,
                     call_succeeded, routing_source, created_at) -> None:
        captured.update(
            mission_id=mission_id, agent_id=agent_id, provider=provider,
            model=model, total=total, cost=cost, pricing_known=pricing_known,
            call_succeeded=call_succeeded, routing_source=routing_source,
        )

    monkeypatch.setattr(ledger, "_insert_usage_sync", _fake_insert)

    asyncio.run(
        ledger.record_llm_usage(
            settings=object(),
            mission_id="mission-1",
            agent_id="AGENT-01-PM",
            provider="openai",
            model="gpt-5.5",
            input_tokens=500,
            output_tokens=250,
            routing_source="primary",
        )
    )

    assert captured["mission_id"] == "mission-1"
    assert captured["total"] == 750
    assert captured["pricing_known"] is True
    assert captured["cost"] is not None
    assert captured["routing_source"] == "primary"


def test_record_llm_usage_swallows_errors(monkeypatch) -> None:
    def _boom(*args, **kwargs) -> None:
        raise RuntimeError("db down")

    monkeypatch.setattr(ledger, "_insert_usage_sync", _boom)

    # Must never raise — cost tracking failures cannot break mission flow.
    asyncio.run(
        ledger.record_llm_usage(
            settings=object(),
            mission_id="mission-1",
            agent_id="AGENT-01-PM",
            provider="openai",
            model="gpt-5.5",
            input_tokens=1,
            output_tokens=1,
        )
    )


# ---------------------------------------------------------------------------
# get_mission_token_usage
# ---------------------------------------------------------------------------
def test_get_mission_token_usage_aggregates(monkeypatch) -> None:
    rows = [
        # agent_id, provider, model, inp, out, tot, cost, pricing_known, calls
        ("AGENT-01-PM", "openai", "gpt-5.5", 500, 250, 750, 0.012, True, 1),
        ("AGENT-02-CEO", "openai", "gpt-5.5", 300, 200, 500, 0.008, True, 2),
    ]
    monkeypatch.setattr(ledger, "_fetch_usage_rows_sync", lambda settings, mid: rows)

    result = asyncio.run(
        ledger.get_mission_token_usage(settings=object(), mission_id="mission-1")
    )

    assert result["mission_id"] == "mission-1"
    assert result["total_input_tokens"] == 800
    assert result["total_output_tokens"] == 450
    assert result["total_tokens"] == 1250
    assert result["call_count"] == 3
    assert result["unknown_pricing_count"] == 0
    assert result["estimated_cost_usd"] == 0.02
    assert len(result["by_agent"]) == 2
    assert len(result["by_provider"]) == 1  # both rows share openai::gpt-5.5


def test_get_mission_token_usage_unknown_pricing(monkeypatch) -> None:
    rows = [
        ("AGENT-01-PM", "mystery", "model-x", 100, 100, 200, None, False, 1),
    ]
    monkeypatch.setattr(ledger, "_fetch_usage_rows_sync", lambda settings, mid: rows)

    result = asyncio.run(
        ledger.get_mission_token_usage(settings=object(), mission_id="mission-2")
    )

    assert result["estimated_cost_usd"] is None
    assert result["unknown_pricing_count"] == 1
    assert result["by_provider"][0]["estimated_cost_usd"] is None


def test_get_mission_token_usage_empty(monkeypatch) -> None:
    monkeypatch.setattr(ledger, "_fetch_usage_rows_sync", lambda settings, mid: [])

    result = asyncio.run(
        ledger.get_mission_token_usage(settings=object(), mission_id="mission-3")
    )

    assert result["total_tokens"] == 0
    assert result["call_count"] == 0
    assert result["by_agent"] == []
    assert result["by_provider"] == []


def test_get_mission_token_usage_db_error_returns_empty(monkeypatch) -> None:
    def _boom(settings, mid):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(ledger, "_fetch_usage_rows_sync", _boom)

    result = asyncio.run(
        ledger.get_mission_token_usage(settings=object(), mission_id="mission-4")
    )

    # Falls back to empty aggregation rather than raising.
    assert result["total_tokens"] == 0
    assert result["call_count"] == 0


# ---------------------------------------------------------------------------
# sync DB helpers (mocked connection)
# ---------------------------------------------------------------------------
def test_insert_usage_sync_executes_insert(monkeypatch) -> None:
    connect, cursor = _make_fake_db()
    monkeypatch.setattr(ledger, "db_connect", connect)

    ledger._insert_usage_sync(
        settings=object(),
        mission_id="mission-1",
        agent_id="AGENT-01-PM",
        provider="openai",
        model="gpt-5.5",
        input_tokens=500,
        output_tokens=250,
        total=750,
        cost=0.012,
        pricing_known=True,
        call_succeeded=True,
        routing_source="primary",
        created_at=datetime.now(UTC),
    )

    cursor.execute.assert_called_once()
    sql, params = cursor.execute.call_args[0]
    assert "INSERT INTO llm_usage_events" in sql
    assert params[0] == "mission-1"
    assert params[6] == 750  # total_tokens


def test_fetch_usage_rows_sync_returns_rows(monkeypatch) -> None:
    rows = [("AGENT-01-PM", "openai", "gpt-5.5", 500, 250, 750, 0.012, True, 1)]
    connect, cursor = _make_fake_db(fetch_rows=rows)
    monkeypatch.setattr(ledger, "db_connect", connect)

    result = ledger._fetch_usage_rows_sync(object(), "mission-1")

    cursor.execute.assert_called_once()
    sql, params = cursor.execute.call_args[0]
    assert "FROM llm_usage_events" in sql
    assert params == ("mission-1",)
    assert result == rows


def test_record_llm_usage_end_to_end_with_mocked_db(monkeypatch) -> None:
    """Exercise record_llm_usage through the real _insert_usage_sync against a
    mocked db_connect, covering the asyncio.to_thread dispatch path."""
    connect, cursor = _make_fake_db()
    monkeypatch.setattr(ledger, "db_connect", connect)

    asyncio.run(
        ledger.record_llm_usage(
            settings=object(),
            mission_id="mission-e2e",
            agent_id="AGENT-02-CEO",
            provider="openai",
            model="gpt-5.5",
            input_tokens=100,
            output_tokens=100,
        )
    )

    cursor.execute.assert_called_once()
