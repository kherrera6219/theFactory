import hashlib
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

prompt_registry = importlib.import_module("orchestrator.prompt_registry")


def _write_asset(directory: Path, prompt_id: str, template: str) -> None:
    (directory / f"{prompt_id}.json").write_text(
        json.dumps(
            {
                "prompt_id": prompt_id,
                "version": "1.0.0",
                "owner_agent_id": "AGENT-01-PM",
                "template": template,
            }
        ),
        encoding="utf-8",
    )


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _reset_registry() -> None:
    prompt_registry._REGISTRY.clear()


def test_load_without_manifest_loads_all(tmp_path) -> None:
    _reset_registry()
    _write_asset(tmp_path, "p.one", "template one")
    _write_asset(tmp_path, "p.two", "template two")
    loaded = prompt_registry.load_prompt_assets(tmp_path)
    assert loaded == 2


def test_matching_manifest_loads_and_verifies(tmp_path) -> None:
    _reset_registry()
    _write_asset(tmp_path, "p.one", "template one")
    (tmp_path / "manifest.json").write_text(
        json.dumps({"p.one": _sha256("template one")}), encoding="utf-8"
    )
    loaded = prompt_registry.load_prompt_assets(tmp_path)
    assert loaded == 1
    assert prompt_registry.get("p.one").sha256 == _sha256("template one")


def test_tampered_asset_is_rejected_fail_closed(tmp_path) -> None:
    _reset_registry()
    # Manifest pins the digest of the ORIGINAL template…
    (tmp_path / "manifest.json").write_text(
        json.dumps({"p.one": _sha256("original template")}), encoding="utf-8"
    )
    # …but the on-disk asset has been tampered with.
    _write_asset(tmp_path, "p.one", "TAMPERED template")
    loaded = prompt_registry.load_prompt_assets(tmp_path)
    assert loaded == 0  # rejected, not registered
    import pytest

    with pytest.raises(KeyError):
        prompt_registry.get("p.one")


def test_unlisted_asset_loads_unless_strict(tmp_path, monkeypatch) -> None:
    _reset_registry()
    _write_asset(tmp_path, "p.listed", "listed")
    _write_asset(tmp_path, "p.unlisted", "unlisted")
    (tmp_path / "manifest.json").write_text(
        json.dumps({"p.listed": _sha256("listed")}), encoding="utf-8"
    )

    # Non-strict (default): unlisted asset still loads.
    monkeypatch.delenv("PROMPT_INTEGRITY_ENFORCED", raising=False)
    assert prompt_registry.load_prompt_assets(tmp_path) == 2

    # Strict: unlisted asset is rejected.
    _reset_registry()
    monkeypatch.setenv("PROMPT_INTEGRITY_ENFORCED", "true")
    assert prompt_registry.load_prompt_assets(tmp_path) == 1


def test_shipped_manifest_matches_shipped_assets() -> None:
    """The committed manifest.json must match the committed prompt assets, so the
    real orchestrator loads all assets integrity-verified (no accidental drift)."""
    _reset_registry()
    loaded = prompt_registry.load_prompt_assets(prompt_registry.PROMPT_ASSETS_DIR)
    assert loaded >= 11
