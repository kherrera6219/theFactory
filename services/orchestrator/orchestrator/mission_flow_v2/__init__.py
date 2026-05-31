"""
mission_flow_v2 — 11-phase Mission Flow v2 lifecycle engine.

Provides the expanded state-machine that replaces v1.1's coarse
``QUEUED → RUNNING → VERIFIED → COMPLETE`` with 11 granular phases.

Gated behind ``MISSION_FLOW_V2_ENABLED=true``.  When disabled the
legacy/LangGraph v1.1 engines handle mission progression as before.

Phase order
-----------
1. INTAKE          (gateway receipt)
2. QUEUED          (persisted + queued)
3. PM_INTAKE       (PM intent translation)
4. CEO_DELEGATED   (CEO delegation plan)
5. POD_ASSIGNED    (pod manager assigned)
6. SPECIALIST_ASSIGNED (specialist assigned)
7. RUNNING         (extraction active)
8. GATING          (QC gating pass)
9. FUSION          (artifact fusion)
10. VERIFIED       (verification gate)
11. COMPLETE       (delivered)

This package was split out of the former 3,161-line ``mission_flow_v2.py``
monolith (issue #186).  The public API is re-exported here so that existing
``from orchestrator.mission_flow_v2 import ...`` imports continue to resolve
unchanged.

Module map
----------
- ``base``           : imports, constants, pure helpers, mission-charter
                       schema validation, and ``build_mission_charter``.
- ``transitions``    : v2/v1 state-transition tables, phase ordering, and the
                       v2→v1 state mapping helpers.
- ``phases_intake``  : queued → specialist-assigned phase preparation
                       (PM intake, FETCH, CEO/pod/specialist delegation).
- ``phases_build``   : pod/specialist assignment, specialist plans, pod-group
                       standards, and verified-build artifact production.
- ``phases_delivery``: delivery-summary, equivalence, and security/compliance
                       gate preparation.
- ``phases_runtime`` : dependency-absorption, runtime-QC, and fusion gate
                       preparation.
- ``lifecycle``      : the ``advance_mission_lifecycle_v2`` driver plus the
                       per-state advance helpers.

The dependency injection points that tests patch on the package namespace
(``storage``, ``record_audit_event``, ``generate_aim`` and the LLM
``generate_*`` helpers) are imported here as module attributes and resolved at
call time through ``importlib.import_module(__package__)`` in the submodules so
that ``unittest.mock.patch('orchestrator.mission_flow_v2.<name>')`` keeps
reaching the live call sites after the split (issue #186).
"""
from __future__ import annotations

# Patch-through dependency injection points.  Imported here so that tests which
# ``unittest.mock.patch('orchestrator.mission_flow_v2.<name>')`` affect the live
# call sites (resolved through ``importlib.import_module(__package__)``).
from .. import storage  # noqa: F401
from ..aim_generator import generate_aim  # noqa: F401
from ..audit_events import record_audit_event  # noqa: F401
from ..llm_delegation import (  # noqa: F401
    generate_ceo_delegation,
    generate_code_from_contract,
    generate_master_logic_stream,
    generate_pm_delivery_summary,
    generate_pm_feature_contract,
    generate_pod_group_standard,
    generate_pod_manager_delegation,
    generate_specialist_plan,
)
from .base import (  # noqa: F401
    build_mission_charter,
    validate_mission_charter_schema,
)
from .lifecycle import (  # noqa: F401
    advance_mission_lifecycle_v2,
)
from .phases_delivery import (  # noqa: F401
    _prepare_equivalence_report,
    _prepare_security_compliance_report,
)
from .phases_intake import (  # noqa: F401
    _prepare_pm_intake,
)
from .phases_runtime import (  # noqa: F401
    _prepare_dependency_absorption_reports,
    _prepare_fusion,
)
from .transitions import (  # noqa: F401
    V1_TRANSITIONS,
    V2_EVENT_TO_PHASE,
    V2_PHASE_ORDER,
    V2_TRANSITIONS,
    v2_map_state_to_v1,
    v2_phase_index,
)

__all__ = [
    "V1_TRANSITIONS",
    "V2_EVENT_TO_PHASE",
    "V2_PHASE_ORDER",
    "V2_TRANSITIONS",
    "advance_mission_lifecycle_v2",
    "build_mission_charter",
    "generate_aim",
    "generate_ceo_delegation",
    "generate_code_from_contract",
    "generate_master_logic_stream",
    "generate_pm_delivery_summary",
    "generate_pm_feature_contract",
    "generate_pod_group_standard",
    "generate_pod_manager_delegation",
    "generate_specialist_plan",
    "record_audit_event",
    "storage",
    "v2_map_state_to_v1",
    "v2_phase_index",
    "validate_mission_charter_schema",
]
