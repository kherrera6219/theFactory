import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "operator_route_auth_matrix_qualification.py"

spec = importlib.util.spec_from_file_location(
    "operator_route_auth_matrix_qualification",
    MODULE_PATH,
)
assert spec is not None and spec.loader is not None
qualification = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = qualification
spec.loader.exec_module(qualification)


def test_parse_args_defaults(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["operator_route_auth_matrix_qualification.py"])
    args = qualification.parse_args()
    assert args.base_url == "http://localhost:8100"
    assert args.orchestrator_url == "http://localhost:8101"
    assert args.compose_file == "deploy/docker-compose.yaml"
    assert args.auth_modes == ["api_key", "hybrid", "oidc"]
    assert args.compose_reconfigure is True
    assert args.restore_initial_mode is True
    assert args.build_gateway is True
    assert args.output_file == "docs/evidence/operator_route_oidc_matrix_latest.json"
    assert args.history_file == "docs/evidence/operator_route_oidc_matrix_history.jsonl"
    # No default credential is allowed (Phase 0/1 hardening): empty unless
    # INTERNAL_SERVICE_API_KEY happens to be set in the environment this runs in.
    assert args.operator_api_key in {"", "bf99cac84f380d705e4fbde69ba980667255280aeff3750f0cf7b633ed30621e"}
    assert args.oidc_shared_secret == ""
    assert args.execute is False
    assert args.oidc_issuer_url == "http://operator-matrix-test"


def test_expected_status_matrix() -> None:
    assert qualification._expected_status("api_key", "no_auth") == 401
    assert qualification._expected_status("api_key", "api_key") == 200
    assert qualification._expected_status("api_key", "bearer_mutate") == 401
    assert qualification._expected_status("api_key", "bearer_observe") == 401
    assert qualification._expected_status("hybrid", "no_auth") == 401
    assert qualification._expected_status("hybrid", "api_key") == 200
    assert qualification._expected_status("hybrid", "bearer_mutate") == 403
    assert qualification._expected_status("hybrid", "bearer_observe") == 200
    assert qualification._expected_status("oidc", "no_auth") == 401
    assert qualification._expected_status("oidc", "api_key") == 401
    assert qualification._expected_status("oidc", "bearer_mutate") == 403
    assert qualification._expected_status("oidc", "bearer_observe") == 200


def test_headers_for_scenario_with_stubbed_bearer(monkeypatch) -> None:
    monkeypatch.setattr(qualification, "_encode_bearer_token", lambda **_: "test-token")
    api_key_headers = qualification._headers_for_scenario(
        scenario="api_key",
        operator_api_key="operator-key",
        shared_secret="secret",
        issuer="",
        audience="",
        required_role="mutate",
        operator_role="observe",
    )
    assert api_key_headers == {"x-api-key": "operator-key"}

    mutate_headers = qualification._headers_for_scenario(
        scenario="bearer_mutate",
        operator_api_key="operator-key",
        shared_secret="secret",
        issuer="",
        audience="",
        required_role="mutate",
        operator_role="observe",
    )
    assert mutate_headers == {"Authorization": "Bearer test-token"}


def test_gateway_env_for_mode_defaults(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["operator_route_auth_matrix_qualification.py"])
    args = qualification.parse_args()
    env = qualification._gateway_env_for_mode(args, "oidc")
    assert env["AUTH_MODE"] == "oidc"
    assert env["OIDC_ENFORCE_OPERATOR_ROUTES"] == "true"
    assert env["OIDC_OPERATOR_ROLE"] == "observe"
