"""Main window with chat interface."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QLineEdit,
    QPushButton,
    QLabel,
    QSplitter,
)

from sokol.core.config import get_config
from sokol.core.types import AgentState
from sokol.observability.logging import get_logger

logger = get_logger("sokol.ui.main_window")


class MainWindow(QMainWindow):
    """Main application window."""

    # Signals
    message_sent = pyqtSignal(str)  # User sent a message
    emergency_stop_requested = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()

        self._config = get_config()
        self._current_state = AgentState.IDLE

        self._setup_ui()
        self._connect_signals()

        logger.info("Main window created")

    def _setup_ui(self) -> None:
        """Setup UI components."""
        # Window properties
        self.setWindowTitle(self._config.agent.name)
        self.setMinimumSize(400, 500)
        self.resize(600, 700)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        # Main layout
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Status bar
        self._status_label = QLabel(self._get_status_text(AgentState.IDLE))
        self._status_label.setStyleSheet(
            "padding: 4px; background-color: #2d2d2d; border-radius: 4px;"
        )
        layout.addWidget(self._status_label)

        # Chat history
        self._chat_history = QTextEdit()
        self._chat_history.setReadOnly(True)
        self._chat_history.setStyleSheet(
            "background-color: #1e1e1e; border: 1px solid #3d3d3d; border-radius: 4px;"
        )
        layout.addWidget(self._chat_history, stretch=1)

        # Input area
        input_layout = QHBoxLayout()

        self._input_field = QLineEdit()
        self._input_field.setPlaceholderText("Enter command...")
        self._input_field.setStyleSheet(
            "background-color: #2d2d2d; border: 1px solid #3d3d3d; "
            "border-radius: 4px; padding: 8px;"
        )
        self._input_field.returnPressed.connect(self._on_send)

        self._send_button = QPushButton("Send")
        self._send_button.setStyleSheet(
            "background-color: #0078d4; border: none; "
            "border-radius: 4px; padding: 8px 16px;"
        )

        self._emergency_button = QPushButton("STOP")
        self._emergency_button.setStyleSheet(
            "background-color: #d41a1a; border: none; "
            "border-radius: 4px; padding: 8px 16px; font-weight: bold;"
        )
        self._emergency_button.clicked.connect(self._on_emergency_stop)

        input_layout.addWidget(self._input_field, stretch=1)
        input_layout.addWidget(self._send_button)
        input_layout.addWidget(self._emergency_button)

        layout.addLayout(input_layout)

        # Apply dark theme
        self.setStyleSheet(
            "QMainWindow { background-color: #1e1e1e; color: #ffffff; }"
            "QLabel { color: #ffffff; }"
            "QLineEdit { color: #ffffff; }"
            "QTextEdit { color: #ffffff; }"
            "QPushButton { color: #ffffff; }"
            "QPushButton:hover { background-color: #404040; }"
        )

    def _connect_signals(self) -> None:
        """Connect signals."""
        self._send_button.clicked.connect(self._on_send)

    def _on_send(self) -> None:
        """Handle send button click."""
        text = self._input_field.text().strip()
        if text:
            self._add_message("user", text)
            self._input_field.clear()
            self.message_sent.emit(text)

    def _on_emergency_stop(self) -> None:
        """Handle emergency stop button."""
        self._add_message("system", "EMERGENCY STOP REQUESTED")
        self.emergency_stop_requested.emit()

    def _add_message(self, role: str, content: str) -> None:
        """Add message to chat history."""
        timestamp = self._get_timestamp()

        if role == "user":
            color = "#0078d4"
            prefix = "You"
        elif role == "assistant":
            color = "#4caf50"
            prefix = self._config.agent.name
        else:
            color = "#ff9800"
            prefix = "System"

        self._chat_history.append(
            f'<span style="color: {color}; font-weight: bold;">'
            f'[{timestamp}] {prefix}:</span> {content}'
        )

        # Scroll to bottom
        scrollbar = self._chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _get_timestamp(self) -> str:
        """Get current timestamp string."""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")

    def _get_status_text(self, state: AgentState) -> str:
        """Get status text for state."""
        status_map = {
            AgentState.IDLE: "Idle - Ready for commands",
            AgentState.LISTENING: "Listening for wake word...",
            AgentState.THINKING: "Thinking...",
            AgentState.EXECUTING: "Executing command...",
            AgentState.WAITING_CONFIRM: "Waiting for confirmation...",
            AgentState.ERROR: "Error - Check logs",
        }
        return status_map.get(state, f"State: {state.value}")

    def _get_status_color(self, state: AgentState) -> str:
        """Get status color for state."""
        color_map = {
            AgentState.IDLE: "#4caf50",
            AgentState.LISTENING: "#2196f3",
            AgentState.THINKING: "#ff9800",
            AgentState.EXECUTING: "#ff5722",
            AgentState.WAITING_CONFIRM: "#9c27b0",
            AgentState.ERROR: "#f44336",
        }
        return color_map.get(state, "#ffffff")

    # Public API

    def add_user_message(self, content: str) -> None:
        """Add user message to chat."""
        self._add_message("user", content)

    def add_assistant_message(self, content: str) -> None:
        """Add assistant message to chat."""
        self._add_message("assistant", content)

    def add_system_message(self, content: str) -> None:
        """Add system message to chat."""
        self._add_message("system", content)

    def update_state(self, state: AgentState) -> None:
        """Update agent state display."""
        self._current_state = state
        color = self._get_status_color(state)
        text = self._get_status_text(state)

        self._status_label.setText(text)
        self._status_label.setStyleSheet(
            f"padding: 4px; background-color: {color}; "
            f"border-radius: 4px; color: white; font-weight: bold;"
        )

    def set_input_enabled(self, enabled: bool) -> None:
        """Enable/disable input."""
        self._input_field.setEnabled(enabled)
        self._send_button.setEnabled(enabled)

    def clear_chat(self) -> None:
        """Clear chat history."""
        self._chat_history.clear()

    def closeEvent(self, event) -> None:
        """Handle window close."""
        if self._config.ui.tray_icon:
            # Hide to tray instead of closing
            event.ignore()
            self.hide()
        else:
            event.accept()
