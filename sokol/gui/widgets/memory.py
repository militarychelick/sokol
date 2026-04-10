"""
Memory widget - Memory viewer
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLabel


class MemoryWidget(QWidget):
    """Widget for viewing memory data."""
    
    def __init__(self) -> None:
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self) -> None:
        """Setup memory widget."""
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Memory"))
        
        self.memory_text = QTextEdit()
        self.memory_text.setReadOnly(True)
        layout.addWidget(self.memory_text)
    
    def display_memory(self, memory_data: str) -> None:
        """Display memory data."""
        self.memory_text.setText(memory_data)
