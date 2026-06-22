import json
from pathlib import Path

from jsonschema import Draft202012Validator, RefResolver

ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_logicnode_example_matches_schema() -> None:
    schema = _read_json(ROOT / "schemas" / "logicnode.schema.json")
    example = _read_json(ROOT / "examples" / "logicnode.example.json")

    errors = sorted(
        Draft202012Validator(schema).iter_errors(example),
        key=lambda error: list(error.path),
    )
    assert errors == []


def test_rir_examples_match_schemas() -> None:
    fn_schema = _read_json(ROOT / "schemas" / "rir.fn.schema.json")
    module_schema = _read_json(ROOT / "schemas" / "rir.module.schema.json")
    fn_example = _read_json(ROOT / "examples" / "rir.fn.example.json")
    module_example = _read_json(ROOT / "examples" / "rir.module.example.json")

    resolver = RefResolver.from_schema(
        module_schema, store={"rir.fn.schema.json": fn_schema}
    )
    module_errors = sorted(
        Draft202012Validator(module_schema, resolver=resolver).iter_errors(
            module_example
        ),
        key=lambda error: list(error.path),
    )
    fn_errors = sorted(
        Draft202012Validator(fn_schema).iter_errors(fn_example),
        key=lambda error: list(error.path),
    )

    assert module_errors == []
    assert fn_errors == []
