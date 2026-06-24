import importlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

atomic_io = importlib.import_module("shared_runtime.atomic_io")


def test_atomic_write_text_creates_file(tmp_path) -> None:
    dest = tmp_path / "out.txt"
    atomic_io.atomic_write_text(dest, "hello world")
    assert dest.read_text(encoding="utf-8") == "hello world"
    # No leftover temp file.
    assert list(tmp_path.glob(".out.txt.*.tmp")) == []


def test_atomic_write_json_roundtrip(tmp_path) -> None:
    dest = tmp_path / "data.json"
    atomic_io.atomic_write_json(dest, {"a": 1, "b": [2, 3]})
    loaded = json.loads(dest.read_text(encoding="utf-8"))
    assert loaded == {"a": 1, "b": [2, 3]}
    assert dest.read_text(encoding="utf-8").endswith("\n")


def test_atomic_write_creates_parent_dirs(tmp_path) -> None:
    dest = tmp_path / "nested" / "deep" / "file.txt"
    atomic_io.atomic_write_text(dest, "x")
    assert dest.read_text(encoding="utf-8") == "x"


def test_atomic_write_overwrites_and_backs_up(tmp_path) -> None:
    dest = tmp_path / "out.txt"
    atomic_io.atomic_write_text(dest, "first")
    atomic_io.atomic_write_text(dest, "second")
    assert dest.read_text(encoding="utf-8") == "second"
    # A backup of the previous valid file is kept.
    backup = tmp_path / "out.txt.bak"
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == "first"


def test_atomic_write_bytes_verify(tmp_path) -> None:
    dest = tmp_path / "blob.bin"
    payload = b"\x00\x01\x02binary\xff"
    atomic_io.atomic_write_bytes(dest, payload, verify=True)
    assert dest.read_bytes() == payload


def test_concurrent_writes_use_unique_temp_files(tmp_path) -> None:
    dest = tmp_path / "shared.txt"
    payloads = [f"payload-{index}" for index in range(16)]

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda payload: atomic_io.atomic_write_text(dest, payload), payloads))

    assert dest.read_text(encoding="utf-8") in payloads
    assert list(tmp_path.glob(".shared.txt.*.tmp")) == []

def test_existing_file_preserved_on_replace_failure(tmp_path, monkeypatch) -> None:
    dest = tmp_path / "out.txt"
    atomic_io.atomic_write_text(dest, "original")

    def _boom(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr(atomic_io.os, "replace", _boom)
    try:
        atomic_io.atomic_write_text(dest, "new")
    except OSError:
        pass
    # Original content survives a failed replace.
    assert dest.read_text(encoding="utf-8") == "original"
    # Temp file is cleaned up.
    assert list(tmp_path.glob(".out.txt.*.tmp")) == []
