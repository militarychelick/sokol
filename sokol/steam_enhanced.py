# -*- coding: utf-8 -*-
"""
SOKOL v8.0 - Enhanced Steam Controller
Complete Steam automation with voice command support
"""
import os
import json
import time
import subprocess
import psutil
import requests
import webbrowser
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
import logging

from .config import VERSION, USER_HOME
from .automation import GUIAutomation
from .app_resolver import AppResolver

logger = logging.getLogger("sokol.steam_enhanced")


@dataclass
class SteamGame:
    """Steam game information"""
    app_id: int
    name: str
    installed: bool
    playing: bool
    last_played: Optional[str]
    playtime_forever: int
    playtime_2weeks: int
    size_on_disk: Optional[int]
    executable: Optional[str]


@dataclass
class SteamCommand:
    """Steam command structure"""
    command_type: str
    game_name: str
    app_id: Optional[int]
    params: Dict[str, Any]
    timestamp: datetime


class SteamAPI:
    """Steam Web API integration"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("STEAM_API_KEY", "")
        self.base_url = "https://store.steampowered.com/api"
        self.user_url = "https://api.steampowered.com"
        
    def search_game(self, query: str) -> List[Dict]:
        """Search for games in Steam store"""
        try:
            url = f"{self.base_url}/storesearch/"
            params = {
                "term": query,
                "l": "russian",  # Russian language
                "cc": "RU",      # Russia region
                "nr": 20         # Number of results
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get("items", [])
            else:
                logger.warning(f"Steam API search failed: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Steam API search error: {e}")
            return []
    
    def get_game_details(self, app_id: int) -> Optional[Dict]:
        """Get detailed game information"""
        try:
            url = f"{self.base_url}/appdetails/"
            params = {
                "appids": app_id,
                "l": "russian",
                "cc": "RU"
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                app_data = data.get(str(app_id), {})
                if app_data.get("success"):
                    return app_data.get("data")
            
            return None
            
        except Exception as e:
            logger.error(f"Steam API details error: {e}")
            return None
    
    def get_user_games(self, steam_id: str) -> List[Dict]:
        """Get user's game library"""
        if not self.api_key:
            return []
        
        try:
            url = f"{self.user_url}/IPlayerService/GetOwnedGames/v0001/"
            params = {
                "key": self.api_key,
                "steamid": steam_id,
                "format": "json",
                "include_appinfo": True,
                "include_played_free_games": True
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get("response", {}).get("games", [])
            
            return []
            
        except Exception as e:
            logger.error(f"Steam API user games error: {e}")
            return []


class SteamInstallation:
    """Steam installation detection and management"""
    
    def __init__(self):
        self.steam_paths = [
            os.path.join(os.environ.get("PROGRAMFILES", "C:\\Program Files"), "Steam"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"), "Steam"),
            "C:\\Steam",
            "D:\\Steam",
            "E:\\Steam"
        ]
        self.steam_exe = None
        self.library_folders = []
        self._detect_installation()
    
    def _detect_installation(self):
        """Detect Steam installation and library folders"""
        for path in self.steam_paths:
            steam_exe = os.path.join(path, "steam.exe")
            if os.path.exists(steam_exe):
                self.steam_exe = steam_exe
                self._detect_library_folders(path)
                break
    
    def _detect_library_folders(self, steam_path: str):
        """Detect Steam library folders"""
        libraryfolders_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
        
        if os.path.exists(libraryfolders_path):
            try:
                with open(libraryfolders_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Parse VDF format
                import re
                path_pattern = r'"path"\s+"([^"]+)"'
                matches = re.findall(path_pattern, content)
                
                self.library_folders = [path.strip('"') for path in matches if os.path.exists(path)]
                
            except Exception as e:
                logger.warning(f"Failed to parse libraryfolders.vdf: {e}")
        
        # Add default library folder
        default_library = os.path.join(steam_path, "steamapps")
        if default_library not in self.library_folders and os.path.exists(default_library):
            self.library_folders.append(default_library)
    
    def is_installed(self) -> bool:
        """Check if Steam is installed"""
        return self.steam_exe is not None
    
    def is_running(self) -> bool:
        """Check if Steam is running"""
        for proc in psutil.process_iter(['name']):
            if proc.info['name'] and 'steam.exe' in proc.info['name'].lower():
                return True
        return False
    
    def launch_steam(self) -> Tuple[bool, str]:
        """Launch Steam"""
        if not self.steam_exe:
            return False, "Steam not found"
        
        try:
            if self.is_running():
                return True, "Steam already running"
            
            subprocess.Popen([self.steam_exe], shell=True)
            
            # Wait for Steam to start
            for _ in range(30):  # Wait up to 30 seconds
                time.sleep(1)
                if self.is_running():
                    return True, "Steam launched successfully"
            
            return False, "Steam launch timeout"
            
        except Exception as e:
            return False, f"Failed to launch Steam: {e}"
    
    def get_installed_games(self) -> List[SteamGame]:
        """Get list of installed games"""
        games = []
        
        for library_folder in self.library_folders:
            apps_path = os.path.join(library_folder, "steamapps")
            
            if not os.path.exists(apps_path):
                continue
            
            # Look for .acf files (app manifest files)
            for filename in os.listdir(apps_path):
                if filename.startswith("appmanifest_") and filename.endswith(".acf"):
                    acf_path = os.path.join(apps_path, filename)
                    game = self._parse_acf_file(acf_path)
                    if game:
                        games.append(game)
        
        return games
    
    def _parse_acf_file(self, acf_path: str) -> Optional[SteamGame]:
        """Parse Steam app manifest file"""
        try:
            with open(acf_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Parse ACF format
            import re
            
            app_id_match = re.search(r'"appid"\s+"(\d+)"', content)
            name_match = re.search(r'"name"\s+"([^"]+)"', content)
            state_match = re.search(r'"state"\s+"(\d+)"', content)
            time_match = re.search(r'"time_last_played"\s+"(\d+)"', content)
            playtime_match = re.search(r'"playtime_forever"\s+"(\d+)"', content)
            
            if not app_id_match or not name_match:
                return None
            
            app_id = int(app_id_match.group(1))
            name = name_match.group(1)
            state = int(state_match.group(1)) if state_match else 0
            last_played = int(time_match.group(1)) if time_match else 0
            playtime = int(playtime_match.group(1)) if playtime_match else 0
            
            # Check if installed (state 4 = fully installed)
            installed = state == 4
            
            # Check if currently playing
            playing = self._is_game_running(app_id)
            
            # Format last played
            last_played_str = None
            if last_played > 0:
                last_played_dt = datetime.fromtimestamp(last_played)
                last_played_str = last_played_dt.strftime("%Y-%m-%d %H:%M")
            
            return SteamGame(
                app_id=app_id,
                name=name,
                installed=installed,
                playing=playing,
                last_played=last_played_str,
                playtime_forever=playtime,
                playtime_2weeks=0,  # Not available in ACF
                size_on_disk=None,
                executable=None
            )
            
        except Exception as e:
            logger.error(f"Failed to parse ACF file {acf_path}: {e}")
            return None
    
    def _is_game_running(self, app_id: int) -> bool:
        """Check if game is currently running"""
        # This is a simplified check - could be enhanced with Steam API
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info.get('cmdline', []))
                if str(app_id) in cmdline:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False


class EnhancedSteamController:
    """Enhanced Steam controller with voice command support"""
    
    def __init__(self):
        self.installation = SteamInstallation()
        self.api = SteamAPI()
        self.automation = GUIAutomation()
        self.app_resolver = AppResolver()
        self.games_cache = {}
        self.last_cache_update = None
        self.cache_duration = 300  # 5 minutes
        
        self.logger = logging.getLogger("sokol.steam_enhanced")
    
    def process_voice_command(self, command: str) -> Tuple[bool, str]:
        """Process voice command for Steam"""
        command_lower = command.lower().strip()
        
        # Launch Steam
        if any(word in command_lower for word in ["steam", "stim", "stim"]):
            if any(word in command_lower for word in ["otkroj", "zapusti", "launch", "start"]):
                return self.launch_steam()
            
            # Store/library
            elif any(word in command_lower for word in ["magazin", "store", "shop"]):
                return self.open_store()
            
            # Library
            elif any(word in command_lower for word in ["biblioteka", "library"]):
                return self.open_library()
        
        # Game commands
        return self._process_game_command(command_lower)
    
    def _process_game_command(self, command: str) -> Tuple[bool, str]:
        """Process game-specific commands"""
        # Extract game name
        game_name = self._extract_game_name(command)
        
        if not game_name:
            return False, "Game name not found in command"
        
        # Play/launch game
        if any(word in command for word in ["play", "start", "launch", "zapusti", "igrat"]):
            return self.launch_game(game_name)
        
        # Download/install game
        elif any(word in command for word in ["download", "install", "buy", "zagruz", "kupi"]):
            return self.download_game(game_name)
        
        # Search game
        elif any(word in command for word in ["search", "find", "poisk", "najdi"]):
            return self.search_game(game_name)
        
        # Game info
        elif any(word in command for word in ["info", "information", "informaciya"]):
            return self.get_game_info(game_name)
        
        return False, "Unknown game command"
    
    def _extract_game_name(self, command: str) -> Optional[str]:
        """Extract game name from command"""
        # Remove command words
        stop_words = [
            "play", "start", "launch", "zapusti", "igrat", "download", "install", 
            "buy", "zagruz", "kupi", "search", "find", "poisk", "najdi", "info",
            "information", "informaciya", "steam", "stim", "game", "igra"
        ]
        
        words = command.split()
        game_words = []
        
        for word in words:
            if word.lower() not in stop_words and len(word) > 2:
                game_words.append(word)
        
        if game_words:
            return " ".join(game_words).strip()
        
        return None
    
    def launch_steam(self) -> Tuple[bool, str]:
        """Launch Steam"""
        return self.installation.launch_steam()
    
    def launch_game(self, game_name: str) -> Tuple[bool, str]:
        """Launch specific game"""
        try:
            # Ensure Steam is running
            if not self.installation.is_running():
                success, msg = self.installation.launch_steam()
                if not success:
                    return False, f"Failed to launch Steam: {msg}"
                time.sleep(3)  # Wait for Steam to fully start
            
            # Get installed games
            games = self.get_installed_games()
            
            # Find game by name (fuzzy matching)
            game = self._find_game_by_name(games, game_name)
            
            if not game:
                return False, f"Game '{game_name}' not found or not installed"
            
            # Launch game using Steam protocol
            steam_url = f"steam://rungameid/{game.app_id}"
            
            try:
                webbrowser.open(steam_url)
                return True, f"Launching {game.name}"
            except Exception as e:
                return False, f"Failed to launch game: {e}"
                
        except Exception as e:
            return False, f"Error launching game: {e}"
    
    def download_game(self, game_name: str) -> Tuple[bool, str]:
        """Download/install game"""
        try:
            # Search for game in store
            search_results = self.api.search_game(game_name)
            
            if not search_results:
                return False, f"Game '{game_name}' not found in store"
            
            # Find best match
            best_match = self._find_best_store_match(search_results, game_name)
            
            if not best_match:
                return False, f"No matching game found for '{game_name}'"
            
            # Open store page
            store_url = f"https://store.steampowered.com/app/{best_match['id']}"
            
            try:
                webbrowser.open(store_url)
                return True, f"Opening store page for {best_match['name']}"
            except Exception as e:
                return False, f"Failed to open store page: {e}"
                
        except Exception as e:
            return False, f"Error downloading game: {e}"
    
    def search_game(self, game_name: str) -> Tuple[bool, str]:
        """Search for game in store"""
        try:
            search_results = self.api.search_game(game_name)
            
            if not search_results:
                return False, f"No games found for '{game_name}'"
            
            # Format results
            lines = [f"Found {len(search_results)} games for '{game_name}':\n"]
            
            for i, game in enumerate(search_results[:10], 1):
                name = game.get('name', 'Unknown')
                price = game.get('price', 'Free')
                review_score = game.get('review_score', 'N/A')
                
                lines.append(f"{i}. {name} - {price} - Reviews: {review_score}")
            
            return True, "\n".join(lines)
            
        except Exception as e:
            return False, f"Error searching game: {e}"
    
    def get_game_info(self, game_name: str) -> Tuple[bool, str]:
        """Get detailed game information"""
        try:
            # First check installed games
            games = self.get_installed_games()
            game = self._find_game_by_name(games, game_name)
            
            if game:
                return True, self._format_installed_game_info(game)
            
            # Search in store
            search_results = self.api.search_game(game_name)
            
            if not search_results:
                return False, f"Game '{game_name}' not found"
            
            best_match = self._find_best_store_match(search_results, game_name)
            
            if best_match:
                details = self.api.get_game_details(best_match['id'])
                if details:
                    return True, self._format_store_game_info(details)
            
            return False, f"Could not get information for '{game_name}'"
            
        except Exception as e:
            return False, f"Error getting game info: {e}"
    
    def open_store(self) -> Tuple[bool, str]:
        """Open Steam store"""
        try:
            webbrowser.open("https://store.steampowered.com/")
            return True, "Opening Steam store"
        except Exception as e:
            return False, f"Failed to open store: {e}"
    
    def open_library(self) -> Tuple[bool, str]:
        """Open Steam library"""
        try:
            webbrowser.open("steam://library")
            return True, "Opening Steam library"
        except Exception as e:
            return False, f"Failed to open library: {e}"
    
    def get_installed_games(self) -> List[SteamGame]:
        """Get cached list of installed games"""
        now = time.time()
        
        # Check cache
        if (self.last_cache_update and 
            now - self.last_cache_update < self.cache_duration and 
            self.games_cache):
            return list(self.games_cache.values())
        
        # Refresh cache
        games = self.installation.get_installed_games()
        
        # Update cache
        self.games_cache = {game.name.lower(): game for game in games}
        self.last_cache_update = now
        
        return games
    
    def _find_game_by_name(self, games: List[SteamGame], name: str) -> Optional[SteamGame]:
        """Find game by name with fuzzy matching"""
        name_lower = name.lower()
        
        # Exact match
        for game in games:
            if game.name.lower() == name_lower:
                return game
        
        # Partial match
        for game in games:
            if name_lower in game.name.lower() or game.name.lower() in name_lower:
                return game
        
        # Fuzzy matching
        from difflib import SequenceMatcher
        best_match = None
        best_score = 0
        
        for game in games:
            score = SequenceMatcher(None, name_lower, game.name.lower()).ratio()
            if score > best_score and score > 0.6:  # 60% similarity threshold
                best_score = score
                best_match = game
        
        return best_match
    
    def _find_best_store_match(self, results: List[Dict], name: str) -> Optional[Dict]:
        """Find best matching game in store results"""
        name_lower = name.lower()
        
        # Exact match
        for game in results:
            if game.get('name', '').lower() == name_lower:
                return game
        
        # Partial match
        for game in results:
            game_name = game.get('name', '').lower()
            if name_lower in game_name or game_name in name_lower:
                return game
        
        # Fuzzy matching
        from difflib import SequenceMatcher
        best_match = None
        best_score = 0
        
        for game in results:
            game_name = game.get('name', '').lower()
            score = SequenceMatcher(None, name_lower, game_name).ratio()
            if score > best_score and score > 0.6:
                best_score = score
                best_match = game
        
        return best_match
    
    def _format_installed_game_info(self, game: SteamGame) -> str:
        """Format installed game information"""
        lines = [
            f"Game: {game.name}",
            f"App ID: {game.app_id}",
            f"Status: {'Playing' if game.playing else 'Installed' if game.installed else 'Not installed'}",
            f"Playtime: {game.playtime_forever // 60}h {game.playtime_forever % 60}m"
        ]
        
        if game.last_played:
            lines.append(f"Last played: {game.last_played}")
        
        if game.size_on_disk:
            size_gb = game.size_on_disk / (1024 * 1024 * 1024)
            lines.append(f"Size: {size_gb:.1f} GB")
        
        return "\n".join(lines)
    
    def _format_store_game_info(self, game_data: Dict) -> str:
        """Format store game information"""
        name = game_data.get('name', 'Unknown')
        description = game_data.get('short_description', 'No description')
        price = game_data.get('price_overview', {}).get('final_formatted', 'Free')
        release_date = game_data.get('release_date', {}).get('date', 'Unknown')
        
        lines = [
            f"Game: {name}",
            f"Price: {price}",
            f"Release Date: {release_date}",
            f"Description: {description[:200]}..."
        ]
        
        # Genres
        genres = game_data.get('genres', [])
        if genres:
            genre_names = [genre['description'] for genre in genres[:5]]
            lines.append(f"Genres: {', '.join(genre_names)}")
        
        return "\n".join(lines)
    
    def get_status(self) -> Dict[str, Any]:
        """Get Steam controller status"""
        return {
            "steam_installed": self.installation.is_installed(),
            "steam_running": self.installation.is_running(),
            "library_folders": len(self.installation.library_folders),
            "installed_games": len(self.get_installed_games()),
            "cache_valid": (self.last_cache_update and 
                          time.time() - self.last_cache_update < self.cache_duration),
            "api_available": bool(self.api.api_key)
        }


# Global enhanced steam controller instance
_enhanced_steam_controller: Optional[EnhancedSteamController] = None


def get_enhanced_steam_controller() -> EnhancedSteamController:
    """Get global enhanced steam controller instance"""
    global _enhanced_steam_controller
    if _enhanced_steam_controller is None:
        _enhanced_steam_controller = EnhancedSteamController()
    return _enhanced_steam_controller


if __name__ == "__main__":
    # Test enhanced steam controller
    print("Enhanced Steam Controller Test")
    print("==============================")
    
    controller = EnhancedSteamController()
    status = controller.get_status()
    
    print(f"Steam installed: {status['steam_installed']}")
    print(f"Steam running: {status['steam_running']}")
    print(f"Library folders: {status['library_folders']}")
    print(f"Installed games: {status['installed_games']}")
    
    if status['steam_installed']:
        print("\nTesting voice commands:")
        test_commands = [
            "launch steam",
            "play counter strike",
            "download gta",
            "search cyberpunk"
        ]
        
        for cmd in test_commands:
            print(f"\nCommand: {cmd}")
            success, result = controller.process_voice_command(cmd)
            print(f"Result: {success} - {result}")
