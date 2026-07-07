import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from orchestrator import protocol_bus_producer  # noqa: E402


class _Response:
    def __init__(self, status: int, body: bytes = b"") -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def _settings(**overrides):
    defaults = {
        "protocol_bus_url": "http://protocol-bus.test",
        "protocol_bus_api_key": "bus-key",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_send_protocol_message_returns_false_when_bus_url_missing() -> None:
    assert (
        protocol_bus_producer.send_protocol_message(
            settings=_settings(protocol_bus_url=""),
            protocol="alpha",
            sender="AGENT-02-CEO",
            recipient="AGENT-12-PODA-MGR",
            payload={"directive": "build"},
        )
        is False
    )


def test_send_protocol_message_returns_false_on_http_error(monkeypatch) -> None:
    requests = []

    def _urlopen(request, timeout):
        requests.append((request, timeout))
        return _Response(503)

    monkeypatch.setattr(protocol_bus_producer, "urlopen", _urlopen)

    assert (
        protocol_bus_producer.send_protocol_message(
            settings=_settings(),
            protocol="alpha",
            sender="AGENT-02-CEO",
            recipient="AGENT-12-PODA-MGR",
            payload={"directive": "build"},
            correlation_id="mission-1",
            timeout=1.5,
        )
        is False
    )

    request, timeout = requests[0]
    assert request.full_url == "http://protocol-bus.test/send"
    assert timeout == 1.5
    assert request.headers["X-api-key"] == "bus-key"
    assert request.headers["X-agent-id"] == "AGENT-02-CEO"
    assert json.loads(request.data.decode("utf-8"))["correlation_id"] == "mission-1"


def test_send_protocol_message_returns_false_on_network_exception(monkeypatch) -> None:
    def _urlopen(_request, _timeout):
        raise TimeoutError("event bus down")

    monkeypatch.setattr(protocol_bus_producer, "urlopen", _urlopen)

    assert (
        protocol_bus_producer.send_protocol_message(
            settings=_settings(),
            protocol="omega",
            sender="AGENT-01-PM",
            recipient=["AGENT-02-CEO"],
            payload={"user_intent": "plan"},
        )
        is False
    )


def test_fetch_lane_activity_returns_none_when_bus_url_missing() -> None:
    assert (
        protocol_bus_producer.fetch_lane_activity(settings=_settings(protocol_bus_url=""))
        is None
    )


def test_fetch_lane_activity_returns_parsed_json_on_success(monkeypatch) -> None:
    body = json.dumps({"generated_at": "now", "redis_ready": True, "lanes": {"alpha": {}}}).encode(
        "utf-8"
    )
    requests = []

    def _urlopen(request, timeout):
        requests.append((request, timeout))
        return _Response(200, body)

    monkeypatch.setattr(protocol_bus_producer, "urlopen", _urlopen)

    result = protocol_bus_producer.fetch_lane_activity(settings=_settings(), timeout=2.0)

    assert result == {"generated_at": "now", "redis_ready": True, "lanes": {"alpha": {}}}
    request, timeout = requests[0]
    assert request.full_url == "http://protocol-bus.test/lane-stats"
    assert request.get_method() == "GET"
    assert timeout == 2.0
    assert request.headers["X-api-key"] == "bus-key"


def test_fetch_lane_activity_returns_none_on_http_error(monkeypatch) -> None:
    monkeypatch.setattr(
        protocol_bus_producer, "urlopen", lambda request, timeout: _Response(503)
    )

    assert protocol_bus_producer.fetch_lane_activity(settings=_settings()) is None


def test_fetch_lane_activity_returns_none_on_network_exception(monkeypatch) -> None:
    def _urlopen(_request, _timeout):
        raise TimeoutError("event bus down")

    monkeypatch.setattr(protocol_bus_producer, "urlopen", _urlopen)

    assert protocol_bus_producer.fetch_lane_activity(settings=_settings()) is None
