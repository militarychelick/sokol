"""QApplication wrapper."""

import sys
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from sokol.core.config import Config, get_config
from sokol.observability.logging import get_logger

logger = get_logger("sokol.ui.app")


class SokolApp:
    """Main application wrapper."""

    _instance: "SokolApp | None" = None

    def __init__(self, config: Config | None = None) -> None:
        if SokolApp._instance is not None:
            raise RuntimeError("SokolApp is a singleton")

        SokolApp._instance = self
        self._config = config or get_config()
        self._app: QApplication | None = None
        self._main_window = None
        self._tray = None

    @classmethod
    def get_instance(cls) -> "SokolApp":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize(self, argv: list[str] | None = None) -> None:
        """Initialize application."""
        argv = argv or sys.argv

        # Enable high DPI scaling
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

        self._app = QApplication(argv)
        self._app.setApplicationName(self._config.agent.name)
        self._app.setApplicationVersion("0.1.0")
        self._app.setQuitOnLastWindowClosed(not self._config.ui.tray_icon)

        logger.info("Application initialized")

    def set_main_window(self, window: Any) -> None:
        """Set main window."""
        self._main_window = window

    def set_tray(self, tray: Any) -> None:
        """Set system tray icon."""
        self._tray = tray

    def run(self) -> int:
        """Run application event loop."""
        if not self._app:
            self.initialize()

        logger.info("Starting application event loop")

        # Show main window if configured
        if self._main_window and self._config.ui.show_on_startup:
            if self._config.ui.start_minimized:
                self._main_window.hide()
            else:
                self._main_window.show()

        return self._app.exec()

    def quit(self) -> None:
        """Quit application."""
        if self._app:
            self._app.quit()

    def get_qapp(self) -> QApplication:
        """Get underlying QApplication."""
        if not self._app:
            raise RuntimeError("Application not initialized")
        return self._app
