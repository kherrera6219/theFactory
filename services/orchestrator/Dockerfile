FROM python:3.11-slim
WORKDIR /app
COPY services/orchestrator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/orchestrator /app
COPY schemas /app/schemas
COPY protocol /app/protocol
RUN useradd --system --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser
CMD ["uvicorn", "orchestrator.main:app", "--host", "0.0.0.0", "--port", "8001"]
