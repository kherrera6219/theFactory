from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

LOGGER = logging.getLogger(__name__)


class RefinedIRParameter(BaseModel):
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)


class RefinedIROperation(BaseModel):
    op_id: str = Field(min_length=1)
    opcode: str = Field(min_length=1)
    args: list[str] = Field(default_factory=list)
    out: str = Field(min_length=1)


class RefinedIREquivalenceVector(BaseModel):
    in_: dict[str, Any] = Field(alias="in")
    out: dict[str, Any]


class RefinedIRTests(BaseModel):
    equivalence_vectors: list[RefinedIREquivalenceVector] = Field(min_length=1)
    properties: list[str] = Field(default_factory=list)


class RefinedIRProvenanceSource(BaseModel):
    kind: str = Field(pattern="^(docs|repo)$")
    ref: str = Field(min_length=1)
    hash: str = Field(min_length=1)


class RefinedIRChainOfCustodyEntry(BaseModel):
    agent: str = Field(min_length=1)
    action: str = Field(min_length=1)
    ts: str = Field(min_length=1)


class RefinedIRProvenance(BaseModel):
    sources: list[RefinedIRProvenanceSource] = Field(default_factory=list)
    chain_of_custody: list[RefinedIRChainOfCustodyEntry] = Field(default_factory=list)


class RefinedIRFunction(BaseModel):
    fn_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    # UNKNOWN added by UPG-41: a function whose side effects were never analysed
    # must be able to say so rather than being forced to claim PURE or IMPURE.
    purity: str = Field(pattern="^(PURE|IMPURE|UNKNOWN)$")
    inputs: list[RefinedIRParameter] = Field(default_factory=list)
    outputs: list[RefinedIRParameter] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    ops: list[RefinedIROperation] = Field(default_factory=list)
    effects: list[str] = Field(default_factory=list)
    tests: RefinedIRTests
    provenance: RefinedIRProvenance
    # UPG-40: a downstream consumer reading this JSON could not previously tell
    # a templated projection from a real one — the honesty lived only in prose
    # in docs/LOGICNODE_SCHEMA.md.
    projection_method: str = Field(default="templated_v1", pattern="^(templated_v1|ast_v1)$")


class RefinedIRModule(BaseModel):
    rir_version: str = Field(default="1.0.0")
    module: dict[str, Any]
    fns: list[RefinedIRFunction] = Field(default_factory=list)
    # "mixed_v1" is a deliberate addition to the plan's two values: one source
    # file legitimately mixes AST-backed and regex-only extraction, and
    # collapsing that to either extreme would misreport the module.
    projection_method: str = Field(
        default="templated_v1", pattern="^(templated_v1|ast_v1|mixed_v1)$"
    )


@dataclass(frozen=True, slots=True)
class RefinedIRStoreWrite:
    path: Path
    relative_path: str
    git_commit: str | None
    sha256: str


def _json_sha256(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _source_hash(logicnode: dict[str, Any]) -> str:
    payload = logicnode.get("node")
    if isinstance(payload, dict):
        return _json_sha256(payload)
    return _json_sha256(logicnode)


def _git_commit_for_path(store_root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(store_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    commit = completed.stdout.strip()
    return commit or None


def _equivalence_vectors_for(
    *,
    node_id: str,
    concept: str,
    domain: str,
    source_language: str,
    types_in: list[str],
    types_out: list[str],
    inputs: list[RefinedIRParameter],
) -> list[RefinedIREquivalenceVector]:
    """Build the equivalence vectors Phase 5 will execute.

    The templated vector restated the node's own identifiers
    (``in: {node_id, source_language}`` / ``out: {concept, domain}``), so it
    could never fail — comparing a node to itself always succeeds.

    When a real signature is available, emit vectors of concrete argument values
    typed to the recovered signature: a nominal case plus boundary cases where
    the type has meaningful boundaries. ``expected`` is deliberately left
    ``null`` — the expected output is not known until something executes the
    artifact, and inventing one would recreate the "cannot fail" problem in a
    new form. Phase 5 (UPG-50) fills it by execution.
    """
    if not inputs:
        # No recovered signature: keep the descriptive vector, but it is
        # explicitly marked so Phase 5 can skip what it cannot execute.
        return [
            RefinedIREquivalenceVector(
                **{
                    "in": {"node_id": node_id, "source_language": source_language},
                    "out": {"concept": concept, "domain": domain, "executable": False},
                }
            )
        ]

    vectors: list[RefinedIREquivalenceVector] = []
    for case in ("nominal", "boundary_low", "boundary_high"):
        args = {
            param.name: _sample_value_for_type(param.type, case) for param in inputs
        }
        if any(value is _NO_SAMPLE for value in args.values()):
            continue
        vectors.append(
            RefinedIREquivalenceVector(
                **{
                    "in": {"case": case, "args": args},
                    "out": {
                        "expected": None,
                        "expected_type": types_out[0] if types_out else None,
                        "executable": True,
                    },
                }
            )
        )
    if not vectors:
        return [
            RefinedIREquivalenceVector(
                **{
                    "in": {"node_id": node_id, "source_language": source_language},
                    "out": {"concept": concept, "domain": domain, "executable": False},
                }
            )
        ]
    return vectors


class _NoSample:
    """Sentinel for a type this projection cannot produce a value for."""

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return "<no-sample>"


_NO_SAMPLE = _NoSample()

# Concrete sample values per recognised type, per case. Deliberately small and
# explicit: a type not listed here yields no sample, which drops the vector
# rather than inventing a value whose semantics are guessed.
_TYPE_SAMPLES: dict[str, dict[str, Any]] = {
    "int": {"nominal": 2, "boundary_low": 0, "boundary_high": -1},
    "float": {"nominal": 1.5, "boundary_low": 0.0, "boundary_high": -1.0},
    "double": {"nominal": 1.5, "boundary_low": 0.0, "boundary_high": -1.0},
    "bool": {"nominal": True, "boundary_low": False, "boundary_high": True},
    "boolean": {"nominal": True, "boundary_low": False, "boundary_high": True},
    "str": {"nominal": "sample", "boundary_low": "", "boundary_high": "  x  "},
    "string": {"nominal": "sample", "boundary_low": "", "boundary_high": "  x  "},
    "list": {"nominal": [1, 2, 3], "boundary_low": [], "boundary_high": [0]},
    "dict": {"nominal": {"k": 1}, "boundary_low": {}, "boundary_high": {"k": None}},
    "set": {"nominal": [1, 2], "boundary_low": [], "boundary_high": [0]},
    "tuple": {"nominal": [1, 2], "boundary_low": [], "boundary_high": [0]},
    "bytes": {"nominal": "c2FtcGxl", "boundary_low": "", "boundary_high": "AA=="},
}


def _sample_value_for_type(type_name: str, case: str) -> Any:
    """Return a concrete sample value for *type_name*, or ``_NO_SAMPLE``.

    Normalisation is intentionally shallow: ``List[int]`` and ``[Int]`` both
    reduce to ``list``, but a bare user-defined class yields no sample. Guessing
    a value for an unknown type would produce a vector that fails for reasons
    unrelated to the code under test.
    """
    normalized = str(type_name or "").strip().lower()
    if not normalized:
        return _NO_SAMPLE

    # Bracket notations must be recognised BEFORE generic parameters are
    # stripped: splitting "[int]" on "[" yields an empty string, which silently
    # dropped every Haskell list type — and Haskell is one of only three
    # languages whose signatures are recovered at all.
    if (normalized.startswith("[") and normalized.endswith("]")) or normalized.endswith("[]"):
        normalized = "list"
    else:
        # Strip Optional[...]/Maybe wrappers, then collapse generic containers.
        for prefix in ("optional[", "maybe "):
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix) :].rstrip("]").strip()
                break
        if normalized.startswith(("list[", "sequence[", "iterable[")):
            normalized = "list"
        else:
            normalized = normalized.split("[", 1)[0].strip()

    samples = _TYPE_SAMPLES.get(normalized)
    if samples is None:
        return _NO_SAMPLE
    return samples.get(case, _NO_SAMPLE)


def build_refined_ir_module(
    *,
    mission_id: str,
    agent_id: str,
    source_language: str,
    target_language: str,
    logicnodes: list[dict[str, Any]],
    source_ref: str,
) -> RefinedIRModule:
    functions: list[RefinedIRFunction] = []
    for index, logicnode in enumerate(logicnodes, start=1):
        node_payload = logicnode.get("node")
        payload = node_payload.get("payload") if isinstance(node_payload, dict) else {}
        if not isinstance(payload, dict):
            payload = {}
        concept = str(payload.get("concept") or logicnode.get("concept") or f"node_{index}")
        domain = str(payload.get("domain") or logicnode.get("domain") or "generic")
        node_id = str(logicnode.get("node_id") or f"{mission_id}:{index}")
        confidence = float(payload.get("confidence", 0.0) or 0.0)
        # node_name is opportunistic, not a required LogicNode field. When
        # absent, `str(node_payload.get("node_name"))` used to evaluate
        # `str(None)` -- the literal string "None" -- instead of falling
        # back to `concept`, silently corrupting the RIR's name field.
        node_name = node_payload.get("node_name") if isinstance(node_payload, dict) else None

        # ------------------------------------------------------------------
        # UPG-40/41: derive real content where Phase 3 recovered it, and fall
        # back to the templated projection where it did not. The two paths are
        # distinguished by `projection_method` so a consumer never has to guess.
        # ------------------------------------------------------------------
        node_types = node_payload.get("types") if isinstance(node_payload, dict) else None
        types_in = [str(t) for t in (node_types or {}).get("in", []) if str(t).strip()]
        types_out = [str(t) for t in (node_types or {}).get("out", []) if str(t).strip()]
        node_purity = node_payload.get("purity") if isinstance(node_payload, dict) else None
        node_side_effects = [str(e) for e in (payload.get("side_effects") or [])]
        has_signature = bool(types_in or types_out)
        fn_projection = "ast_v1" if has_signature else "templated_v1"

        if has_signature:
            # Parameter names are not recovered by the extractors (only types),
            # so they are positional. The types are real; the names are not
            # claimed to be the source's.
            inputs = [
                RefinedIRParameter(name=f"arg{position}", type=type_name)
                for position, type_name in enumerate(types_in)
            ]
            outputs = [
                RefinedIRParameter(name="return", type=type_name) for type_name in types_out
            ]
            # Real statement sequence when the extractor recovered one; the
            # single synthetic CALL is only the fallback. The RIR used to emit
            # exactly one EXTRACT_CONCEPT op per function regardless of body.
            raw_ops = payload.get("op_stream") or []
            ops = [
                RefinedIROperation(
                    op_id=f"{node_id}:op{position}",
                    opcode=str(entry[0]),
                    args=[str(entry[1])] if len(entry) > 1 and str(entry[1]) else [],
                    out="return" if outputs else "intent",
                )
                for position, entry in enumerate(raw_ops)
                if isinstance(entry, list | tuple) and entry
            ]
            if not ops:
                ops = [
                    RefinedIROperation(
                        op_id=f"{node_id}:call",
                        opcode="CALL",
                        args=[param.name for param in inputs],
                        out="return" if outputs else "intent",
                    )
                ]
            preconditions = [
                f"{param.name} is of type {param.type}" for param in inputs
            ] or ["mission payload available"]
            postconditions = (
                [f"return is of type {outputs[0].type}"]
                if outputs
                else [f"concept '{concept}' extracted in domain '{domain}'"]
            )
        else:
            inputs = [RefinedIRParameter(name="source", type=source_language or "unknown")]
            outputs = [
                RefinedIRParameter(
                    name="intent",
                    type=target_language or source_language or "generic",
                )
            ]
            ops = [
                RefinedIROperation(
                    op_id=f"{node_id}:extract",
                    opcode="EXTRACT_CONCEPT",
                    args=[domain, concept],
                    out="intent",
                )
            ]
            preconditions = ["mission payload available"]
            postconditions = [f"concept '{concept}' extracted in domain '{domain}'"]

        # Purity now comes from real side-effect analysis when it ran. The old
        # derivation was `"IMPURE" if payload.get("intent") else "PURE"` --
        # purity decided by whether an unrelated string was truthy.
        if node_purity in ("PURE", "IMPURE", "UNKNOWN"):
            purity = node_purity
        else:
            purity = "UNKNOWN"

        # Real detected effects when analysis ran; otherwise the provenance
        # marker, which is what the templated path always emitted.
        if node_side_effects:
            effects = node_side_effects
        elif node_purity == "PURE":
            effects = []
        else:
            effects = ["logicnode_recorded"] if confidence < 1 else []

        functions.append(
            RefinedIRFunction(
                fn_id=node_id,
                name=str(node_name) if node_name else concept,
                purity=purity,
                inputs=inputs,
                outputs=outputs,
                preconditions=preconditions,
                postconditions=postconditions,
                ops=ops,
                effects=effects,
                projection_method=fn_projection,
                tests=RefinedIRTests(
                    equivalence_vectors=_equivalence_vectors_for(
                        node_id=node_id,
                        concept=concept,
                        domain=domain,
                        source_language=source_language,
                        types_in=types_in,
                        types_out=types_out,
                        inputs=inputs if has_signature else [],
                    ),
                    properties=[
                        "deterministic_logicnode_projection",
                        "schema_validated_refined_ir",
                    ]
                    + (["ast_derived_signature"] if has_signature else []),
                ),
                provenance=RefinedIRProvenance(
                    sources=[
                        RefinedIRProvenanceSource(
                            kind="repo",
                            ref=source_ref,
                            hash=_source_hash(logicnode),
                        )
                    ],
                    chain_of_custody=[
                        RefinedIRChainOfCustodyEntry(
                            agent=agent_id,
                            action="logicnode_to_refined_ir",
                            ts=datetime.now(UTC).isoformat(),
                        )
                    ],
                ),
            )
        )

    # Module-level summary of how its functions were projected (UPG-40). A file
    # that mixes AST-backed and regex-only extraction is genuinely mixed;
    # reporting it as either extreme would misstate the module.
    fn_methods = {fn.projection_method for fn in functions}
    if not fn_methods or fn_methods == {"templated_v1"}:
        module_projection = "templated_v1"
    elif fn_methods == {"ast_v1"}:
        module_projection = "ast_v1"
    else:
        module_projection = "mixed_v1"

    return RefinedIRModule(
        module={
            "mission_id": mission_id,
            "agent_id": agent_id,
            "source_language": source_language,
            "target_language": target_language or source_language,
            "logicnode_count": len(logicnodes),
            "ast_projected_fn_count": sum(
                1 for fn in functions if fn.projection_method == "ast_v1"
            ),
        },
        fns=functions,
        projection_method=module_projection,
    )


def write_refined_ir_module(
    module: RefinedIRModule,
    *,
    store_root: str | Path,
    mission_id: str,
    agent_id: str,
) -> RefinedIRStoreWrite:
    root = Path(store_root)
    root.mkdir(parents=True, exist_ok=True)
    target_dir = root / "missions" / mission_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{agent_id.lower()}.rir.module.json"
    payload = module.model_dump(by_alias=True)
    serialized = json.dumps(payload, indent=2) + "\n"
    target_path.write_text(serialized, encoding="utf-8")
    # Best-effort ECDSA signature so FUSION can verify the module's authenticity.
    # Non-fatal: a signing failure must not block the mission pipeline.
    try:
        from shared_runtime.crypto_signing import sign_artifact

        sign_artifact(target_path)
        LOGGER.info("RIR module signed: %s", target_path)
    except Exception as e:
        LOGGER.warning("RIR module signing failed (non-fatal): %s", type(e).__name__)
    relative_path = target_path.relative_to(root).as_posix()
    # UPG-43: keep the catalog in step with what is actually on disk.
    # `artifacts/refined-ir/index.json` sat empty at `{"artifacts": []}` while
    # signed modules accumulated per mission, because the only thing that ever
    # wrote it was a script nothing invoked. Non-fatal, like signing above.
    try:
        update_refined_ir_catalog(root, module, relative_path=relative_path)
    except Exception as e:
        LOGGER.warning("RIR catalog update failed (non-fatal): %s", type(e).__name__)
    return RefinedIRStoreWrite(
        path=target_path,
        relative_path=relative_path,
        git_commit=_git_commit_for_path(root),
        sha256=_json_sha256(payload),
    )


def catalog_record_for(module: RefinedIRModule, *, relative_path: str) -> dict[str, Any]:
    """Return the index record describing one stored RIR module.

    Shared by the write path and ``scripts/build_refined_ir_catalog.py`` so a
    rebuilt catalog and an incrementally-updated one cannot drift apart.
    """
    return {
        "path": relative_path,
        "mission_id": module.module.get("mission_id"),
        "agent_id": module.module.get("agent_id"),
        "source_language": module.module.get("source_language"),
        "target_language": module.module.get("target_language"),
        "function_count": len(module.fns),
        # Surfaced in the catalog so "how many of our projections are real?"
        # is answerable without opening every module (UPG-40).
        "projection_method": module.projection_method,
        "ast_projected_fn_count": sum(
            1 for fn in module.fns if fn.projection_method == "ast_v1"
        ),
    }


def update_refined_ir_catalog(
    store_root: str | Path,
    module: RefinedIRModule,
    *,
    relative_path: str,
) -> Path:
    """Upsert *module*'s record into the store's ``index.json``.

    Keyed by ``path``, so re-running a mission replaces its record rather than
    appending a duplicate. The write is atomic because several pod workers can
    finish missions concurrently against the same store.
    """
    root = Path(store_root)
    index_path = root / "index.json"
    records: list[dict[str, Any]] = []
    if index_path.exists():
        try:
            existing = json.loads(index_path.read_text(encoding="utf-8"))
            candidate = existing.get("artifacts")
            if isinstance(candidate, list):
                records = [r for r in candidate if isinstance(r, dict)]
        except (OSError, json.JSONDecodeError):
            # A corrupt index must not block the mission; it is rebuilt from
            # the modules on disk by scripts/build_refined_ir_catalog.py.
            LOGGER.warning("RIR catalog unreadable, rewriting: %s", index_path)
            records = []

    record = catalog_record_for(module, relative_path=relative_path)
    records = [r for r in records if r.get("path") != relative_path]
    records.append(record)
    records.sort(key=lambda r: str(r.get("path") or ""))

    from shared_runtime.atomic_io import atomic_write_json

    atomic_write_json(index_path, {"artifacts": records}, indent=2)
    return index_path
