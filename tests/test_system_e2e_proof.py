from types import SimpleNamespace

from sokol.core.types import AgentState
from sokol.runtime.live_loop import LiveLoopController
from sokol.runtime.replay_runner import (
    RuntimeReplayEvent,
    RuntimeReplayRunner,
    build_default_runtime_runner,
)
from sokol.runtime.result import Result


def _build_unavailable_surface_runner() -> RuntimeReplayRunner:
    from sokol.perception.voice_input import VoiceEvent

    class _UnavailableVoice:
        def is_available(self) -> bool:
            return False

        def transcribe(self, audio_data: bytes):
            _ = audio_data
            return VoiceEvent(text="", confidence=0.0)

    class _UnavailableScreen:
        def is_available(self) -> bool:
            return False

    def _factory() -> LiveLoopController:
        orchestrator = SimpleNamespace(
            state=AgentState.IDLE,
            process_input=lambda **kwargs: Result.ok(type("Response", (), {"user_text": f"ack:{kwargs['text']}"})()),
            emergency_stop=lambda reason, emit_event=True: None,
        )
        controller = LiveLoopController(
            orchestrator=orchestrator,
            voice_input=_UnavailableVoice(),
            screen_input=_UnavailableScreen(),
        )
        return controller

    return RuntimeReplayRunner(controller_factory=_factory)


def test_required_e2e_proof_scenarios_pass_runtime_replay():
    runner = build_default_runtime_runner()
    scenarios = {
        "normal_text_flow": [RuntimeReplayEvent(kind="text", source="ui", text="open notes")],
        "dangerous_confirm_flow": [
            RuntimeReplayEvent(kind="text", source="ui", text="dangerous delete file"),
            RuntimeReplayEvent(kind="text", source="ui", text="yes"),
        ],
        "emergency_interrupt_flow": [RuntimeReplayEvent(kind="text", source="ui_button", text="emergency stop")],
    }

    for scenario_name, events in scenarios.items():
        report = runner.capture_and_replay(events)
        assert report.verdict.status == "PASS", scenario_name
        assert report.capture.final_state == "idle", scenario_name
        assert report.capture.accepted_events >= 1, scenario_name


def test_voice_and_screen_surfaces_are_truthful_when_available():
    runner = build_default_runtime_runner()
    events = [
        RuntimeReplayEvent(kind="voice", source="voice", audio=b"voice"),
        RuntimeReplayEvent(kind="screen", source="screen"),
    ]
    report = runner.capture_and_replay(events)
    assert report.verdict.status == "PASS"
    assert report.capture.availability["voice"] is True
    assert report.capture.availability["screen"] is True


def test_voice_and_screen_surfaces_explicitly_unavailable_when_disabled():
    runner = _build_unavailable_surface_runner()
    events = [
        RuntimeReplayEvent(kind="voice", source="voice", audio=b"voice"),
        RuntimeReplayEvent(kind="screen", source="screen"),
    ]
    report = runner.capture_and_replay(events)
    assert report.verdict.status == "PASS"
    assert report.capture.availability["voice"] is False
    assert report.capture.availability["screen"] is False
