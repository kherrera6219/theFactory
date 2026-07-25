from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import time
import uuid
from dataclasses import dataclass

import httpx


@dataclass
class Sample:
    status_code: int
    latency_seconds: float


async def _send_mission(
    client: httpx.AsyncClient,
    base_url: str,
    index: int,
    semaphore: asyncio.Semaphore,
    api_key: str | None = None,
) -> Sample:
    payload = {
        "prompt": f"performance-smoke-{index}",
        "requested_target_language": "python",
        "metadata": {"source": "perf_smoke"},
    }
    headers = {"Idempotency-Key": f"perf-{uuid.uuid4()}"}
    if api_key:
        headers["X-API-Key"] = api_key

    async with semaphore:
        started = time.perf_counter()
        response = await client.post(f"{base_url}/v1/missions", json=payload, headers=headers)
        latency = time.perf_counter() - started
        return Sample(status_code=response.status_code, latency_seconds=latency)



def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    # statistics.quantiles uses 1-100 percentiles when n=100.
    return statistics.quantiles(values, n=100)[max(0, min(99, int(pct) - 1))]


async def run(args: argparse.Namespace) -> int:
    semaphore = asyncio.Semaphore(args.concurrency)
    async with httpx.AsyncClient(timeout=args.timeout_seconds) as client:
        tasks = [
            _send_mission(client, args.base_url.rstrip("/"), i, semaphore, api_key=args.api_key)
            for i in range(args.requests)
        ]
        samples = await asyncio.gather(*tasks, return_exceptions=True)


    latencies: list[float] = []
    status_counts: dict[int, int] = {}
    errors = 0

    for sample in samples:
        if isinstance(sample, Exception):
            errors += 1
            continue
        latencies.append(sample.latency_seconds)
        status_counts[sample.status_code] = status_counts.get(sample.status_code, 0) + 1
        if sample.status_code >= 400:
            errors += 1

    total = len(samples)
    success_rate = ((total - errors) / total) * 100 if total else 0.0
    p50 = _percentile(latencies, 50)
    p95 = _percentile(latencies, 95)
    max_latency = max(latencies) if latencies else 0.0

    print("== Performance Smoke Report ==")
    print(f"Requests: {total}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Success rate: {success_rate:.2f}%")
    print(f"Status counts: {status_counts}")
    print(f"Latency p50: {p50:.3f}s")
    print(f"Latency p95: {p95:.3f}s")
    print(f"Latency max: {max_latency:.3f}s")

    failed = False
    if success_rate < args.min_success_rate:
        threshold = f"{args.min_success_rate:.2f}%"
        print(
            f"FAIL: success rate {success_rate:.2f}% is below threshold {threshold}"
        )
        failed = True
    if p95 > args.max_p95_seconds:
        print(f"FAIL: p95 {p95:.3f}s is above threshold {args.max_p95_seconds:.3f}s")
        failed = True

    if failed:
        return 1
    print("PASS: performance smoke thresholds met")
    return 0


def parse_args() -> argparse.Namespace:
    default_api_key = (
        os.getenv("ORCHESTRATOR_ADMIN_API_KEY")
        or os.getenv("INTERNAL_SERVICE_API_KEY")
        or os.getenv("API_KEY")
        or ""
    ).strip()

    parser = argparse.ArgumentParser(
        description="Run a performance smoke test against API gateway."
    )
    parser.add_argument("--base-url", default="http://localhost:8100", help="API gateway base URL")
    parser.add_argument(
        "--api-key",
        default=default_api_key,
        help="X-API-Key header for gateway authentication (defaults to ORCHESTRATOR_ADMIN_API_KEY env var)",
    )
    parser.add_argument("--requests", type=int, default=40, help="Total number of requests")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent workers")
    parser.add_argument("--timeout-seconds", type=float, default=10.0, help="HTTP timeout")
    parser.add_argument(
        "--min-success-rate",
        type=float,
        default=99.0,
        help="Minimum success rate percentage",
    )
    parser.add_argument(
        "--max-p95-seconds",
        type=float,
        default=2.0,
        help="Maximum p95 response time in seconds",
    )
    return parser.parse_args()



if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
