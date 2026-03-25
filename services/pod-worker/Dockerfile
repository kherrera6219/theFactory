FROM python:3.11-slim
WORKDIR /app
COPY services/pod-worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/pod-worker /app
COPY shared_runtime /app/shared_runtime
COPY services/orchestrator/orchestrator /app/orchestrator
COPY schemas /app/schemas
COPY protocol /app/protocol
RUN useradd --system --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8201/health')" || exit 1
CMD ["uvicorn", "pod_worker.main:app", "--host", "0.0.0.0", "--port", "8201"]
