# -*- coding: utf-8 -*-
"""
SOKOL Steam Integration — Launch Steam games by name
v8.0: Steam URL protocol support for game launching
"""
import os
import re
import subprocess
from typing import Dict, Optional, Tuple

from .config import STEAM_GAME_IDS

_STEAM_GAMES_BASE: Dict[str, Optional[int]] = {
        # Valve games
        "cs2": 730,
        "cs": 730,
        "counter strike": 730,
        "контра": 730,
        "кс": 730,
        "кс2": 730,
        "кс го": 730,
        "csgo": 730,
        "dota": 570,
        "dota2": 570,
        "дота": 570,
        "дота2": 570,
        "half life": 70,
        "halflife": 70,
        "half-life": 70,
        "team fortress": 440,
        "tf2": 440,
        "portal": 400,
        "portal2": 620,
        "left4dead": 500,
        "left4dead2": 550,
        "garrysmod": 4000,
        "garrys mod": 4000,
        "гаррис": 4000,
        
        # Popular games
        "pubg": 578080,
        "пубг": 578080,
        "apex": 1172470,
        "apex legends": 1172470,
        "apexlegends": 1172470,
        "fortnite": None,  # Not on Steam, handled separately
        "gta5": 271590,
        "gta": 271590,
        "gta v": 271590,
        "гта": 271590,
        "гта5": 271590,
        "gtaonline": 271590,
        "gtav": 271590,
        "witcher": 292030,
        "witcher3": 292030,
        "ведьмак": 292030,
        "ведьмак3": 292030,
        "cyberpunk": 1091500,
        "cyberpunk2077": 1091500,
        "киберпанк": 1091500,
        "rust": 252490,
        "раст": 252490,
        "ark": 346110,
        "terraria": 105600,
        "террария": 105600,
        "stardew": 413150,
        "stardewvalley": 413150,
        "hades": 1145360,
        "hollow": 367520,
        "hollowknight": 367520,
        "celeste": 504230,
        "undertale": 391540,
        "undertail": 391540,
        "rimworld": 294100,
        "factorio": 427520,
        "satisfactory": 526870,
        "valheim": 892970,
        "palworld": 1623730,
        "enshrouded": 1203620,
        "bg3": 1086940,
        "baldursgate3": 1086940,
        "baldur": 1086940,
        "eldenring": 1245620,
        "elden": 1245620,
        "sekiro": 814380,
        "dark souls": 570940,
        "darksouls": 570940,
        "darksouls3": 374320,
        "monsterhunter": 582010,
        "mhw": 582010,
        "rocketleague": 252950,
        "rocket league": 252950,
        "rl": 252950,
        "forza": 1551360,
        "forza5": 1551360,
        "forzahorizon": 1551360,
        "warframe": 230410,
        "destiny2": 1085660,
        "destiny": 1085660,
        "dbd": 381210,
        "deadbydaylight": 381210,
        "escapefromtarkov": None,  # Not on Steam
        "tarkov": None,
        "rainbow": 359550,
        "rainbowsix": 359550,
        "r6": 359550,
        "r6s": 359550,
        "overwatch": None,  # Not on Steam (Battle.net)
        "overwatch2": None,
        "minecraft": None,  # Not on Steam
        "roblox": None,  # Not on Steam
        "robloxplayer": None,
        "valorant": None,  # Not on Steam (Riot)
        "валорант": None,
        "варик": None,  # slang: Valorant
        "lol": None,  # League of Legends - not on Steam
        "league": None,
        "wow": None,  # World of Warcraft - not on Steam
        "fortnite": None,  # Epic exclusive
}

_STEAM_GAMES_MERGED = {**_STEAM_GAMES_BASE, **STEAM_GAME_IDS}


class SteamHelper:
    """
    Helper for launching Steam games via Steam URL protocol.
    Games can be launched by Steam AppID or searched by name.
    """

    STEAM_GAMES = _STEAM_GAMES_MERGED

    @classmethod
    def find_steam_exe(cls) -> Optional[str]:
        """Find Steam.exe installation path."""
        common_paths = [
            r"C:\Program Files (x86)\Steam\Steam.exe",
            r"C:\Program Files\Steam\Steam.exe",
            r"D:\Steam\Steam.exe",
            r"E:\Steam\Steam.exe",
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
        return None
    
    @classmethod
    def is_steam_game(cls, game_name: str) -> Tuple[bool, Optional[int]]:
        """
        Check if game is available on Steam.
        Returns (is_steam_game, appid or None)
        """
        name_clean = re.sub(r'[^\w]', '', game_name.lower())
        
        # Direct match
        for key, appid in cls.STEAM_GAMES.items():
            key_clean = re.sub(r'[^\w]', '', key.lower())
            if name_clean == key_clean:
                if appid is not None:
                    return True, appid
                else:
                    return False, None  # Known non-Steam game
        
        # Partial match
        for key, appid in cls.STEAM_GAMES.items():
            if key in game_name.lower() or game_name.lower() in key:
                if appid is not None:
                    return True, appid
                else:
                    return False, None
        
        return False, None
    
    @classmethod
    def launch_steam_game(cls, appid: int) -> Tuple[bool, str]:
        """Launch installed Steam game by AppID (rungameid preferred)."""
        steam_url = f"steam://rungameid/{appid}"
        try:
            os.startfile(steam_url)  # type: ignore[attr-defined]
            return True, f"Launching Steam game (AppID: {appid})"
        except (OSError, AttributeError):
            pass
        try:
            fallback = f"steam://run/{appid}"
            subprocess.Popen(
                ["cmd", "/c", "start", "", fallback],
                shell=False,
                creationflags=0x08000000,
            )
            return True, f"Launching Steam game (AppID: {appid})"
        except Exception as e:
            return False, f"Failed to launch Steam game: {e}"
    
    @classmethod
    def launch(cls, game_name: str) -> Tuple[bool, str]:
        """
        Try to launch game via Steam.
        Returns (success, message)
        """
        is_steam, appid = cls.is_steam_game(game_name)
        
        if not is_steam:
            if appid is None and game_name.lower() in [k.lower() for k in cls.STEAM_GAMES]:
                return False, f"'{game_name}' is not available on Steam ( Epic / Battle.net / Riot / Standalone )"
            return False, f"'{game_name}' not found in Steam library"
        
        return cls.launch_steam_game(appid)
    
    @classmethod
    def get_game_info(cls, game_name: str) -> str:
        """Get information about where to find the game."""
        is_steam, appid = cls.is_steam_game(game_name)
        
        if is_steam:
            return f"'{game_name}' available on Steam (AppID: {appid})"
        
        # Check if known non-Steam
        name_clean = re.sub(r'[^\w]', '', game_name.lower())
        non_steam_info = {
            "варик": "Riot Client (Valorant slang)",
            "валорант": "Riot Client (standalone)",
            "valorant": "Riot Client (standalone)",
            "fortnite": "Epic Games Launcher",
            "overwatch": "Battle.net (Blizzard)",
            "overwatch2": "Battle.net (Blizzard)",
            "minecraft": "Minecraft Launcher (Microsoft/Standalone)",
            "roblox": "Roblox Player (standalone)",
            "wow": "Battle.net (Blizzard)",
            "worldofwarcraft": "Battle.net (Blizzard)",
            "lol": "Riot Client (standalone)",
            "leagueoflegends": "Riot Client (standalone)",
            "tarkov": "Escape from Tarkov Launcher (standalone)",
        }
        
        for key, launcher in non_steam_info.items():
            if key in name_clean or name_clean in key:
                return f"'{game_name}' is available via {launcher}, not Steam"
        
        return f"'{game_name}' — location unknown, try searching in Start Menu"


# Convenience function
def launch_steam_game(game_name: str) -> Tuple[bool, str]:
    """Try to launch a game via Steam."""
    return SteamHelper.launch(game_name)


if __name__ == "__main__":
    # Test
    test_games = ["cs2", "gta5", "варно", "roblox", "dota"]
    for game in test_games:
        print(f"\n{game}:")
        print(f"  Info: {SteamHelper.get_game_info(game)}")
        is_steam, appid = SteamHelper.is_steam_game(game)
        if is_steam:
            print(f"  AppID: {appid}")
