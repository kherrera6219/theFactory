import time

from shared_runtime.agent_auth import sign_agent_message, verify_agent_message

AGENT = "AGENT-31-PYTHON"
SECRET = "s3cret-with-enough-entropy-1234"
PAYLOAD = {"b": 2, "a": 1, "nested": {"y": True, "x": [3, 1, 2]}}


def test_sign_then_verify_roundtrip() -> None:
    header = sign_agent_message(AGENT, SECRET, PAYLOAD)
    assert verify_agent_message(AGENT, SECRET, PAYLOAD, header)


def test_header_shape_is_timestamp_colon_sig() -> None:
    header = sign_agent_message(AGENT, SECRET, PAYLOAD)
    ts, sig = header.split(":", 1)
    assert ts.isdigit()
    assert len(sig) == 64  # sha256 hexdigest


def test_verify_rejects_wrong_secret() -> None:
    header = sign_agent_message(AGENT, SECRET, PAYLOAD)
    assert not verify_agent_message(AGENT, "different-secret-value", PAYLOAD, header)


def test_verify_rejects_wrong_agent_id() -> None:
    header = sign_agent_message(AGENT, SECRET, PAYLOAD)
    assert not verify_agent_message("AGENT-32-RUST", SECRET, PAYLOAD, header)


def test_verify_rejects_tampered_payload() -> None:
    header = sign_agent_message(AGENT, SECRET, PAYLOAD)
    tampered = {**PAYLOAD, "a": 999}
    assert not verify_agent_message(AGENT, SECRET, tampered, header)


def test_verify_is_key_order_insensitive() -> None:
    header = sign_agent_message(AGENT, SECRET, {"a": 1, "b": 2})
    assert verify_agent_message(AGENT, SECRET, {"b": 2, "a": 1}, header)


def test_verify_rejects_stale_signature() -> None:
    old_ts = str(int(time.time()) - 3600)
    # Forge a syntactically valid but stale header; freshness check fails first.
    header = sign_agent_message(AGENT, SECRET, PAYLOAD)
    _, sig = header.split(":", 1)
    stale_header = f"{old_ts}:{sig}"
    assert not verify_agent_message(AGENT, SECRET, PAYLOAD, stale_header)


def test_verify_honors_custom_max_age() -> None:
    header = sign_agent_message(AGENT, SECRET, PAYLOAD)
    ts, sig = header.split(":", 1)
    past = f"{int(ts) - 120}:{sig}"
    assert not verify_agent_message(AGENT, SECRET, PAYLOAD, past, max_age_seconds=60)
    # Re-sign so the body/timestamp match, then verify within a generous window.
    fresh = sign_agent_message(AGENT, SECRET, PAYLOAD)
    assert verify_agent_message(AGENT, SECRET, PAYLOAD, fresh, max_age_seconds=300)


def test_verify_rejects_malformed_header() -> None:
    assert not verify_agent_message(AGENT, SECRET, PAYLOAD, "not-a-valid-header")
    assert not verify_agent_message(AGENT, SECRET, PAYLOAD, "")

def test_sign_rejects_empty_identity_or_secret() -> None:
    import pytest

    with pytest.raises(ValueError, match="agent_id"):
        sign_agent_message("", SECRET, PAYLOAD)
    with pytest.raises(ValueError, match="agent_secret"):
        sign_agent_message(AGENT, "", PAYLOAD)


def test_verify_rejects_signature_too_far_in_future(monkeypatch) -> None:
    now = int(time.time())
    monkeypatch.setattr("shared_runtime.agent_auth.time.time", lambda: now + 30)
    future_header = sign_agent_message(AGENT, SECRET, PAYLOAD)
    monkeypatch.setattr("shared_runtime.agent_auth.time.time", lambda: now)

    assert not verify_agent_message(AGENT, SECRET, PAYLOAD, future_header)
    assert verify_agent_message(
        AGENT,
        SECRET,
        PAYLOAD,
        future_header,
        max_future_skew_seconds=30,
    )


def test_verify_rejects_invalid_window_and_non_hex_signature() -> None:
    header = sign_agent_message(AGENT, SECRET, PAYLOAD)
    timestamp, _signature = header.split(":", 1)

    assert not verify_agent_message(AGENT, SECRET, PAYLOAD, header, max_age_seconds=0)
    assert not verify_agent_message(AGENT, SECRET, PAYLOAD, f"{timestamp}:{'z' * 64}")
