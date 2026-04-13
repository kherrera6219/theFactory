"""prompt_loader — versioned prompt template loader.

Prompt templates live under ``prompts/<version>/`` as plain ``.txt`` files
with ``{variable}`` placeholders.  The active version is selected by the
``PROMPT_VERSION`` environment variable (default ``v1``).

Keeping prompts outside Python source makes them:
- auditable via diff (template changes are reviewable independently of logic)
- rollbackable (pin ``PROMPT_VERSION`` to an older version without redeployment)
- classifiable (templates contain no user data — they are static policy assets)

Callers must supply all placeholder values explicitly; missing keys raise
``KeyError`` rather than silently producing a malformed prompt.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

# Active prompt version — pin via PROMPT_VERSION env var to roll back.
PROMPT_VERSION: str = os.getenv("PROMPT_VERSION", "v1").strip() or "v1"

_PROMPTS_ROOT = Path(__file__).parent / "prompts"


@lru_cache(maxsize=32)
def _load_raw_template(version: str, name: str) -> str:
    """Load and cache a raw template string.

    Cached per (version, name) pair so the file is read once per process
    lifetime.  Cache is invalidated between test runs because each test process
    starts fresh.
    """
    path = _PROMPTS_ROOT / version / f"{name}.txt"
    if not path.is_file():
        raise FileNotFoundError(
            f"Prompt template not found: {path}. "
            f"Check PROMPT_VERSION='{version}' and that '{name}.txt' exists."
        )
    return path.read_text(encoding="utf-8")


def render_prompt(name: str, **kwargs: str) -> str:
    """Load template *name* for the active version and render with *kwargs*.

    Args:
        name: Template filename without extension (e.g. ``"ceo_delegation"``).
        **kwargs: Placeholder values.  All placeholders in the template must
            be supplied; extras are silently ignored.

    Returns:
        The fully-rendered prompt string, ready to send to an LLM provider.

    Raises:
        FileNotFoundError: When the template file does not exist.
        KeyError: When a required placeholder is missing from *kwargs*.
    """
    template = _load_raw_template(PROMPT_VERSION, name)
    return template.format(**kwargs)
