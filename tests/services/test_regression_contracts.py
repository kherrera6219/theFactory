from pathlib import Path


def test_protocol_topics_include_required_runtime_topics() -> None:
    root = Path(__file__).resolve().parents[2]
    topics_file = root / "protocol" / "topics.yaml"
    text = topics_file.read_text(encoding="utf-8")
    required = [
        "intake.feature_contract.created",
        "fusion.requested",
        "artifact.rir.verified",
        "binary.build.ready",
        "incident.runtime.errorlog",
        "cluster.assigned.podA",
        "cluster.assigned.podB",
        "cluster.assigned.podC",
        "cluster.assigned.podD",
    ]
    for topic in required:
        assert topic in text
