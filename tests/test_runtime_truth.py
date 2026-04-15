from types import SimpleNamespace

from sokol.core.types import AgentState
from sokol.runtime.live_loop import LiveLoopController, LoopEventType
from sokol.runtime.memory_layer import MemoryLayer
from sokol.runtime.user_model import UserModel
from sokol.runtime.result import Result
from sokol.action.executor import ActionExecutor
from sokol.tools.registry import get_registry


def _make_stub_orchestrator():
    return SimpleNamespace(
        state=AgentState.IDLE,
        process_input=lambda **kwargs: None,
        emergency_stop=lambda reason, emit_event=True: None,
    )


def test_live_loop_requires_response_channel_before_start():
    loop = LiveLoopController(orchestrator=_make_stub_orchestrator())
    try:
        loop.start()
        assert False, "start() must require response result channel"
    except RuntimeError as exc:
        assert "response result channel" in str(exc)


def test_emergency_classification_is_explicit_command_only():
    loop = LiveLoopController(orchestrator=_make_stub_orchestrator())

    assert loop.submit_text("yes please", source="ui")
    event_normal = loop._event_queue.get_nowait()[2]
    assert event_normal.event_type == LoopEventType.TEXT_INPUT

    assert loop.submit_text("emergency stop", source="ui_button")
    event_emergency = loop._event_queue.get_nowait()[2]
    assert event_emergency.event_type == LoopEventType.EMERGENCY


def test_memory_retrieval_returns_isolated_snapshots():
    memory = MemoryLayer(UserModel())
    memory.store_interaction(
        source="ui",
        input_text="create file note",
        response_text="created",
        tool_used="file_ops",
        tool_success=True,
    )
    first = memory.retrieve_context("file", limit=5)
    second = memory.retrieve_context("file", limit=5)

    assert first.success and second.success
    first.value.tool_memory["file_ops"]["success_count"] = 999

    third = memory.retrieve_context("file", limit=5)
    assert third.value.tool_memory["file_ops"]["success_count"] != 999


def test_unavailable_tools_return_explicit_failure():
    registry = get_registry()

    translate_result = registry.execute("translate", {"text": "hello", "target_language": "ru"})
    transcript_result = registry.execute("transcript_to_text", {"file_path": "sample.wav"})

    assert translate_result.success and not translate_result.value.success
    assert "not configured" in (translate_result.value.error or "").lower()

    assert transcript_result.success and not transcript_result.value.success
    assert "not configured" in (transcript_result.value.error or "").lower()


def test_emergency_execution_calls_orchestrator_interrupt():
    calls = []
    orch = SimpleNamespace(
        state=AgentState.THINKING,
        process_input=lambda **kwargs: None,
        emergency_stop=lambda reason, emit_event=True: calls.append((reason, emit_event)),
    )
    loop = LiveLoopController(orchestrator=orch)
    loop.set_response_result_channel(lambda message: Result.ok(True))

    assert loop._execute_emergency("emergency stop", "ui_button")
    assert len(calls) == 1
    assert calls[0][1] is True


def test_emergency_path_does_not_mutate_loop_state():
    calls = []
    state_updates = []
    orch = SimpleNamespace(
        state=AgentState.THINKING,
        process_input=lambda **kwargs: None,
        emergency_stop=lambda reason, emit_event=True: calls.append((reason, emit_event)),
    )
    loop = LiveLoopController(orchestrator=orch)
    loop.set_response_result_channel(lambda message: Result.ok(True))
    loop.set_state_change_callback(lambda state: state_updates.append(state.value))

    assert loop._execute_emergency("emergency stop", "ui_button")
    assert len(calls) == 1
    assert state_updates == []


def test_action_executor_single_path_no_internal_fallback():
    executor = ActionExecutor()
    called = {"uia": 0, "ocr": 0}

    executor._uia_executor = SimpleNamespace(
        is_available=lambda: True,
        execute=lambda action_type, target, params: {"success": False, "error": "uia-fail"},
    )
    executor._ocr_fallback = SimpleNamespace(
        is_available=lambda: True,
        execute=lambda action_type, target, params: called.__setitem__("ocr", called["ocr"] + 1) or {"success": True},
    )
    executor._is_browser_target = lambda target: False

    result = executor.execute("click", "button")
    assert result.success is False
    assert "uia" in (result.method_used or "")
    assert called["ocr"] == 0
