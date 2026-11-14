from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_app_module():
    path = Path(__file__).resolve().parent / "app.py"
    spec = importlib.util.spec_from_file_location("flask_legacy_app", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_calculate_order_total_rounding() -> None:
    mod = _load_app_module()
    assert mod.calculate_order_total(1000, 2, tax_bps=825) == 2165


def test_health_and_order_crud() -> None:
    mod = _load_app_module()
    app = mod.create_app()
    client = app.test_client()

    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.get_json() == {"status": "ok", "count": 0}

    bad_resp = client.post("/items", json={"name": "", "unit_price_cents": 100, "quantity": 1})
    assert bad_resp.status_code == 400

    create_resp = client.post(
        "/items",
        json={"name": "Widget", "unit_price_cents": 1500, "quantity": 2},
    )
    assert create_resp.status_code == 201
    created = create_resp.get_json()
    assert created["id"] == 1
    assert created["total_cents"] == 3248

    list_resp = client.get("/items")
    assert list_resp.status_code == 200
    assert list_resp.get_json()["total"] == 1

    missing_resp = client.get("/items/999")
    assert missing_resp.status_code == 404
