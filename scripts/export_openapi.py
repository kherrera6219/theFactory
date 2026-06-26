from __future__ import annotations

import argparse
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
        _render_openapi(app),
        encoding="utf-8",
    )


def _render_openapi(app) -> str:
    return json.dumps(app.openapi(), indent=2, sort_keys=True)


def _check_openapi(app, output_path: Path) -> str | None:
    expected = _render_openapi(app)
    actual = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
    if actual == expected:
        return None
    return str(output_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export committed OpenAPI snapshots.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if committed OpenAPI snapshots differ from the current apps",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "services" / "api-gateway"))
    sys.path.insert(0, str(root / "services" / "orchestrator"))

    api_gateway_app = _load_app("api_gateway.main")
    orchestrator_app = _load_app("orchestrator.main")
    targets = [
        (api_gateway_app, root / "docs" / "openapi" / "api-gateway.v1.json"),
        (orchestrator_app, root / "docs" / "openapi" / "orchestrator.v1.json"),
    ]

    if args.check:
        drifted: list[str] = []
        for app, path in targets:
            drifted_path = _check_openapi(app, path)
            if drifted_path is not None:
                drifted.append(drifted_path)
        if drifted:
            print("OpenAPI specs are stale:")
            for path in drifted:
                print(f" - {path}")
            print("Run `python scripts/export_openapi.py` and commit the updated specs.")
            return 1
        print("OpenAPI specs are current")
        return 0

    for app, path in targets:
        _write_openapi(app, path)
    print("OpenAPI specs exported to docs/openapi/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
