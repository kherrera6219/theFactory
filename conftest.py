from __future__ import annotations

import sys
from pathlib import Path

# Ensure the repo root is on sys.path so that:
#   - shared_runtime.*  is importable as a top-level package
#   - from services.orchestrator.orchestrator.xxx import ...  works via namespace packages
_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
