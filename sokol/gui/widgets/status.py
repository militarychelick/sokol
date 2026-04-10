"""
Status widget - Agent status display
"""

from PyQt6.QtWidgets import QWidget, QLabel, QHBoxLayout


class StatusWidget(QWidget):
    """Widget displaying agent status."""
    
    def __init__(self) -> None:
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self) -> None:
        """Setup status widget."""
        layout = QHBoxLayout(self)
        
        self.status_label = QLabel("IDLE")
        layout.addWidget(self.status_label)
    
    def set_status(self, status: str) -> None:
        """Set status text."""
        self.status_label.setText(status)
