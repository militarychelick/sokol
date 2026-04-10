"""Sokol Windows Agent - Main entry point."""

import sys
from pathlib import Path

from sokol.core.config import get_config, reload_config
from sokol.core.types import AgentState, EventType
from sokol.observability.logging import get_logger, setup_logging
from sokol.runtime.orchestrator import Orchestrator
from sokol.safety.emergency import register_emergency_callback
from sokol.memory.manager import MemoryManager
from sokol.tools.registry import get_registry
from sokol.ui.app import SokolApp
from sokol.ui.main_window import MainWindow
from sokol.ui.tray import TrayIcon

logger = get_logger("sokol.main")


def main() -> int:
    """Main entry point."""
    # Load configuration
    config = get_config()

    # Setup logging
    setup_logging(
        level=config.logging.level,
        log_file=config.logging.file,
        max_size=config.logging.max_size,
        backup_count=config.logging.backup_count,
        use_json=config.logging.format == "json",
    )

    logger.info(f"Starting {config.agent.name} v0.1.0")

    # Initialize components
    orchestrator = Orchestrator(config)
    orchestrator.setup()

    # Initialize memory
    memory = MemoryManager()
    memory.start_session()
    memory.load_profile()

    # Initialize tools
    tool_registry = get_registry()
    logger.info(f"Tools registered: {len(tool_registry)}")

    # Register emergency stop callback
    register_emergency_callback(lambda reason: orchestrator.emergency_stop(reason))

    # Initialize UI
    app = SokolApp(config)
    app.initialize(sys.argv)

    main_window = MainWindow()
    app.set_main_window(main_window)

    tray = TrayIcon(main_window)
    app.set_tray(tray)

    # Wire UI to orchestrator
    def on_user_input(text: str) -> None:
        main_window.add_user_message(text)
        memory.add_message("user", text)
        # Process through orchestrator
        orchestrator.process_input(text)

    def on_response(text: str) -> None:
        main_window.add_assistant_message(text)
        memory.add_message("assistant", text)

    def on_state_change(event) -> None:
        state = orchestrator.state
        main_window.update_state(state)
        tray.update_state(state)

    orchestrator.set_callbacks(
        on_input=on_user_input,
        on_response=on_response,
    )
    orchestrator.event_bus.subscribe(EventType.STATE_CHANGE, on_state_change)

    # Wire UI signals
    main_window.message_sent.connect(on_user_input)
    main_window.emergency_stop_requested.connect(
        lambda: orchestrator.emergency_stop("ui_button")
    )

    # Start orchestrator
    orchestrator.start()

    # Run application
    logger.info("Application ready")

    try:
        exit_code = app.run()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
        exit_code = 0
    finally:
        orchestrator.stop("shutdown")
        memory.shutdown()
        logger.info("Shutdown complete")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
