"""Sokol Windows Agent - Main entry point."""

import sys
from pathlib import Path
from PyQt6.QtCore import QTimer

from sokol.core.config import get_config, reload_config
from sokol.core.types import AgentState, EventType
from sokol.observability.logging import get_logger, setup_logging
from sokol.runtime.orchestrator import Orchestrator
from sokol.runtime.live_loop import LiveLoopController
from sokol.runtime.input import submit_input
from sokol.safety.emergency import register_emergency_callback, get_emergency_handler
from sokol.memory.manager import MemoryManager
from sokol.tools.registry import get_registry
from sokol.ui.app import SokolApp
from sokol.ui.main_window import MainWindow
from sokol.ui.tray import TrayIcon
from sokol.perception.voice_input import VoiceInputAdapter
from sokol.perception.screen_input import ScreenInputAdapter
from sokol.perception.wake_word import WakeWordDetector
from sokol.runtime.result import Result
from sokol.runtime.errors import ErrorBuilder, ErrorCategory

logger = get_logger("sokol.main")

# Global reference for main_window (for logging callback)
_main_window_ref = None

def set_main_window_ref(window):
    """Set global reference to main window for logging callback."""
    global _main_window_ref
    _main_window_ref = window


def main() -> int:
    """Main entry point."""
    global _main_window_ref
    
    # Load configuration
    config = get_config()

    # Initialize UI FIRST (before logging)
    app = SokolApp(config)
    app.initialize(sys.argv)

    main_window = MainWindow()
    app.set_main_window(main_window)
    set_main_window_ref(main_window)

    tray = TrayIcon(main_window)
    app.set_tray(tray)

    # Setup logging AFTER UI is ready
    def ui_log_callback(log_line: str) -> None:
        """Forward logs to main window via signal."""
        global _main_window_ref
        if _main_window_ref:
            try:
                _main_window_ref.log_received.emit(log_line)
            except Exception:
                pass

    setup_logging(
        level=config.logging.level,
        log_file=config.logging.file,
        max_size=config.logging.max_size,
        backup_count=config.logging.backup_count,
        use_json=config.logging.format == "json",
        ui_log_callback=ui_log_callback,
    )

    logger.info(f"Starting {config.agent.name} v0.1.0")

    # Initialize components
    orchestrator = Orchestrator(config)
    orchestrator.setup()

    # Initialize memory
    memory = MemoryManager()
    memory.start_session()
    memory.load_profile()

    # Wire memory to orchestrator for context injection and event persistence
    orchestrator.set_memory_manager(memory)

    # Initialize tools
    tool_registry = get_registry()
    logger.info(f"Tools registered: {len(tool_registry)}")

    # Initialize perception components
    voice_input = None
    screen_input = None
    wake_word_detector = None

    if config.perception.enable_voice_input:
        voice_input = VoiceInputAdapter(
            wake_words=config.agent.wake_words,
            model_size="base"
        )
        logger.info("Voice input initialized")

    if config.perception.enable_screen_input:
        screen_input = ScreenInputAdapter()
        logger.info("Screen input initialized")

    if config.voice.enabled and config.voice.wake_word_engine:
        wake_word_detector = WakeWordDetector(
            wake_words=config.agent.wake_words,
            engine=config.voice.wake_word_engine
        )
        logger.info("Wake word detector initialized")

    # Initialize live loop controller
    loop_controller = LiveLoopController(
        orchestrator=orchestrator,
        voice_input=voice_input,
        screen_input=screen_input,
        wake_word_detector=wake_word_detector,
    )

    # Register emergency stop callback
    # FIX: Register LiveLoopController with emergency handler to ensure full mitigation/observer/verification coverage
    emergency_handler = get_emergency_handler()
    emergency_handler.set_loop_controller(loop_controller)
    # FIX: No fallback callback - emergency must go through pipeline (fail-stop model)


    # Wire UI to loop controller (unified input stream)
    def on_user_input(text: str) -> None:
        # Don't add to memory here - orchestrator will do it
        # Submit through live loop controller
        loop_controller.submit_text(text)

    # State projection listener (observer-only event stream).
    def on_state_event(event) -> None:
        state_name = (event.data or {}).get("to_state")
        if not state_name:
            return
        try:
            state = AgentState(state_name)
        except Exception:
            return
        main_window.state_changed.emit(state)
        tray.update_state(state)
        main_window.runtime_event_received.emit(
            f"state_change: {event.source} -> {state_name} reason={(event.data or {}).get('reason', '')}"
        )

    def on_runtime_event(event) -> None:
        data = event.data or {}
        main_window.runtime_event_received.emit(f"{event.type.value}: source={event.source} payload={data}")
        if event.type in {EventType.EMERGENCY_STOP, EventType.CONFIRM_REQUEST, EventType.ERROR}:
            main_window.safety_updated.emit(f"{event.type.value}: {data}")

    # Wire response callback
    def on_response(message: str) -> None:
        """Handle agent responses."""
        main_window.response_received.emit(message)

    def response_result_channel(message: str) -> Result[bool]:
        """Single response delivery channel for runtime output."""
        try:
            on_response(message)
            return Result.ok(True)
        except Exception as e:
            error_info = ErrorBuilder.from_exception(
                e,
                category=ErrorCategory.INFRASTRUCTURE,
                context={"phase": "ui_response_channel"},
            )
            return Result.error(error_info)

    # Observer-only state projection via orchestrator event stream.
    orchestrator.event_bus.subscribe(EventType.STATE_CHANGE, on_state_event)
    orchestrator.event_bus.subscribe(EventType.USER_INPUT, on_runtime_event)
    orchestrator.event_bus.subscribe(EventType.CONFIRM_REQUEST, on_runtime_event)
    orchestrator.event_bus.subscribe(EventType.EMERGENCY_STOP, on_runtime_event)
    orchestrator.event_bus.subscribe(EventType.TOOL_RESULT, on_runtime_event)
    orchestrator.event_bus.subscribe(EventType.ERROR, on_runtime_event)
    # loop_controller.set_response_callback REMOVED
    loop_controller.set_response_result_channel(response_result_channel)

    # Wire history and logs updates
    def update_ui_panels() -> None:
        """Update UI panels with current data."""
        try:
            # Update history from memory
            interactions = memory.get_recent_interactions(limit=20)
            history_text = "\n".join([
                f"[{i['timestamp']}] {i['source']}: {i['input_text'][:50]}... -> {i['response_text'][:50]}..."
                for i in interactions
            ])
            main_window.history_updated.emit(history_text)
            
            # Update logs from log file if available
            log_file = config.logging.file
            if log_file and Path(log_file).exists():
                main_window.load_logs(log_file)
        except Exception as e:
            logger.error(f"Failed to update UI panels: {e}")

    # PHASE B B5 FIX: Remove orchestrator callbacks (UI purification)
    # UI now observes via event stream only, no callbacks into kernel
    # orchestrator.set_callbacks REMOVED (no callback registration)
    # orchestrator.event_bus.subscribe REMOVED (UI observes via event stream only)

    # Wire UI signals
    main_window.message_sent.connect(on_user_input)
    # FIX: Use submit_text for emergency as normal event through pipeline (final architecture)
    main_window.emergency_stop_requested.connect(
        lambda: loop_controller.submit_text("emergency stop", source="ui_button")
    )
    # FIX: Connect tray emergency stop to submit_text (normal event through pipeline)
    tray.emergency_stop_requested.connect(
        lambda: loop_controller.submit_text("emergency stop", source="tray")
    )
    tray.open_section_requested.connect(main_window.navigate_to)

    # Periodic observer-only UI projections.
    ui_projection_timer = QTimer()
    ui_projection_timer.setInterval(1000)
    ui_projection_timer.timeout.connect(update_ui_panels)

    def publish_telemetry() -> None:
        try:
            health = loop_controller.get_health_status()
            metrics = loop_controller.get_metrics()
            telemetry = (
                f"queue_pressure={loop_controller.get_queue_pressure()}\n"
                f"queue_fill={loop_controller.get_queue_fill_ratio():.2f}\n"
                f"health={health.get('status', 'unknown')}\n"
                f"metrics_keys={list(metrics.keys())[:6]}"
            )
            main_window.telemetry_updated.emit(telemetry)
        except Exception as e:
            logger.error(f"Telemetry projection failed: {e}")

    telemetry_timer = QTimer()
    telemetry_timer.setInterval(1200)
    telemetry_timer.timeout.connect(publish_telemetry)

    # Start orchestrator
    orchestrator.start()

    # Start live loop controller
    loop_controller.start()
    logger.info("Live loop controller started")
    update_ui_panels()
    publish_telemetry()
    ui_projection_timer.start()
    telemetry_timer.start()

    # Run application
    logger.info("Application ready")

    try:
        exit_code = app.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        exit_code = 0
    finally:
        ui_projection_timer.stop()
        telemetry_timer.stop()
        loop_controller.stop()
        orchestrator.stop("shutdown")
        memory.shutdown()
        logger.info("Shutdown complete")

    return exit_code


def trigger_voice_input(audio_data: bytes, loop_controller: LiveLoopController, config) -> None:
    """
    Trigger voice input processing (manual trigger, no background loop).

    Args:
        audio_data: Raw audio data from microphone
        loop_controller: LiveLoopController instance
        config: Config instance

    This is a manual trigger function - does NOT run in background loop.
    Converts audio to text and sends to unified input layer via loop controller.
    """
    if not config.perception.enable_voice_input:
        logger.warning("Voice input disabled in config")
        return

    loop_controller.submit_voice(audio_data)


def trigger_screen_input(loop_controller: LiveLoopController, config) -> None:
    """
    Trigger screen input processing (manual trigger, no background loop).

    Args:
        loop_controller: LiveLoopController instance
        config: Config instance

    This is a manual trigger function - does NOT run in background loop.
    Captures screen state and sends to unified input layer via loop controller.
    """
    if not config.perception.enable_screen_input:
        logger.warning("Screen input disabled in config")
        return

    loop_controller.request_screen_capture()


if __name__ == "__main__":
    sys.exit(main())
