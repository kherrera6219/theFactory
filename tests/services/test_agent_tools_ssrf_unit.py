"""SSRF guard for the agent harness ``research.fetch`` tool.

Covers validation (non-global ranges, fail-closed DNS) and DNS pinning: the HTTP
request must connect to the address that passed validation, for http *and*
https, so a DNS-rebinding host cannot be re-resolved to an internal address.
"""

from __future__ import annotations

import asyncio
import socket

import httpcore
import httpx
import pytest
from orchestrator import agent_tools


def _fake_getaddrinfo(address: str):
    def _resolver(host, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 0))]

    return _resolver


@pytest.mark.parametrize(
    "url",
    [
        "http://100.64.0.10/",  # CGNAT shared address space (not is_private)
        "http://198.18.0.1/",  # benchmarking range
        "http://192.0.2.10/",  # documentation range
        "http://[::ffff:127.0.0.1]/",  # IPv4-mapped loopback
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://0.0.0.0/",
    ],
)
def test_non_global_ip_literals_are_rejected(url: str) -> None:
    safe, reason, pinned = agent_tools._resolve_and_validate_fetch_target(url)
    assert safe is False, reason
    assert pinned is None


def test_public_ip_literal_is_allowed_and_pinned() -> None:
    safe, reason, pinned = agent_tools._resolve_and_validate_fetch_target("https://8.8.8.8/x")
    assert safe is True, reason
    assert pinned == "8.8.8.8"


def test_hostname_resolving_to_cgnat_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent_tools.socket, "getaddrinfo", _fake_getaddrinfo("100.64.1.1"))
    safe, _, pinned = agent_tools._resolve_and_validate_fetch_target("https://rebind.example/")
    assert safe is False
    assert pinned is None


def test_dns_failure_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args, **_kwargs):
        raise socket.gaierror("temporary failure in name resolution")

    monkeypatch.setattr(agent_tools.socket, "getaddrinfo", _boom)
    safe, reason, pinned = agent_tools._resolve_and_validate_fetch_target("https://flaky.example/")
    assert safe is False
    assert "could not be resolved" in reason
    assert pinned is None


def test_hostname_resolving_to_public_ip_is_pinned(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent_tools.socket, "getaddrinfo", _fake_getaddrinfo("93.184.216.34"))
    safe, _, pinned = agent_tools._resolve_and_validate_fetch_target("https://example.org/")
    assert safe is True
    assert pinned == "93.184.216.34"


class _RecordingBackend(httpcore.AsyncNetworkBackend):
    def __init__(self) -> None:
        self.dialled: list[tuple[str, int]] = []

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        self.dialled.append((host, port))
        raise httpcore.ConnectError("recorded; not connecting")

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise httpcore.ConnectError("no unix sockets")

    async def sleep(self, seconds):
        await asyncio.sleep(seconds)


@pytest.mark.asyncio
async def test_https_request_dials_pinned_ip_not_re_resolved_host() -> None:
    transport = agent_tools._PinnedTransport(hostname="rebind.example", pinned_ip="93.184.216.34")
    recorder = _RecordingBackend()
    transport.network_backend._inner = recorder
    async with httpx.AsyncClient(transport=transport, trust_env=False) as client:
        with pytest.raises(httpx.ConnectError):
            await client.get("https://rebind.example/")
    assert recorder.dialled == [("93.184.216.34", 443)]


@pytest.mark.asyncio
async def test_pinned_backend_refuses_other_hosts() -> None:
    backend = agent_tools._PinnedNetworkBackend(hostname="a.example", pinned_ip="93.184.216.34")
    with pytest.raises(httpcore.ConnectError):
        await backend.connect_tcp("b.example", 443)


async def _start_recording_http_server() -> tuple[asyncio.AbstractServer, int, list[str]]:
    requests: list[str] = []

    async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        raw = await reader.readuntil(b"\r\n\r\n")
        requests.append(raw.decode("latin-1"))
        body = b"hello from pinned server"
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n"
            + f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
            + body
        )
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(_handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, port, requests


@pytest.mark.asyncio
async def test_research_fetch_connects_to_pinned_ip_without_leaking_userinfo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, port, requests = await _start_recording_http_server()
    # Validation "resolved" the host to 127.0.0.1 for this test only; the real
    # validator would reject loopback. The hostname itself does not resolve, so
    # a 200 proves the request went to the pinned address.
    monkeypatch.setattr(
        agent_tools,
        "_resolve_and_validate_fetch_target",
        lambda _url: (True, "", "127.0.0.1"),
    )
    ctx = agent_tools.ToolExecutionContext(
        role="specialist", agent_id="AGENT-12-PYTHON", mission_id="m-ssrf", workspace=None
    )
    try:
        result = await agent_tools._tool_research_fetch(
            {"_call_id": "c1", "url": f"http://admin:secret@does-not-resolve.invalid:{port}/page"},
            ctx,
        )
    finally:
        server.close()
        await server.wait_closed()

    assert result.is_error is False, result.output_text
    assert "hello from pinned server" in result.output_text
    assert len(requests) == 1
    host_lines = [line for line in requests[0].split("\r\n") if line.lower().startswith("host:")]
    # Host carries hostname[:port] only, never the URL's user:password@ part.
    assert host_lines == [f"Host: does-not-resolve.invalid:{port}"]
