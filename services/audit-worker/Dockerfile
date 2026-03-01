FROM python:3.11-slim
WORKDIR /app
COPY services/audit-worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/audit-worker /app
COPY schemas /app/schemas
COPY protocol /app/protocol
CMD ["uvicorn", "audit_worker.main:app", "--host", "0.0.0.0", "--port", "8202"]
