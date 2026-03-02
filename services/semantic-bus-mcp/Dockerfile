FROM python:3.11-slim
WORKDIR /app
COPY services/semantic-bus-mcp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/semantic-bus-mcp /app
RUN useradd --system --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser
CMD ["uvicorn", "semantic_bus.mcp_server:app", "--host", "0.0.0.0", "--port", "8090"]
