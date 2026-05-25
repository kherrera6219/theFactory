import json
from pathlib import Path


def main():
    schemas = list(Path("schemas").glob("*.schema.json"))
    if not schemas:
        raise SystemExit("No schemas found in /schemas")

    for p in schemas:
        json.loads(p.read_text(encoding="utf-8"))
        print(f"OK: {p}")

    print("All schemas are valid JSON (syntax).")
    print("Tip: add jsonschema validation against sample artifacts in /examples.")

if __name__ == "__main__":
    main()
