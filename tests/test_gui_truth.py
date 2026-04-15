from pathlib import Path


def test_main_window_control_center_panels_exist():
    source = Path("C:/projekt/sokol/sokol/ui/main_window.py").read_text(encoding="utf-8")
    assert "runtime_event_received = pyqtSignal(str)" in source
    assert "telemetry_updated = pyqtSignal(str)" in source
    assert "safety_updated = pyqtSignal(str)" in source
    assert 'self._tab_names["overview"]' in source
    assert 'self._tab_names["runtime"]' in source
    assert 'self._tab_names["history"]' in source
    assert 'self._tab_names["logs"]' in source
    assert 'self._tab_names["safety"]' in source


def test_tray_supports_control_center_section_navigation():
    source = Path("C:/projekt/sokol/sokol/ui/tray.py").read_text(encoding="utf-8")
    assert "open_section_requested = pyqtSignal(str)" in source
    assert 'lambda: self._open_section("overview")' in source
    assert 'lambda: self._open_section("runtime")' in source
    assert 'lambda: self._open_section("safety")' in source


def test_main_projection_wiring_and_canonical_emergency_route():
    main_source = Path("C:/projekt/sokol/sokol/main.py").read_text(encoding="utf-8")
    assert "orchestrator.event_bus.subscribe(EventType.STATE_CHANGE, on_state_event)" in main_source
    assert "orchestrator.event_bus.subscribe(EventType.USER_INPUT, on_runtime_event)" in main_source
    assert "orchestrator.event_bus.subscribe(EventType.CONFIRM_REQUEST, on_runtime_event)" in main_source
    assert "orchestrator.event_bus.subscribe(EventType.EMERGENCY_STOP, on_runtime_event)" in main_source
    assert "main_window.emergency_stop_requested.connect(" in main_source
    assert 'loop_controller.submit_text("emergency stop", source="ui_button")' in main_source
    assert 'loop_controller.submit_text("emergency stop", source="tray")' in main_source
