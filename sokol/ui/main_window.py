"""Main window with chat interface and panels."""

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
    QTabWidget,
    QMenuBar,
    QMenu,
    QDialog,
    QFormLayout,
    QSpinBox,
    QComboBox,
    QCheckBox,
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
    response_received = pyqtSignal(str)
    state_changed = pyqtSignal(object)
    log_received = pyqtSignal(str)
    history_updated = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()

        self._config = get_config()
        self._current_state = AgentState.IDLE

        self._setup_ui()
        self._setup_menu()
        self._connect_signals()

        logger.info("Main window created")

    def _setup_ui(self) -> None:
        """Setup UI components."""
        # Window properties
        self.setWindowTitle(self._config.agent.name)
        self.setMinimumSize(400, 500)
        self.resize(800, 700)

        # Central widget with tabs
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Status bar
        self._status_label = QLabel(self._get_status_text(AgentState.IDLE))
        self._status_label.setStyleSheet(
            "padding: 4px; background-color: #2d2d2d; border-radius: 4px;"
        )
        layout.addWidget(self._status_label)

        # Tab widget
        self._tab_widget = QTabWidget()
        self._tab_widget.setStyleSheet(
            "QTabWidget::pane { border: 1px solid #3d3d3d; }"
            "QTabBar::tab { background-color: #2d2d2d; color: white; padding: 8px; }"
            "QTabBar::tab:selected { background-color: #0078d4; }"
        )

        # Chat tab
        self._chat_tab = QWidget()
        chat_layout = QVBoxLayout(self._chat_tab)
        
        self._chat_history = QTextEdit()
        self._chat_history.setReadOnly(True)
        self._chat_history.setStyleSheet(
            "background-color: #1e1e1e; border: none; border-radius: 4px;"
        )
        chat_layout.addWidget(self._chat_history, stretch=1)

        # Input area in chat tab
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

        chat_layout.addLayout(input_layout)

        self._tab_widget.addTab(self._chat_tab, "Chat")

        # History tab
        self._history_tab = QWidget()
        history_layout = QVBoxLayout(self._history_tab)
        
        self._history_viewer = QTextEdit()
        self._history_viewer.setReadOnly(True)
        self._history_viewer.setStyleSheet(
            "background-color: #1e1e1e; border: none; border-radius: 4px;"
        )
        self._history_viewer.setPlaceholderText("History viewer - shows past sessions")
        history_layout.addWidget(self._history_viewer, stretch=1)

        self._tab_widget.addTab(self._history_tab, "History")

        # Logs tab
        self._logs_tab = QWidget()
        logs_layout = QVBoxLayout(self._logs_tab)
        
        self._logs_viewer = QTextEdit()
        self._logs_viewer.setReadOnly(True)
        self._logs_viewer.setStyleSheet(
            "background-color: #1e1e1e; border: none; border-radius: 4px; font-family: monospace; font-size: 10px;"
        )
        self._logs_viewer.setPlaceholderText("Logs viewer - shows system logs")
        logs_layout.addWidget(self._logs_viewer, stretch=1)

        self._tab_widget.addTab(self._logs_tab, "Logs")

        layout.addWidget(self._tab_widget, stretch=1)

        # Apply dark theme
        self.setStyleSheet(
            "QMainWindow { background-color: #1e1e1e; color: #ffffff; }"
            "QLabel { color: #ffffff; }"
            "QLineEdit { color: #ffffff; }"
            "QTextEdit { color: #ffffff; }"
            "QPushButton { color: #ffffff; }"
            "QPushButton:hover { background-color: #404040; }"
            "QTabWidget { color: #ffffff; }"
            "QMenuBar { background-color: #2d2d2d; color: white; }"
            "QMenu { background-color: #2d2d2d; color: white; }"
        )

    def _setup_menu(self) -> None:
        """Setup menu bar."""
        menubar = self.menuBar()
        menubar.setStyleSheet("QMenuBar { background-color: #2d2d2d; color: white; }")

        # Settings menu
        settings_menu = menubar.addMenu("Settings")
        
        settings_action = settings_menu.addAction("Preferences")
        settings_action.triggered.connect(self._show_settings_dialog)

        # View menu
        view_menu = menubar.addMenu("View")
        
        view_menu.addAction("Chat").triggered.connect(lambda: self._tab_widget.setCurrentIndex(0))
        view_menu.addAction("History").triggered.connect(lambda: self._tab_widget.setCurrentIndex(1))
        view_menu.addAction("Logs").triggered.connect(lambda: self._tab_widget.setCurrentIndex(2))

    def _show_settings_dialog(self) -> None:
        """Show settings dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Sokol Settings")
        dialog.setMinimumSize(400, 300)
        dialog.setStyleSheet(
            "QDialog { background-color: #1e1e1e; color: white; }"
            "QLabel { color: white; }"
            "QSpinBox { color: white; }"
            "QComboBox { color: white; }"
            "QCheckBox { color: white; }"
        )

        layout = QFormLayout(dialog)

        # Response style
        response_style_combo = QComboBox()
        response_style_combo.addItems(["brief", "normal", "detailed"])
        response_style_combo.setCurrentText(self._config.agent.response_style)
        layout.addRow("Response Style:", response_style_combo)

        # Voice enabled
        voice_enabled = QCheckBox()
        voice_enabled.setChecked(self._config.perception.enable_voice_input if hasattr(self._config, 'perception') else False)
        layout.addRow("Voice Input:", voice_enabled)

        # Confirm dangerous
        confirm_dangerous = QCheckBox()
        confirm_dangerous.setChecked(self._config.safety.confirm_dangerous)
        layout.addRow("Confirm Dangerous:", confirm_dangerous)

        # Buttons
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(dialog.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addRow(button_layout)

        dialog.exec()

    def _connect_signals(self) -> None:
        """Connect signals."""
        self._send_button.clicked.connect(self._on_send)
        self.response_received.connect(self.add_assistant_message)
        self.state_changed.connect(self.update_state)
        self.log_received.connect(self.append_log)
        self.history_updated.connect(self.update_history)

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

    def append_log(self, log_line: str) -> None:
        """Append a single log line to logs viewer (for real-time UI logging)."""
        self._logs_viewer.append(log_line)
        # Auto-scroll to bottom
        cursor = self._logs_viewer.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._logs_viewer.setTextCursor(cursor)

    def update_history(self, history_data: str) -> None:
        """Update history viewer with data."""
        try:
            if history_data is None:
                history_data = ""
            self._history_viewer.setText(history_data)
        except Exception as e:
            logger.error(f"Failed to update history: {e}")
            self._history_viewer.setText(f"Error loading history: {e}")

    def update_logs(self, log_data: str) -> None:
        """Update logs viewer with data."""
        self._logs_viewer.setText(log_data)

    def load_logs(self, log_path: str, max_lines: int = 1000) -> None:
        """Load last N lines from log file into logs viewer (tail-based to prevent OOM)."""
        try:
            from collections import deque
            with open(log_path, 'r', encoding='utf-8') as f:
                # Read only last N lines to prevent memory issues
                last_lines = deque(f, maxlen=max_lines)
                log_content = ''.join(last_lines)
                self._logs_viewer.setText(log_content)
        except Exception as e:
            self._logs_viewer.setText(f"Failed to load logs: {str(e)}")

    def closeEvent(self, event) -> None:
        """Handle window close."""
        if self._config.ui.tray_icon:
            # Hide to tray instead of closing
            event.ignore()
            self.hide()
        else:
            event.accept()
