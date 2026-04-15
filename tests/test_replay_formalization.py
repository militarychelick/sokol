from sokol.runtime.observability import TraceCollector
from sokol.runtime.replay_verifier import compare_execution_graphs


def _build_trace_for_scenario(scenario: str):
    collector = TraceCollector()
    collector.start_trace(input_text=scenario, source="ui")
    collector.start_execution_timer()
    collector.record_router_decision(type("Decision", (), {
        "action_type": "tool_call" if scenario != "emergency_interrupt" else "final_answer",
        "source": "rule_router",
        "tool": "app_launcher" if scenario == "normal" else "",
        "confidence": 0.95,
    })())
    collector.record_control_decision(type("Control", (), {
        "decision": "allow" if scenario != "dangerous_confirm" else "confirm_required",
        "risk_level": "write" if scenario == "dangerous_confirm" else "read",
        "explanation": f"scenario={scenario}",
    })())
    collector.record_tool_call("demo_tool", {"scenario": scenario})
    collector.record_tool_result("demo_tool", type("ToolResult", (), {"success": True, "data": {"scenario": scenario}})())
    collector.record_memory_context(f"context::{scenario}")
    collector.record_memory_influence({"lineage": [scenario], "selected": True})
    return collector.finalize_trace(
        response=f"response::{scenario}",
        success=True,
    )


def test_strict_replay_reports_mismatch_with_path():
    trace_a = _build_trace_for_scenario("normal")
    trace_b = _build_trace_for_scenario("normal")
    trace_b.final_response = "response::tampered"

    verdict = compare_execution_graphs(trace_a, trace_b)
    assert verdict.status == "FAIL"
    assert len(verdict.mismatches) >= 1
    assert any(m.path.endswith(".final_response") for m in verdict.mismatches)


def test_three_required_proof_scenarios_pass_strict_replay():
    scenarios = ["normal", "dangerous_confirm", "emergency_interrupt"]

    for scenario in scenarios:
        run_a = _build_trace_for_scenario(scenario)
        run_b = _build_trace_for_scenario(scenario)
        verdict = compare_execution_graphs(run_a, run_b)
        assert verdict.status == "PASS", f"scenario={scenario} mismatches={verdict.mismatches}"
