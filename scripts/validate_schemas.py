import json
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    schema_dir = repo_root / "schemas"
    schemas = sorted(schema_dir.glob("*.schema.json"))
    if not schemas:
        raise SystemExit(f"No schemas found in {schema_dir}")

    for schema_path in schemas:
        json.loads(schema_path.read_text(encoding="utf-8"))
        print(f"OK: {schema_path.relative_to(repo_root)}")

    print("All schemas are valid JSON (syntax).")
    print("Tip: add jsonschema validation against sample artifacts in /examples.")


if __name__ == "__main__":
    main()
