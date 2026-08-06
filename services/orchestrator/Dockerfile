# Stage 1: install Python dependencies into a virtual environment
FROM python:3.11-slim-bookworm@sha256:721dc13fd1be0a771e54b72097634291d628d0007dee9da777e2ce676a9c998f AS builder
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
COPY services/orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: lean runtime image — no pip, no build artefacts
FROM python:3.11-slim-bookworm@sha256:721dc13fd1be0a771e54b72097634291d628d0007dee9da777e2ce676a9c998f
WORKDIR /app
ENV PATH=/opt/venv/bin:$PATH
COPY --from=builder /opt/venv /opt/venv
COPY services/orchestrator /app
COPY shared_runtime /app/shared_runtime
COPY schemas /app/schemas
COPY protocol /app/protocol
# aim_generator.py imports pod_worker.language_extractor for source-code
# concept/import extraction (AIM generation for ANALYZE_ONLY/PORT/
# DEBUG_REPAIR/SECURITY_HARDEN/REDUCE_DEPENDENCIES missions). Only the
# extractor package is needed here, not pod-worker's own service entrypoint
# or its requirements — the extractor modules have no external dependencies
# beyond the standard library, with optional AST libraries (esprima,
# javalang) that gracefully degrade to regex-only extraction when absent.
COPY services/pod-worker/pod_worker /app/pod_worker
# RQCA runtime QC and behavioural-equivalence verification execute generated
# code inside a hardened, throwaway SIBLING container (see sandbox_exec.py).
# Only the Docker *client* belongs here -- the daemon stays on the host and is
# reached through a socket mounted by compose. The compose plugin is required by
# RQCA's multi-container path. Copied from the official CLI image rather than
# installed via apt, so no package repository or GPG key is added to this image.
COPY --from=docker:27-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker:27-cli \
     /usr/local/libexec/docker/cli-plugins/docker-compose \
     /usr/local/libexec/docker/cli-plugins/docker-compose
RUN useradd --system --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser
# Liveness probe: /health returns 200 whenever the process is serving, even if
# an optional service (Qdrant/Neo4j/object storage) is unavailable. Container
# health must reflect process liveness, not full readiness — /readyz (which
# also gates on optional services and consumer startup) is used by orchestration
# readiness probes, not as the restart/dependency signal.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1
CMD ["uvicorn", "orchestrator.main:app", "--host", "0.0.0.0", "--port", "8001"]
