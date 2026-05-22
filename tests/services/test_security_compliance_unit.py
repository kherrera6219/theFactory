from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

security_compliance = importlib.import_module("orchestrator.security_compliance")


def _metadata(code: str = "def read_csv(path):\n    return []\n") -> dict[str, object]:
    return {
        "generated_output": {
            "source": "llm",
            "generated_code": code,
            "filename": "solution.py",
            "language": "python",
        },
        "equivalence_report": {
            "report_id": "equivalence-mission-1",
            "passed": True,
        },
        "application_intelligence_map": {
            "aim_id": "aim-mission-1",
            "risk_flags": [],
        },
    }


def test_mission_requires_security_compliance_for_generated_or_source_artifacts() -> None:
    assert security_compliance.mission_requires_security_compliance(_metadata())
    assert security_compliance.mission_requires_security_compliance({"source_code": "print('x')"})
    assert security_compliance.mission_requires_security_compliance(
        {"application_intelligence_map": {"aim_id": "aim-1"}}
    )
    assert not security_compliance.mission_requires_security_compliance({})


def test_build_security_compliance_report_passes_low_risk_output() -> None:
    report = security_compliance.build_security_compliance_report(
        mission_id="mission-1",
        metadata=_metadata(),
        enforcement_enabled=True,
    )

    assert report["schema_version"] == "security_compliance_report.v1"
    assert report["passed"] is True
    assert report["blocking"] is False
    assert report["status"] == "passed"
    assert report["risk_level"] == "low"


def test_build_security_compliance_report_blocks_secret_when_enforced() -> None:
    report = security_compliance.build_security_compliance_report(
        mission_id="mission-1",
        metadata=_metadata("API_KEY = 'sk-test-secret-value-123456'\n"),
        enforcement_enabled=True,
    )

    assert report["passed"] is False
    assert report["blocking"] is True
    assert report["status"] == "blocked"
    assert any("secret-like" in finding for finding in report["findings"])


def test_build_security_compliance_report_warns_without_enforcement() -> None:
    report = security_compliance.build_security_compliance_report(
        mission_id="mission-1",
        metadata=_metadata("eval(user_input)\n"),
        enforcement_enabled=False,
    )

    assert report["passed"] is True
    assert report["blocking"] is False
    assert report["status"] == "warned"
    assert report["risk_level"] == "medium"


def test_build_security_compliance_report_blocks_regulated_missing_equivalence() -> None:
    metadata = _metadata()
    metadata.pop("equivalence_report")
    metadata["data_classification"] = "TIER_3_REGULATED"

    report = security_compliance.build_security_compliance_report(
        mission_id="mission-1",
        metadata=metadata,
        enforcement_enabled=False,
    )

    assert report["regulated_context"] is True
    assert report["blocking"] is True
    assert report["status"] == "blocked"
