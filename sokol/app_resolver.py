# -*- coding: utf-8 -*-
"""
SOKOL App Resolver — Smart application name resolution
v8.0: Web lookup via LLM for unknown applications
"""
import os
import json
import re
from typing import Optional, Dict, List, Tuple
from difflib import SequenceMatcher


class AppResolver:
    """
    Resolves application names to executable files.
    Uses local dictionary first, then queries LLM for unknown apps.
    """
    
    CACHE_FILE = os.path.join(os.path.expanduser("~"), ".sokol", "app_cache.json")
    CACHE_MAX_AGE_DAYS = 30
    
    # Common patterns for app executable names
    EXE_PATTERNS = {
        # Launchers
        "roblox": ["RobloxPlayerLauncher.exe", "RobloxPlayerBeta.exe"],
        "valorant": ["VALORANT-Win64-Shipping.exe", "RiotClientServices.exe"],
        "fortnite": ["FortniteClient-Win64-Shipping.exe", "EpicGamesLauncher.exe"],
        "apex": ["r5apex.exe", "EASteamLauncher.exe"],
        "pubg": ["TslGame.exe"],
        "cs2": ["cs2.exe", "Steam.exe"],
        "dota2": ["dota2.exe", "Steam.exe"],
        "lol": ["LeagueClient.exe"],
        "minecraft": ["MinecraftLauncher.exe", "minecraft.exe"],
        "gta5": ["GTA5.exe", "PlayGTAV.exe"],
        "overwatch": ["Overwatch.exe", "Overwatch Launcher.exe"],
        "wow": ["Wow.exe", "WoWClassic.exe"],
        "warzone": ["cod.exe", "Call of Duty HQ.exe"],
        "destiny2": ["destiny2.exe"],
        "rainbowsix": ["RainbowSix.exe", "RainbowSix_Vulkan.exe"],
        "eldenring": ["eldenring.exe", "start_protected_game.exe"],
        "witcher3": ["witcher3.exe"],
        "cyberpunk": ["Cyberpunk2077.exe", "REDprelauncher.exe"],
        "skyrim": ["SkyrimSE.exe", "SkyrimVR.exe"],
        "baldursgate3": ["bg3.exe", "LariLauncher.exe"],
        "stalker2": ["Stalker2.exe"],
        "hogwarts": ["HogwartsLegacy.exe"],
        "palworld": ["Palworld-Win64-Shipping.exe"],
        "valheim": ["valheim.exe"],
        "rust": ["RustClient.exe"],
        "ark": ["ShooterGame.exe"],
        "terraria": ["Terraria.exe"],
        "enshrouded": ["enshrouded.exe"],
        "satisfactory": ["FactoryGameSteam.exe", "FactoryGameEGS.exe"],
        "forza": ["ForzaHorizon5.exe", "ForzaMotorsport.exe"],
        "fifa": ["FC24.exe", "FC25.exe"],
        "nba2k": ["NBA2K24.exe", "NBA2K25.exe"],
        "rocketleague": ["RocketLeague.exe"],
        # Launchers
        "steam": ["Steam.exe"],
        "epic": ["EpicGamesLauncher.exe"],
        "gog": ["GalaxyClient.exe"],
        "ea": ["EADesktop.exe", "Origin.exe"],
        "ubisoft": ["Uplay.exe", "UbisoftConnect.exe"],
        "xbox": ["XboxApp.exe"],
        "tlauncher": ["TLauncher.exe"],
    }
    
    def __init__(self):
        self._cache = {}
        self._ensure_dir()
        self._load_cache()
    
    def _ensure_dir(self):
        """Ensure cache directory exists."""
        os.makedirs(os.path.dirname(self.CACHE_FILE), exist_ok=True)
    
    def _load_cache(self):
        """Load cached app lookups."""
        try:
            if os.path.exists(self.CACHE_FILE):
                with open(self.CACHE_FILE, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
        except Exception:
            self._cache = {}
    
    def _save_cache(self):
        """Save app lookup cache."""
        try:
            with open(self.CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def _get_cache_key(self, app_name: str) -> str:
        """Generate normalized cache key."""
        return app_name.lower().strip()
    
    def _is_in_cache(self, app_name: str) -> bool:
        """Check if app is in cache."""
        key = self._get_cache_key(app_name)
        return key in self._cache
    
    def _get_from_cache(self, app_name: str) -> Optional[Dict]:
        """Get cached app info."""
        key = self._get_cache_key(app_name)
        return self._cache.get(key)
    
    def _add_to_cache(self, app_name: str, exe_names: List[str], source: str = "llm"):
        """Add app to cache."""
        key = self._get_cache_key(app_name)
        self._cache[key] = {
            "exe_names": exe_names,
            "source": source,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }
        self._save_cache()
    
    def _similarity(self, a: str, b: str) -> float:
        """Calculate string similarity."""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    def _fuzzy_find_in_dict(self, app_name: str, dictionary: Dict[str, str], threshold: float = 0.7) -> Optional[str]:
        """Fuzzy search in dictionary."""
        name_lower = app_name.lower().strip()
        
        # Exact match
        if name_lower in dictionary:
            return dictionary[name_lower]
        
        # Contains match
        for key, value in dictionary.items():
            if name_lower in key or key in name_lower:
                return value
        
        # Similarity match
        best_match = None
        best_score = 0
        
        for key in dictionary:
            score = self._similarity(name_lower, key)
            if score > best_score and score >= threshold:
                best_score = score
                best_match = key
        
        if best_match:
            return dictionary[best_match]
        
        return None
    
    def resolve(self, app_name: str, llm_client=None) -> Tuple[List[str], str]:
        """
        Resolve app name to list of possible exe names.
        
        Returns:
            Tuple of (list of exe names, source description)
        """
        name_lower = app_name.lower().strip()
        
        # 1. Check EXE_PATTERNS (exact match)
        if name_lower in self.EXE_PATTERNS:
            return self.EXE_PATTERNS[name_lower], "built-in patterns"
        
        # 2. Check cache
        cached = self._get_from_cache(app_name)
        if cached:
            return cached["exe_names"], f"cache (from {cached.get('source', 'unknown')})"
        
        # 3. Check RUS_APP_MAP from config
        from ..config import RUS_APP_MAP
        mapped = self._fuzzy_find_in_dict(app_name, RUS_APP_MAP, threshold=0.8)
        if mapped:
            # Convert mapped name to common exe patterns
            if mapped in self.EXE_PATTERNS:
                return self.EXE_PATTERNS[mapped], f"RUS_APP_MAP → {mapped}"
            # Generic exe name
            return [f"{mapped}.exe", f"{mapped}64.exe"], f"RUS_APP_MAP → {mapped}"
        
        # 4. Query LLM for unknown apps (if client provided)
        if llm_client:
            exe_names = self._query_llm_for_exe(app_name, llm_client)
            if exe_names:
                self._add_to_cache(app_name, exe_names, source="llm")
                return exe_names, "LLM lookup"
        
        # 5. Fallback: generate likely exe names
        fallback_names = self._generate_fallback_names(app_name)
        return fallback_names, "generated fallback"
    
    def _query_llm_for_exe(self, app_name: str, llm_client) -> List[str]:
        """Query LLM for executable names of an application."""
        prompt = f"""What is the main executable file name (.exe) for the application "{app_name}" on Windows?

Respond ONLY with the executable filename(s), one per line.
If there are multiple common executables (like game + launcher), list them.
If this is a game distributed via Steam/Epic, include the launcher too.

Examples:
User: "roblox"
Response:
RobloxPlayerLauncher.exe
RobloxPlayerBeta.exe

User: "valorant"
Response:
VALORANT-Win64-Shipping.exe
RiotClientServices.exe

User: "{app_name}"
Response:"""
        
        try:
            response = llm_client.chat(prompt, one_shot=True)
            if response:
                # Parse response - extract exe names
                exe_names = []
                for line in response.strip().split('\n'):
                    line = line.strip()
                    # Clean up common LLM artifacts
                    line = re.sub(r'^[\s\-\d\.\)]*', '', line)  # Remove leading bullets/numbers
                    line = line.strip()
                    
                    if line.endswith('.exe'):
                        exe_names.append(line)
                    elif '.' not in line and ' ' not in line:
                        # Likely a process name without .exe
                        exe_names.append(f"{line}.exe")
                
                return exe_names if exe_names else None
        except Exception:
            pass
        
        return None
    
    def _generate_fallback_names(self, app_name: str) -> List[str]:
        """Generate likely exe names from app name."""
        name_clean = re.sub(r'[^\w\s]', '', app_name).strip()
        
        candidates = [
            f"{name_clean}.exe",
            f"{name_clean}64.exe",
            f"{name_clean}32.exe",
            f"{name_clean}Launcher.exe",
            f"{name_clean}Client.exe",
        ]
        
        # Remove duplicates while preserving order
        seen = set()
        result = []
        for c in candidates:
            key = c.lower()
            if key not in seen:
                seen.add(key)
                result.append(c)
        
        return result
    
    def find_in_system(self, app_name: str, llm_client=None) -> Optional[str]:
        """
        Resolve app name and search filesystem for the executable.
        
        Returns:
            Full path to executable if found, None otherwise
        """
        exe_names, source = self.resolve(app_name, llm_client)
        
        # Search common locations
        search_paths = [
            os.environ.get("PROGRAMFILES", "C:\\Program Files"),
            os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", ""),
            os.path.join(os.path.expanduser("~"), "Desktop"),
            "C:\\",
        ]
        
        for exe_name in exe_names:
            for base_path in search_paths:
                if not base_path or not os.path.exists(base_path):
                    continue
                
                # Quick search (limit depth for speed)
                result = self._quick_search(base_path, exe_name, max_depth=4)
                if result:
                    return result
        
        return None
    
    def _quick_search(self, root: str, filename: str, max_depth: int = 4) -> Optional[str]:
        """Quick filesystem search for a file."""
        try:
            for dirpath, dirnames, filenames in os.walk(root):
                # Check depth
                depth = dirpath.replace(root, "").count(os.sep)
                if depth > max_depth:
                    dirnames.clear()
                    continue
                
                # Check for file
                for fname in filenames:
                    if fname.lower() == filename.lower():
                        return os.path.join(dirpath, fname)
                
                # Limit directories to search
                dirnames[:] = [d for d in dirnames if not d.startswith('.') and 
                               d.lower() not in {'windows', 'system32', 'winsxs', '$recycle.bin'}]
        except Exception:
            pass
        
        return None
    
    def format_resolution(self, app_name: str, exe_names: List[str], source: str) -> str:
        """Format resolution result for display."""
        lines = [f"🎯 Приложение: {app_name}"]
        lines.append(f"   Источник: {source}")
        lines.append("")
        lines.append("   Возможные exe-файлы:")
        for i, exe in enumerate(exe_names[:5], 1):
            lines.append(f"   {i}. {exe}")
        return "\n".join(lines)


class SmartLauncher:
    """
    Enhanced launcher with app resolution capabilities.
    """
    
    def __init__(self):
        self.resolver = AppResolver()
    
    def launch(self, app_name: str, llm_client=None) -> Tuple[bool, str]:
        """
        Smart launch with resolution.
        
        Returns:
            (success, message)
        """
        # First try to find in system
        path = self.resolver.find_in_system(app_name, llm_client)
        
        if path:
            try:
                import os
                os.startfile(path)
                return True, f"✅ Запущено: {path}"
            except Exception as e:
                return False, f"❌ Найдено, но не удалось запустить: {e}"
        
        # If not found, show what we tried
        exe_names, source = self.resolver.resolve(app_name, llm_client)
        
        return False, (
            f"❌ Не удалось найти '{app_name}'\n\n"
            f"Искали исполняемые файлы:\n" +
            "\n".join(f"  • {exe}" for exe in exe_names[:5]) +
            f"\n\nИсточник: {source}\n"
            "Возможно, приложение не установлено или путь неизвестен."
        )


# Global resolver
_global_resolver: Optional[AppResolver] = None


def get_resolver() -> AppResolver:
    """Get or create global app resolver."""
    global _global_resolver
    if _global_resolver is None:
        _global_resolver = AppResolver()
    return _global_resolver


# Convenience functions
def resolve_app(app_name: str, llm_client=None) -> Tuple[List[str], str]:
    """Resolve app name to executable names."""
    return get_resolver().resolve(app_name, llm_client)


def find_app_executable(app_name: str, llm_client=None) -> Optional[str]:
    """Find full path to app executable."""
    return get_resolver().find_in_system(app_name, llm_client)


if __name__ == "__main__":
    # Test mode
    resolver = AppResolver()
    
    test_apps = [
        "роблокс",
        "варно",
        "valorant",
        "steam",
        "telegram",
    ]
    
    print("App Resolver Test")
    print("=================")
    for app in test_apps:
        exe_names, source = resolver.resolve(app)
        print(f"\n{app}:")
        print(resolver.format_resolution(app, exe_names, source))
