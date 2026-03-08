import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "langgraph_v2_prototype_matrix.py"

spec = importlib.util.spec_from_file_location("langgraph_v2_prototype_matrix", MODULE_PATH)
assert spec is not None and spec.loader is not None
qualification = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = qualification
spec.loader.exec_module(qualification)


def test_parse_args_defaults(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["langgraph_v2_prototype_matrix.py"])
    args = qualification.parse_args()
    assert args.output_file == "docs/evidence/langgraph_v2_prototype_matrix_latest.json"
    assert args.history_file == "docs/evidence/langgraph_v2_prototype_matrix_history.jsonl"


def test_resolve_pass_flag() -> None:
    assert qualification._resolve_pass_flag({"pass": True}, "pass", "passed") is True
    assert qualification._resolve_pass_flag({"passed": False}, "pass", "passed") is False
    assert qualification._resolve_pass_flag({}, "pass", "passed") is False
