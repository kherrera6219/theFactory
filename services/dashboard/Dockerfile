FROM python:3.11-slim
WORKDIR /app
COPY services/dashboard/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/dashboard /app
CMD ["uvicorn", "dashboard.main:app", "--host", "0.0.0.0", "--port", "8080"]
