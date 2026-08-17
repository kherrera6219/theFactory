"""P2: multi-file delivery tree serialize/parse."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))
sys.path.insert(0, str(ROOT))

from orchestrator.file_tree import (  # noqa: E402
    codegen_bundle_from_result,
    first_filename,
    normalize_codegen_files,
    parse_file_tree,
    sanitize_rel_path,
    serialize_file_tree,
)


def test_sanitize_strips_traversal_and_drive_prefix() -> None:
    assert sanitize_rel_path("../secret.py") == "secret.py"
    assert sanitize_rel_path("C:evil.txt") == "evil.txt"
    assert sanitize_rel_path("/abs/app.py") == "abs/app.py"


def test_round_trip_tree() -> None:
    files = [
        {"path": "app.py", "content": "print('a')\n"},
        {"path": "lib/util.py", "content": "x = 1\n"},
    ]
    bundle = serialize_file_tree(files)
    parsed = parse_file_tree(bundle)
    assert [item["path"] for item in parsed] == ["app.py", "lib/util.py"]
    assert "print('a')" in parsed[0]["content"]


def test_normalize_codegen_files_accepts_path_and_content() -> None:
    files = normalize_codegen_files(
        [
            {"path": "src/main.go", "content": "package main\n"},
            {"filename": "skip.py", "content": ""},
            "not-a-dict",
        ]
    )
    assert len(files) == 1
    assert files[0]["path"] == "src/main.go"


def test_codegen_bundle_prefers_files_array() -> None:
    bundle, files = codegen_bundle_from_result(
        {
            "generated_code": "print('ignore single file')\n",
            "files": [
                {"path": "pkg/a.py", "content": "A = 1\n"},
                {"path": "pkg/b.py", "content": "B = 2\n"},
            ],
        },
        "print('ignore single file')\n",
    )
    assert "## FILE pkg/a.py" in bundle
    assert "## FILE pkg/b.py" in bundle
    assert len(files) == 2


def test_first_filename_and_empty_inputs() -> None:
    assert first_filename([], "dir/fallback.py") == "fallback.py"
    assert first_filename([{"path": "pkg/main.go", "content": "package main\n"}], "x.py") == "main.go"
    assert parse_file_tree("") == []
    assert serialize_file_tree([]) == ""
    assert normalize_codegen_files(None) == []
    assert normalize_codegen_files([{"path": "dup.py", "content": "a"}, {"path": "dup.py", "content": "b"}]) == [
        {"path": "dup.py", "content": "a"}
    ]
    bundle, files = codegen_bundle_from_result({}, "print('single')\n")
    assert files == []
    assert bundle == "print('single')\n"
