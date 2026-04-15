"""Deterministic single-process runtime replay runner."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from sokol.core.types import AgentState
from sokol.runtime.live_loop import LiveLoopController, LoopEvent, LoopEventType
from sokol.runtime.replay_verifier import ReplayVerdict, compare_structured_payloads
from sokol.runtime.result import Result


@dataclass(frozen=True)
class RuntimeReplayEvent:
    """Input event for runtime replay."""

    kind: str
    source: str
    text: str = ""
    audio: bytes = b""


@dataclass(frozen=True)
class RuntimeReplayArtifact:
    """Execution-level runtime artifact for strict replay checks."""

    responses: list[str]
    event_sequence: list[str]
    tool_outputs: list[dict[str, Any]]
    memory_state: list[dict[str, Any]]
    final_state: str
    accepted_events: int
    dropped_events: int
    availability: dict[str, bool]

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuntimeReplayReport:
    """Capture + replay final report."""

    capture: RuntimeReplayArtifact
    replay: RuntimeReplayArtifact
    verdict: ReplayVerdict


@dataclass
class _DeterministicRuntimeOrchestrator:
    """Deterministic runtime stub that mimics tool+memory behavior."""

    state: AgentState = AgentState.IDLE
    pending_dangerous_action: str | None = None
    interactions: list[dict[str, Any]] = field(default_factory=list)
    tool_outputs: list[dict[str, Any]] = field(default_factory=list)

    def process_input(self, *, text: str, source: str, screen_context: dict[str, Any] | None = None):
        normalized = text.strip().lower()
        if self.pending_dangerous_action and normalized in {"да", "yes", "confirm"}:
            tool_result = {
                "tool": "dangerous_action",
                "args": {"action": self.pending_dangerous_action},
                "result": {"success": True},
            }
            self.tool_outputs.append(tool_result)
            self.interactions.append(
                {"source": source, "input": text, "response": "Опасное действие подтверждено и выполнено."}
            )
            self.pending_dangerous_action = None
            return Result.ok(type("Response", (), {"user_text": "Опасное действие подтверждено и выполнено."})())

        if "delete" in normalized or "dangerous" in normalized:
            self.pending_dangerous_action = text
            self.interactions.append(
                {"source": source, "input": text, "response": "Требуется подтверждение опасного действия."}
            )
            return Result.ok(type("Response", (), {"user_text": "Требуется подтверждение опасного действия."})())

        if screen_context:
            self.tool_outputs.append(
                {
                    "tool": "screen_analyzer",
                    "args": {"has_image": screen_context.get("has_image", False)},
                    "result": {"success": True, "elements": screen_context.get("element_count", 0)},
                }
            )

        self.interactions.append({"source": source, "input": text, "response": f"ok:{text}"})
        return Result.ok(type("Response", (), {"user_text": f"ok:{text}"})())

    def emergency_stop(self, reason: str, emit_event: bool = True) -> None:
        _ = emit_event
        self.state = AgentState.IDLE
        self.interactions.append({"source": "emergency", "input": reason, "response": "interrupted"})


class RuntimeReplayRunner:
    """Capture a run and replay it in deterministic single-process mode."""

    def __init__(self, controller_factory: Callable[[], LiveLoopController]) -> None:
        self._controller_factory = controller_factory

    def capture_and_replay(self, events: list[RuntimeReplayEvent]) -> RuntimeReplayReport:
        capture = self._run(events)
        replay = self._run(events)
        verdict = compare_structured_payloads(capture.to_payload(), replay.to_payload())
        return RuntimeReplayReport(capture=capture, replay=replay, verdict=verdict)

    def _run(self, events: list[RuntimeReplayEvent]) -> RuntimeReplayArtifact:
        controller = self._controller_factory()
        responses: list[str] = []
        processed: list[str] = []
        drop_reasons: list[str] = []
        controller.set_response_result_channel(lambda message: responses.append(message) or Result.ok(True))
        controller.set_event_drop_callback(lambda source, reason: drop_reasons.append(f"{source}:{reason}"))

        accepted = 0
        for event in events:
            if event.kind == "text":
                accepted += 1 if controller.submit_text(event.text, source=event.source) else 0
            elif event.kind == "voice":
                accepted += 1 if controller.submit_voice(event.audio, source=event.source) else 0
            elif event.kind == "screen":
                accepted += 1 if controller.request_screen_capture(source=event.source) else 0
            else:
                raise ValueError(f"Unsupported replay event kind: {event.kind}")

        self._drain_queue(controller, processed)

        orchestrator = controller._orchestrator  # Runtime harness access for deterministic artifact capture.
        tool_outputs = list(getattr(orchestrator, "tool_outputs", []))
        memory_state = list(getattr(orchestrator, "interactions", []))
        return RuntimeReplayArtifact(
            responses=responses,
            event_sequence=processed,
            tool_outputs=tool_outputs,
            memory_state=memory_state,
            final_state=controller._orchestrator.state.value,
            accepted_events=accepted,
            dropped_events=len(drop_reasons),
            availability={
                "voice": bool(controller._voice_input and controller._voice_input.is_available()),
                "screen": bool(controller._screen_input and controller._screen_input.is_available()),
            },
        )

    def _drain_queue(self, controller: LiveLoopController, processed: list[str]) -> None:
        while True:
            try:
                _, _, event = controller._event_queue.get_nowait()
            except Exception:
                break
            if not isinstance(event, LoopEvent):
                continue
            if event.event_type == LoopEventType.STOP:
                break
            processed.append(event.event_type.value)
            controller._process_event(event)


def build_default_runtime_runner() -> RuntimeReplayRunner:
    """Build replay runner with deterministic local harness."""
    from sokol.perception.voice_input import VoiceInputAdapter, VoiceEvent
    from sokol.perception.screen_input import ScreenInputAdapter

    class _Voice(VoiceInputAdapter):
        def is_available(self) -> bool:
            return True

        def transcribe(self, audio_data: bytes) -> VoiceEvent:
            _ = audio_data
            return VoiceEvent(text="voice_command", confidence=1.0)

    class _Screen(ScreenInputAdapter):
        def is_available(self) -> bool:
            return True

        def capture(self):
            return type(
                "Snapshot",
                (),
                {"active_window": "deterministic", "image_bytes": b"i", "elements": [{"id": "a"}]},
            )()

    def _factory() -> LiveLoopController:
        return LiveLoopController(
            orchestrator=_DeterministicRuntimeOrchestrator(),
            voice_input=_Voice(),
            screen_input=_Screen(),
        )

    return RuntimeReplayRunner(controller_factory=_factory)
