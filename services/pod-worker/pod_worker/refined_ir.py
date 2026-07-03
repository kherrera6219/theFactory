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
    purity: str = Field(pattern="^(PURE|IMPURE)$")
    inputs: list[RefinedIRParameter] = Field(default_factory=list)
    outputs: list[RefinedIRParameter] = Field(default_factory=list)
    preconditions: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)
    ops: list[RefinedIROperation] = Field(default_factory=list)
    effects: list[str] = Field(default_factory=list)
    tests: RefinedIRTests
    provenance: RefinedIRProvenance


class RefinedIRModule(BaseModel):
    rir_version: str = Field(default="1.0.0")
    module: dict[str, Any]
    fns: list[RefinedIRFunction] = Field(default_factory=list)


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
        functions.append(
            RefinedIRFunction(
                fn_id=node_id,
                name=str(node_name) if node_name else concept,
                purity="IMPURE" if payload.get("intent") else "PURE",
                inputs=[RefinedIRParameter(name="source", type=source_language or "unknown")],
                outputs=[
                    RefinedIRParameter(
                        name="intent",
                        type=target_language or source_language or "generic",
                    )
                ],
                preconditions=["mission payload available"],
                postconditions=[f"concept '{concept}' extracted in domain '{domain}'"],
                ops=[
                    RefinedIROperation(
                        op_id=f"{node_id}:extract",
                        opcode="EXTRACT_CONCEPT",
                        args=[domain, concept],
                        out="intent",
                    )
                ],
                effects=["logicnode_recorded"] if confidence < 1 else [],
                tests=RefinedIRTests(
                    equivalence_vectors=[
                        RefinedIREquivalenceVector(
                            **{
                                "in": {"node_id": node_id, "source_language": source_language},
                                "out": {"concept": concept, "domain": domain},
                            }
                        )
                    ],
                    properties=[
                        "deterministic_logicnode_projection",
                        "schema_validated_refined_ir",
                    ],
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

    return RefinedIRModule(
        module={
            "mission_id": mission_id,
            "agent_id": agent_id,
            "source_language": source_language,
            "target_language": target_language or source_language,
            "logicnode_count": len(logicnodes),
        },
        fns=functions,
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
    return RefinedIRStoreWrite(
        path=target_path,
        relative_path=relative_path,
        git_commit=_git_commit_for_path(root),
        sha256=_json_sha256(payload),
    )
