from fastapi import FastAPI

app = FastAPI(title="Unified Logic Refinery Orchestrator", version="0.1.0")

@app.get("/health")
def health():
    return {"ok": True}

# TODO:
# - Implement state machine (INTAKE -> DEPLOY)
# - Subscribe/publish to semantic bus topics
# - Read/write registry + ledger
