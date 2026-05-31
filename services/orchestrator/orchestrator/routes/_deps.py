from __future__ import annotations

# Auth dependency callables are imported from the parent main module.
# They are defined there before the routers are loaded, so the circular
# import resolves correctly.  Tests patch orchestrator.main.INTERNAL_AUTH /
# orchestrator.main.MUTATION_AUTH and FastAPI's dependency_overrides uses
# the callable object as the key, so both must refer to the same objects.
from fastapi import Depends

# Lazy re-export so other modules can do: from .routes._deps import INTERNAL_AUTH_DEP
# The actual callables come from ..main to ensure object identity with test overrides.
from ..main import INTERNAL_AUTH, MUTATION_AUTH, READ_AUTH  # noqa: F401 (re-exported)

MUTATION_AUTH_DEP = Depends(MUTATION_AUTH)
INTERNAL_AUTH_DEP = Depends(INTERNAL_AUTH)
READ_AUTH_DEP = Depends(READ_AUTH)
