"""Phase 4 verification: offline dependency provisioning, :ro sandbox mount & SBOM."""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_brownfield_benchmark  # noqa: E402
from orchestrator import (  # noqa: E402
    dependency_absorption,
    dependency_provisioner,
    deploy_exporter,
    rqca_agent,
    sandbox_exec,
)


def test_parse_all_ecosystem_manifests_without_executing_project_code(tmp_path: Path) -> None:
    """Static parsers handle every supported ecosystem without running setup/postinstall."""
    ws = tmp_path / "polyglot"
    ws.mkdir()
    marker_npm = ws / "pwned-npm.txt"
    marker_py = ws / "pwned-py.txt"

    (ws / "setup.py").write_text(
        f"open({str(marker_py)!r}, 'w').write('executed')\n",
        encoding="utf-8",
    )
    (ws / "requirements.txt").write_text(
        "# comment\nflask==3.0.3\nrequests>=2.32.0 ; python_version >= '3.10'\n",
        encoding="utf-8",
    )
    (ws / "pyproject.toml").write_text(
        '[project]\ndependencies = ["pydantic>=2.9.0"]\n',
        encoding="utf-8",
    )
    (ws / "package.json").write_text(
        json.dumps(
            {
                "name": "evil-test",
                "scripts": {"postinstall": f"node -e \"require('fs').writeFileSync({str(marker_npm)!r}, '1')\""},
                "dependencies": {"express": "^4.19.2"},
                "devDependencies": {"vitest": "^2.0.0"},
            }
        ),
        encoding="utf-8",
    )
    (ws / "pom.xml").write_text(
        "<project><dependencies><dependency><groupId>junit</groupId>"
        "<artifactId>junit</artifactId><version>4.13.2</version><scope>test</scope>"
        "</dependency></dependencies></project>",
        encoding="utf-8",
    )
    (ws / "App.csproj").write_text(
        '<Project><ItemGroup><PackageReference Include="xunit" Version="2.9.2" /></ItemGroup></Project>',
        encoding="utf-8",
    )
    (ws / "composer.json").write_text(
        json.dumps({"require": {"php": "^8.1"}, "require-dev": {"phpunit/phpunit": "^9.6"}}),
        encoding="utf-8",
    )
    (ws / "go.mod").write_text(
        "module example.com/app\ngo 1.22\nrequire (\n\tgithub.com/pkg/errors v0.9.1\n)\n",
        encoding="utf-8",
    )
    (ws / "Cargo.toml").write_text(
        '[package]\nname="app"\n[dependencies]\nserde = { version = "1.0.210" }\n',
        encoding="utf-8",
    )
    (ws / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'sinatra', '~> 4.0'\n", encoding="utf-8")
    (ws / "build.gradle").write_text("plugins { id 'java' }\n", encoding="utf-8")

    deps, manifests, warnings = dependency_provisioner.scan_workspace_manifests(ws)
    names = {d["name"] for d in deps}
    assert {
        "flask",
        "requests",
        "pydantic",
        "express",
        "vitest",
        "junit:junit",
        "xunit",
        "phpunit/phpunit",
        "github.com/pkg/errors",
        "serde",
        "sinatra",
    } <= names
    assert "requirements.txt" in manifests
    assert any("Gradle build script treated as executable code" in w for w in warnings)
    assert not marker_npm.exists()
    assert not marker_py.exists()


def test_provision_no_exec_postinstall_leaves_no_marker_and_uses_safe_flags(tmp_path: Path) -> None:
    """Provisioning enforces --ignore-scripts / --only-binary=:all: and creates no marker."""
    ws = tmp_path / "node-repo"
    ws.mkdir()
    marker = ws / "postinstall-ran.txt"
    (ws / "package.json").write_text(
        json.dumps(
            {
                "name": "postinstall-probe",
                "scripts": {
                    "postinstall": (
                        "python -c \"open('postinstall-ran.txt','w').write('PWNED')\""
                    )
                },
                "dependencies": {"express": "^4.19.2"},
            }
        ),
        encoding="utf-8",
    )

    recorded_cmds: list[list[str]] = []

    def fake_fetcher(cmd: list[str], cwd: Path, env: dict[str, str]) -> tuple[int, str, str]:
        recorded_cmds.append(list(cmd))
        assert "--ignore-scripts" in cmd
        assert env.get("NPM_CONFIG_IGNORE_SCRIPTS") == "true"
        # Simulate writing packed tarball into cache without running postinstall
        cache_idx = cmd.index("--pack-destination") + 1
        dest = Path(cmd[cache_idx])
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "express-4.19.2.tgz").write_bytes(b"tarball-bytes")
        return 0, "packed", ""

    manifest = dependency_provisioner.provision_workspace_dependencies(
        ws,
        mission_id="mission-noexec-node",
        language="javascript",
        dep_cache_root=tmp_path / "dep-cache",
        execute_fetch=True,
        fetcher=fake_fetcher,
    )
    assert not marker.exists()
    assert recorded_cmds
    assert manifest["executable_with_cache"] is True
    assert "express" in manifest["provisioned_packages"]
    pkg = next(p for p in manifest["packages"] if p["name"] == "express")
    expected_sha = hashlib.sha256(b"tarball-bytes").hexdigest()
    assert pkg["sha256"] == expected_sha
    assert pkg["status"] == "provisioned"


def test_egress_allow_list_and_tier3_regulated_mirror_policy(tmp_path: Path) -> None:
    """Only allow-listed registries pass; TIER_3_REGULATED requires an internal mirror."""
    ok_pypi, _ = dependency_provisioner.validate_registry_url("https://pypi.org/simple/flask/")
    ok_npm, _ = dependency_provisioner.validate_registry_url("https://registry.npmjs.org/express")
    bad_host, reason = dependency_provisioner.validate_registry_url("https://evil.example.com/pkg")
    bad_http, _ = dependency_provisioner.validate_registry_url("http://pypi.org/simple/")
    assert ok_pypi and ok_npm
    assert not bad_host and "not in ALLOWED_REGISTRIES" in reason
    assert not bad_http

    ws = tmp_path / "reg-py"
    ws.mkdir()
    (ws / "requirements.txt").write_text("flask==3.0.3\n", encoding="utf-8")

    blocked = dependency_provisioner.provision_workspace_dependencies(
        ws,
        mission_id="mission-reg-blocked",
        language="python",
        data_classification="TIER_3_REGULATED",
        dep_cache_root=tmp_path / "cache-blocked",
        internal_mirror_url="",
        execute_fetch=True,
        fetcher=lambda *_args: (_ for _ in ()).throw(AssertionError("must not fetch without mirror")),
    )
    assert blocked["policy_allowed"] is False
    assert blocked["unmet_reasons"] == {"flask": "blocked_by_policy"}
    assert blocked["executable_with_cache"] is False

    def fake_mirror_fetch(cmd: list[str], cwd: Path, env: dict[str, str]) -> tuple[int, str, str]:
        assert env.get("PIP_INDEX_URL") == "http://mirror.corp.internal/simple"
        assert "--only-binary=:all:" in cmd
        dest = Path(cmd[cmd.index("--dest") + 1])
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "flask-3.0.3-py3-none-any.whl").write_bytes(b"wheel-data")
        return 0, "", ""

    allowed = dependency_provisioner.provision_workspace_dependencies(
        ws,
        mission_id="mission-reg-mirror",
        language="python",
        data_classification="TIER_3_REGULATED",
        dep_cache_root=tmp_path / "cache-allowed",
        internal_mirror_url="http://mirror.corp.internal/simple",
        execute_fetch=True,
        fetcher=fake_mirror_fetch,
    )
    assert allowed["policy_allowed"] is True
    assert "flask" in allowed["provisioned_packages"]


def test_build_provision_commands_and_needs_build_classification(tmp_path: Path) -> None:
    """Sdist failures under --only-binary=:all: record needs_build instead of building code."""
    for lang, expected_token in (
        ("python", "--only-binary=:all:"),
        ("javascript", "--ignore-scripts"),
        ("java", "dependency:go-offline"),
        ("csharp", "restore"),
        ("go", "download"),
        ("rust", "fetch"),
        ("php", "--no-plugins"),
        ("ruby", "--no-install"),
    ):
        cmd = dependency_provisioner.build_provision_command(
            lang, cache_dir="/dep-cache/m1", manifest_file="requirements.txt", packages=["pkg"]
        )
        assert any(expected_token in part for part in cmd), (lang, cmd)
        assert dependency_provisioner.offline_sandbox_env(lang)

    ws = tmp_path / "sdist-py"
    ws.mkdir()
    (ws / "requirements.txt").write_text("customsdist==0.1.0\n", encoding="utf-8")
    manifest = dependency_provisioner.provision_workspace_dependencies(
        ws,
        mission_id="mission-sdist",
        language="python",
        dep_cache_root=tmp_path / "cache-sdist",
        execute_fetch=True,
        fetcher=lambda _c, _w, _e: (
            1,
            "",
            "ERROR: No matching distribution found for customsdist (only-binary=:all:)",
        ),
    )
    assert manifest["unmet_reasons"] == {"customsdist": "needs_build"}


def test_factory_sandbox_deps_mount_keeps_security_flags_and_is_readonly(monkeypatch) -> None:
    """Mounting /deps must always be :ro and must preserve all SANDBOX_SECURITY_FLAGS."""
    monkeypatch.setenv("SANDBOX_DEPS_ROOT", "/dep-cache")
    monkeypatch.setenv("SANDBOX_DEPS_HOST_ROOT", "/host/dep-cache")
    args = sandbox_exec.build_sandbox_args(
        docker_bin="docker",
        workspace_dir="/tmp/ws",
        base_image="python:3.11-slim",
        command="pytest -q",
        timeout_seconds=15,
        memory_mb=256,
        deps_dir="/dep-cache/mission-1",
        env_vars={"PIP_NO_INDEX": "1", "BAD KEY": "ignored"},
    )
    for flag in sandbox_exec.SANDBOX_SECURITY_FLAGS:
        assert flag in args, f"lost security flag: {flag}"
    assert "--network=none" in args
    assert "--volume=/host/dep-cache/mission-1:/deps:ro" in args
    assert not any(":/deps:rw" in a for a in args)
    assert "--env=PIP_NO_INDEX=1" in args
    assert not any("BAD KEY" in a for a in args)


def test_rqca_unmet_dependencies_honors_manifest_and_wires_sandbox_mount(
    monkeypatch, tmp_path: Path
) -> None:
    """RQCA clears provisioned deps, classifies unmet reasons, and passes :ro deps_dir."""
    dep_dir = tmp_path / "deps"
    dep_dir.mkdir()
    manifest = {
        "schema_version": "provisioning_manifest.v1",
        "dep_cache_dir": str(dep_dir),
        "policy_allowed": True,
        "offline_env": {"PIP_NO_INDEX": "1", "PIP_FIND_LINKS": "/deps/pip"},
        "provisioned_packages": ["requests"],
        "packages": [
            {"name": "requests", "version": "2.32.0", "ecosystem": "pypi", "status": "provisioned"},
            {
                "name": "sdistonly",
                "version": "1.0.0",
                "ecosystem": "pypi",
                "status": "needs_build",
                "reason": "needs_build",
            },
        ],
    }

    assert rqca_agent._unmet_dependencies("python", ["requests"], provisioning_manifest=manifest) == []
    unmet = rqca_agent._unmet_dependencies(
        "python", ["requests", "sdistonly", "missingpkg"], provisioning_manifest=manifest
    )
    assert unmet == ["sdistonly", "missingpkg"]
    assert rqca_agent.classify_unmet_dependencies(
        "python", unmet, provisioning_manifest=manifest
    ) == {"sdistonly": "needs_build", "missingpkg": "not_in_registry"}

    async def _docker_ok(_bin: str = "docker") -> bool:
        return True

    sandbox_calls: list[dict] = []

    async def _fake_sandbox(**kwargs):
        sandbox_calls.append(kwargs)
        return sandbox_exec.SandboxResult(
            exit_code=0,
            stdout="ok\n",
            stderr="",
            timed_out=False,
            timeout_seconds=15,
            memory_limit_mb=256,
            base_image="python:3.11-slim",
        )

    monkeypatch.setattr(rqca_agent, "_check_docker_available", _docker_ok)
    monkeypatch.setattr(rqca_agent, "run_in_sandbox", _fake_sandbox)

    qc = asyncio.run(
        rqca_agent.run_runtime_qc(
            mission_id="mission-prov-run",
            generated_output={
                "filename": "app.py",
                "generated_code": "import requests\nprint('ok')\n",
                "usage_example": "python app.py",
                "dependencies": ["requests"],
                "provisioning_manifest": manifest,
            },
            testdata_manifest={"invocation_args": ["--help"]},
            integration_tests=None,
            language="python",
            settings=SimpleNamespace(docker_bin="docker", rqca_test_command_template=""),
        )
    )
    assert qc["verdict"] == "PASS"
    assert sandbox_calls[0]["deps_dir"] == str(dep_dir)
    assert sandbox_calls[0]["env_vars"] == manifest["offline_env"]

    dry = asyncio.run(
        rqca_agent.run_runtime_qc(
            mission_id="mission-unmet",
            generated_output={
                "filename": "app.py",
                "generated_code": "import sdistonly\nprint('hi')\n",
                "usage_example": "python app.py",
                "dependencies": ["sdistonly"],
                "provisioning_manifest": manifest,
            },
            testdata_manifest={"invocation_args": ["--help"]},
            integration_tests=None,
            language="python",
            settings=SimpleNamespace(docker_bin="docker", rqca_test_command_template=""),
        )
    )
    assert dry["verdict"] == "DRY_RUN"
    assert dry["unmet_dependency_reasons"] == {"sdistonly": "needs_build"}


def test_sbom_and_absorption_include_provisioning_manifest_hashes() -> None:
    """CycloneDX SBOM and dependency_absorption inventory read provisioned hashes/versions."""
    digest = "a" * 64
    prov = {
        "packages": [
            {
                "name": "flask",
                "version": "3.0.3",
                "ecosystem": "pypi",
                "sha256": digest,
                "status": "provisioned",
            }
        ]
    }
    sbom = deploy_exporter.generate_cyclonedx_sbom(
        "mission-sbom-p4",
        generated_output={"filename": "app.py", "language": "python", "code": "print(1)"},
        provisioning_manifest=prov,
    )
    flask_comp = next(c for c in sbom["components"] if c["name"] == "flask")
    assert flask_comp["version"] == "3.0.3"
    assert flask_comp["purl"] == "pkg:pypi/flask@3.0.3"
    assert flask_comp["hashes"] == [{"alg": "SHA-256", "content": digest}]

    inventory = dependency_absorption.build_dependency_inventory(
        mission_id="mission-sbom-p4",
        metadata={"provisioning_manifest": prov},
    )
    assert inventory["dependency_count"] == 1
    assert "provisioning_manifest.packages" in inventory["sources"]
    assert inventory["dependencies"][0]["version"] == "3.0.3"


def test_provisioner_http_api_and_benchmark_threshold(monkeypatch, tmp_path: Path) -> None:
    """FastAPI endpoints require key auth; offline benchmark clears >=5 of 7 apps."""
    client = TestClient(dependency_provisioner.app)
    assert client.get("/livez").json() == {"ok": True}

    monkeypatch.setenv("INTERNAL_SERVICE_API_KEY", "")
    resp_503 = client.post(
        "/internal/provision",
        json={"workspace_dir": str(tmp_path), "mission_id": "m-api"},
    )
    assert resp_503.status_code == 503

    monkeypatch.setenv("INTERNAL_SERVICE_API_KEY", "test-provisioner-secret-123456")
    resp_401 = client.post(
        "/internal/provision",
        json={"workspace_dir": str(tmp_path), "mission_id": "m-api"},
        headers={"Authorization": "Bearer wrong"},
    )
    assert resp_401.status_code == 401

    (tmp_path / "requirements.txt").write_text("pytest==8.3.0\n", encoding="utf-8")
    monkeypatch.setenv("DEP_CACHE_ROOT", str(tmp_path / "api-cache"))
    resp_200 = client.post(
        "/internal/provision",
        json={"workspace_dir": str(tmp_path), "mission_id": "m-api", "language": "python"},
        headers={"Authorization": "Bearer test-provisioner-secret-123456"},
    )
    assert resp_200.status_code == 200
    assert "pytest" in resp_200.json()["provisioned_packages"]

    resp_404 = client.post(
        "/internal/provision",
        json={"workspace_dir": str(tmp_path / "does-not-exist"), "mission_id": "m-api-404"},
        headers={"Authorization": "Bearer test-provisioner-secret-123456"},
    )
    assert resp_404.status_code == 404

    scorecard = run_brownfield_benchmark.run_benchmark(mode="offline")
    assert scorecard["total_projects"] == 7
    assert scorecard["executable_with_cache_count"] >= 5
