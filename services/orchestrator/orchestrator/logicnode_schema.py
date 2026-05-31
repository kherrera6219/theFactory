"""logicnode_schema.py — load and enforce schemas/logicnode.schema.json.

The orchestrator validates every LogicNode ``node`` payload against the
canonical JSON Schema at the ``/internal/logicnodes`` write boundary, mirroring
the envelope-validation pattern introduced for event envelopes (#189). The
schema is loaded once and cached (load once, validate many).

Validation is non-fatal: a node that fails the schema is logged and reported
back to the caller so extraction is not aborted wholesale, but the orchestrator
can decide whether to skip it. ``schemas/logicnode.schema.json`` is the single
source of truth for LogicNode shape.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema import ValidationError as JSONSchemaValidationError

LOGGER = logging.getLogger(__name__)

_DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "schemas" / "logicnode.schema.json"


@lru_cache(maxsize=8)
def _load_validator(schema_path: str) -> Draft202012Validator:
    path = Path(schema_path)
    if not path.exists():
        # Fall back to the repo-relative schema if the configured path is absent
        # (e.g. unit tests constructing Settings with the default placeholder).
        path = _DEFAULT_SCHEMA_PATH
    schema = json.loads(path.read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)


def validate_logicnode(node: dict[str, Any], *, schema_path: str | Path) -> list[str]:
    """Validate *node* against the LogicNode schema.

    Returns a list of human-readable validation error strings — empty when the
    node is valid. Never raises on a schema violation; only a missing/broken
    schema file surfaces as an exception (a deployment misconfiguration).
    """
    validator = _load_validator(str(schema_path))
    errors: list[str] = []
    for error in sorted(validator.iter_errors(node), key=lambda exc: list(exc.absolute_path)):
        location = ".".join(str(part) for part in error.absolute_path)
        if location:
            errors.append(f"'{location}': {error.message}")
        else:
            errors.append(error.message)
    return errors


def is_valid_logicnode(node: dict[str, Any], *, schema_path: str | Path) -> bool:
    try:
        return not validate_logicnode(node, schema_path=schema_path)
    except JSONSchemaValidationError:  # pragma: no cover - defensive
        return False
