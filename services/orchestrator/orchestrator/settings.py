from __future__ import annotations

import logging
import os
import socket
from dataclasses import dataclass
from pathlib import Path

from shared_runtime.agent_keys import configured_agent_service_key_map

from .agent_registry import AGENT_REGISTRY

TRUTHY_VALUES = {"1", "true", "yes", "on"}
_AGENT_REGISTRY_IDS = {agent.agent_id for agent in AGENT_REGISTRY}


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
    qdrant_vector_size: int = 256
    qdrant_timeout_seconds: float = 3.0
    milvus_uri: str = "http://milvus:19530"
    milvus_token: str = ""
    milvus_enabled: bool = True
    milvus_collection: str = "mission_knowledge"
    milvus_vector_size: int = 64
    milvus_timeout_seconds: float = 3.0
    knowledge_embedding_provider: str = "gemini"
    # Empty by default so knowledge_embeddings._default_model() selects the
    # correct per-provider model (gemini → gemini-embedding-001,
    # openai → text-embedding-3-small). An explicit env var still overrides.
    knowledge_embedding_model: str = ""
    # Dedicated embedding API key. When set, overrides GEMINI_API_KEY /
    # OPENAI_API_KEY for embedding calls, allowing separate quota management.
    # Empty means fall back to the global provider key.
    knowledge_embedding_api_key: str = ""
    knowledge_embedding_timeout_seconds: float = 10.0
    knowledge_refresh_enabled: bool = True
    neo4j_url: str = "http://neo4j:7474"
    neo4j_enabled: bool = True
    neo4j_username: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"
    neo4j_timeout_seconds: float = 3.0
    object_storage_enabled: bool = True
    object_storage_endpoint: str = "http://minio:9000"
    object_storage_access_key: str = ""
    object_storage_secret_key: str = ""
    object_storage_bucket: str = "mission-audit-artifacts"
    object_storage_prefix: str = "missions"
    object_storage_region: str = "us-east-1"
    object_storage_timeout_seconds: float = 5.0
    object_storage_retention_days: int = 90
    object_storage_size_threshold_bytes: int = 524288  # 512 KB — artifacts above this go to S3
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
    mission_flow_v2_enabled: bool = True
    mission_equivalence_enforcement_enabled: bool = False
    mission_equivalence_python_execution_enabled: bool = False
    # Defaults to True (was False): a mission with a required security-
    # compliance check failure (e.g. a hard-coded secret) must not silently
    # proceed to delivery. Operators can still opt out for staged rollouts.
    mission_security_compliance_enforcement_enabled: bool = True
    testdata_agent_enabled: bool = False
    rqca_agent_enabled: bool = False
    # Defaults to True (was False): a mission that fails its RQCA runtime QC
    # check must not silently proceed to delivery. Operators can still opt
    # out for staged rollouts.
    rqca_enforcement_enabled: bool = True
    # Per-language template for the command RQCA runs to determine pass/fail.
    # "{filename}" is the artifact name and "{test_filename}" is the test file
    # (test_<filename>). Defaults run the language's test framework against the
    # test file when one was generated rather than just executing the artifact.
    rqca_test_command_template: str = ""
    docker_bin: str = "docker"
    depabs_execution_enabled: bool = False
    port_two_phase_enabled: bool = False
    llm_safety_block_enabled: bool = False
    knowledge_refresh_interval_seconds: int = 3600
    agent_scaling_enabled: bool = False
    agent_scaling_max_instances: int = 4
    agent_scaling_items_per_instance: int = 3
    intake_dlq_stream: str = "factory:dlq:intake-stream"
    intake_dlq_max_len: int = 1000
    stale_consumer_idle_ms: int = 300_000
    stale_consumer_reap_interval_seconds: int = 3600
    # topology_mode describes which compose profile is active:
    #   "condensed"       — default; shared pod workers, synthesized non-pod heartbeats
    #   "dedicated"       — dedicated-agents profile; one container per pod manager
    #   "full-dedicated"  — full-dedicated-agents profile; one container per language specialist
    topology_mode: str = "condensed"
    # Protocol Bus MCP — typed protocol-lane router (:8090 in-network, :8102 host).
    # protocol_bus_api_key is the shared MCP_API_KEY the bus validates via
    # hmac.compare_digest; producers also send X-Agent-Id matching their sender.
    protocol_bus_url: str = "http://protocol-bus-mcp:8090"
    protocol_bus_api_key: str = ""
    protocol_bus_consumer_enabled: bool = True
    event_driven_control_plane_enabled: bool = False
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10
    # Direct-to-Postgres URL used only for schema migrations, which take a
    # session-level advisory lock and so cannot run through PgBouncer's
    # transaction pooling. Empty falls back to ``postgres_url`` (see the
    # ``migration_postgres_url`` property) so non-pooled setups are unaffected.
    migration_postgres_url_override: str = ""
    audit_retention_days: int = 90
    logicnode_schema_path: Path = Path("schemas/logicnode.schema.json")
    delivery_dir: Path = Path("output")
    environment: str = "development"
    # "shared" — agents without a dedicated key fall back to the shared service key.
    # "strict" — each agent must have its own key (no shared-identity fallback).
    agent_service_key_mode: str = "shared"

    @property
    def migration_postgres_url(self) -> str:
        """Connection URL for schema migrations (Postgres directly, no bouncer)."""
        return self.migration_postgres_url_override.strip() or self.postgres_url

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

        for key in self.agent_service_api_keys.values():
            if key:
                mapping[key] = {"worker", "mutate", "internal", "read"}

        return mapping

    @property
    def agent_service_api_keys(self) -> dict[str, str]:
        return configured_agent_service_key_map(
            os.getenv("AGENT_SERVICE_API_KEYS", ""),
            allowed_agent_ids=_AGENT_REGISTRY_IDS,
        )

    def topic_for_state(self, state_value: str) -> str:
        if state_value == "RUNNING":
            return os.getenv("STATE_TOPIC_RUNNING", "fusion.requested")
        if state_value == "VERIFIED":
            return os.getenv("STATE_TOPIC_VERIFIED", "artifact.rir.verified")
        if state_value == "COMPLETE":
            return os.getenv("STATE_TOPIC_COMPLETE", "mission.state.complete")
        if state_value == "FAILED":
            return os.getenv("STATE_TOPIC_FAILED", "incident.runtime.errorlog")
        return os.getenv("STATE_TOPIC_QUEUED", self.intake_topic)


def _as_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in TRUTHY_VALUES


def load_settings() -> Settings:
    if Path("/app/schemas").exists() and Path("/app/protocol").exists():
        repo_root = Path("/app")
    else:
        repo_root = Path(__file__).resolve().parents[3]

    admin_key = os.getenv("ORCHESTRATOR_ADMIN_API_KEY", "")
    readonly_key = os.getenv("ORCHESTRATOR_READONLY_API_KEY", "")
    internal_key = os.getenv("INTERNAL_SERVICE_API_KEY", "")
    extra_keys = os.getenv("ORCHESTRATOR_API_KEYS", "")
    environment = os.getenv("ENVIRONMENT", "development").strip().lower() or "development"
    is_production = environment == "production"
    agent_service_key_mode = (
        os.getenv("AGENT_SERVICE_KEY_MODE", "shared").strip().lower() or "shared"
    )
    if is_production and agent_service_key_mode == "shared":
        logging.getLogger(__name__).warning(
            "SECURITY: agent_service_key_mode=shared in production — all agents "
            "share one identity. Set AGENT_SERVICE_KEY_MODE=strict so each agent "
            "authenticates with its own dedicated service key."
        )
    if is_production:
        if not any([admin_key, readonly_key, internal_key, extra_keys.strip()]):
            raise RuntimeError(
                "ENVIRONMENT=production requires at least one of "
                "ORCHESTRATOR_ADMIN_API_KEY, ORCHESTRATOR_READONLY_API_KEY, "
                "INTERNAL_SERVICE_API_KEY, or ORCHESTRATOR_API_KEYS to be set"
            )

    rqca_enforcement_enabled = _as_bool(os.getenv("RQCA_ENFORCEMENT_ENABLED", "true"), True)
    if is_production and not rqca_enforcement_enabled:
        raise RuntimeError(
            "ENVIRONMENT=production requires RQCA_ENFORCEMENT_ENABLED=true — a "
            "mission that fails its RQCA runtime QC check must not silently "
            "proceed to delivery in production."
        )

    object_storage_access_key = os.getenv("OBJECT_STORAGE_ACCESS_KEY", "")
    object_storage_secret_key = os.getenv("OBJECT_STORAGE_SECRET_KEY", "")
    if is_production and (
        object_storage_access_key == "minioadmin" or object_storage_secret_key == "minioadmin123"
    ):
        raise RuntimeError(
            "ENVIRONMENT=production must not use the default MinIO credentials "
            "(minioadmin/minioadmin123) — set OBJECT_STORAGE_ACCESS_KEY and "
            "OBJECT_STORAGE_SECRET_KEY to real production credentials."
        )

    # langgraph_fail_open lets the LangGraph engine fall back to the legacy path
    # on error. Convenient in development, but in production a silent fallback can
    # mask a broken graph, so default to fail-closed there. An explicit env var
    # still wins in either direction.
    _langgraph_fail_open_default = "false" if is_production else "true"
    _langgraph_fail_open = _as_bool(
        os.getenv("LANGGRAPH_FAIL_OPEN", _langgraph_fail_open_default),
        not is_production,
    )
    if is_production and _langgraph_fail_open:
        logging.getLogger(__name__).warning(
            "LANGGRAPH_FAIL_OPEN=true in production — LangGraph errors will "
            "silently fall back to the legacy engine instead of failing the "
            "mission. Set LANGGRAPH_FAIL_OPEN=false for fail-closed behavior."
        )

    return Settings(
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        postgres_url=os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@postgres:5432/ulr"),
        # Migrations take a session-level advisory lock and must run on a stable
        # session. PgBouncer transaction pooling reassigns the backend (and runs
        # DISCARD ALL) between statements, silently dropping that lock — so point
        # migrations directly at Postgres. Empty falls back to postgres_url.
        migration_postgres_url_override=os.getenv("MIGRATION_POSTGRES_URL", "").strip(),
        db_pool_min_size=max(0, int(os.getenv("DB_POOL_MIN_SIZE", "2"))),
        db_pool_max_size=max(1, int(os.getenv("DB_POOL_MAX_SIZE", "10"))),
        audit_retention_days=max(1, int(os.getenv("AUDIT_RETENTION_DAYS", "90"))),
        qdrant_url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY", ""),
        milvus_uri=os.getenv("MILVUS_URI", "http://milvus:19530"),
        milvus_token=os.getenv("MILVUS_TOKEN", ""),
        neo4j_url=os.getenv("NEO4J_URL", "http://neo4j:7474"),
        object_storage_endpoint=os.getenv("OBJECT_STORAGE_ENDPOINT", "http://minio:9000"),
        object_storage_access_key=object_storage_access_key,
        object_storage_secret_key=object_storage_secret_key,
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
        logicnode_schema_path=Path(
            os.getenv(
                "LOGICNODE_SCHEMA_PATH", str(repo_root / "schemas" / "logicnode.schema.json")
            )
        ),
        topics_path=Path(os.getenv("TOPICS_PATH", str(repo_root / "protocol" / "topics.yaml"))),
        delivery_dir=Path(os.getenv("DELIVERY_DIR", str(repo_root / "output"))),
        admin_api_key=admin_key,
        internal_service_api_key=internal_key,
        readonly_api_key=readonly_key,
        extra_api_keys=extra_keys,
        qdrant_enabled=_as_bool(os.getenv("QDRANT_ENABLED", "true"), True)
        and bool(os.getenv("QDRANT_URL", "http://qdrant:6333").strip()),
        qdrant_collection=os.getenv("QDRANT_COLLECTION", "mission_knowledge").strip()
        or "mission_knowledge",
        qdrant_vector_size=max(8, int(os.getenv("QDRANT_VECTOR_SIZE", "256"))),
        qdrant_timeout_seconds=max(0.5, float(os.getenv("QDRANT_TIMEOUT_SECONDS", "3.0"))),
        milvus_enabled=_as_bool(os.getenv("MILVUS_ENABLED", "true"), True)
        and bool(os.getenv("MILVUS_URI", "http://milvus:19530").strip()),
        milvus_collection=os.getenv("MILVUS_COLLECTION", "mission_knowledge").strip()
        or "mission_knowledge",
        milvus_vector_size=max(8, int(os.getenv("MILVUS_VECTOR_SIZE", "64"))),
        milvus_timeout_seconds=max(0.5, float(os.getenv("MILVUS_TIMEOUT_SECONDS", "3.0"))),
        knowledge_embedding_provider=os.getenv(
            "KNOWLEDGE_EMBEDDING_PROVIDER", "gemini"
        ).strip().lower()
        or "gemini",
        knowledge_embedding_model=os.getenv(
            "KNOWLEDGE_EMBEDDING_MODEL", ""
        ).strip(),
        knowledge_embedding_api_key=os.getenv("KNOWLEDGE_EMBEDDING_API_KEY", "").strip(),
        knowledge_embedding_timeout_seconds=max(
            1.0, float(os.getenv("KNOWLEDGE_EMBEDDING_TIMEOUT_SECONDS", "10.0"))
        ),
        knowledge_refresh_enabled=_as_bool(
            os.getenv("KNOWLEDGE_REFRESH_ENABLED", "true"), True
        ),
        neo4j_enabled=_as_bool(os.getenv("NEO4J_ENABLED", "true"), True)
        and bool(os.getenv("NEO4J_URL", "http://neo4j:7474").strip()),
        neo4j_username=os.getenv("NEO4J_USERNAME", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
        neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j").strip() or "neo4j",
        neo4j_timeout_seconds=max(0.5, float(os.getenv("NEO4J_TIMEOUT_SECONDS", "3.0"))),
        object_storage_enabled=_as_bool(os.getenv("OBJECT_STORAGE_ENABLED", "true"), True)
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
        object_storage_size_threshold_bytes=max(
            4096, int(os.getenv("OBJECT_STORAGE_SIZE_THRESHOLD_BYTES", "524288"))
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
        langgraph_fail_open=_langgraph_fail_open,
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
            os.getenv("MISSION_FLOW_V2_ENABLED", "true"), True
        ),
        mission_equivalence_enforcement_enabled=_as_bool(
            os.getenv("MISSION_EQUIVALENCE_ENFORCEMENT_ENABLED", "false"), False
        ),
        mission_equivalence_python_execution_enabled=_as_bool(
            os.getenv("MISSION_EQUIVALENCE_PYTHON_EXECUTION_ENABLED", "false"), False
        ),
        mission_security_compliance_enforcement_enabled=_as_bool(
            os.getenv("MISSION_SECURITY_COMPLIANCE_ENFORCEMENT_ENABLED", "true"), True
        ),
        testdata_agent_enabled=_as_bool(os.getenv("TESTDATA_AGENT_ENABLED", "false"), False),
        rqca_agent_enabled=_as_bool(os.getenv("RQCA_AGENT_ENABLED", "false"), False),
        rqca_enforcement_enabled=rqca_enforcement_enabled,
        rqca_test_command_template=os.getenv("RQCA_TEST_COMMAND_TEMPLATE", "").strip(),
        docker_bin=os.getenv("DOCKER_BIN", "docker").strip() or "docker",
        depabs_execution_enabled=_as_bool(
            os.getenv("DEPABS_EXECUTION_ENABLED", "false"), False
        ),
        port_two_phase_enabled=_as_bool(
            os.getenv("PORT_TWO_PHASE_ENABLED", "false"), False
        ),
        llm_safety_block_enabled=_as_bool(
            os.getenv("LLM_SAFETY_BLOCK_ENABLED", "false"), False
        ),
        knowledge_refresh_interval_seconds=max(
            10, int(os.getenv("KNOWLEDGE_REFRESH_INTERVAL_SECONDS", "3600"))
        ),
        agent_scaling_enabled=_as_bool(
            os.getenv("AGENT_SCALING_ENABLED", "false"), False
        ),
        agent_scaling_max_instances=max(
            1, min(8, int(os.getenv("AGENT_SCALING_MAX_INSTANCES", "4")))
        ),
        agent_scaling_items_per_instance=max(
            1, int(os.getenv("AGENT_SCALING_ITEMS_PER_INSTANCE", "3"))
        ),
        intake_dlq_stream=os.getenv("INTAKE_DLQ_STREAM", "factory:dlq:intake-stream").strip()
        or "factory:dlq:intake-stream",
        intake_dlq_max_len=max(100, int(os.getenv("INTAKE_DLQ_MAX_LEN", "1000"))),
        stale_consumer_idle_ms=max(
            1000, int(os.getenv("STALE_CONSUMER_IDLE_MS", "300000"))
        ),
        stale_consumer_reap_interval_seconds=max(
            60, int(os.getenv("STALE_CONSUMER_REAP_INTERVAL_SECONDS", "3600"))
        ),
        topology_mode=os.getenv("TOPOLOGY_MODE", "condensed").strip().lower() or "condensed",
        # In-network the bus listens on :8090 (the :8102 in compose is the host
        # port mapping). PROTOCOL_BUS_API_KEY is the canonical name; MCP_API_KEY
        # is accepted as a backward-compatible alias since the bus validates that
        # single shared key.
        protocol_bus_url=os.getenv(
            "PROTOCOL_BUS_URL", "http://protocol-bus-mcp:8090"
        ).strip()
        or "http://protocol-bus-mcp:8090",
        protocol_bus_api_key=(
            os.getenv("PROTOCOL_BUS_API_KEY", "").strip()
            or os.getenv("MCP_API_KEY", "").strip()
        ),
        protocol_bus_consumer_enabled=_as_bool(
            os.getenv("PROTOCOL_BUS_CONSUMER_ENABLED", "true"), True
        ),
        event_driven_control_plane_enabled=_as_bool(
            os.getenv("EVENT_DRIVEN_CONTROL_PLANE_ENABLED", "false"), False
        ),
        environment=environment,
        agent_service_key_mode=agent_service_key_mode,
    )
