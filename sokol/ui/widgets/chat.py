"""Chat widget for conversation display."""

from datetime import datetime
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLineEdit, QPushButton, QHBoxLayout


class ChatWidget(QWidget):
    """Chat interface widget."""

    message_sent = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Chat display
        self._display = QTextEdit()
        self._display.setReadOnly(True)
        layout.addWidget(self._display, stretch=1)

        # Input
        input_layout = QHBoxLayout()

        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a command...")
        self._input.returnPressed.connect(self._send)

        self._send_btn = QPushButton("Send")
        self._send_btn.clicked.connect(self._send)

        input_layout.addWidget(self._input, stretch=1)
        input_layout.addWidget(self._send_btn)
        layout.addLayout(input_layout)

    def _send(self) -> None:
        text = self._input.text().strip()
        if text:
            self.add_message("user", text)
            self._input.clear()
            self.message_sent.emit(text)

    def add_message(self, role: str, content: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {"user": "#0078d4", "assistant": "#4caf50", "system": "#ff9800"}
        names = {"user": "You", "assistant": "Sokol", "system": "System"}

        color = colors.get(role, "#ffffff")
        name = names.get(role, role.title())

        self._display.append(
            f'<span style="color: {color}; font-weight: bold;">'
            f'[{timestamp}] {name}:</span> {content}'
        )

        scrollbar = self._display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def clear(self) -> None:
        self._display.clear()

    def set_enabled(self, enabled: bool) -> None:
        self._input.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)
