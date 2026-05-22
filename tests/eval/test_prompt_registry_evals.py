"""test_prompt_registry_evals.py — Prompt registry unit tests."""
import pytest

from services.orchestrator.orchestrator.prompt_registry import (
    PromptAsset,
    get,
    list_prompts,
    load_prompt_assets,
    register,
)


class TestPromptAsset:
    def test_sha256_computed(self) -> None:
        asset = PromptAsset(
            prompt_id="test.v1",
            version="1.0.0",
            owner_agent_id="AGENT-01-PM",
            template="Hello {name}",
            variables=("name",),
            change_note="test",
            created_at="2026-05-20T00:00:00Z",
        )
        assert len(asset.sha256) == 64  # SHA-256 hex digest

    def test_render_success(self) -> None:
        asset = PromptAsset(
            prompt_id="test.v1",
            version="1.0.0",
            owner_agent_id="AGENT-01-PM",
            template="Hello {name}, mission: {mission}",
            variables=("name", "mission"),
            change_note="test",
            created_at="2026-05-20T00:00:00Z",
        )
        result = asset.render(name="Kevin", mission="BUILD_NEW")
        assert "Kevin" in result
        assert "BUILD_NEW" in result

    def test_render_missing_variable_raises(self) -> None:
        asset = PromptAsset(
            prompt_id="test.v1",
            version="1.0.0",
            owner_agent_id="AGENT-01-PM",
            template="Hello {name}",
            variables=("name",),
            change_note="test",
            created_at="2026-05-20T00:00:00Z",
        )
        with pytest.raises(ValueError, match="missing required variables"):
            asset.render()  # no name provided


class TestRegistry:
    def test_register_and_get(self) -> None:
        asset = PromptAsset(
            prompt_id="registry_test.v1",
            version="1.0.0",
            owner_agent_id="AGENT-01-PM",
            template="test {x}",
            variables=("x",),
            change_note="test",
            created_at="2026-05-20T00:00:00Z",
        )
        register(asset)
        retrieved = get("registry_test.v1")
        assert retrieved.prompt_id == "registry_test.v1"
        assert retrieved.sha256 == asset.sha256

    def test_get_missing_raises_key_error(self) -> None:
        with pytest.raises(KeyError, match="nonexistent_prompt"):
            get("nonexistent_prompt")

    def test_load_prompt_assets_from_disk(self) -> None:
        from pathlib import Path
        assets_dir = (
            Path(__file__).resolve().parents[2]
            / "services" / "orchestrator" / "orchestrator" / "prompt_assets"
        )
        count = load_prompt_assets(assets_dir)
        assert count >= 5
        prompts = list_prompts()
        ids = [p["prompt_id"] for p in prompts]
        assert "pm_feature_contract.v1" in ids
        assert "ceo_delegation.v1" in ids
        assert "specialist_codegen.v1" in ids

    def test_list_prompts_returns_records(self) -> None:
        prompts = list_prompts()
        assert isinstance(prompts, list)
        if prompts:
            record = prompts[0]
            assert "prompt_id" in record
            assert "version" in record
            assert "sha256" in record
