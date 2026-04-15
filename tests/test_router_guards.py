from types import SimpleNamespace

from sokol.runtime.router import IntentRouter


def _stub_response(content: str):
    return SimpleNamespace(content=content)


def test_router_rejects_unknown_tool_calls():
    router = IntentRouter()
    router._llm_manager.complete = lambda *args, **kwargs: _stub_response(
        '{"type":"tool_call","tool":"SetUserFact","args":{"name":"x"}}'
    )
    result = router.route("Запомни факт")
    assert not result.is_ok()


def test_router_normalizes_open_application_alias():
    router = IntentRouter()
    router._llm_manager.complete = lambda *args, **kwargs: _stub_response(
        '{"type":"tool_call","tool":"open_application","args":{"app_name":"telegram"}}'
    )
    result = router.route("Открой телеграмм")
    assert result.is_ok()
    assert result.value.tool == "app_launcher"


def test_router_enforces_russian_text_for_clarification():
    router = IntentRouter()
    router._llm_manager.complete = lambda *args, **kwargs: _stub_response(
        '{"type":"clarification","question":"Can you explain?"}'
    )
    result = router.route("что?")
    assert result.is_ok()
    assert result.value.text.startswith("Поясните, пожалуйста, запрос на русском")
