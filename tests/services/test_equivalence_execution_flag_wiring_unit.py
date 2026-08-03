"""UPG-21 — keep ``mission_equivalence_python_execution_enabled`` from rotting.

The flag is declared at ``settings.py:88`` and loaded from
``MISSION_EQUIVALENCE_PYTHON_EXECUTION_ENABLED`` at ``settings.py:384`` — and read
nowhere else in the repository. It is a declared capability with no
implementation behind it, which is worse than no flag at all: an operator can set
it, see no error, and reasonably conclude execution-based equivalence is running.

The decision (upgrade plan UPG-21) is to **keep it and wire it in Phase 5**
(UPG-51), where it is exactly the right gate for execution-based equivalence
verification. If Phase 5 slips, delete the flag rather than leave it dangling.

## Why the wiring test is xfail(strict=True)

Phase 2's own exit criteria are in tension: criterion 2 says *"a test fails if the
setting has no consumer"*, criterion 5 says *"full backend suite green"*. Both
cannot hold while the flag genuinely has no consumer.

``xfail(strict=True)`` resolves it in the direction that keeps the signal alive at
both ends:

* **Today** the flag has no consumer, the test fails as expected, and the suite
  stays green — the known gap is recorded in executable form rather than prose.
* **When Phase 5 lands** and wires the flag, the test starts passing. Under
  ``strict=True`` an unexpected pass is itself a failure, so the suite goes red
  and forces someone to delete this marker and promote the test to a normal
  assertion.

Either way the flag cannot silently rot: it is impossible for it to gain or lose
a consumer without a test changing state.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

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


@pytest.mark.xfail(
    strict=True,
    reason=(
        "UPG-21: the flag has no consumer until Phase 5 (UPG-51) wires the "
        "execution-based equivalence harness. When this starts passing, strict "
        "xfail turns the suite red on purpose — delete this marker and keep the "
        "assertion."
    ),
)
def test_flag_has_at_least_one_consumer() -> None:
    sites = _consumer_sites()
    assert sites, (
        f"{FLAG_ATTRIBUTE} is declared and loaded in settings.py but read "
        "nowhere in services/ or shared_runtime/. Either wire it (UPG-51) or "
        "delete it — do not leave a declared capability with no implementation."
    )
