"""Regression tests for `.env` validation (scripts/check_env.py).

`.env` files parsed by Docker Compose have no inline-comment support: everything
after `=` is the value. So this line, which shipped in a working `.env`:

    ENVIRONMENT=development# Dev bypass - removes the admin key unlock gate

set `ENVIRONMENT` to the entire string including the comment. Nothing raised.
Every `ENVIRONMENT == "development"` branch silently stopped matching, and it was
found only by reading the resolved value out of a running container.

The old checker looked for `CHANGE_ME` and nothing else, so it passed this file
happily. These tests pin the checks that now catch it at `make up`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_env  # noqa: E402


@pytest.fixture
def env_dir(tmp_path, monkeypatch):
    """Point the checker at an isolated .env, never the real one."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(check_env, "_env_files", lambda _root: [tmp_path / ".env"])
    return tmp_path


def _write(env_dir: Path, body: str) -> None:
    (env_dir / ".env").write_text(body, encoding="utf-8")


def test_the_real_world_corruption_is_rejected(env_dir, capsys) -> None:
    """The exact line that shipped and silently broke ENVIRONMENT."""
    _write(
        env_dir,
        "ENVIRONMENT=development# Dev bypass - removes the admin key unlock gate\n",
    )
    assert check_env.check_env() == 1
    out = capsys.readouterr().out
    assert "ENVIRONMENT" in out
    assert "inline-comment" in out


def test_a_clean_env_passes(env_dir) -> None:
    _write(
        env_dir,
        "# a comment on its own line is fine\n"
        "ENVIRONMENT=development\n"
        "LLM_PROVIDER=gemini\n"
        "\n"
        "CORS_ALLOW_ORIGINS=http://localhost:3100,http://127.0.0.1:3100\n",
    )
    assert check_env.check_env() == 0


def test_hash_is_allowed_in_secrets_and_urls(env_dir) -> None:
    """A '#' is legitimate in a generated secret or a URL fragment — flagging
    those would train people to ignore the check."""
    _write(
        env_dir,
        "POSTGRES_PASSWORD=ab#cd3f\n"
        "SOME_API_KEY=k#ey\n"
        "REDIS_URL=redis://user:p#ass@host:6379/0\n"
        "MISSION_CONTROL_ADMIN_KEY=aa#bb\n",
    )
    assert check_env.check_env() == 0


def test_single_token_keys_reject_embedded_spaces(env_dir, capsys) -> None:
    """Keys compared by equality must not contain whitespace."""
    _write(env_dir, "LLM_PROVIDER=gemini with a note\n")
    assert check_env.check_env() == 1
    assert "single bare token" in capsys.readouterr().out


def test_change_me_is_still_rejected(env_dir, capsys) -> None:
    """The original check must survive the rewrite."""
    _write(env_dir, "POSTGRES_PASSWORD=CHANGE_ME\n")
    assert check_env.check_env() == 1
    assert "CHANGE_ME" in capsys.readouterr().out


def test_comment_lines_and_blank_lines_are_ignored(env_dir) -> None:
    _write(
        env_dir,
        "# ENVIRONMENT=development# this is inside a comment, not an assignment\n"
        "\n"
        "   \n"
        "ENVIRONMENT=development\n",
    )
    assert check_env.check_env() == 0


def test_missing_env_warns_but_does_not_fail(tmp_path, monkeypatch, capsys) -> None:
    """A fresh checkout with no .env must not be blocked from starting."""
    monkeypatch.setattr(check_env, "_env_files", lambda _root: [])
    assert check_env.check_env() == 0
    assert "WARNING" in capsys.readouterr().out


def test_the_repository_env_example_is_itself_valid() -> None:
    """.env.example is what people copy — it must pass its own checker."""
    example = ROOT / ".env.example"
    text = example.read_text(encoding="utf-8", errors="replace")
    errors = check_env._inline_comment_errors(example, text)
    errors += check_env._single_token_errors(example, text)
    assert errors == [], "\n".join(errors)
