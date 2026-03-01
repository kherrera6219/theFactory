import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "services" / "orchestrator"))

import orchestrator.main as orchestrator_main  # noqa: E402
from orchestrator import storage  # noqa: E402
from orchestrator.main import app as orchestrator_app  # noqa: E402
from orchestrator.models import MissionRecord, MissionState  # noqa: E402


async def _mock_db_ready(_: object) -> tuple[bool, bool]:
    return False, True


async def _mock_fetch_mission(_: object, mission_id: str) -> MissionRecord:
    return MissionRecord(
        mission_id=mission_id,
        prompt="test",
        requested_target_language="python",
        metadata={},
        state=MissionState.running,
        created_at="2026-02-28T00:00:00+00:00",
    )


def test_internal_pod_assignment_conflict_returns_409(monkeypatch) -> None:
    existing = {
        "mission_id": "mission-42",
        "pod_name": "podA",
        "metadata": {"assigned_by": "pod-worker"},
        "assigned_at": "2026-02-28T00:00:00+00:00",
        "updated_at": "2026-02-28T00:00:00+00:00",
    }

    def _mock_upsert(
        settings: object,
        mission_id: str,
        pod_name: str,
        metadata: dict[str, str],
        assigned_at: str,
    ) -> dict[str, str]:
        raise storage.PodAssignmentConflictError(existing)

    monkeypatch.setattr(orchestrator_main, "_ensure_db_ready", _mock_db_ready)
    monkeypatch.setattr(orchestrator_main, "_fetch_existing_mission", _mock_fetch_mission)
    monkeypatch.setattr(orchestrator_main.storage, "upsert_pod_assignment", _mock_upsert)

    client = TestClient(orchestrator_app)
    response = client.post(
        "/internal/pod-assignment",
        headers={"x-api-key": "worker-key"},
        json={
            "mission_id": "mission-42",
            "pod_name": "podB",
            "metadata": {"reason": "language-match"},
        },
    )

    assert response.status_code == 409
    body = response.json()
    assert body["detail"]["assignment"]["pod_name"] == "podA"
