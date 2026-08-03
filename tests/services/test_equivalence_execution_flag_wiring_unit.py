"""UPG-21 — keep ``mission_equivalence_python_execution_enabled`` from rotting.

**Status: the flag is wired.** Phase 5 (UPG-51) connected it in
``mission_flow_v2/phases_delivery.py``, where it gates behavioural equivalence
execution. These tests now guard against it being orphaned *again*.

## History, kept because the mechanism is worth reusing

The flag was declared at ``settings.py:88`` and loaded from
``MISSION_EQUIVALENCE_PYTHON_EXECUTION_ENABLED`` at ``settings.py:384`` — and read
nowhere else. That is worse than no flag at all: an operator could set it, see no
error, and reasonably conclude execution-based equivalence was running.

Phase 2's exit criteria were in direct tension about it — criterion 2 wanted a
test that *fails* while the setting has no consumer, criterion 5 wanted a green
suite — and both could not hold while the flag was genuinely dead.

``xfail(strict=True)`` resolved it in the only direction that kept the signal
alive at both ends: the gap was recorded in executable form while the suite
stayed green, and the moment Phase 5 wired the flag the unexpected pass turned
the suite **red on purpose**, forcing the marker's removal. That is exactly what
happened on 2026-08-02, two phases after the marker was written.

The marker is gone and the assertion is live. A regression that orphans the flag
now fails normally.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

FLAG_ATTRIBUTE = "mission_equivalence_python_execution_enabled"
FLAG_ENV_VAR = "MISSION_EQUIVALENCE_PYTHON_EXECUTION_ENABLED"

SETTINGS_PATH = ROOT / "services" / "orchestrator" / "orchestrator" / "settings.py"

# Directories searched for a consumer. Tests are excluded on purpose: a test
# referencing the flag is not the same as the product using it.
SEARCH_ROOTS = (
    ROOT / "services",
    ROOT / "shared_runtime",
)


def _python_sources() -> list[Path]:
    files: list[Path] = []
    for root in SEARCH_ROOTS:
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts or ".venv" in path.parts:
                continue
            files.append(path)
    return files


def _consumer_sites() -> list[str]:
    """Return non-declaration references to the flag, as ``path:line`` strings.

    ``settings.py`` is where the flag is declared and loaded; a reference there
    is definitional, not consumption. Everything else counts.
    """
    pattern = re.compile(rf"\b{FLAG_ATTRIBUTE}\b|\b{FLAG_ENV_VAR}\b")
    sites: list[str] = []
    for path in _python_sources():
        if path == SETTINGS_PATH:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                sites.append(f"{path.relative_to(ROOT).as_posix()}:{lineno}")
    return sites


def test_flag_is_still_declared_and_loaded() -> None:
    """The flag must not be silently deleted while Phase 5 is outstanding.

    If Phase 5 is abandoned, delete the flag *and* this whole module together —
    per UPG-21, a dangling declared capability is the outcome to avoid.
    """
    from orchestrator.settings import Settings

    assert hasattr(Settings, "__annotations__")
    assert FLAG_ATTRIBUTE in Settings.__annotations__, (
        f"{FLAG_ATTRIBUTE} was removed from Settings. If that was deliberate "
        "(Phase 5 abandoned), delete this test module too."
    )
    settings_source = SETTINGS_PATH.read_text(encoding="utf-8")
    assert FLAG_ENV_VAR in settings_source, (
        f"{FLAG_ENV_VAR} is no longer loaded from the environment"
    )


def test_flag_default_is_off() -> None:
    """Flag discipline: every unproven capability defaults to false.

    Guiding principle 3 of the upgrade plan — flag off must mean byte-identical
    behaviour.
    """
    from orchestrator.settings import Settings

    assert Settings.__dataclass_fields__[FLAG_ATTRIBUTE].default is False


def test_flag_has_at_least_one_consumer() -> None:
    """Promoted from xfail(strict=True) to a live assertion on 2026-08-02.

    This test shipped in Phase 2 as a strict xfail because the flag genuinely
    had no consumer and Phase 2's exit criteria could not otherwise both hold.
    Phase 5 (UPG-51) wired it in `mission_flow_v2/phases_delivery.py`, the
    unexpected pass turned the suite red exactly as the marker was designed to,
    and the marker has been removed. From here a regression that orphans the
    flag again fails normally.
    """
    sites = _consumer_sites()
    assert sites, (
        f"{FLAG_ATTRIBUTE} is declared and loaded in settings.py but read "
        "nowhere in services/ or shared_runtime/. Either wire it (UPG-51) or "
        "delete it — do not leave a declared capability with no implementation."
    )
