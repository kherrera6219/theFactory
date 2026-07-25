"""Unit tests for the deployment handshake exporter engine."""

import io
import tarfile

from orchestrator.deploy_exporter import (
    generate_github_actions_workflow,
    generate_helm_chart_archive,
)


def test_generate_helm_chart_archive():
    mission_data = {"title": "Test Mission App"}
    chart_bytes = generate_helm_chart_archive("mission-123", mission_data)
    assert len(chart_bytes) > 0

    # Unpack tarfile and verify contents
    with tarfile.open(fileobj=io.BytesIO(chart_bytes), mode="r:gz") as tar:
        names = tar.getnames()
        assert "test-mission-app/Chart.yaml" in names
        assert "test-mission-app/values.yaml" in names
        assert "test-mission-app/templates/deployment.yaml" in names
        assert "test-mission-app/templates/service.yaml" in names


def test_generate_github_actions_workflow():
    mission_data = {"title": "Test Mission App"}
    workflow = generate_github_actions_workflow("mission-123", mission_data)
    assert "name: Deploy test-mission-app" in workflow
    assert "mission-123" in workflow
    assert "actions/checkout@v4" in workflow
