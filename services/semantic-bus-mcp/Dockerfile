FROM python:3.11-slim
WORKDIR /app
COPY services/semantic-bus-mcp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/semantic-bus-mcp /app
RUN useradd --system --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8090/health')" || exit 1
CMD ["uvicorn", "semantic_bus.mcp_server:app", "--host", "0.0.0.0", "--port", "8090"]
