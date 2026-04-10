"""
Settings widget - Configuration panel
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QLabel


class SettingsWidget(QWidget):
    """Widget for settings configuration."""
    
    def __init__(self) -> None:
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self) -> None:
        """Setup settings widget."""
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Settings"))
        
        # Add setting fields as needed
        self.llm_api_key = QLineEdit()
        self.llm_api_key.setPlaceholderText("OpenAI API Key")
        layout.addWidget(self.llm_api_key)
