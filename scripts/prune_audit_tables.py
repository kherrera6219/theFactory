"""Trigger audit-table retention via the orchestrator maintenance endpoint.

POSTs to /v1/maintenance/prune-audit, which invokes the SECURITY DEFINER
prune_audit_tables() SQL function. Intended to be run on a schedule (cron /
systemd timer) so the append-only audit tables stay bounded.

Environment:
  ORCHESTRATOR_URL            base URL (default http://localhost:8101)
  ORCHESTRATOR_ADMIN_API_KEY  x-api-key sent with the request (mutate role)
  AUDIT_RETENTION_DAYS        optional retention override passed as a query param
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune audit tables via the orchestrator API.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("ORCHESTRATOR_URL", "http://localhost:8101"),
        help="Orchestrator base URL.",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=None,
        help="Override AUDIT_RETENTION_DAYS for this run.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    api_key = os.getenv("ORCHESTRATOR_ADMIN_API_KEY", "").strip()
    headers = {"x-api-key": api_key} if api_key else {}
    params = {}
    retention = args.retention_days
    if retention is None:
        env_retention = os.getenv("AUDIT_RETENTION_DAYS", "").strip()
        retention = int(env_retention) if env_retention.isdigit() else None
    if retention is not None:
        params["retention_days"] = retention

    url = f"{args.base_url.rstrip('/')}/v1/maintenance/prune-audit"
    try:
        response = httpx.post(
            url, headers=headers, params=params, timeout=args.timeout_seconds
        )
    except httpx.HTTPError as exc:
        print(f"prune-audit request failed: {exc}", file=sys.stderr)
        return 1

    if response.status_code >= 400:
        print(
            f"prune-audit returned {response.status_code}: {response.text}",
            file=sys.stderr,
        )
        return 1

    print(json.dumps(response.json(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
