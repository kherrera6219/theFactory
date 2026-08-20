from __future__ import annotations

import sys
from pathlib import Path

# Ensure the repo root is on sys.path so that:
#   - shared_runtime.*  is importable as a top-level package
#   - from services.orchestrator.orchestrator.xxx import ...  works via namespace packages
_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Service package roots. Most test modules insert the one they need themselves,
# but a module that forgets is only importable by accident of collection order —
# and under the default "prepend" import mode a miss also let a test *directory*
# named after a real package (tests/services/orchestrator, tests/services/
# pod_worker, tests/shared_runtime) get imported as that package, emptying it
# for every later module. Registering the roots here once removes the ordering
# dependency; `importmode = "importlib"` in pyproject removes the shadowing.
_SERVICE_ROOTS = (
    _REPO_ROOT / "services" / "pod-worker",
    _REPO_ROOT / "services" / "orchestrator",
    _REPO_ROOT / "services" / "api-gateway",
    _REPO_ROOT / "services" / "agent-runtime",
    _REPO_ROOT / "services" / "audit-worker",
    _REPO_ROOT / "services" / "protocol-bus-mcp",
)
for _service_root in _SERVICE_ROOTS:
    if _service_root.is_dir() and str(_service_root) not in sys.path:
        sys.path.insert(0, str(_service_root))

