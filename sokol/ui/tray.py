"""System tray icon."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import QSystemTrayIcon, QMenu

from sokol.core.config import get_config
from sokol.core.constants import (
    TRAY_TOOLTIP_IDLE,
    TRAY_TOOLTIP_LISTENING,
    TRAY_TOOLTIP_THINKING,
    TRAY_TOOLTIP_EXECUTING,
    TRAY_TOOLTIP_ERROR,
)
from sokol.core.types import AgentState
from sokol.observability.logging import get_logger

logger = get_logger("sokol.ui.tray")


class TrayIcon(QSystemTrayIcon):
    """System tray icon with menu."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._config = get_config()
        self._current_state = AgentState.IDLE

        self._setup_icon()
        self._setup_menu()

        logger.info("Tray icon created")

    def _setup_icon(self) -> None:
        """Setup tray icon."""
        # Create a simple icon (colored circle)
        from PyQt6.QtGui import QPixmap, QPainter, QColor, QBrush

        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw circle
        painter.setBrush(QBrush(QColor("#4caf50")))  # Green for idle
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(4, 4, 56, 56)

        # Draw "S" letter
        painter.setPen(QColor("#ffffff"))
        font = painter.font()
        font.setPointSize(32)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "S")

        painter.end()

        self.setIcon(QIcon(pixmap))
        self.setToolTip(TRAY_TOOLTIP_IDLE)
        self.setVisible(True)

    def _setup_menu(self) -> None:
        """Setup context menu."""
        menu = QMenu()

        # Show window action
        self._show_action = QAction("Show Window", self)
        self._show_action.triggered.connect(self._on_show)
        menu.addAction(self._show_action)

        menu.addSeparator()

        # Emergency stop action
        self._stop_action = QAction("Emergency Stop", self)
        self._stop_action.triggered.connect(self._on_emergency_stop)
        menu.addAction(self._stop_action)

        menu.addSeparator()

        # Quit action
        self._quit_action = QAction("Quit", self)
        self._quit_action.triggered.connect(self._on_quit)
        menu.addAction(self._quit_action)

        self.setContextMenu(menu)

    def _on_show(self) -> None:
        """Show main window."""
        if self.parent():
            self.parent().show()
            self.parent().activateWindow()

    def _on_emergency_stop(self) -> None:
        """Trigger emergency stop."""
        logger.warning("Emergency stop from tray")
        self.showMessage(
            self._config.agent.name,
            "Emergency stop triggered!",
            QSystemTrayIcon.MessageIcon.Warning,
            2000,
        )

    def _on_quit(self) -> None:
        """Quit application."""
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    def update_state(self, state: AgentState) -> None:
        """Update icon and tooltip based on state."""
        self._current_state = state

        # Update tooltip
        tooltip_map = {
            AgentState.IDLE: TRAY_TOOLTIP_IDLE,
            AgentState.LISTENING: TRAY_TOOLTIP_LISTENING,
            AgentState.THINKING: TRAY_TOOLTIP_THINKING,
            AgentState.EXECUTING: TRAY_TOOLTIP_EXECUTING,
            AgentState.ERROR: TRAY_TOOLTIP_ERROR,
        }
        self.setToolTip(tooltip_map.get(state, TRAY_TOOLTIP_IDLE))

        # Update icon color
        self._update_icon_color(state)

    def _update_icon_color(self, state: AgentState) -> None:
        """Update icon color based on state."""
        from PyQt6.QtGui import QPixmap, QPainter, QColor, QBrush

        color_map = {
            AgentState.IDLE: "#4caf50",  # Green
            AgentState.LISTENING: "#2196f3",  # Blue
            AgentState.THINKING: "#ff9800",  # Orange
            AgentState.EXECUTING: "#ff5722",  # Deep orange
            AgentState.WAITING_CONFIRM: "#9c27b0",  # Purple
            AgentState.ERROR: "#f44336",  # Red
        }
        color = color_map.get(state, "#4caf50")

        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(4, 4, 56, 56)

        painter.setPen(QColor("#ffffff"))
        font = painter.font()
        font.setPointSize(32)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "S")

        painter.end()

        self.setIcon(QIcon(pixmap))

    def show_notification(self, title: str, message: str) -> None:
        """Show notification balloon."""
        self.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 3000)
