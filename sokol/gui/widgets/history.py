"""
History widget - Action history log
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit


class HistoryWidget(QWidget):
    """Widget displaying action history."""
    
    def __init__(self) -> None:
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self) -> None:
        """Setup history widget."""
        layout = QVBoxLayout(self)
        
        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        layout.addWidget(self.history_text)
    
    def add_entry(self, action: str, result: str) -> None:
        """Add entry to history."""
        self.history_text.append(f"{action}: {result}")
