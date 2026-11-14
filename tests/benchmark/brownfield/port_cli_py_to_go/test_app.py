from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_cli_module():
    path = Path(__file__).resolve().parent / "app.py"
    spec = importlib.util.spec_from_file_location("port_cli_py_app", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_summarize_events_and_cli(tmp_path: Path, capsys) -> None:
    mod = _load_cli_module()
    input_file = tmp_path / "events.jsonl"
    input_file.write_text(
        '{"category":"api","ms":120}\n{"category":"db","ms":80}\n{"category":"api","ms":30}\n',
        encoding="utf-8",
    )

    rc = mod.main(["--input", str(input_file)])
    assert rc == 0
    captured = json.loads(capsys.readouterr().out)
    assert captured == {
        "total_events": 3,
        "total_ms": 230,
        "by_category": {
            "api": {"count": 2, "total_ms": 150},
            "db": {"count": 1, "total_ms": 80},
        },
    }
