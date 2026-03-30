from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="ULR Dashboard", version="0.1.0")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/", response_class=HTMLResponse)
def index():
    return """<html><body>
    <h1>Unified Logic Refinery Dashboard</h1>
    <p>Placeholder UI. Connect to Redis streams/queues to visualize state.</p>
    </body></html>"""
