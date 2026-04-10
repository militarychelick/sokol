"""History widget for action history display."""

from datetime import datetime
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QListWidget, QListWidgetItem


class HistoryWidget(QWidget):
    """Action history display widget."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._list = QListWidget()
        layout.addWidget(self._list)

    def add_entry(
        self,
        action: str,
        tool: str,
        success: bool,
        timestamp: datetime | None = None,
    ) -> None:
        timestamp = timestamp or datetime.now()
        time_str = timestamp.strftime("%H:%M:%S")

        status = "â" if success else "â"
        color = "#4caf50" if success else "#f44336"

        item = QListWidgetItem(
            f"{status} [{time_str}] {tool}: {action}"
        )
        item.setForeground(Qt.GlobalColor.white if success else Qt.GlobalColor.red)

        self._list.insertItem(0, item)

        # Keep only last 100 entries
        while self._list.count() > 100:
            self._list.takeItem(self._list.count() - 1)

    def clear(self) -> None:
        self._list.clear()

    def count(self) -> int:
        return self._list.count()
