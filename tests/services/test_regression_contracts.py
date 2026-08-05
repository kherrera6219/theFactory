from pathlib import Path


def test_protocol_topics_include_required_runtime_topics() -> None:
    root = Path(__file__).resolve().parents[2]
    topics_file = root / "protocol" / "topics.yaml"
    text = topics_file.read_text(encoding="utf-8")
    required = [
        "intake.feature_contract.created",
        "fusion.requested",
        "artifact.rir.verified",
        "mission.partition.ready",
        "incident.runtime.errorlog",
        "agent.heartbeat",
        "agent.state.changed",
        "cluster.assigned.podA",
        "cluster.assigned.podB",
        "cluster.assigned.podC",
        "cluster.assigned.podD",
    ]
    for topic in required:
        assert topic in text


def test_every_persisted_mission_event_type_is_declared_in_event_type() -> None:
    """Every event written to mission_events must be a member of ``EventType``.

    ``EventType`` is the response model for mission events, so one unlisted
    value makes pydantic reject the whole payload and
    ``/missions/{id}/events``, ``/chain-trace`` and ``/operations/alerts`` all
    500. That is silent until a mission actually emits the value -- and the
    three gate-failure events that were missing (`MISSION_EQUIVALENCE_BLOCKED`,
    `MISSION_SECURITY_COMPLIANCE_BLOCKED`,
    `MISSION_DEPENDENCY_ABSORPTION_BLOCKED`) only fire on the unhappy path, so
    they made exactly the missions an operator needs to inspect unopenable in
    Mission Control.
    """
    import re

    root = Path(__file__).resolve().parents[2]
    orchestrator = root / "services" / "orchestrator" / "orchestrator"

    models_src = (orchestrator / "models.py").read_text(encoding="utf-8")
    literal_block = re.search(r"EventType = Literal\[(.*?)\n\]", models_src, re.S)
    assert literal_block is not None, "could not locate the EventType Literal in models.py"
    declared = set(re.findall(r'"([A-Z][A-Z0-9_]+)"', literal_block.group(1)))
    assert declared, "EventType parsed as empty -- the regex no longer matches"

    # String literals passed to insert_mission_event / transition_mission_state.
    # Both write the event_type column; anything reaching them must be declared.
    #
    # Matching `name(` is not enough: the orchestrator calls these off the event
    # loop as `asyncio.to_thread(storage.insert_mission_event, ..., "EVENT")`,
    # where the name is an *argument* and the literal belongs to the enclosing
    # to_thread call. An earlier version of this guard missed exactly the three
    # events it was written for. So walk forward from each mention to the `)`
    # that closes whichever call it sits in, and read the literals in between.
    def _call_arguments(source: str, start: int) -> str:
        depth = 0
        for index in range(start, len(source)):
            char = source[index]
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    return source[start:index]  # name used as an argument
                depth -= 1
                if depth == 0:
                    return source[start:index]  # name used as a call
        return source[start : start + 500]

    persisted: dict[str, str] = {}
    for path in sorted(orchestrator.rglob("*.py")):
        source = path.read_text(encoding="utf-8", errors="ignore")
        for call in ("insert_mission_event", "transition_mission_state"):
            for match in re.finditer(re.escape(call), source):
                # Skip quoted mentions -- storage.py re-exports these names in
                # __all__, and walking forward from there just reads the rest of
                # that list.
                if match.start() > 0 and source[match.start() - 1] in "\"'":
                    continue
                arguments = _call_arguments(source, match.end())
                for event_type in re.findall(r'"([A-Z][A-Z0-9_]+)"', arguments):
                    persisted.setdefault(event_type, f"{path.name} ({call})")

    # Guard the guard: if the scan stops finding the known write sites, the
    # assertion below would pass vacuously forever.
    assert "MISSION_SECURITY_COMPLIANCE_BLOCKED" in persisted, (
        "the scan no longer finds known insert_mission_event call sites, so this "
        f"test would pass vacuously; found: {sorted(persisted)}"
    )

    undeclared = {name: where for name, where in persisted.items() if name not in declared}
    assert not undeclared, (
        "event types are written to mission_events but missing from EventType, "
        "which makes the mission-events, chain-trace and alerts endpoints 500 for "
        f"any mission that emits them: {undeclared}"
    )
