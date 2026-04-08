# -*- coding: utf-8 -*-
"""
SOKOL v8.0 - Voice Command System
Jarvis-like voice assistant with offline/online recognition
"""
import os
import json
import threading
import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime
import queue
import time

try:
    import speech_recognition as sr
    SPEECH_AVAILABLE = True
except ImportError:
    SPEECH_AVAILABLE = False
    sr = None

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    pyttsx3 = None

from .config import VERSION
from .dispatcher import ActionDispatcher
from .automation import GUIAutomation
from .app_controller import get_app_controller

logger = logging.getLogger("sokol.voice")


@dataclass
class VoiceCommand:
    """Voice command structure"""
    command: str
    action_type: str
    target: str
    params: Dict[str, Any]
    confidence: float
    timestamp: datetime


class VoiceRecognizer:
    """Speech recognition with multiple engines"""
    
    def __init__(self):
        self.recognizer = sr.Recognizer() if SPEECH_AVAILABLE else None
        self.microphone = None
        self.is_listening = False
        self.language = "ru-RU"
        self.alternative_language = "en-US"
        
        if SPEECH_AVAILABLE:
            try:
                self.microphone = sr.Microphone()
                # Calibrate for ambient noise
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=1)
            except Exception as e:
                logger.warning(f"Microphone initialization failed: {e}")
    
    def recognize_speech(self, timeout: int = 5) -> Optional[str]:
        """Recognize speech from microphone"""
        if not SPEECH_AVAILABLE or not self.microphone:
            return None
        
        try:
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=10)
            
            # Try Google Speech Recognition (online)
            try:
                text = self.recognizer.recognize_google(audio, language=self.language)
                return text
            except sr.UnknownValueError:
                # Try alternative language
                try:
                    text = self.recognizer.recognize_google(audio, language=self.alternative_language)
                    return text
                except sr.UnknownValueError:
                    return None
            except sr.RequestError:
                # Fallback to offline recognition if available
                return self._offline_recognition(audio)
                
        except Exception as e:
            logger.error(f"Speech recognition error: {e}")
            return None
    
    def _offline_recognition(self, audio) -> Optional[str]:
        """Offline speech recognition (placeholder for Vosk integration)"""
        # TODO: Integrate Vosk for offline recognition
        return None


class VoiceSynthesizer:
    """Text-to-speech with multiple engines"""
    
    def __init__(self):
        self.engine = None
        self.voice_enabled = TTS_AVAILABLE
        
        if TTS_AVAILABLE:
            try:
                self.engine = pyttsx3.init()
                # Configure voice
                voices = self.engine.getProperty('voices')
                # Try to find Russian voice
                for voice in voices:
                    if 'russian' in voice.languages[0].lower() or 'ru' in voice.id.lower():
                        self.engine.setProperty('voice', voice.id)
                        break
                
                self.engine.setProperty('rate', 150)  # Speed
                self.engine.setProperty('volume', 0.9)  # Volume
            except Exception as e:
                logger.warning(f"TTS initialization failed: {e}")
                self.voice_enabled = False
    
    def speak(self, text: str, blocking: bool = False):
        """Speak text using TTS"""
        if not self.voice_enabled or not self.engine:
            return
        
        try:
            if blocking:
                self.engine.say(text)
                self.engine.runAndWait()
            else:
                # Non-blocking speech in thread
                threading.Thread(target=self._speak_thread, args=(text,), daemon=True).start()
        except Exception as e:
            logger.error(f"TTS error: {e}")
    
    def _speak_thread(self, text: str):
        """Thread for non-blocking speech"""
        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception:
            pass


class VoiceCommandProcessor:
    """Process voice commands and convert to actions"""
    
    def __init__(self, dispatcher: ActionDispatcher):
        self.dispatcher = dispatcher
        self.app_controller = get_app_controller()
        
        # Command patterns
        self.command_patterns = {
            # Application control
            r"(?:otkroj|otkryt|zapusti|run|launch|start)\s+(.+?)\s*$": "app_launch",
            r"(?:zakroj|close|exit|quit)\s+(.+?)\s*$": "app_close",
            
            # Steam commands
            r"(?:steam|stim|stim)\s+(.+?)\s*$": "steam_command",
            r"(?:zagruz|download|install|buy)\s+(.+?)\s*$": "steam_download",
            r"(?:igrat|play|start)\s+(.+?)\s*$": "steam_play",
            
            # System commands
            r"(?:vkluch|include|enable|turn on)\s+(.+?)\s*$": "system_enable",
            r"(?:vykluch|disable|turn off)\s+(.+?)\s*$": "system_disable",
            r"(?:perestart|restart|reboot)\s+(.+?)\s*$": "system_restart",
            
            # Web commands
            r"(?:otkroj|open|navigate|go to)\s+(.+?)(?:\s+v\s+(.+))?$": "web_open",
            r"(?:poisk|search|find|google)\s+(.+?)\s*$": "web_search",
            
            # File commands
            r"(?:najdi|find|search)\s+(.+?)\s*(?:v\s+(.+))?$": "file_search",
            r"(?:sozdaj|create|make)\s+(.+?)\s*$": "file_create",
            r"(?:udali|delete|remove)\s+(.+?)\s*$": "file_delete",
            
            # Communication
            r"(?:napishi|write|send)\s+(.+?)\s+(.+?)\s*$": "messenger_send",
            r"(?:pozvoni|call|dial)\s+(.+?)\s*$": "phone_call",
            
            # Media
            r"(?:vkluch|play|start)\s+(?:muziku|music|song)\s*$": "music_play",
            r"(?:ostanov|stop|pause)\s+(?:muziku|music)\s*$": "music_stop",
            r"(?:sleduyushiy|next|next track)\s*$": "music_next",
            
            # Information
            r"(?:skazhi|tell|what|how)\s+(.+?)\s*$": "info_query",
            r"(?:pokazhi|show|display)\s+(.+?)\s*$": "info_show",
            r"(?:status|sostoyanie|state)\s+(.+?)\s*$": "status_query",
        }
    
    def process_command(self, text: str) -> Optional[VoiceCommand]:
        """Process voice text and convert to command"""
        import re
        
        text = text.lower().strip()
        
        for pattern, action_type in self.command_patterns.items():
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                if action_type == "app_launch":
                    return VoiceCommand(
                        command=text,
                        action_type="app_launch",
                        target=groups[0].strip(),
                        params={},
                        confidence=0.9,
                        timestamp=datetime.now()
                    )
                
                elif action_type == "steam_command":
                    return self._process_steam_command(groups[0].strip(), text)
                
                elif action_type == "messenger_send":
                    return VoiceCommand(
                        command=text,
                        action_type="messenger_send",
                        target=groups[0].strip(),
                        params={"message": groups[1].strip() if len(groups) > 1 else ""},
                        confidence=0.9,
                        timestamp=datetime.now()
                    )
                
                elif action_type == "web_open":
                    url = groups[0].strip()
                    if len(groups) > 1:
                        # Search query in browser
                        return VoiceCommand(
                            command=text,
                            action_type="web_search",
                            target=groups[1].strip(),
                            params={"browser": url},
                            confidence=0.9,
                            timestamp=datetime.now()
                        )
                    else:
                        return VoiceCommand(
                            command=text,
                            action_type="web_open",
                            target=url,
                            params={},
                            confidence=0.9,
                            timestamp=datetime.now()
                        )
                
                # Add more command types as needed
        
        return None
    
    def _process_steam_command(self, command: str, original_text: str) -> VoiceCommand:
        """Process Steam-specific commands"""
        command_lower = command.lower()
        
        # Game actions
        if any(word in command_lower for word in ["play", "start", "launch", "zapusti", "igrat"]):
            game_name = self._extract_game_name(command)
            return VoiceCommand(
                command=original_text,
                action_type="steam_play_game",
                target=game_name,
                params={},
                confidence=0.9,
                timestamp=datetime.now()
            )
        
        # Download/install
        elif any(word in command_lower for word in ["download", "install", "buy", "zagruz", "kupi"]):
            game_name = self._extract_game_name(command)
            return VoiceCommand(
                command=original_text,
                action_type="steam_download_game",
                target=game_name,
                params={},
                confidence=0.9,
                timestamp=datetime.now()
            )
        
        # Store/library
        elif any(word in command_lower for word in ["library", "store", "biblioteka", "magazin"]):
            return VoiceCommand(
                command=original_text,
                action_type="steam_open_store",
                target="store",
                params={},
                confidence=0.9,
                timestamp=datetime.now()
            )
        
        # Default: open Steam
        return VoiceCommand(
            command=original_text,
            action_type="app_launch",
            target="steam",
            params={},
            confidence=0.9,
            timestamp=datetime.now()
        )
    
    def _extract_game_name(self, text: str) -> str:
        """Extract game name from command"""
        # Remove command words and return game name
        stop_words = ["play", "start", "launch", "zapusti", "igrat", "download", "install", "buy", "zagruz", "kupi"]
        words = text.split()
        game_words = []
        
        for word in words:
            if word.lower() not in stop_words:
                game_words.append(word)
        
        return " ".join(game_words).strip()


class VoiceAssistant:
    """Main voice assistant - Jarvis-like interface"""
    
    def __init__(self, gui_instance=None):
        self.gui = gui_instance
        self.recognizer = VoiceRecognizer()
        self.synthesizer = VoiceSynthesizer()
        self.processor = VoiceCommandProcessor(None)  # Will be set later
        self.is_active = False
        self.is_listening = False
        self.wake_word = "sokol"
        self.alternative_wake_words = ["jarvis", "assistant", " Sokol"]
        self.command_queue = queue.Queue()
        self.response_queue = queue.Queue()
        
        # Thread management
        self.listen_thread = None
        self.process_thread = None
        self.stop_event = threading.Event()
        
        self.logger = logging.getLogger("sokol.voice_assistant")
    
    def initialize(self, dispatcher: ActionDispatcher):
        """Initialize with dispatcher"""
        self.processor = VoiceCommandProcessor(dispatcher)
    
    def start_listening(self):
        """Start continuous listening"""
        if self.is_active:
            return
        
        self.is_active = True
        self.stop_event.clear()
        
        # Start listening thread
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()
        
        # Start processing thread
        self.process_thread = threading.Thread(target=self._process_loop, daemon=True)
        self.process_thread.start()
        
        self.synthesizer.speak("Voice assistant activated. Say Sokol to wake me up.")
        self.logger.info("Voice assistant started")
    
    def stop_listening(self):
        """Stop voice assistant"""
        self.is_active = False
        self.stop_event.set()
        
        if self.listen_thread:
            self.listen_thread.join(timeout=2)
        if self.process_thread:
            self.process_thread.join(timeout=2)
        
        self.synthesizer.speak("Voice assistant deactivated.")
        self.logger.info("Voice assistant stopped")
    
    def _listen_loop(self):
        """Continuous listening loop"""
        while self.is_active and not self.stop_event.is_set():
            try:
                # Listen for wake word or command
                text = self.recognizer.recognize_speech(timeout=2)
                
                if text:
                    text_lower = text.lower().strip()
                    
                    # Check for wake word
                    if any(wake_word in text_lower for wake_word in [self.wake_word] + self.alternative_wake_words):
                        self.synthesizer.speak("Yes?")
                        self._listen_for_command()
                    
                    # Direct command (if wake word not detected but command is clear)
                    elif self._is_direct_command(text_lower):
                        self.command_queue.put(text)
                
            except Exception as e:
                self.logger.error(f"Listen loop error: {e}")
                time.sleep(1)
    
    def _listen_for_command(self):
        """Listen for command after wake word"""
        self.synthesizer.speak("Listening...")
        
        for _ in range(3):  # Try 3 times
            text = self.recognizer.recognize_speech(timeout=5)
            if text:
                self.command_queue.put(text)
                break
            time.sleep(0.5)
    
    def _is_direct_command(self, text: str) -> bool:
        """Check if text is a direct command without wake word"""
        direct_patterns = [
            "otkroj", "zapusti", "vkluch", "vkluchi", "skazhi", "pokazhi",
            "open", "launch", "start", "tell", "show", "play", "stop"
        ]
        return any(pattern in text for pattern in direct_patterns)
    
    def _process_loop(self):
        """Process commands from queue"""
        while self.is_active and not self.stop_event.is_set():
            try:
                # Get command from queue
                try:
                    text = self.command_queue.get(timeout=1)
                except queue.Empty:
                    continue
                
                self.logger.info(f"Processing voice command: {text}")
                
                # Process command
                command = self.processor.process_command(text)
                
                if command:
                    self.synthesizer.speak(f"Executing: {command.action_type}")
                    
                    # Execute command
                    success, result = self._execute_command(command)
                    
                    # Respond
                    if success:
                        response = self._format_success_response(command, result)
                        self.synthesizer.speak(response)
                    else:
                        response = self._format_error_response(command, result)
                        self.synthesizer.speak(response)
                else:
                    self.synthesizer.speak("I didn't understand that command.")
                
            except Exception as e:
                self.logger.error(f"Process loop error: {e}")
                self.synthesizer.speak("Sorry, I encountered an error.")
    
    def _execute_command(self, command: VoiceCommand) -> tuple[bool, str]:
        """Execute voice command"""
        try:
            if command.action_type == "app_launch":
                return self._execute_app_launch(command.target)
            
            elif command.action_type == "steam_play_game":
                return self._execute_steam_play(command.target)
            
            elif command.action_type == "steam_download_game":
                return self._execute_steam_download(command.target)
            
            elif command.action_type == "messenger_send":
                return self._execute_messenger_send(command.target, command.params.get("message", ""))
            
            elif command.action_type == "web_open":
                return self._execute_web_open(command.target)
            
            elif command.action_type == "web_search":
                return self._execute_web_search(command.target, command.params.get("browser", "chrome"))
            
            # Add more command types
            
        except Exception as e:
            self.logger.error(f"Command execution error: {e}")
            return False, str(e)
        
        return False, "Unknown command"
    
    def _execute_app_launch(self, app_name: str) -> tuple[bool, str]:
        """Launch application"""
        try:
            from .tools import SmartLauncher
            launcher = SmartLauncher()
            success, message = launcher.launch(app_name)
            return success, message
        except Exception as e:
            return False, str(e)
    
    def _execute_steam_play(self, game_name: str) -> tuple[bool, str]:
        """Launch Steam game"""
        try:
            # First ensure Steam is running
            success, _ = self._execute_app_launch("steam")
            if not success:
                return False, "Failed to launch Steam"
            
            # Launch game through app controller
            result = self.processor.app_controller.execute_command(
                "steam_launch_game", 
                {"target": game_name}
            )
            
            if result.get("success"):
                return True, f"Launching {game_name}"
            else:
                return False, result.get("message", "Failed to launch game")
                
        except Exception as e:
            return False, str(e)
    
    def _execute_steam_download(self, game_name: str) -> tuple[bool, str]:
        """Download Steam game"""
        try:
            result = self.processor.app_controller.execute_command(
                "steam_download_game",
                {"target": game_name}
            )
            
            if result.get("success"):
                return True, f"Downloading {game_name}"
            else:
                return False, result.get("message", "Failed to download game")
                
        except Exception as e:
            return False, str(e)
    
    def _execute_messenger_send(self, contact: str, message: str) -> tuple[bool, str]:
        """Send messenger message"""
        try:
            result = self.processor.app_controller.execute_command(
                "messenger_send",
                {"target": contact, "message": message}
            )
            
            if result.get("success"):
                return True, f"Message sent to {contact}"
            else:
                return False, result.get("message", "Failed to send message")
                
        except Exception as e:
            return False, str(e)
    
    def _execute_web_open(self, url: str) -> tuple[bool, str]:
        """Open website"""
        try:
            import webbrowser
            if not url.startswith(('http://', 'https://')):
                url = f'https://{url}'
            webbrowser.open(url)
            return True, f"Opening {url}"
        except Exception as e:
            return False, str(e)
    
    def _execute_web_search(self, query: str, browser: str = "chrome") -> tuple[bool, str]:
        """Search web"""
        try:
            import urllib.parse
            import webbrowser
            
            search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            webbrowser.open(search_url)
            return True, f"Searching for {query}"
        except Exception as e:
            return False, str(e)
    
    def _format_success_response(self, command: VoiceCommand, result: str) -> str:
        """Format success response"""
        responses = {
            "app_launch": "Application launched successfully",
            "steam_play_game": "Game is starting now",
            "steam_download_game": "Download started",
            "messenger_send": "Message sent",
            "web_open": "Website opened",
            "web_search": "Search completed"
        }
        
        base_response = responses.get(command.action_type, "Command completed")
        return f"{base_response}. {result}"
    
    def _format_error_response(self, command: VoiceCommand, error: str) -> str:
        """Format error response"""
        return f"Sorry, I couldn't {command.action_type.replace('_', ' ')}. {error}"
    
    def get_status(self) -> Dict[str, Any]:
        """Get voice assistant status"""
        return {
            "active": self.is_active,
            "listening": self.is_listening,
            "speech_available": SPEECH_AVAILABLE,
            "tts_available": TTS_AVAILABLE,
            "microphone_available": self.recognizer.microphone is not None,
            "queue_size": self.command_queue.qsize()
        }


# Global voice assistant instance
_voice_assistant: Optional[VoiceAssistant] = None


def get_voice_assistant(gui_instance=None) -> VoiceAssistant:
    """Get global voice assistant instance"""
    global _voice_assistant
    if _voice_assistant is None:
        _voice_assistant = VoiceAssistant(gui_instance)
    return _voice_assistant


def initialize_voice_assistant(gui_instance=None, dispatcher: ActionDispatcher = None) -> VoiceAssistant:
    """Initialize voice assistant with GUI and dispatcher"""
    assistant = get_voice_assistant(gui_instance)
    if dispatcher:
        assistant.initialize(dispatcher)
    return assistant


if __name__ == "__main__":
    # Test voice assistant
    print("SOKOL Voice Assistant Test")
    print("==========================")
    
    assistant = VoiceAssistant()
    print(f"Speech available: {SPEECH_AVAILABLE}")
    print(f"TTS available: {TTS_AVAILABLE}")
    print(f"Microphone: {assistant.recognizer.microphone is not None}")
    
    if SPEECH_AVAILABLE and TTS_AVAILABLE:
        assistant.synthesizer.speak("Voice assistant test complete")
        print("Test completed")
    else:
        print("Install speech_recognition and pyttsx3 for full functionality")
