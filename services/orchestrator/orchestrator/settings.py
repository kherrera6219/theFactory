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
    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: str = ""
    qdrant_enabled: bool = True
    qdrant_collection: str = "mission_knowledge"
    qdrant_vector_size: int = 64
    qdrant_timeout_seconds: float = 3.0
    neo4j_url: str = "http://neo4j:7474"
    neo4j_enabled: bool = False
    neo4j_username: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"
    neo4j_timeout_seconds: float = 3.0
    object_storage_enabled: bool = False
    object_storage_endpoint: str = "http://minio:9000"
    object_storage_access_key: str = ""
    object_storage_secret_key: str = ""
    object_storage_bucket: str = "mission-audit-artifacts"
    object_storage_prefix: str = "missions"
    object_storage_region: str = "us-east-1"
    object_storage_timeout_seconds: float = 5.0
    object_storage_retention_days: int = 90
    object_storage_legal_hold_on_fail: bool = True
    object_storage_force_path_style: bool = True
    object_storage_require_tls: bool = False
    langgraph_enabled: bool = False
    langgraph_fail_open: bool = True
    langgraph_checkpointer: str = "none"
    langgraph_thread_prefix: str = "mission"
    langgraph_checkpointer_postgres_url: str = ""
    langgraph_checkpointer_setup: bool = False
    langgraph_checkpoint_namespace: str = ""
    mission_flow_v2_enabled: bool = False

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
        qdrant_url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY", ""),
        neo4j_url=os.getenv("NEO4J_URL", "http://neo4j:7474"),
        object_storage_endpoint=os.getenv("OBJECT_STORAGE_ENDPOINT", "http://minio:9000"),
        object_storage_access_key=os.getenv("OBJECT_STORAGE_ACCESS_KEY", ""),
        object_storage_secret_key=os.getenv("OBJECT_STORAGE_SECRET_KEY", ""),
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
        qdrant_enabled=_as_bool(os.getenv("QDRANT_ENABLED", "true"), True)
        and bool(os.getenv("QDRANT_URL", "http://qdrant:6333").strip()),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "mission_knowledge").strip()
        or "mission_knowledge",
        qdrant_vector_size=max(8, int(os.getenv("QDRANT_VECTOR_SIZE", "64"))),
        qdrant_timeout_seconds=max(0.5, float(os.getenv("QDRANT_TIMEOUT_SECONDS", "3.0"))),
        neo4j_enabled=_as_bool(os.getenv("NEO4J_ENABLED", "false"), False)
        and bool(os.getenv("NEO4J_URL", "http://neo4j:7474").strip()),
        neo4j_username=os.getenv("NEO4J_USERNAME", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j").strip() or "neo4j",
        neo4j_timeout_seconds=max(0.5, float(os.getenv("NEO4J_TIMEOUT_SECONDS", "3.0"))),
        object_storage_enabled=_as_bool(os.getenv("OBJECT_STORAGE_ENABLED", "false"), False)
        and bool(os.getenv("OBJECT_STORAGE_ENDPOINT", "http://minio:9000").strip()),
        object_storage_bucket=os.getenv("OBJECT_STORAGE_BUCKET", "mission-audit-artifacts").strip()
        or "mission-audit-artifacts",
        object_storage_prefix=os.getenv("OBJECT_STORAGE_PREFIX", "missions").strip() or "missions",
        object_storage_region=os.getenv("OBJECT_STORAGE_REGION", "us-east-1").strip()
        or "us-east-1",
        object_storage_timeout_seconds=max(
            1.0, float(os.getenv("OBJECT_STORAGE_TIMEOUT_SECONDS", "5.0"))
        ),
        object_storage_retention_days=max(
            1, int(os.getenv("OBJECT_STORAGE_RETENTION_DAYS", "90"))
        ),
        object_storage_legal_hold_on_fail=_as_bool(
            os.getenv("OBJECT_STORAGE_LEGAL_HOLD_ON_FAIL", "true"), True
        ),
        object_storage_force_path_style=_as_bool(
            os.getenv("OBJECT_STORAGE_FORCE_PATH_STYLE", "true"), True
        ),
        object_storage_require_tls=_as_bool(
            os.getenv("OBJECT_STORAGE_REQUIRE_TLS", "false"), False
        ),
        langgraph_enabled=_as_bool(os.getenv("LANGGRAPH_ENABLED", "false"), False),
        langgraph_fail_open=_as_bool(os.getenv("LANGGRAPH_FAIL_OPEN", "true"), True),
        langgraph_checkpointer=os.getenv("LANGGRAPH_CHECKPOINTER", "none").strip().lower()
        or "none",
        langgraph_thread_prefix=os.getenv("LANGGRAPH_THREAD_PREFIX", "mission").strip()
        or "mission",
        langgraph_checkpointer_postgres_url=os.getenv(
            "LANGGRAPH_CHECKPOINTER_POSTGRES_URL", ""
        ).strip(),
        langgraph_checkpointer_setup=_as_bool(
            os.getenv("LANGGRAPH_CHECKPOINTER_SETUP", "false"), False
        ),
        langgraph_checkpoint_namespace=os.getenv("LANGGRAPH_CHECKPOINT_NAMESPACE", "").strip(),
        mission_flow_v2_enabled=_as_bool(
            os.getenv("MISSION_FLOW_V2_ENABLED", "false"), False
        ),
    )
