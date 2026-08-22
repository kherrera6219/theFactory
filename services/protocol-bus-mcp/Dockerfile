# Stage 1: install Python dependencies into a virtual environment
FROM python:3.11-slim-bookworm@sha256:721dc13fd1be0a771e54b72097634291d628d0007dee9da777e2ce676a9c998f AS builder
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
RUN pip install --no-cache-dir --upgrade "pip>=26.1.2" "setuptools>=83.0.0"
COPY services/protocol-bus-mcp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: lean runtime image — no pip, no build artefacts
FROM python:3.11-slim-bookworm@sha256:721dc13fd1be0a771e54b72097634291d628d0007dee9da777e2ce676a9c998f
WORKDIR /app
ENV PATH=/opt/venv/bin:$PATH
COPY --from=builder /opt/venv /opt/venv
COPY services/protocol-bus-mcp /app
COPY shared_runtime /app/shared_runtime
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends ca-certificates liblzma5 \
    && python -m pip install --no-cache-dir --upgrade "pip>=26.1.2" "setuptools>=83.0.0" \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8090/readyz')" || exit 1
CMD ["uvicorn", "protocol_bus.mcp_server:app", "--host", "0.0.0.0", "--port", "8090"]
