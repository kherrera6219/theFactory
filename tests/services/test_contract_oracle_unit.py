"""WQ7: contract-oracle behavioural equivalence for BUILD_NEW missions.

The invariants pinned here are the ones that make the result evidence:

* the oracle never sees the implementation (``interface_for_oracle``);
* a vector the harness could not execute exactly as written is rejected, never
  repaired, and a vector with no falsifiable expectation is not accepted;
* ``passed`` requires the artifact to reproduce the contract's answer, and a
  wrong answer is ``failed`` -- a check that cannot fail is not a check;
* no model means no vectors and an honest ``skipped``, never a stub.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestrator"))

from orchestrator import contract_oracle as co  # noqa: E402
from orchestrator import equivalence_execution as ee  # noqa: E402
from orchestrator.equivalence_verifier import attach_behavioural_report  # noqa: E402

SOURCE = '''
import sys

SECRET_CONSTANT = 41

def add(a: int, b: int) -> int:
    """Return the sum of two integers."""
    return a + b + SECRET_CONSTANT - 41

def _helper(x):
    return x

def main():
    print(add(int(sys.argv[1]), int(sys.argv[2])))

if __name__ == "__main__":
    main()
'''

CRITERIA = ["add(2, 3) returns 5", "prints the sum of two command-line integers"]


def _interface(kind: str = "cli") -> dict:
    return co.interface_for_oracle(
        language="python",
        code=SOURCE,
        generated_output={"filename": "adder.py", "usage_example": "python adder.py 2 3"},
        artifact_kind=kind,
    )


# --------------------------------------------------------------------------- interface


def test_interface_exposes_signatures_but_never_the_body() -> None:
    interface = _interface()
    (fn,) = interface["callable_functions"]
    assert fn["name"] == "add"
    assert [p["name"] for p in fn["params"]] == ["a", "b"]
    assert fn["summary"] == "Return the sum of two integers."
    flattened = repr(interface)
    assert "SECRET_CONSTANT" not in flattened and "return a + b" not in flattened
    # private helpers and main() are not part of the callable interface
    assert "_helper" not in flattened


def test_interface_for_unparseable_python_offers_no_call_vectors() -> None:
    interface = co.interface_for_oracle(
        language="python", code="def broken(:", generated_output={}, artifact_kind="library"
    )
    assert interface["callable_functions"] == []
    assert not interface["supports_call_vectors"] and not interface["supports_cli_vectors"]


def test_non_python_interface_is_cli_only() -> None:
    interface = co.interface_for_oracle(
        language="go", code="package main", generated_output={}, artifact_kind="cli"
    )
    assert interface["callable_functions"] == [] and interface["supports_cli_vectors"]


def test_acceptance_criteria_merge_and_dedupe() -> None:
    metadata = {
        "feature_contract": {"acceptance_criteria": ["A", "b"]},
        "mission_contract": {"acceptance_criteria": ["B", "c", ""]},
    }
    assert co.acceptance_criteria(metadata) == ["A", "b", "c"]


# --------------------------------------------------------------------------- validation


def test_valid_call_and_cli_vectors_are_accepted() -> None:
    vectors, rejections = co.validate_vectors(
        [
            {"kind": "call", "criterion_index": 0, "function": "add", "args": [2, 3], "expected": 5},
            {
                "kind": "cli",
                "criterion_index": 1,
                "argv": ["2", "3"],
                "expected_stdout": "5",
                "stdout_match": "exact",
            },
        ],
        interface=_interface(),
        criteria=CRITERIA,
    )
    assert rejections == []
    assert [v["kind"] for v in vectors] == ["call", "cli"]
    assert vectors[0]["criterion"] == CRITERIA[0]
    assert vectors[1]["expected_exit_code"] == 0


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        ({"kind": "call", "criterion_index": 0, "function": "nope", "args": [], "expected": 1},
         "not in the interface"),
        ({"kind": "call", "criterion_index": 0, "function": "add", "args": [1], "expected": 1},
         "takes 2 argument"),
        ({"kind": "call", "criterion_index": 0, "function": "add", "args": [1, 2]},
         "missing or oversized expected"),
        ({"kind": "call", "criterion_index": 9, "function": "add", "args": [1, 2], "expected": 3},
         "does not cite"),
        ({"kind": "cli", "criterion_index": 1, "argv": ["1"]}, "no observable expectation"),
        ({"kind": "cli", "criterion_index": 1, "argv": "1 2", "expected_stdout": "3"},
         "argv must be a list"),
        ({"kind": "cli", "criterion_index": 1, "argv": [], "expected_stdout": "3",
          "stdout_match": "regex"}, "unknown stdout_match"),
        ({"kind": "shell", "criterion_index": 1}, "unknown kind"),
    ],
)
def test_unexecutable_vectors_are_rejected_not_repaired(raw: dict, reason: str) -> None:
    vectors, rejections = co.validate_vectors([raw], interface=_interface(), criteria=CRITERIA)
    assert vectors == []
    assert reason in rejections[0]


def test_cli_vectors_rejected_for_non_cli_artifacts() -> None:
    vectors, rejections = co.validate_vectors(
        [{"kind": "cli", "criterion_index": 0, "argv": [], "expected_stdout": "x"}],
        interface=_interface(kind="library"),
        criteria=CRITERIA,
    )
    assert vectors == [] and "not a command-line program" in rejections[0]


def test_nonzero_exit_expectation_counts_as_falsifiable() -> None:
    vectors, _ = co.validate_vectors(
        [{"kind": "cli", "criterion_index": 1, "argv": ["x"], "expected_exit_code": 2}],
        interface=_interface(),
        criteria=CRITERIA,
    )
    assert vectors and vectors[0]["expected_stdout"] is None


def test_vector_count_is_capped() -> None:
    raw = [
        {"kind": "call", "criterion_index": 0, "function": "add", "args": [i, i], "expected": 2 * i}
        for i in range(40)
    ]
    vectors, _ = co.validate_vectors(raw, interface=_interface(), criteria=CRITERIA)
    assert len(vectors) == co.MAX_CONTRACT_VECTORS


# --------------------------------------------------------------------------- comparison


def test_values_equal_tolerates_float_representation_only() -> None:
    assert co.values_equal(0.3, 0.1 + 0.2)
    assert not co.values_equal(0.3, 0.31)
    assert not co.values_equal(True, 1)
    assert co.values_equal([1, {"a": 2.0}], (1, {"a": 2}))
    assert not co.values_equal({"a": 1}, {"a": 1, "b": 2})


def test_stdout_matching_modes() -> None:
    assert co.stdout_matches("5", "5  \r\n", "exact")
    assert not co.stdout_matches("5", "15\n", "exact")
    assert co.stdout_matches("total: 5", "header\ntotal: 5\n", "contains")
    assert co.stdout_matches('{"a": [1, 2]}', '{"a":[1,2.0]}', "json")
    assert not co.stdout_matches('{"a": 1}', "not json", "json")


def test_cli_command_binds_args_and_stdin_to_the_program() -> None:
    command = co.cli_command(
        "go build -o /tmp/a.out /workspace/m.go && /tmp/a.out",
        ["a b", "$(rm -rf /)"],
        stdin_file="/workspace/__in__.txt",
    )
    assert command.endswith("/tmp/a.out 'a b' '$(rm -rf /)' < /workspace/__in__.txt")


# --------------------------------------------------------------------------- execution


class _FakeSandbox:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[dict] = []

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        workspace = Path(kwargs["workspace_dir"])
        self.calls[-1]["files"] = {
            p.name: p.read_text(encoding="utf-8") for p in workspace.iterdir()
        }
        stdout, exit_code, timed_out = self.responses.pop(0)
        stderr = "main.go:3: syntax error" if exit_code not in (0, 124) else ""
        return SimpleNamespace(
            stdout=stdout, stderr=stderr, exit_code=exit_code, timed_out=timed_out,
            infrastructure_error=None,
        )


def _run(monkeypatch, vectors, responses, *, language="python", code=SOURCE, deps=None):
    sandbox = _FakeSandbox(responses)
    monkeypatch.setattr(ee, "run_in_sandbox", sandbox)

    async def _docker_ok(_bin="docker"):
        return True

    monkeypatch.setattr(ee, "check_docker_available", _docker_ok)
    report = asyncio.run(
        ee.run_contract_equivalence(
            mission_id="mission-1234abcd",
            language=language,
            artifact_filename="adder.py" if language == "python" else "main.go",
            artifact_code=code,
            contract_vectors={
                "source": "llm",
                "criteria_total": 2,
                "vectors": vectors,
                "rejections": ["vector 9: nope"],
            },
            dependencies=deps,
        )
    )
    return report, sandbox


CALL = {
    "vector_id": "cv-1", "kind": "call", "criterion_index": 0, "function": "add",
    "args": [2, 3], "expected": 5,
}
CLI = {
    "vector_id": "cv-2", "kind": "cli", "criterion_index": 1, "argv": ["2", "3"],
    "stdin": "", "expected_exit_code": 0, "expected_stdout": "5", "stdout_match": "exact",
}


def test_matching_artifact_passes(monkeypatch) -> None:
    report, sandbox = _run(
        monkeypatch,
        [CALL, CLI],
        [('__EQV__{"status": "ok", "result": 5}', 0, False), ("5\n", 0, False)],
    )
    assert report["status"] == "passed"
    assert report["equivalence_vectors_passed"] == 2
    assert report["verification_basis"] == "contract_oracle"
    assert report["oracle_independence"] == "interface_only"
    assert report["criteria_with_vectors"] == 2 and report["oracle"]["rejected_vectors"] == 1
    # the CLI vector ran the real program with the vector's argv
    assert sandbox.calls[1]["command"] == "python /workspace/adder.py 2 3"


def test_wrong_answer_fails(monkeypatch) -> None:
    report, _ = _run(
        monkeypatch,
        [CALL, CLI],
        [('__EQV__{"status": "ok", "result": 6}', 0, False), ("6\n", 0, False)],
    )
    assert report["status"] == "failed"
    assert report["equivalence_vectors_failed"] == 2
    assert any("expected 5, got 6" in f for f in report["findings"])


def test_wrong_exit_code_fails(monkeypatch) -> None:
    report, _ = _run(monkeypatch, [CLI], [("5\n", 1, False)])
    assert report["status"] == "failed"
    assert "exit code 1, expected 0" in report["findings"][0]
    # the compiler/runtime error is surfaced so an operator can diagnose it
    assert "syntax error" in report["findings"][0]


def test_timeout_is_a_skip_not_a_failure(monkeypatch) -> None:
    report, _ = _run(monkeypatch, [CLI], [("", 124, True)])
    assert report["status"] == "skipped"
    assert report["equivalence_vectors_failed"] == 0


def test_bundle_header_is_stripped_before_execution(monkeypatch) -> None:
    bundled = "## FILE adder.py\n" + SOURCE
    _, sandbox = _run(monkeypatch, [CLI], [("5\n", 0, False)], code=bundled)
    assert not sandbox.calls[0]["files"]["adder.py"].startswith("## FILE")


def test_stdin_is_materialised_and_redirected(monkeypatch) -> None:
    vector = {**CLI, "argv": [], "stdin": "2 3\n"}
    _, sandbox = _run(monkeypatch, [vector], [("5\n", 0, False)])
    assert sandbox.calls[0]["files"]["__contract_stdin__.txt"] == "2 3\n"
    assert sandbox.calls[0]["command"].endswith("< /workspace/__contract_stdin__.txt")


def test_call_vectors_are_skipped_outside_python(monkeypatch) -> None:
    report, sandbox = _run(monkeypatch, [CALL], [], language="go", code="package main")
    assert report["status"] == "skipped" and sandbox.calls == []


def test_go_cli_vector_uses_the_go_runtime(monkeypatch) -> None:
    _, sandbox = _run(monkeypatch, [CLI], [("5\n", 0, False)], language="go", code="package main")
    assert sandbox.calls[0]["base_image"].startswith("golang:")
    assert sandbox.calls[0]["command"].endswith("&& /tmp/a.out 2 3")


def test_unmet_dependencies_skip_honestly(monkeypatch) -> None:
    report, sandbox = _run(monkeypatch, [CLI], [], deps=["requests"])
    assert report["status"] == "skipped" and "offline sandbox" in report["reason"]
    assert sandbox.calls == []


def test_no_vectors_is_skipped_with_the_oracles_reason(monkeypatch) -> None:
    sandbox = _FakeSandbox([])
    monkeypatch.setattr(ee, "run_in_sandbox", sandbox)
    report = asyncio.run(
        ee.run_contract_equivalence(
            mission_id="m",
            language="python",
            artifact_filename="a.py",
            artifact_code=SOURCE,
            contract_vectors={"source": "unavailable", "vectors": [], "reason": "no model"},
        )
    )
    assert report["status"] == "skipped" and report["reason"] == "no model"
    assert sandbox.calls == []


# --------------------------------------------------------------------------- enforcement


def _correctness_report() -> dict:
    return {"status": "passed", "passed": True, "blocking": False, "risk_level": "low",
            "findings": []}


def test_behavioural_failure_is_advisory_by_default() -> None:
    enriched = attach_behavioural_report(
        _correctness_report(), {"status": "failed", "findings": ["cv-1 wrong"]}
    )
    assert enriched["passed"] and not enriched["blocking"]
    assert enriched["findings"] == ["[behavioural] cv-1 wrong"]
    assert enriched["behavioural_enforcement_enabled"] is False


def test_enforcement_blocks_on_failure_only() -> None:
    blocked = attach_behavioural_report(
        _correctness_report(), {"status": "failed", "findings": []}, enforce=True
    )
    assert blocked["blocking"] and blocked["status"] == "blocked"
    assert blocked["blocked_by"] == "behavioural"
    skipped = attach_behavioural_report(
        _correctness_report(), {"status": "skipped", "findings": []}, enforce=True
    )
    assert skipped["passed"] and not skipped["blocking"]


# --------------------------------------------------------------------------- generator


def test_generator_has_no_fallback_vectors(monkeypatch) -> None:
    from orchestrator.llm_delegation import generators_artifacts as ga

    async def _no_model(**_kwargs):
        return None, "none", "none", {}

    monkeypatch.setattr(ga, "_call_with_agent_system", _no_model)
    result = asyncio.run(
        ga.generate_contract_vectors(
            mission_id="m", acceptance_criteria=CRITERIA, contract_summary="adder",
            interface=_interface(),
        )
    )
    assert result["source"] == "unavailable" and result["vectors"] == []


def test_generator_prompt_never_contains_the_implementation(monkeypatch) -> None:
    from orchestrator.llm_delegation import generators_artifacts as ga

    seen: dict = {}

    async def _capture(**kwargs):
        seen["prompt"] = kwargs["prompt"]
        return (
            {"vectors": [{"kind": "call", "criterion_index": 0, "function": "add",
                          "args": [2, 3], "expected": 5}]},
            "gemini", "gemini-3.7-flash", {},
        )

    monkeypatch.setattr(ga, "_call_with_agent_system", _capture)
    result = asyncio.run(
        ga.generate_contract_vectors(
            mission_id="m", acceptance_criteria=CRITERIA, contract_summary="adder",
            interface=_interface(),
        )
    )
    assert "SECRET_CONSTANT" not in seen["prompt"]
    assert "return a + b" not in seen["prompt"]
    assert result["source"] == "llm" and len(result["vectors"]) == 1


def test_generator_refuses_without_criteria() -> None:
    from orchestrator.llm_delegation import generators_artifacts as ga

    result = asyncio.run(
        ga.generate_contract_vectors(
            mission_id="m", acceptance_criteria=[], contract_summary="", interface=_interface()
        )
    )
    assert result["source"] == "unavailable" and "no acceptance criteria" in result["reason"]
