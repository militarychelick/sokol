from sokol.runtime.replay_runner import (
    RuntimeReplayEvent,
    build_default_runtime_runner,
)


def test_runtime_replay_runner_passes_with_identical_event_stream():
    runner = build_default_runtime_runner()
    events = [
        RuntimeReplayEvent(kind="text", source="ui", text="hello"),
        RuntimeReplayEvent(kind="text", source="ui", text="dangerous delete file"),
        RuntimeReplayEvent(kind="text", source="ui", text="yes"),
        RuntimeReplayEvent(kind="voice", source="voice", audio=b"voice"),
        RuntimeReplayEvent(kind="screen", source="screen"),
        RuntimeReplayEvent(kind="text", source="ui_button", text="emergency stop"),
    ]

    report = runner.capture_and_replay(events)
    assert report.verdict.status == "PASS"
    assert report.capture.event_sequence == report.replay.event_sequence
    assert len(report.capture.memory_state) > 0
    assert any("подтверждение" in message.lower() for message in report.capture.responses)


def test_runtime_replay_runner_detects_artifact_mismatch():
    runner = build_default_runtime_runner()
    events = [RuntimeReplayEvent(kind="text", source="ui", text="hello")]
    report = runner.capture_and_replay(events)

    tampered = report.replay.to_payload()
    tampered["responses"][0] = "tampered"
    from sokol.runtime.replay_verifier import compare_structured_payloads

    verdict = compare_structured_payloads(report.capture.to_payload(), tampered)
    assert verdict.status == "FAIL"
    assert any(m.path.endswith(".responses[0]") for m in verdict.mismatches)
