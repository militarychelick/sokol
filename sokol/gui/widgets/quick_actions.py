"""
Quick actions widget - Quick action buttons
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton


class QuickActionsWidget(QWidget):
    """Widget with quick action buttons."""
    
    def __init__(self) -> None:
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self) -> None:
        """Setup quick actions widget."""
        layout = QVBoxLayout(self)
        
        # Quick action buttons
        self.launch_browser = QPushButton("Open Browser")
        layout.addWidget(self.launch_browser)
        
        self.launch_notepad = QPushButton("Open Notepad")
        layout.addWidget(self.launch_notepad)
