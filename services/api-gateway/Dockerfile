FROM python:3.11-slim
WORKDIR /app
COPY services/api-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/api-gateway /app
COPY schemas /app/schemas
COPY protocol /app/protocol
RUN useradd --system --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser
CMD ["uvicorn", "api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
