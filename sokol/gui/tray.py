"""
System tray icon
"""

from typing import Any

from PyQt6.QtWidgets import QSystemTrayIcon, QMenu
from PyQt6.QtGui import QAction, QIcon


class TrayIcon:
    """System tray icon for Sokol."""
    
    def __init__(self, agent: Any) -> None:
        self.agent = agent
        self.tray: QSystemTrayIcon | None = None
    
    def setup(self) -> None:
        """Setup system tray icon."""
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(QIcon())
        
        # Create menu
        menu = QMenu()
        
        show_action = QAction("Show", None)
        show_action.triggered.connect(self.show_window)
        menu.addAction(show_action)
        
        quit_action = QAction("Quit", None)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)
        
        self.tray.setContextMenu(menu)
        self.tray.show()
    
    def show_window(self) -> None:
        """Show main window."""
        if self.agent and hasattr(self.agent, "gui"):
            self.agent.gui.show()
    
    def quit_app(self) -> None:
        """Quit application."""
        if self.agent:
            self.agent.shutdown()
