import logging
import os
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .tracing import configure_tracing

LOGGER = logging.getLogger(__name__)

API_GATEWAY_URL = os.getenv("API_GATEWAY_URL", "http://api-gateway:8000")

app = FastAPI(title="HolyGrail Dashboard", version="0.1.0")
configure_tracing(app, service_name="dashboard")


@app.get("/health")
def health() -> dict[str, bool | str]:
    return {"ok": True, "service": "dashboard"}


@app.get("/snapshot")
async def snapshot() -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            response = await client.get(f"{API_GATEWAY_URL}/health")
        return {
            "ok": True,
            "api_gateway_status": response.status_code,
            "api_gateway": response.json(),
        }
    except Exception as exc:
        LOGGER.warning("dashboard snapshot failed: %s", exc)
        return {"ok": False, "error": f"snapshot unavailable: {exc}"}


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """<!doctype html>
<html>
  <head>
    <meta charset='utf-8'/>
    <title>HolyGrail Dashboard</title>
    <style>
      body {
        font-family: Segoe UI, sans-serif;
        margin: 40px;
        background: #f3f6fb;
        color: #1f2937;
      }
      .card {
        background: #fff;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.08);
        max-width: 840px;
      }
      code { background: #eef2ff; padding: 2px 5px; border-radius: 4px; }
      button {
        border: 0;
        background: #2563eb;
        color: #fff;
        padding: 9px 14px;
        border-radius: 8px;
        cursor: pointer;
      }
      pre {
        background: #111827;
        color: #f9fafb;
        padding: 12px;
        border-radius: 8px;
        overflow-x: auto;
      }
    </style>
  </head>
  <body>
    <div class='card'>
      <h1>HolyGrail Operations Dashboard</h1>
      <p>
        This is the lightweight operations shell. The primary Mission Control UI lives in
        <code>apps/mission-control</code>.
      </p>
      <button onclick='loadSnapshot()'>Load API Snapshot</button>
      <pre id='out'>{}</pre>
    </div>
    <script>
      async function loadSnapshot() {
        const res = await fetch('/snapshot');
        const data = await res.json();
        document.getElementById('out').textContent = JSON.stringify(data, null, 2);
      }
    </script>
  </body>
</html>"""
