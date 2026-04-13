"""Sokol Windows Agent - Main entry point."""

import sys
from pathlib import Path

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

logger = get_logger("sokol.main")


def main() -> int:
    """Main entry point."""
    # Load configuration
    config = get_config()

    # Setup logging
    def ui_log_callback(log_line: str) -> None:
        """Forward logs to main window via signal."""
        if 'main_window' in locals() or 'main_window' in globals():
            try:
                main_window.log_received.emit(log_line)
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

    # Initialize UI
    app = SokolApp(config)
    app.initialize(sys.argv)

    main_window = MainWindow()
    app.set_main_window(main_window)

    tray = TrayIcon(main_window)
    app.set_tray(tray)

    # Wire UI to loop controller (unified input stream)
    def on_user_input(text: str) -> None:
        # UI widget already adds the message to display, so we don't add it again
        memory.add_message("user", text)
        # Submit through live loop controller
        loop_controller.submit_text(text)

    # Wire state change callback
    def on_state_change(state: AgentState) -> None:
        """Handle agent state changes."""
        main_window.state_changed.emit(state)
        tray.update_state(state)

    # Wire response callback
    def on_response(message: str) -> None:
        """Handle agent responses."""
        # ONLY emit signal, do not call UI methods directly
        main_window.response_received.emit(message)

    # Wire loop controller callbacks
    loop_controller.set_state_change_callback(on_state_change)
    loop_controller.set_response_callback(on_response)

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

    # Wire orchestrator callbacks (response and state only - input handled by UI signal)
    # Note: on_input is NOT set here to avoid double callback invocation
    # UI signal message_sent already calls on_user_input
    orchestrator.set_callbacks(
        on_input=None,  # Handled by UI signal to avoid duplication
        on_response=None, # Disable orchestrator direct callback to prevent double echo
        on_confirm=None,
        on_preprocess=None,
    )
    orchestrator.event_bus.subscribe(EventType.STATE_CHANGE, on_state_change)

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

    # Start orchestrator
    orchestrator.start()

    # Start live loop controller
    loop_controller.start()
    logger.info("Live loop controller started")

    # Run application
    logger.info("Application ready")

    try:
        exit_code = app.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        exit_code = 0
    finally:
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
