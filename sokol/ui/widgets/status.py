"""Status indicator widget."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout
from PyQt6.QtGui import QColor

from sokol.core.types import AgentState


class StatusWidget(QWidget):
    """Agent status indicator."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current_state = AgentState.IDLE
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        # Status indicator (colored dot)
        self._indicator = QLabel("â¬¤")
        self._indicator.setStyleSheet("font-size: 20px; color: #4caf50;")
        layout.addWidget(self._indicator)

        # Status text
        self._status_text = QLabel("Idle")
        layout.addWidget(self._status_text)
        layout.addStretch()

    def update_state(self, state: AgentState) -> None:
        self._current_state = state

        state_info = {
            AgentState.IDLE: ("#4caf50", "Idle - Ready"),
            AgentState.LISTENING: ("#2196f3", "Listening..."),
            AgentState.THINKING: ("#ff9800", "Thinking..."),
            AgentState.EXECUTING: ("#ff5722", "Executing..."),
            AgentState.WAITING_CONFIRM: ("#9c27b0", "Waiting for confirmation"),
            AgentState.ERROR: ("#f44336", "Error"),
        }

        color, text = state_info.get(state, ("#ffffff", state.value))
        self._indicator.setStyleSheet(f"font-size: 20px; color: {color};")
        self._status_text.setText(text)
