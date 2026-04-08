# -*- coding: utf-8 -*-
"""
SOKOL v8.0 - Advanced App Control System
Direct API integration for Telegram, Steam, Discord
"""
import os
import json
import time
import threading
import subprocess
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from .automation import GUIAutomation, SmartLauncher
    AUTOMATION_AVAILABLE = True
except ImportError:
    AUTOMATION_AVAILABLE = False

class AppType(Enum):
    TELEGRAM = "telegram"
    STEAM = "steam"
    DISCORD = "discord"
    WHATSAPP = "whatsapp"
    VIBER = "viber"

@dataclass
class AppCommand:
    """Command for app control"""
    action: str  # send_message, open_chat, launch_game, etc
    params: Dict[str, Any]
    target_app: AppType
    timeout: int = 10

class TelegramBotAPI:
    """Telegram Bot API integration"""
    
    def __init__(self, bot_token: str = None):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
        
    def send_message(self, chat_id: str, text: str, parse_mode: str = None) -> bool:
        """Send message via Bot API"""
        if not self.api_url:
            return False
            
        try:
            url = f"{self.api_url}/sendMessage"
            data = {"chat_id": chat_id, "text": text}
            if parse_mode:
                data["parse_mode"] = parse_mode
                
            response = requests.post(url, json=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Telegram API error: {e}")
            return False
    
    def get_chat_id_by_username(self, username: str) -> Optional[str]:
        """Get chat ID by username (requires user to interact with bot first)"""
        # This would require maintaining a user database
        # For now, return None to fall back to automation
        return None

class TelegramDesktopAPI:
    """Telegram Desktop automation with improved control"""
    
    def __init__(self):
        self.process_name = "telegram"
        self.window_titles = ["Telegram Desktop", "Telegram", "AyuGram", "AyuGram Desktop", "AyuGram Max", "AyuGram MaxGround"]
        
    def is_running(self) -> bool:
        """Check if Telegram is running"""
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {self.process_name}.exe"],
                capture_output=True, text=True, timeout=5
            )
            return self.process_name in result.stdout
        except:
            return False
    
    def focus_telegram(self) -> bool:
        """Focus Telegram window with multiple methods"""
        if not self.is_running():
            return False
            
        # Method 1: Try window titles
        for title in self.window_titles:
            if AUTOMATION_AVAILABLE:
                success, _ = GUIAutomation.focus_window(title)
                if success:
                    time.sleep(0.5)
                    return True
        
        # Method 2: Try process-based focus
        try:
            if AUTOMATION_AVAILABLE:
                from .tools import WindowFocuser
                success, _ = WindowFocuser.bring_to_front(self.process_name)
                if success:
                    time.sleep(0.5)
                    return True
        except:
            pass
        
        return False
    
    def send_message(self, contact: str, message: str) -> Tuple[bool, str]:
        """Send message with improved reliability"""
        if not AUTOMATION_AVAILABLE:
            return False, "Automation not available"
            
        # Ensure Telegram is focused
        if not self.focus_telegram():
            return False, "Cannot focus Telegram"
        
        try:
            # Method 1: Try Ctrl+F search
            GUIAutomation.hotkey_telegram_jump_chat()
            time.sleep(1.0)
            
            # Type contact name
            ok, msg = GUIAutomation.type_unicode(contact)
            if not ok:
                return False, f"Failed to type contact: {msg}"
            
            time.sleep(1.5)
            
            # Press Enter to select contact
            GUIAutomation.low_level_press(0x0D)
            time.sleep(1.0)
            
            # Type message
            ok, msg = GUIAutomation.type_unicode(message)
            if not ok:
                return False, f"Failed to type message: {msg}"
            
            time.sleep(0.5)
            
            # Send message
            GUIAutomation.low_level_press(0x0D)
            time.sleep(0.5)
            
            return True, f"Message sent to {contact}"
            
        except Exception as e:
            return False, f"Error sending message: {e}"
    
    def get_active_chat(self) -> Optional[str]:
        """Get current active chat name (if possible)"""
        # This would require OCR or window text extraction
        # For now, return None
        return None

class SteamAPI:
    """Steam API and automation integration"""
    
    def __init__(self):
        self.process_name = "steam"
        self.window_title = "Steam"
        
    def is_running(self) -> bool:
        """Check if Steam is running"""
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {self.process_name}.exe"],
                capture_output=True, text=True, timeout=5
            )
            return self.process_name in result.stdout
        except:
            return False
    
    def launch_game(self, game_name: str) -> Tuple[bool, str]:
        """Launch game by name"""
        try:
            # Method 1: Try steam:// protocol
            steam_url = f"steam://run/{game_name}"
            os.startfile(steam_url)
            return True, f"Launching {game_name} via Steam"
        except Exception as e:
            # Method 2: Focus Steam and search
            if AUTOMATION_AVAILABLE:
                if not self.is_running():
                    SmartLauncher.launch("steam")
                    time.sleep(3)
                
                if GUIAutomation.focus_window(self.window_title)[0]:
                    # Search for game
                    GUIAutomation.hotkey_telegram_jump_chat()  # Ctrl+F
                    time.sleep(1.0)
                    
                    ok, msg = GUIAutomation.type_unicode(game_name)
                    if ok:
                        time.sleep(2.0)
                        GUIAutomation.low_level_press(0x0D)  # Enter
                        return True, f"Searching for {game_name} in Steam"
            
            return False, f"Failed to launch {game_name}: {e}"
    
    def get_games_list(self) -> List[str]:
        """Get list of installed games (requires Steam API key)"""
        # This would require Steam Web API key
        # For now, return empty list
        return []

class DiscordAPI:
    """Discord automation integration"""
    
    def __init__(self):
        self.process_name = "discord"
        self.window_titles = ["Discord", "Discord Canary"]
        
    def is_running(self) -> bool:
        """Check if Discord is running"""
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {self.process_name}.exe"],
                capture_output=True, text=True, timeout=5
            )
            return self.process_name in result.stdout
        except:
            return False
    
    def send_message(self, channel: str, message: str) -> Tuple[bool, str]:
        """Send message to Discord channel"""
        if not AUTOMATION_AVAILABLE:
            return False, "Automation not available"
            
        try:
            # Focus Discord
            focused = False
            for title in self.window_titles:
                success, _ = GUIAutomation.focus_window(title)
                if success:
                    focused = True
                    break
            
            if not focused:
                return False, "Cannot focus Discord"
            
            # Navigate to channel (Ctrl+K)
            GUIAutomation.hotkey_telegram_jump_chat()  # Ctrl+F/Ctrl+K
            time.sleep(1.0)
            
            # Type channel name
            ok, msg = GUIAutomation.type_unicode(channel)
            if not ok:
                return False, f"Failed to type channel: {msg}"
            
            time.sleep(1.5)
            GUIAutomation.low_level_press(0x0D)  # Enter
            time.sleep(1.0)
            
            # Type message
            ok, msg = GUIAutomation.type_unicode(message)
            if not ok:
                return False, f"Failed to type message: {msg}"
            
            time.sleep(0.5)
            GUIAutomation.low_level_press(0x0D)  # Enter
            
            return True, f"Message sent to #{channel}"
            
        except Exception as e:
            return False, f"Error sending Discord message: {e}"

class AppController:
    """Universal app controller"""
    
    def __init__(self):
        self.telegram_bot = TelegramBotAPI()
        self.telegram_desktop = TelegramDesktopAPI()
        self.steam = SteamAPI()
        self.discord = DiscordAPI()
        
    def execute_command(self, command: AppCommand) -> Tuple[bool, str]:
        """Execute app command"""
        try:
            if command.target_app == AppType.TELEGRAM:
                return self._handle_telegram(command)
            elif command.target_app == AppType.STEAM:
                return self._handle_steam(command)
            elif command.target_app == AppType.DISCORD:
                return self._handle_discord(command)
            else:
                return False, f"Unsupported app: {command.target_app}"
        except Exception as e:
            return False, f"Command execution error: {e}"
    
    def _handle_telegram(self, command: AppCommand) -> Tuple[bool, str]:
        """Handle Telegram commands"""
        if command.action == "send_message":
            contact = command.params.get("contact", "")
            message = command.params.get("message", "")
            
            # Try Bot API first (if available)
            if self.telegram_bot.bot_token:
                chat_id = self.telegram_bot.get_chat_id_by_username(contact)
                if chat_id:
                    success = self.telegram_bot.send_message(chat_id, message)
                    if success:
                        return True, f"Message sent via Bot API"
            
            # Fall back to desktop automation
            return self.telegram_desktop.send_message(contact, message)
        
        return False, f"Unsupported Telegram action: {command.action}"
    
    def _handle_steam(self, command: AppCommand) -> Tuple[bool, str]:
        """Handle Steam commands"""
        if command.action == "launch_game":
            game_name = command.params.get("game", "")
            return self.steam.launch_game(game_name)
        
        return False, f"Unsupported Steam action: {command.action}"
    
    def _handle_discord(self, command: AppCommand) -> Tuple[bool, str]:
        """Handle Discord commands"""
        if command.action == "send_message":
            channel = command.params.get("channel", "")
            message = command.params.get("message", "")
            return self.discord.send_message(channel, message)
        
        return False, f"Unsupported Discord action: {command.action}"
    
    def get_app_status(self, app_type: AppType) -> Dict[str, Any]:
        """Get app status"""
        status = {
            "running": False,
            "focused": False,
            "available": False
        }
        
        if app_type == AppType.TELEGRAM:
            status["running"] = self.telegram_desktop.is_running()
            status["available"] = bool(self.telegram_bot.bot_token) or status["running"]
        elif app_type == AppType.STEAM:
            status["running"] = self.steam.is_running()
            status["available"] = status["running"]
        elif app_type == AppType.DISCORD:
            status["running"] = self.discord.is_running()
            status["available"] = status["running"]
        
        return status


# Global instance
_app_controller = None

def get_app_controller() -> AppController:
    """Get global app controller instance"""
    global _app_controller
    if _app_controller is None:
        _app_controller = AppController()
    return _app_controller


# Convenience functions
def send_telegram_message(contact: str, message: str) -> Tuple[bool, str]:
    """Send Telegram message"""
    controller = get_app_controller()
    command = AppCommand(
        action="send_message",
        params={"contact": contact, "message": message},
        target_app=AppType.TELEGRAM
    )
    return controller.execute_command(command)

def launch_steam_game(game_name: str) -> Tuple[bool, str]:
    """Launch Steam game"""
    controller = get_app_controller()
    command = AppCommand(
        action="launch_game", 
        params={"game": game_name},
        target_app=AppType.STEAM
    )
    return controller.execute_command(command)

def send_discord_message(channel: str, message: str) -> Tuple[bool, str]:
    """Send Discord message"""
    controller = get_app_controller()
    command = AppCommand(
        action="send_message",
        params={"channel": channel, "message": message},
        target_app=AppType.DISCORD
    )
    return controller.execute_command(command)
