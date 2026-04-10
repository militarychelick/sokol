"""
Main window - Control panel for Sokol
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QTextEdit,
    QLabel,
    QLineEdit,
    QTabWidget,
)

from ..core.config import Config


class MainWindow(QMainWindow):
    """Main control panel window."""
    
    def __init__(self, config: Config, agent: Any) -> None:
        super().__init__()
        self.config = config
        self.agent = agent
        self.setup_ui()
    
    def setup_ui(self) -> None:
        """Setup the main window UI."""
        self.setWindowTitle(f"Sokol v2 - {self.config.agent.name}")
        self.setGeometry(100, 100, self.config.gui.window_width, self.config.gui.window_height)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Status label
        self.status_label = QLabel("Status: IDLE")
        layout.addWidget(self.status_label)
        
        # Tab widget
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Log tab
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        tabs.addTab(log_tab, "Log")
        
        # Input tab
        input_tab = QWidget()
        input_layout = QVBoxLayout(input_tab)
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Type command...")
        self.send_button = QPushButton("Send")
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_button)
        tabs.addTab(input_tab, "Input")
        
        # Connect signals
        self.send_button.clicked.connect(self.send_command)
        self.input_field.returnPressed.connect(self.send_command)
    
    def update_status(self, status: str) -> None:
        """Update status label."""
        self.status_label.setText(f"Status: {status}")
    
    def add_log(self, message: str) -> None:
        """Add message to log."""
        self.log_text.append(message)
    
    def send_command(self) -> None:
        """Send command from input field."""
        text = self.input_field.text()
        if text:
            self.input_field.clear()
            # Submit to agent
            if self.agent:
                self.agent.text.submit_input(text)
