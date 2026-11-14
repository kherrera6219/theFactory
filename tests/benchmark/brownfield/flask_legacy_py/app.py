from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from flask import Flask, jsonify, request


def calculate_order_total(unit_price_cents: int, quantity: int, tax_bps: int = 825) -> int:
    """Compute total cents including tax in basis points (legacy integer arithmetic)."""
    if unit_price_cents < 0 or quantity <= 0:
        raise ValueError("unit_price_cents must be >= 0 and quantity > 0")
    if tax_bps < 0:
        raise ValueError("tax_bps must be >= 0")
    subtotal = unit_price_cents * quantity
    tax = (subtotal * tax_bps + 5000) // 10000
    return subtotal + tax


@dataclass
class InMemoryOrderStore:
    """Minimal in-memory order store used by legacy handlers."""

    items: dict[int, dict[str, Any]] = field(default_factory=dict)
    next_id: int = 1

    def list_items(self) -> list[dict[str, Any]]:
        return [dict(self.items[k]) for k in sorted(self.items)]

    def add_item(self, name: str, unit_price_cents: int, quantity: int) -> dict[str, Any]:
        total_cents = calculate_order_total(unit_price_cents, quantity)
        record = {
            "id": self.next_id,
            "name": name,
            "unit_price_cents": unit_price_cents,
            "quantity": quantity,
            "total_cents": total_cents,
            "status": "pending",
        }
        self.items[self.next_id] = record
        self.next_id += 1
        return dict(record)

    def get_item(self, item_id: int) -> dict[str, Any] | None:
        record = self.items.get(item_id)
        return dict(record) if record is not None else None


def create_app(store: InMemoryOrderStore | None = None) -> Flask:
    """Create the legacy Flask orders application."""
    app = Flask(__name__)
    backing_store = store or InMemoryOrderStore()

    @app.get("/health")
    def health() -> tuple[Any, int]:
        return jsonify({"status": "ok", "count": len(backing_store.items)}), 200

    @app.get("/items")
    def list_items() -> tuple[Any, int]:
        items = backing_store.list_items()
        return jsonify({"items": items, "total": len(items)}), 200

    @app.post("/items")
    def create_item() -> tuple[Any, int]:
        payload = request.get_json(silent=True) or {}
        name = str(payload.get("name") or "").strip()
        if not name:
            return jsonify({"error": "name is required"}), 400
        try:
            unit_price_cents = int(payload.get("unit_price_cents", 0))
            quantity = int(payload.get("quantity", 0))
            record = backing_store.add_item(name, unit_price_cents, quantity)
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(record), 201

    @app.get("/items/<int:item_id>")
    def get_item(item_id: int) -> tuple[Any, int]:
        record = backing_store.get_item(item_id)
        if record is None:
            return jsonify({"error": "not found"}), 404
        return jsonify(record), 200

    return app


app = create_app()
