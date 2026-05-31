import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from orchestrator.mission_flow_v2 import phases_runtime  # noqa: E402


def test_verify_noop_without_store_path(monkeypatch) -> None:
    monkeypatch.delenv("REFINED_IR_STORE_PATH", raising=False)
    # Must not raise even though no store is configured.
    phases_runtime._verify_rir_module_signatures("mission-1")


def test_verify_warns_on_unsigned_module(tmp_path, monkeypatch, caplog) -> None:
    monkeypatch.setenv("REFINED_IR_STORE_PATH", str(tmp_path))
    mission_dir = tmp_path / "missions" / "mission-1"
    mission_dir.mkdir(parents=True)
    (mission_dir / "agent-14-python.rir.module.json").write_text("{}\n", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="orchestrator.mission_flow_v2.phases_runtime"):
        phases_runtime._verify_rir_module_signatures("mission-1")
    assert any("signature missing or invalid" in rec.message for rec in caplog.records)


def test_verify_passes_on_signed_module(tmp_path, monkeypatch, caplog) -> None:
    monkeypatch.setenv("REFINED_IR_STORE_PATH", str(tmp_path))
    monkeypatch.setenv("ARTIFACT_SIGNING_KEY_PATH", str(tmp_path / "keys" / "k.key"))
    mission_dir = tmp_path / "missions" / "mission-1"
    mission_dir.mkdir(parents=True)
    module = mission_dir / "agent-14-python.rir.module.json"
    module.write_text('{"module": {"agent_id": "AGENT-14-PYTHON"}}\n', encoding="utf-8")
    from shared_runtime.crypto_signing import sign_artifact

    sign_artifact(module)
    with caplog.at_level(logging.INFO, logger="orchestrator.mission_flow_v2.phases_runtime"):
        phases_runtime._verify_rir_module_signatures("mission-1")
    assert any("signature verified" in rec.message for rec in caplog.records)
