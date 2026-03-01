FROM python:3.11-slim
WORKDIR /app
COPY services/pod-worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/pod-worker /app
COPY schemas /app/schemas
COPY protocol /app/protocol
CMD ["uvicorn", "pod_worker.main:app", "--host", "0.0.0.0", "--port", "8201"]
