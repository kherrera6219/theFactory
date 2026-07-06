from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

try:
    import jwt
except ModuleNotFoundError:
    jwt = None

MATRIX_AUTH_MODES = ("api_key", "hybrid", "oidc")
SCENARIOS = ("no_auth", "api_key", "bearer_mutate", "bearer_observe")
OPERATOR_ENDPOINTS = ("/v1/operations/summary", "/v1/stream/state")


def _read_env_file() -> dict[str, str]:
    # Returns a local dict instead of mutating os.environ. This module's
    # helpers are also imported directly by tests (spec.loader.exec_module),
    # and the previous version unconditionally wrote every .env key into
    # os.environ at import time — silently clobbering the surrounding
    # process's real environment (RQCA_ENFORCEMENT_ENABLED, PROMPT_GUARD_MODE,
    # etc.) for the rest of any pytest session that happened to import this
    # module. Confirmed as the actual cause of an order-dependent test flake,
    # not just a theoretical risk.
    env_file = Path(__file__).resolve().parent.parent / ".env"
    values: dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                values[key.strip()] = val.strip()
    return values

_DOTENV_VALUES = _read_env_file()



@dataclass
class CommandResult:
    command: list[str]
    exit_code: int | None
    executed: bool
    stderr_tail: str | None
    error: str | None


@dataclass
class ReadinessProbe:
    passed: bool
    polls: int
    duration_seconds: float
    last_status_code: int | None
    last_error: str | None


def _compose_command(compose_file: str, *tail: str) -> list[str]:
    # Always inject --env-file .env so docker compose picks up the real
    # POSTGRES_PASSWORD rather than the placeholder default in the compose file.
    env_file = str((Path(compose_file).parent.parent / ".env").resolve())
    cmd = ["docker", "compose", "-f", compose_file]
    if Path(env_file).exists():
        cmd += ["--env-file", env_file]
    return [*cmd, *tail]


def _gateway_up_command(*, compose_file: str, build_gateway: bool) -> list[str]:
    command = _compose_command(
        compose_file,
        "up",
        "-d",
        "--force-recreate",
        "--no-deps",
    )
    if build_gateway:
        command.append("--build")
    command.append("api-gateway")
    return command


def _run_command(
    command: list[str],
    *,
    env_overrides: dict[str, str] | None = None,
) -> CommandResult:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
    except Exception as exc:
        return CommandResult(
            command=command,
            exit_code=None,
            executed=False,
            stderr_tail=None,
            error=repr(exc),
        )
    return CommandResult(
        command=command,
        exit_code=completed.returncode,
        executed=True,
        stderr_tail=completed.stderr[-500:] if completed.stderr else None,
        error=None,
    )


def _expected_status(auth_mode: str, scenario: str) -> int:
    mode = auth_mode.strip().lower()
    if mode == "api_key":
        return {
            "no_auth": 401,
            "api_key": 200,
            "bearer_mutate": 401,
            "bearer_observe": 401,
        }[scenario]
    if mode == "hybrid":
        return {
            "no_auth": 401,
            "api_key": 200,
            "bearer_mutate": 403,
            "bearer_observe": 200,
        }[scenario]
    if mode == "oidc":
        return {
            "no_auth": 401,
            "api_key": 401,
            "bearer_mutate": 403,
            "bearer_observe": 200,
        }[scenario]
    raise ValueError(f"unsupported auth mode: {auth_mode}")


def _bool_arg(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError("expected true/false")


def _encode_bearer_token(
    *,
    shared_secret: str,
    role: str,
    issuer: str,
    audience: str,
) -> str:
    if jwt is None:
        raise RuntimeError("PyJWT is required for bearer-token matrix checks")
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": "operator-matrix-test",
        "iat": now,
        "exp": now + 600,
        "roles": [role],
        "scope": role,
    }
    if issuer:
        claims["iss"] = issuer
    if audience:
        claims["aud"] = audience
    token = jwt.encode(claims, shared_secret, algorithm="HS256")
    return token.decode("utf-8") if isinstance(token, bytes) else str(token)


def _headers_for_scenario(
    *,
    scenario: str,
    operator_api_key: str,
    shared_secret: str,
    issuer: str,
    audience: str,
    required_role: str,
    operator_role: str,
) -> dict[str, str]:
    if scenario == "no_auth":
        return {}
    if scenario == "api_key":
        return {"x-api-key": operator_api_key}
    if scenario == "bearer_mutate":
        token = _encode_bearer_token(
            shared_secret=shared_secret,
            role=required_role,
            issuer=issuer,
            audience=audience,
        )
        return {"Authorization": f"Bearer {token}"}
    if scenario == "bearer_observe":
        token = _encode_bearer_token(
            shared_secret=shared_secret,
            role=operator_role,
            issuer=issuer,
            audience=audience,
        )
        return {"Authorization": f"Bearer {token}"}
    raise ValueError(f"unsupported scenario: {scenario}")


async def _wait_ready(
    client: httpx.AsyncClient,
    *,
    ready_urls: list[str],
    timeout_seconds: float,
    poll_seconds: float,
) -> ReadinessProbe:
    deadline = time.monotonic() + timeout_seconds
    polls = 0
    started = time.monotonic()
    last_status: int | None = None
    last_error: str | None = None
    while time.monotonic() < deadline:
        polls += 1
        all_passed = True
        for url in ready_urls:
            try:
                response = await client.get(url)
                last_status = response.status_code
                if response.status_code >= 400:
                    all_passed = False
                    last_error = f"{url} returned status {response.status_code}: {response.text[:200]}"
                    break
            except Exception as exc:
                all_passed = False
                last_error = f"{url} failed: {repr(exc)}"
                break
        if all_passed:
            return ReadinessProbe(
                passed=True,
                polls=polls,
                duration_seconds=time.monotonic() - started,
                last_status_code=last_status,
                last_error=None,
            )
        await asyncio.sleep(poll_seconds)
    return ReadinessProbe(
        passed=False,
        polls=polls,
        duration_seconds=time.monotonic() - started,
        last_status_code=last_status,
        last_error=last_error,
    )


async def _probe_operator_route(
    client: httpx.AsyncClient,
    *,
    base_url: str,
    endpoint: str,
    headers: dict[str, str],
) -> tuple[int | None, str | None]:
    url = f"{base_url.rstrip('/')}{endpoint}"
    try:
        if endpoint.startswith("/v1/stream/state"):
            async with client.stream("GET", url, headers=headers) as response:
                return response.status_code, None
        response = await client.get(url, headers=headers)
        return response.status_code, None
    except Exception as exc:
        return None, repr(exc)


async def _health_mode(client: httpx.AsyncClient, *, base_url: str) -> str | None:
    try:
        response = await client.get(f"{base_url.rstrip('/')}/health")
    except Exception:
        return None
    if response.status_code >= 400:
        return None
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    mode = payload.get("auth_mode")
    return str(mode).strip().lower() if isinstance(mode, str) else None


def _gateway_env_for_mode(args: argparse.Namespace, auth_mode: str) -> dict[str, str]:
    return {
        "AUTH_MODE": auth_mode,
        "OIDC_SHARED_SECRET": args.oidc_shared_secret,
        "OIDC_ISSUER_URL": args.oidc_issuer_url,
        "OIDC_AUDIENCE": args.oidc_audience,
        "OIDC_REQUIRED_ROLE": args.oidc_required_role,
        "OIDC_OPERATOR_ROLE": args.oidc_operator_role,
        "OIDC_ENFORCE_OPERATOR_ROUTES": "true" if args.enforce_operator_routes else "false",
        "OIDC_ALLOWED_ALGORITHMS": "HS256",
    }


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, separators=(",", ":")) + "\n")


async def run(args: argparse.Namespace) -> int:
    if not args.operator_api_key:
        # There is no safe way to auto-generate this one: it must match the
        # credential the target gateway was actually deployed with
        # (INTERNAL_SERVICE_API_KEY). Leaving it empty is not a security risk
        # by itself (the api_key/hybrid scenarios will just correctly report
        # a 401 mismatch instead of silently probing with a well-known guess)
        # so this only warns rather than blocking.
        print(
            "WARNING: --operator-api-key/INTERNAL_SERVICE_API_KEY is empty — "
            "api_key/hybrid scenarios will report a mismatch rather than "
            "exercising real operator credentials."
        )
    if not args.oidc_shared_secret:
        # Safe to auto-generate: this script both signs test tokens with this
        # value and injects it into the target gateway's OIDC_SHARED_SECRET
        # env when reconfiguring (_gateway_env_for_mode), so a random value
        # is self-consistent and removes the well-known-default guess risk
        # entirely without requiring any external configuration.
        args.oidc_shared_secret = secrets.token_urlsafe(32)
        print("INFO: generated a random --oidc-shared-secret for this run")

    base_url = args.base_url.rstrip("/")
    orchestrator_url = args.orchestrator_url.rstrip("/")
    ready_urls = [f"{base_url}/readyz", f"{orchestrator_url}/readyz"]
    matrix_rows: list[dict[str, Any]] = []
    compose_steps: list[dict[str, Any]] = []
    # Only the intent to mutate (--compose-reconfigure, the default) combined
    # with the absence of an explicit --execute confirmation makes this a
    # dry-run. --compose-reconfigure=false is a deliberate read-only probe of
    # whatever is currently running and is never treated as a dry-run.
    dry_run = args.compose_reconfigure and not args.execute

    timeout = httpx.Timeout(args.http_timeout_seconds, connect=args.http_timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout) as client:
        initial_mode = await _health_mode(client, base_url=base_url)

        if args.compose_reconfigure and not args.skip_bootstrap:
            bootstrap_command = _compose_command(
                args.compose_file,
                "up",
                "-d",
                "redis",
                "postgres",
                "qdrant",
                "orchestrator",
            )
            if args.build_gateway:
                bootstrap_command.append("--build")
            bootstrap_command.append("api-gateway")
            if dry_run:
                print(f"DRY-RUN: would run bootstrap command: {' '.join(bootstrap_command)}")
                compose_steps.append(
                    {"step": "bootstrap", "dry_run": True, "command": bootstrap_command}
                )
            else:
                bootstrap = _run_command(bootstrap_command)
                compose_steps.append({"step": "bootstrap", **asdict(bootstrap)})
                if bootstrap.exit_code != 0:
                    report = {
                        "run_timestamp_utc": datetime.now(UTC).isoformat(),
                        "pass": False,
                        "failure_reasons": [
                            f"bootstrap command failed with exit code {bootstrap.exit_code}"
                        ],
                        "compose_steps": compose_steps,
                        "matrix_rows": [],
                    }
                    _write_report(Path(args.output_file), report)
                    return 1

        failure_reasons: list[str] = []
        for auth_mode in args.auth_modes:
            row_checks: list[dict[str, Any]] = []
            if args.compose_reconfigure:
                configure_command = _gateway_up_command(
                    compose_file=args.compose_file,
                    build_gateway=args.build_gateway,
                )
                if dry_run:
                    print(
                        f"DRY-RUN: would reconfigure api-gateway to AUTH_MODE={auth_mode}: "
                        f"{' '.join(configure_command)}"
                    )
                    compose_steps.append(
                        {
                            "step": f"configure-{auth_mode}",
                            "dry_run": True,
                            "command": configure_command,
                        }
                    )
                    matrix_rows.append(
                        {
                            "auth_mode": auth_mode,
                            "dry_run": True,
                            "ready": None,
                            "health_auth_mode": None,
                            "checks": [],
                        }
                    )
                    continue

                configure = _run_command(
                    configure_command,
                    env_overrides=_gateway_env_for_mode(args, auth_mode),
                )
                compose_steps.append(
                    {
                        "step": f"configure-{auth_mode}",
                        **asdict(configure),
                    }
                )
                if configure.exit_code != 0:
                    failure_reasons.append(
                        f"gateway reconfigure failed for mode={auth_mode} "
                        f"(exit={configure.exit_code})"
                    )
                    matrix_rows.append(
                        {
                            "auth_mode": auth_mode,
                            "ready": asdict(
                                ReadinessProbe(
                                    passed=False,
                                    polls=0,
                                    duration_seconds=0.0,
                                    last_status_code=None,
                                    last_error="compose reconfigure failed",
                                )
                            ),
                            "health_auth_mode": None,
                            "checks": row_checks,
                        }
                    )
                    continue

            readiness = await _wait_ready(
                client,
                ready_urls=ready_urls,
                timeout_seconds=args.ready_timeout_seconds,
                poll_seconds=args.ready_poll_seconds,
            )
            observed_mode = await _health_mode(client, base_url=base_url)
            if not readiness.passed:
                failure_reasons.append(f"readyz failed for mode={auth_mode}")

            if observed_mode is not None and observed_mode != auth_mode:
                failure_reasons.append(
                    f"health auth_mode mismatch for mode={auth_mode} observed={observed_mode}"
                )

            for endpoint in OPERATOR_ENDPOINTS:
                for scenario in SCENARIOS:
                    expected = _expected_status(auth_mode, scenario)
                    try:
                        headers = _headers_for_scenario(
                            scenario=scenario,
                            operator_api_key=args.operator_api_key,
                            shared_secret=args.oidc_shared_secret,
                            issuer=args.oidc_issuer_url,
                            audience=args.oidc_audience,
                            required_role=args.oidc_required_role,
                            operator_role=args.oidc_operator_role,
                        )
                    except Exception as exc:
                        status_code = None
                        error = repr(exc)
                    else:
                        status_code, error = await _probe_operator_route(
                            client,
                            base_url=base_url,
                            endpoint=endpoint,
                            headers=headers,
                        )
                    passed = status_code == expected and error is None
                    check_row = {
                        "endpoint": endpoint,
                        "scenario": scenario,
                        "expected_status": expected,
                        "status_code": status_code,
                        "error": error,
                        "passed": passed,
                    }
                    row_checks.append(check_row)
                    if not passed:
                        failure_reasons.append(
                            f"matrix mismatch mode={auth_mode} endpoint={endpoint} "
                            f"scenario={scenario} expected={expected} observed={status_code}"
                        )

            matrix_rows.append(
                {
                    "auth_mode": auth_mode,
                    "ready": asdict(readiness),
                    "health_auth_mode": observed_mode,
                    "checks": row_checks,
                }
            )

        if (
            args.compose_reconfigure
            and args.restore_initial_mode
            and initial_mode in MATRIX_AUTH_MODES
        ):
            restore_command = _gateway_up_command(
                compose_file=args.compose_file,
                build_gateway=args.build_gateway,
            )
            if dry_run:
                print(
                    f"DRY-RUN: would restore api-gateway to AUTH_MODE={initial_mode}: "
                    f"{' '.join(restore_command)}"
                )
                compose_steps.append(
                    {
                        "step": f"restore-{initial_mode}",
                        "dry_run": True,
                        "command": restore_command,
                    }
                )
            else:
                restore = _run_command(
                    restore_command,
                    env_overrides=_gateway_env_for_mode(args, initial_mode),
                )
                compose_steps.append({"step": f"restore-{initial_mode}", **asdict(restore)})

    report = {
        "run_timestamp_utc": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "auth_modes": list(args.auth_modes),
        "initial_health_auth_mode": initial_mode,
        "compose_reconfigure": args.compose_reconfigure,
        "dry_run": dry_run,
        # A dry-run never verified anything, so it must not report a real
        # pass/fail verdict — qualification_gate_summary.py's _resolve_pass_flag
        # treats a non-bool "pass" as "ignore this run", which is exactly right
        # here (a preview run must never count as qualification evidence).
        "pass": None if dry_run else not failure_reasons,
        "failure_reasons": failure_reasons,
        "matrix_rows": matrix_rows,
        "compose_steps": compose_steps,
    }
    _write_report(Path(args.output_file), report)
    # A dry-run preview is not qualification evidence — don't pollute the
    # history file that qualification_gate_summary.py trends over time.
    if args.history_file and not dry_run:
        _append_jsonl(
            Path(args.history_file),
            {
                "run_timestamp_utc": report["run_timestamp_utc"],
                "pass": report["pass"],
                "auth_modes": list(args.auth_modes),
                "failure_reasons": list(report["failure_reasons"]),
                "output_file": args.output_file,
            },
        )

    print("== Operator Route Auth Matrix Qualification ==")
    if dry_run:
        print("mode=DRY-RUN (no containers were mutated; pass --execute to run for real)")
    print(f"pass={report['pass']}")
    print(f"modes={','.join(args.auth_modes)}")
    print(f"output={args.output_file}")
    if failure_reasons:
        for reason in failure_reasons:
            print(f"FAIL: {reason}")
    elif dry_run:
        print("DRY-RUN: no live containers/auth config were mutated")
    else:
        print("PASS: operator-route auth matrix checks satisfied")
    return 0 if dry_run else (0 if report["pass"] else 1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Qualify operator-route auth behavior across api_key, hybrid, and oidc "
            "gateway deployments."
        )
    )
    parser.add_argument("--base-url", default="http://localhost:8100", help="API gateway URL")
    parser.add_argument(
        "--orchestrator-url",
        default="http://localhost:8101",
        help="Orchestrator URL",
    )
    parser.add_argument(
        "--compose-file",
        default="deploy/docker-compose.yaml",
        help="Compose file used to reconfigure api-gateway auth mode",
    )
    parser.add_argument(
        "--auth-modes",
        nargs="+",
        default=list(MATRIX_AUTH_MODES),
        choices=list(MATRIX_AUTH_MODES),
        help="Auth modes to qualify",
    )
    parser.add_argument(
        "--operator-api-key",
        default=os.getenv("INTERNAL_SERVICE_API_KEY")
        or _DOTENV_VALUES.get("INTERNAL_SERVICE_API_KEY", ""),
        help="Operator API key used for api_key and hybrid scenarios. No well-known "
        "default credential is used — set this flag, export INTERNAL_SERVICE_API_KEY, "
        "or set it in .env. Must match the target gateway's real configured key.",
    )
    parser.add_argument(
        "--oidc-shared-secret",
        default=os.getenv("QUALIFICATION_OIDC_SHARED_SECRET", ""),
        help="Shared secret used to sign HS256 matrix test tokens, and injected "
        "into the target gateway's own OIDC_SHARED_SECRET when reconfiguring "
        "(self-consistent, not a real external secret). No well-known default "
        "is used — a random value is generated per run if left unset.",
    )
    parser.add_argument(
        "--oidc-required-role",
        default="mutate",
        help="Role used for mutation-role bearer scenario",
    )
    parser.add_argument(
        "--oidc-operator-role",
        default="observe",
        help="Role used for operator-route bearer scenario",
    )
    parser.add_argument(
        "--oidc-issuer-url",
        default="http://operator-matrix-test",
        help="Optional OIDC issuer claim",
    )
    parser.add_argument(
        "--oidc-audience",
        default="",
        help="Optional OIDC audience claim",
    )
    parser.add_argument(
        "--enforce-operator-routes",
        type=_bool_arg,
        default=True,
        help="Enable operator-route OIDC enforcement during qualification",
    )
    parser.add_argument(
        "--compose-reconfigure",
        type=_bool_arg,
        default=True,
        help="Reconfigure api-gateway per mode via docker compose",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually force-recreate/rebuild the live api-gateway container and "
        "flip its auth mode. Without this flag (the default), --compose-reconfigure "
        "runs in dry-run mode: it prints the exact commands and auth-mode changes "
        "that would happen and mutates nothing.",
    )
    parser.add_argument(
        "--skip-bootstrap",
        type=_bool_arg,
        default=False,
        help="Skip initial docker compose bootstrap command",
    )
    parser.add_argument(
        "--restore-initial-mode",
        type=_bool_arg,
        default=True,
        help="Restore gateway auth mode observed before matrix execution",
    )
    parser.add_argument(
        "--build-gateway",
        type=_bool_arg,
        default=True,
        help="Build api-gateway image before mode qualification runs",
    )
    parser.add_argument(
        "--ready-timeout-seconds",
        type=float,
        default=90.0,
        help="Gateway readiness timeout",
    )
    parser.add_argument(
        "--ready-poll-seconds",
        type=float,
        default=2.0,
        help="Gateway readiness poll interval",
    )
    parser.add_argument(
        "--http-timeout-seconds",
        type=float,
        default=8.0,
        help="HTTP request timeout",
    )
    parser.add_argument(
        "--output-file",
        default="docs/evidence/operator_route_oidc_matrix_latest.json",
        help="Output JSON report path",
    )
    parser.add_argument(
        "--history-file",
        default="docs/evidence/operator_route_oidc_matrix_history.jsonl",
        help="Append-only JSONL history file",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
