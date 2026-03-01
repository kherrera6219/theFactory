from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


def _load_app(module_path: str, app_name: str = "app"):
    module = importlib.import_module(module_path)
    return getattr(module, app_name)


def _write_openapi(app, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "services" / "api-gateway"))
    sys.path.insert(0, str(root / "services" / "orchestrator"))

    api_gateway_app = _load_app("api_gateway.main")
    orchestrator_app = _load_app("orchestrator.main")

    _write_openapi(api_gateway_app, root / "docs" / "openapi" / "api-gateway.v1.json")
    _write_openapi(orchestrator_app, root / "docs" / "openapi" / "orchestrator.v1.json")
    print("OpenAPI specs exported to docs/openapi/")


if __name__ == "__main__":
    main()
