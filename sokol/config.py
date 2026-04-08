# -*- coding: utf-8 -*-
"""
SOKOL v8.0 — Configuration & Environment
UPGRADED: llama3.2:3b for speed, vision settings, keep_alive.
AMD ROCm GPU optimization for RX 5700 XT.
"""
import os
import sys

CPU_COUNT = os.cpu_count() or 4
OLLAMA_NUM_THREAD = max(1, CPU_COUNT - 2)

# GPU backend mode:
#   auto (default): don't force vendor-specific backend vars
#   rocm: force AMD ROCm tuning
#   cuda: force CUDA-visible devices
#   cpu: disable GPU usage hints
SOKOL_GPU_BACKEND = os.environ.get("SOKOL_GPU_BACKEND", "auto").strip().lower()

# ━━━ Runtime backend tuning ━━━
os.environ["OLLAMA_FLASH_ATTENTION"]   = "1"
os.environ["OLLAMA_NUM_PARALLEL"]      = "1"
os.environ["OLLAMA_MAX_LOADED_MODELS"] = "1"
os.environ["no_proxy"]                 = "localhost,127.0.0.1"
os.environ["NO_PROXY"]                 = "localhost,127.0.0.1"
os.environ["OPENAI_API_KEY"]           = "sk-dummy-not-needed"

if SOKOL_GPU_BACKEND == "rocm":
    os.environ["HSA_OVERRIDE_GFX_VERSION"] = os.environ.get("HSA_OVERRIDE_GFX_VERSION", "10.1.0")  # RX 5700 XT = gfx1010
    os.environ["GPU_MAX_ALLOC_PERCENT"] = os.environ.get("GPU_MAX_ALLOC_PERCENT", "100")
    os.environ["OLLAMA_GPU_OVERHEAD"] = os.environ.get("OLLAMA_GPU_OVERHEAD", "0")
    os.environ["HIP_VISIBLE_DEVICES"] = os.environ.get("HIP_VISIBLE_DEVICES", "0")
elif SOKOL_GPU_BACKEND == "cuda":
    os.environ["CUDA_VISIBLE_DEVICES"] = os.environ.get("CUDA_VISIBLE_DEVICES", "0")
elif SOKOL_GPU_BACKEND == "cpu":
    os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["HIP_VISIBLE_DEVICES"] = ""

# ━━━ Ollama LLM Settings ━━━
# v8.0: switched to qwen2.5:1.5b for better AMD GPU performance
OLLAMA_MODEL          = "qwen2.5:1.5b"
OLLAMA_API_BASE       = "http://127.0.0.1:11434"
OLLAMA_API_KEY        = os.environ.get("OLLAMA_API_KEY", "")
OLLAMA_KEEP_ALIVE     = "10m"  # Keep model in VRAM between requests
OLLAMA_MAX_LOADED_MODELS = int(os.environ.get("OLLAMA_MAX_LOADED_MODELS", "1"))
OLLAMA_NUM_PARALLEL   = int(os.environ.get("OLLAMA_NUM_PARALLEL", "1"))
OLLAMA_FLASH_ATTENTION = os.environ.get("OLLAMA_FLASH_ATTENTION", "1")
OLLAMA_MAX_CONTEXT   = int(os.environ.get("OLLAMA_MAX_CONTEXT", "4096"))
# Ollama: GPU layers (99 = all). 0 = CPU-only. Set OLLAMA_NUM_GPU when debugging GPU.
try:
    OLLAMA_NUM_GPU = int(os.environ.get("OLLAMA_NUM_GPU", "99"))
except ValueError:
    OLLAMA_NUM_GPU = 99

# FAST mode — classification (PreRouter miss → LLM classify)
FAST_CONTEXT_WINDOW   = 512
FAST_MAX_TOKENS       = 128
FAST_TEMPERATURE      = 0.1
FAST_TOP_K            = 20
FAST_TOP_P            = 0.5

# FULL mode — conversations and code (Phase 2, rare)
FULL_CONTEXT_WINDOW   = 2048
FULL_MAX_TOKENS       = 512
FULL_TEMPERATURE      = 0.0
FULL_TOP_K            = 10
FULL_TOP_P            = 0.3

# VISION mode — agentic control (step-by-step GUI actions)
VISION_CONTEXT_WINDOW = 768
VISION_MAX_TOKENS     = 96
VISION_MAX_STEPS      = 10
VISION_STEP_DELAY     = 0.6  # seconds between vision steps
VISION_TOP_K          = 20
VISION_TOP_P          = 0.5

# Legacy aliases
OLLAMA_CONTEXT_WINDOW = FAST_CONTEXT_WINDOW
OLLAMA_MAX_TOKENS     = FAST_MAX_TOKENS
OLLAMA_TEMPERATURE    = FAST_TEMPERATURE

# ━━━ Execution ━━━
CODE_EXEC_TIMEOUT = 45
NOWINDOW          = 0x08000000
VERSION           = "8.0"

# ━━━ Paths ━━━
USER_HOME       = os.path.expanduser("~")
SCREENSHOTS_DIR = os.path.join(USER_HOME, "Pictures", "Sokol_Screenshots")
CONTACTS_PATH   = os.path.join(os.path.dirname(__file__), "contacts.json")
NOTES_PATH      = os.path.join(USER_HOME, "Desktop", "Sokol_Notes.txt")
KNOWLEDGE_BASE_PATH = os.path.join(os.path.dirname(__file__), "knowledge_base.json")
SOKOL_LOG_DIR   = os.path.join(USER_HOME, ".sokol", "logs")

# ━━━ Steam (merged into steam_helper.STEAM_GAMES; overrides built-ins) ━━━
# WARNO (Steam); «варно» was previously confused with Valorant.
STEAM_GAME_IDS = {
    "warno": 1876880,
    "варно": 1876880,
    "warn": 1876880,
    "wargame warno": 1876880,
}

# ━━━ External LLM (Groq OpenAI-compatible) ━━━
# Set GROQ_API_KEY in environment or .env (loaded by your shell). Optional: GROQ_MODEL.
GROQ_MODEL_DEFAULT = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile").strip()

# ━━━ Stockfish (chess_engine tool) ━━━
STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "").strip()

# ━━━ Security & agent behaviour ━━━
# Code blocks from LLM: off unless explicitly enabled (see CodeExecutor.execute).
ALLOW_CODE_EXEC = os.environ.get("SOKOL_ALLOW_CODE_EXEC", "").strip().lower() in ("1", "true", "yes", "on")
# Extra confirmation before sending Telegram/AyuGram messages
CONFIRM_MESSENGER_SEND = os.environ.get("SOKOL_CONFIRM_MESSENGER", "").strip().lower() in ("1", "true", "yes", "on")

# ━━━ TTS & Voice Settings ━━━
TTS_ENABLED     = False      # Озвучка ответов отключена (только текст в логе)
TTS_ENGINE      = "pyttsx3"  # unused when TTS_ENABLED is False
TTS_VOICE_ID    = None
TTS_RATE        = 180
TTS_VOLUME      = 1.0
VOICE_INPUT_LANG = "ru-RU"   # Google Speech Recognition language
# google | whisper_local (requires openai-whisper + torch; heavy)
VOICE_STT_BACKEND = os.environ.get("SOKOL_STT", "google").strip().lower()

# Микрофон: чувствительность и скорость окончания фразы
VOICE_AMBIENT_DURATION   = 0.25   # сек калибровки шума (меньше = быстрее старт)
VOICE_TIMEOUT            = 10.0   # ждать начала речи (увеличено для надежности)
VOICE_PHRASE_TIME_LIMIT  = 30.0   # максимум длины фразы (увеличено)
VOICE_PAUSE_THRESHOLD    = 1.2    # пауза до конца фразы (сек) — увеличено, чтобы не обрывал
VOICE_NON_SPEAKING       = 0.8    # короче тишины между словами внутри фразы
VOICE_PHRASE_THRESHOLD   = 0.15   # мин. длительность звука как «речь»
# Опционально: pip install noisereduce numpy — подавление стационарного шума перед отправкой в Google
VOICE_DENOISE            = True

# ━━━ Optional Dependencies (v8.0: Fast lazy detection) ━━━
import importlib.util

def is_installed(name):
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False

HAS_PSUTIL      = is_installed("psutil")
HAS_PYAUTOGUI   = is_installed("pyautogui")
HAS_EASYOCR     = is_installed("easyocr")
HAS_PYGETWINDOW = is_installed("pygetwindow")
HAS_PYWIN32     = is_installed("win32gui")

if HAS_PYAUTOGUI:
    try:
        import pyautogui
        pyautogui.FAILSAFE = False # v8.0.9: Disabled to allow clicks in corners (1920x1080 logic)
        pyautogui.PAUSE    = 0.05
    except Exception:
        HAS_PYAUTOGUI = False

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Russian App Names — STRICT MAPPING v8.0
# Key fix: Telegram and AyuGram are now completely separated
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# TELEGRAM-ONLY mappings (strict)
TELEGRAM_ALIASES = {
    "телеграм": "telegram",
    "телеграмм": "telegram",
    "телега": "telegram",
    "тг": "telegram",
    "telegram": "telegram",
    "telegram desktop": "telegram",
}

# AYUGRAM-ONLY mappings (strict)
AYUGRAM_ALIASES = {
    "аюграм": "ayugram",
    "аюграмм": "ayugram",
    "аю": "ayugram",
    "ayugram": "ayugram",
    "ayugram desktop": "ayugram",
    "ayu": "ayugram",
}

# GAMES — expanded dictionary for popular games
GAME_ALIASES = {
    # Battle Royale / Shooter
    "роблокс": "roblox",
    "роблок": "roblox",
    "roblox": "roblox",
    "варно": "valorant",
    "варик": "valorant",
    "валорант": "valorant",
    "valorant": "valorant",
    "фортнайт": "fortnite",
    "форт": "fortnite",
    "fortnite": "fortnite",
    "апекс": "apex",
    "apex": "apex",
    "apex legends": "apex",
    "кс": "cs2",
    "ксго": "cs2",
    "кс2": "cs2",
    "cs": "cs2",
    "csgo": "cs2",
    "cs2": "cs2",
    "counter-strike": "cs2",
    "пабг": "pubg",
    "пубг": "pubg",
    "pubg": "pubg",
    "кал оф дьюти": "cod",
    "код": "cod",
    "call of duty": "cod",
    "warzone": "warzone",
    "варзон": "warzone",
    "овервотч": "overwatch",
    "overwatch": "overwatch",
    "овер": "overwatch",
    "дестини": "destiny2",
    "destiny": "destiny2",
    "rainbow six": "rainbowsix",
    "радуга": "rainbowsix",
    "р6": "rainbowsix",
    "siege": "rainbowsix",
    
    # MOBA / Strategy
    "дота": "dota2",
    "дотка": "dota2",
    "dota": "dota2",
    "dota 2": "dota2",
    "лол": "lol",
    "lol": "lol",
    "лига": "lol",
    "league of legends": "lol",
    "hots": "hots",
    "хотс": "hots",
    "heroes": "hots",
    "старакрафт": "starcraft",
    "старкрафт": "starcraft",
    "starcraft": "starcraft",
    "варкрафт": "warcraft",
    "warcraft": "warcraft",
    "wow": "wow",
    "вов": "wow",
    "world of warcraft": "wow",
    
    # Sandbox / Survival
    "майнкрафт": "minecraft",
    "minecraft": "minecraft",
    "минекрафт": "minecraft",
    "тераррия": "terraria",
    "terraria": "terraria",
    "раст": "rust",
    "rust": "rust",
    "арк": "ark",
    "ark": "ark",
    "палворлд": "palworld",
    "palworld": "palworld",
    "валхейм": "valheim",
    "valheim": "valheim",
    "эншrounded": "enshrouded",
    "enshrouded": "enshrouded",
    "сатисфактори": "satisfactory",
    "satisfactory": "satisfactory",
    
    # RPG / Adventure
    "гта": "gta5",
    "гта5": "gta5",
    "гта 5": "gta5",
    "gta": "gta5",
    "gta5": "gta5",
    " Elden Ring": "eldenring",
    "элден": "eldenring",
    "elden": "eldenring",
    "скайрим": "skyrim",
    "skyrim": "skyrim",
    "ведьмак": "witcher3",
    "ведьмак 3": "witcher3",
    "witcher": "witcher3",
    "киберпанк": "cyberpunk",
    "cyberpunk": "cyberpunk",
    "2077": "cyberpunk",
    "бaldur": "baldursgate3",
    "балдурс": "baldursgate3",
    "baldur": "baldursgate3",
    "hogwarts": "hogwarts",
    "хогвартс": "hogwarts",
    "сталкер": "stalker2",
    "stalker": "stalker2",
    "голодные игры": "stalker2",
    
    # Racing / Sports
    "форза": "forza",
    "forza": "forza",
    "фифа": "fifa",
    "fifa": "fifa",
    "fc 24": "fifa",
    "fc 25": "fifa",
    "нба": "nba2k",
    "nba": "nba2k",
    "rocket league": "rocketleague",
    "рокет": "rocketleague",
    
    # Launchers
    "стим": "steam",
    "steam": "steam",
    "епик": "epic",
    "эпик": "epic",
    "epic": "epic",
    "epic games": "epic",
    "гог": "gog",
    "gog": "gog",
    "galaxy": "gog",
    "ea": "ea",
    "origin": "origin",
    "юбисофт": "ubisoft",
    "ubisoft": "ubisoft",
    "uplay": "ubisoft",
    "xbox": "xbox",
    "иксбокс": "xbox",
    "тлаунчер": "tlauncher",
    "tlauncher": "tlauncher",
    "лаунчер": "launcher",
}

# APPLICATIONS — productivity and utility apps
APP_ALIASES = {
    # Office
    "ворд": "winword",
    "word": "winword",
    "ms word": "winword",
    "эксель": "excel",
    "excel": "excel",
    "паверпоинт": "powerpnt",
    "павер поинт": "powerpnt",
    "powerpoint": "powerpnt",
    "ппт": "powerpnt",
    "outlook": "outlook",
    "аутлук": "outlook",
    "onenote": "onenote",
    "вандноут": "onenote",
    "teams": "teams",
    "тимс": "teams",
    "мстимс": "teams",
    "zoom": "zoom",
    "зум": "zoom",
    "skype": "skype",
    "скайп": "skype",
    "notion": "notion",
    "ноушн": "notion",
    "obsidian": "obsidian",
    "обсидиан": "obsidian",
    
    # Creative
    "фотошоп": "photoshop",
    "photoshop": "photoshop",
    "пс": "photoshop",
    "premiere": "premiere",
    "премьера": "premiere",
    "after effects": "afterfx",
    "ае": "afterfx",
    "иллюстратор": "illustrator",
    "illustrator": "illustrator",
    "аи": "illustrator",
    "blender": "blender",
    "блендер": "blender",
    "figma": "figma",
    "фигма": "figma",
    "gimp": "gimp",
    "гимп": "gimp",
    "audacity": "audacity",
    "аудатис": "audacity",
    "davinci": "davinci",
    "давинчи": "davinci",
    "resolve": "davinci",
    
    # Dev Tools
    "вскод": "code",
    "вс код": "code",
    "vscode": "code",
    "code": "code",
    "код": "code",
    "курсор": "cursor",
    "cursor": "cursor",
    "пайчарм": "pycharm",
    "pycharm": "pycharm",
    "идеа": "idea",
    "idea": "idea",
    "intellij": "idea",
    "вебшторм": "webstorm",
    "webstorm": "webstorm",
    "саблайм": "sublime_text",
    "sublime": "sublime_text",
    "нотепад": "notepad++",
    "notepad++": "notepad++",
    "нотепад++": "notepad++",
    "vim": "vim",
    "вим": "vim",
    "neovim": "nvim",
    "невим": "nvim",
    "git": "git-bash",
    "гит": "git-bash",
    "github desktop": "github",
    "гитхаб": "github",
    "docker": "docker",
    "докер": "docker",
    "postman": "postman",
    "постман": "postman",
    "insomnia": "insomnia",
    "инсомния": "insomnia",
    
    # Browsers
    "хром": "chrome",
    "chrome": "chrome",
    "google chrome": "chrome",
    "файрфокс": "firefox",
    "firefox": "firefox",
    "лиса": "firefox",
    "опера": "opera",
    "opera": "opera",
    "opera gx": "opera_gx",
    "браузер": "chrome",
    "edge": "msedge",
    "эдж": "msedge",
    "microsoft edge": "msedge",
    "brave": "brave",
    "брейв": "brave",
    "vivaldi": "vivaldi",
    "вивальди": "vivaldi",
    "tor": "tor",
    "тор": "tor",
    
    # Media
    "spotify": "spotify",
    "спотифай": "spotify",
    "music": "spotify",
    "apple music": "applemusic",
    "яблоко музыка": "applemusic",
    "yt music": "ytmusic",
    "youtube music": "ytmusic",
    "vlc": "vlc",
    "влц": "vlc",
    "плеер": "vlc",
    "media player": "vlc",
    "обс": "obs64",
    "obs": "obs64",
    "стрим": "obs64",
    "discord": "discord",
    "дискорд": "discord",
    "дс": "discord",
    "вайбер": "viber",
    "viber": "viber",
    "ватсап": "whatsapp",
    "whatsapp": "whatsapp",
    "slack": "slack",
    "слак": "slack",
    
    # Utilities
    "телеграм": "telegram",
    "телеграмм": "telegram",
    "телега": "telegram",
    "тг": "telegram",
    "аюграм": "ayugram",
    "аюграмм": "ayugram",
    "аю": "ayugram",
    "steam": "steam",
    "стим": "steam",
    "epic": "epicgameslauncher",
    "епик": "epicgameslauncher",
    "блокнот": "notepad",
    "notepad": "notepad",
    "калькулятор": "calc",
    "calc": "calc",
    "проводник": "explorer",
    "explorer": "explorer",
    "пейнт": "mspaint",
    "paint": "mspaint",
    "mspaint": "mspaint",
    "калькулятор": "calc",
    "calc": "calc",
    "терминал": "wt",
    "wt": "wt",
    "windows terminal": "wt",
    "командная строка": "cmd",
    "cmd": "cmd",
    "powershell": "powershell",
    "павершелл": "powershell",
    "7zip": "7z",
    "7зип": "7z",
    "винрар": "winrar",
    "winrar": "winrar",
    "teamviewer": "teamviewer",
    "тимвьювер": "teamviewer",
    "anydesk": "anydesk",
    "энидеск": "anydesk",
}

# MERGE ALL into RUS_APP_MAP with priority (TELEGRAM > AYUGRAM > GAMES > APPS)
# This ensures no overlap between telegram and ayugram
_RUS_APP_PRIORITY = [
    TELEGRAM_ALIASES,
    AYUGRAM_ALIASES,
    GAME_ALIASES,
    APP_ALIASES,
]

RUS_APP_MAP = {}
for mapping in _RUS_APP_PRIORITY:
    RUS_APP_MAP.update(mapping)

# Process mappings (for killing processes)
RUS_PROCESS_MAP = {
    # Telegram vs AyuGram strict separation
    "телеграм": "telegram",
    "телеграмм": "telegram",
    "телега": "telegram",
    "тг": "telegram",
    "аюграм": "ayugram",
    "аюграмм": "ayugram",
    "аю": "ayugram",
    # Games
    "роблокс": "roblox",
    "варно": "valorant",
    "варик": "valorant",
    "валорант": "valorant",
    "фортнайт": "fortnite",
    "форт": "fortnite",
    "кс": "cs2",
    "ксго": "cs2",
    "кс2": "cs2",
    "дота": "dota2",
    "дотка": "dota2",
    "майнкрафт": "minecraft",
    "гта": "gta5",
    "гта5": "gta5",
    "сталкер": "stalker2",
    "стим": "steam",
    "тлаунчер": "tlauncher",
    "апекс": "apex",
    # Apps
    "дискорд": "discord",
    "дс": "discord",
    "хром": "chrome",
    "браузер": "chrome",
    "пайчарм": "pycharm",
    "фотошоп": "photoshop",
    "ворд": "winword",
    "эксель": "excel",
    "пейнт": "mspaint",
    "скайп": "skype",
    "зум": "zoom",
    "блендер": "blender",
    "фигма": "figma",
    "вайбер": "viber",
    "ватсап": "whatsapp",
    "спотифай": "spotify",
    "обс": "obs64",
    "файрфокс": "firefox",
    "опера": "opera",
    "юнити": "unity",
    "докер": "docker",
    "постман": "postman",
    "слак": "slack",
    "тимс": "teams",
    "код": "code",
    "вс код": "code",
    "курсор": "cursor",
    "блокнот": "notepad",
    "калькулятор": "calc",
    "проводник": "explorer",
    "паверпоинт": "powerpnt",
}

FOLDER_ALIASES = {
    "downloads": os.path.join(USER_HOME, "Downloads"),
    "desktop":   os.path.join(USER_HOME, "Desktop"),
    "documents": os.path.join(USER_HOME, "Documents"),
    "pictures":  os.path.join(USER_HOME, "Pictures"),
    "music":     os.path.join(USER_HOME, "Music"),
    "videos":    os.path.join(USER_HOME, "Videos"),
    "загрузки":       os.path.join(USER_HOME, "Downloads"),
    "рабочий стол":   os.path.join(USER_HOME, "Desktop"),
    "документы":      os.path.join(USER_HOME, "Documents"),
    "изображения":    os.path.join(USER_HOME, "Pictures"),
    "картинки":       os.path.join(USER_HOME, "Pictures"),
    "музыка":         os.path.join(USER_HOME, "Music"),
    "видео":          os.path.join(USER_HOME, "Videos"),
}

WEB_SERVICES = {
    "chatgpt": "https://chat.openai.com",
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "twitter": "https://twitter.com",
    "x.com": "https://x.com",
    "reddit": "https://www.reddit.com",
    "whatsapp web": "https://web.whatsapp.com",
    "netflix": "https://www.netflix.com",
    "twitch": "https://www.twitch.tv",
    "linkedin": "https://www.linkedin.com",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "amazon": "https://www.amazon.com",
    "wikipedia": "https://www.wikipedia.org",
    "spotify web": "https://open.spotify.com",
    "notion web": "https://www.notion.so",
    "figma web": "https://www.figma.com",
    "canva": "https://www.canva.com",
    "trello": "https://trello.com",
    "google docs": "https://docs.google.com",
    "google drive": "https://drive.google.com",
    "google maps": "https://maps.google.com",
    "чатгпт": "https://chat.openai.com",
    "чат гпт": "https://chat.openai.com",
    "ютуб": "https://www.youtube.com",
    "гугл": "https://www.google.com",
    "гитхаб": "https://github.com",
    "гмейл": "https://mail.google.com",
    "твиттер": "https://x.com",
    "реддит": "https://www.reddit.com",
    "нетфликс": "https://www.netflix.com",
    "твич": "https://www.twitch.tv",
    "вики": "https://ru.wikipedia.org",
    "википедия": "https://ru.wikipedia.org",
    "яндекс": "https://ya.ru",
    "вк": "https://vk.com",
    "вконтакте": "https://vk.com",
    "инстаграм": "https://www.instagram.com",
    "тикток": "https://www.tiktok.com",
    "трелло": "https://trello.com",
    "карты": "https://maps.google.com",
}

SYSTEM_TOOLS = {
    "task manager": "taskmgr", "taskmgr": "taskmgr",
    "control panel": "control", "registry editor": "regedit",
    "regedit": "regedit", "device manager": "devmgmt.msc",
    "disk management": "diskmgmt.msc", "services": "services.msc",
    "event viewer": "eventvwr.msc", "computer management": "compmgmt.msc",
    "system configuration": "msconfig", "msconfig": "msconfig",
    "resource monitor": "resmon", "performance monitor": "perfmon",
    "task scheduler": "taskschd.msc", "windows firewall": "firewall.cpl",
    "firewall": "firewall.cpl", "programs and features": "appwiz.cpl",
    "system properties": "sysdm.cpl", "network connections": "ncpa.cpl",
    "power options": "powercfg.cpl", "sound settings": "mmsys.cpl",
    "sound": "mmsys.cpl", "date and time": "timedate.cpl",
    "calculator": "calc", "calc": "calc", "notepad": "notepad",
    "paint": "mspaint", "mspaint": "mspaint", "cmd": "cmd",
    "command prompt": "cmd", "powershell": "powershell",
    "terminal": "wt", "windows terminal": "wt",
    "explorer": "explorer", "file explorer": "explorer",
    "snipping tool": "snippingtool", "magnifier": "magnify",
    "on-screen keyboard": "osk", "character map": "charmap",
    "wordpad": "wordpad", "disk cleanup": "cleanmgr",
    "system info": "msinfo32", "directx diagnostics": "dxdiag",
    "remote desktop": "mstsc",
    "диспетчер задач": "taskmgr", "панель управления": "control",
    "редактор реестра": "regedit", "диспетчер устройств": "devmgmt.msc",
    "управление дисками": "diskmgmt.msc", "службы": "services.msc",
    "просмотр событий": "eventvwr.msc", "планировщик заданий": "taskschd.msc",
    "брандмауэр": "firewall.cpl", "сетевые подключения": "ncpa.cpl",
    "электропитание": "powercfg.cpl", "калькулятор": "calc",
    "блокнот": "notepad", "пейнт": "mspaint",
    "командная строка": "cmd", "терминал": "wt",
    "проводник": "explorer", "очистка диска": "cleanmgr",
    "сведения о системе": "msinfo32",
    "удалённый рабочий стол": "mstsc",
    "экранная клавиатура": "osk", "таблица символов": "charmap",
}

BLOATWARE_PROCESSES = [
    "OneDrive.exe", "Cortana.exe", "SearchUI.exe", "YourPhone.exe",
    "GameBar.exe", "GameBarPresenceWriter.exe", "SkypeApp.exe",
    "HxTsr.exe", "HxOutlook.exe", "HxCalendarAppImm.exe",
    "Microsoft.Photos.exe", "Video.UI.exe", "Music.UI.exe",
]
