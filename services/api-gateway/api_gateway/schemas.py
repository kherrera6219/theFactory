"""Pydantic request and response schemas for api-gateway."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

_METADATA_MAX_BYTES = 4096


class MissionAttachment(BaseModel):
    file_id: str
    filename: str
    content_type: str
    size_bytes: int = 0
    purpose: str | None = "reference"


class MissionCreate(BaseModel):
    prompt: str = Field(min_length=3)
    requested_target_language: str | None = None
    source_code: str | None = Field(default=None, max_length=512_000)
    mission_type: str | None = None
    depth_mode: str | None = None
    output_mode: str | None = None
    data_classification: str | None = None
    attachments: list[MissionAttachment] = Field(default_factory=list)
    global_style_directives: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def __get_validators__(cls):
        yield from super().__get_validators__()

    def model_post_init(self, __context: Any) -> None:
        serialized = json.dumps(self.metadata, separators=(",", ":"))
        if len(serialized.encode("utf-8")) > _METADATA_MAX_BYTES:
            raise ValueError(
                f"metadata exceeds maximum allowed size of {_METADATA_MAX_BYTES} bytes"
            )


class MissionRecord(BaseModel):
    mission_id: str
    prompt: str
    requested_target_language: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    project_id: str | None = None
    lifecycle_engine: str | None = None
    state: str
    created_at: str


class MissionStateUpdate(BaseModel):
    new_state: str
    expected_state: str | None = None


class AlertStateUpdate(BaseModel):
    state: str = Field(pattern="^(acknowledged|resolved)$")


class BuilderPreviewRequest(BaseModel):
    request: str = Field(min_length=3, max_length=4000)
    constraints: list[str] = Field(default_factory=list)
    view_mode: str | None = Field(default=None, pattern="^(desktop|tablet|mobile)$")
    provider: str | None = Field(default=None, pattern="^(openai|anthropic|gemini|offline)$")
    model: str | None = Field(default=None, min_length=2, max_length=120)
    reasoning_effort: str | None = Field(
        default=None,
        pattern="^(none|minimal|low|medium|high|xhigh)$",
    )
    thinking_budget: int | None = Field(default=None, ge=-1, le=65536)
