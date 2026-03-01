from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path

TRUTHY_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    redis_url: str
    postgres_url: str
    intake_stream: str
    state_stream: str
    max_stream_len: int
    consumer_group: str
    consumer_name: str
    auto_transition_enabled: bool
    transition_step_seconds: float
    intake_topic: str
    default_priority: str
    producer_name: str
    event_schema_path: Path
    topics_path: Path
    admin_api_key: str
    internal_service_api_key: str
    readonly_api_key: str
    extra_api_keys: str

    @property
    def api_key_roles(self) -> dict[str, set[str]]:
        mapping: dict[str, set[str]] = {}

        if self.admin_api_key:
            mapping[self.admin_api_key] = {"admin", "mutate", "internal", "read"}
        if self.internal_service_api_key:
            mapping[self.internal_service_api_key] = {"worker", "mutate", "internal", "read"}
        if self.readonly_api_key:
            mapping[self.readonly_api_key] = {"read"}

        # Format: "key=role1,role2;otherkey=role3"
        for entry in (part.strip() for part in self.extra_api_keys.split(";") if part.strip()):
            if "=" not in entry:
                continue
            key, roles_csv = entry.split("=", 1)
            roles = {role.strip().lower() for role in roles_csv.split(",") if role.strip()}
            if key.strip() and roles:
                mapping[key.strip()] = roles

        return mapping

    def topic_for_state(self, state_value: str) -> str:
        if state_value == "RUNNING":
            return os.getenv("STATE_TOPIC_RUNNING", "fusion.requested")
        if state_value == "VERIFIED":
            return os.getenv("STATE_TOPIC_VERIFIED", "artifact.rir.verified")
        if state_value == "COMPLETE":
            return os.getenv("STATE_TOPIC_COMPLETE", "binary.build.ready")
        if state_value == "FAILED":
            return os.getenv("STATE_TOPIC_FAILED", "incident.runtime.errorlog")
        return os.getenv("STATE_TOPIC_QUEUED", self.intake_topic)


def _as_bool(raw: str, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in TRUTHY_VALUES


def load_settings() -> Settings:
    if Path("/app/schemas").exists() and Path("/app/protocol").exists():
        repo_root = Path("/app")
    else:
        repo_root = Path(__file__).resolve().parents[3]

    return Settings(
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        postgres_url=os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@postgres:5432/ulr"),
        intake_stream=os.getenv("INTAKE_STREAM", "missions.intake"),
        state_stream=os.getenv("STATE_STREAM", "missions.state"),
        max_stream_len=int(os.getenv("MAX_STREAM_LEN", "20000")),
        consumer_group=os.getenv("MISSION_CONSUMER_GROUP", "orchestrator"),
        consumer_name=os.getenv("MISSION_CONSUMER_NAME", f"orchestrator-{socket.gethostname()}"),
        auto_transition_enabled=_as_bool(os.getenv("AUTO_TRANSITION_ENABLED", "true"), True),
        transition_step_seconds=float(os.getenv("TRANSITION_STEP_SECONDS", "1.0")),
        intake_topic=os.getenv("INTAKE_TOPIC", "intake.feature_contract.created"),
        default_priority=os.getenv("DEFAULT_EVENT_PRIORITY", "NORMAL"),
        producer_name=os.getenv("ORCHESTRATOR_PRODUCER", "orchestrator"),
        event_schema_path=Path(
            os.getenv(
                "EVENT_SCHEMA_PATH", str(repo_root / "schemas" / "event.envelope.schema.json")
            )
        ),
        topics_path=Path(os.getenv("TOPICS_PATH", str(repo_root / "protocol" / "topics.yaml"))),
        admin_api_key=os.getenv("ORCHESTRATOR_ADMIN_API_KEY", "admin-key"),
        internal_service_api_key=os.getenv("INTERNAL_SERVICE_API_KEY", "worker-key"),
        readonly_api_key=os.getenv("ORCHESTRATOR_READONLY_API_KEY", ""),
        extra_api_keys=os.getenv("ORCHESTRATOR_API_KEYS", ""),
    )
