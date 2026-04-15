import random
import sys
from types import SimpleNamespace
from pathlib import Path

from sokol.core.types import AgentState
from sokol.runtime.live_loop import LiveLoopController
from sokol.runtime.result import Result

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.append(str(TESTS_DIR))

from chaos_harness import ContinuousChaosRunner


def _build_controller() -> LiveLoopController:
    memory_log = []

    def process_input(*, text: str, source: str, screen_context=None):
        _ = screen_context
        memory_log.append({"source": source, "text": text})
        return Result.ok(type("Response", (), {"user_text": f"ack:{text}"})())

    orchestrator = SimpleNamespace(
        state=AgentState.IDLE,
        process_input=process_input,
        emergency_stop=lambda reason, emit_event=True: memory_log.append(
            {"source": "emergency", "text": reason, "emit_event": emit_event}
        ),
    )
    controller = LiveLoopController(orchestrator=orchestrator)
    controller.set_response_result_channel(lambda message: Result.ok(True))
    return controller


def _drain(controller: LiveLoopController) -> int:
    processed = 0
    while True:
        try:
            _, _, event = controller._event_queue.get_nowait()
        except Exception:
            break
        controller._process_event(event)
        processed += 1
    return processed


def test_fuzz_mixed_payloads_have_no_silent_crash():
    rng = random.Random(123)
    controller = _build_controller()
    for _ in range(120):
        action = rng.choice(["text", "voice", "screen", "broken"])
        if action == "text":
            controller.submit_text(rng.choice(["hello", "", "emergency stop", "dangerous op"]), source="fuzz")
        elif action == "voice":
            controller.submit_voice(b"audio", source="fuzz_voice")
        elif action == "screen":
            controller.request_screen_capture(source="fuzz_screen")
        else:
            controller.submit_text("", source="broken")

    processed = _drain(controller)
    assert processed >= 1
    stats = controller._execution_tracker.get_overall_stats()
    assert stats["total_executions"] >= 1


def test_chaos_runner_short_profile_collects_drift_metrics():
    controller = _build_controller()
    runner = ContinuousChaosRunner(controller, seed=99)
    report = runner.run_destructive_test(duration_hours=1, max_iterations=40)

    assert report["status"] in {"completed", "interrupted"}
    assert report["seed"] == 99
    assert "fault_injections" in report
    assert report["fault_injections"]["latency_injections"] >= 0
    assert report["observations"]["max_queue_depth"] >= 0
