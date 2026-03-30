"""Regression coverage for transient LLM retry handling."""

from __future__ import annotations

import asyncio

import httpx

from services.orchestrator.orchestrator import llm_delegation


class _ResponseContext:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self._responses = responses

    async def __aenter__(self) -> "_ResponseContext":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False

    async def post(
        self,
        url: str,
        json: dict,
        headers: dict[str, str],
        params=None,
    ) -> httpx.Response:
        _ = url, json, headers, params
        if not self._responses:
            raise AssertionError("unexpected extra retry attempt")
        return self._responses.pop(0)


def _make_response(status_code: int, *, retry_after: str | None = None) -> httpx.Response:
    request = httpx.Request("POST", "https://example.test/llm")
    headers = {"Retry-After": retry_after} if retry_after is not None else None
    return httpx.Response(status_code, request=request, headers=headers)


def test_post_with_retry_retries_rate_limits(monkeypatch) -> None:
    responses = [_make_response(429, retry_after="2"), _make_response(200)]
    sleep_calls: list[float] = []

    monkeypatch.setattr(
        llm_delegation.httpx,
        "AsyncClient",
        lambda timeout: _ResponseContext(responses),
    )

    async def _sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(llm_delegation.asyncio, "sleep", _sleep)
    monkeypatch.setattr(llm_delegation, "_LLM_MAX_RETRIES", 2)
    monkeypatch.setattr(llm_delegation, "_LLM_RETRY_BASE_SECONDS", 1.0)

    response = asyncio.run(
        llm_delegation._post_with_retry(
            "https://example.test/llm",
            json_payload={"prompt": "test"},
            headers={"authorization": "Bearer test"},
            timeout=5.0,
            call_context="unit-test",
        )
    )

    assert response is not None
    assert response.status_code == 200
    assert sleep_calls == [2.0]


def test_post_with_retry_returns_last_rate_limit_response_when_retries_exhausted(
    monkeypatch,
) -> None:
    responses = [_make_response(429), _make_response(429)]

    monkeypatch.setattr(
        llm_delegation.httpx,
        "AsyncClient",
        lambda timeout: _ResponseContext(responses),
    )

    async def _sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(llm_delegation.asyncio, "sleep", _sleep)
    monkeypatch.setattr(llm_delegation, "_LLM_MAX_RETRIES", 2)
    monkeypatch.setattr(llm_delegation, "_LLM_RETRY_BASE_SECONDS", 1.0)

    response = asyncio.run(
        llm_delegation._post_with_retry(
            "https://example.test/llm",
            json_payload={"prompt": "test"},
            headers={"authorization": "Bearer test"},
            timeout=5.0,
            call_context="unit-test",
        )
    )

    assert response is not None
    assert response.status_code == 429
