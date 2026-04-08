# -*- coding: utf-8 -*-
"""
SOKOL — Dispatcher: ActionDispatcher + LLM routing.

Routing pieces live in pre_router, vision_agent, prompts.
"""

import ast
import json
import logging
import os
import random
import re
import textwrap
import threading
import time
import urllib.request
from datetime import datetime

from .core import INTERRUPT, CodeExecutor, OllamaClient
from .config import (
    OLLAMA_MODEL, OLLAMA_API_BASE, OLLAMA_API_KEY, VERSION, SOKOL_GPU_BACKEND,
    OLLAMA_KEEP_ALIVE, OLLAMA_NUM_GPU,
    VOICE_INPUT_LANG, VOICE_AMBIENT_DURATION, VOICE_TIMEOUT, VOICE_PHRASE_TIME_LIMIT,
    VOICE_PAUSE_THRESHOLD, VOICE_NON_SPEAKING, VOICE_PHRASE_THRESHOLD,
    VOICE_DENOISE, VOICE_STT_BACKEND, ALLOW_CODE_EXEC, HAS_PSUTIL,
)
from .automation import GUIAutomation, VisionLite, ScreenCapture
from .app_controller import get_app_controller, send_telegram_message, AppType, AppCommand
from .tools import (
    SystemTools, SmartLauncher, ProcessKiller, WebRouter,
    MediaController, PowerController, NetworkDiag, SystemTriage,
    WindowManager, ScreenManager, FileMachine, FileAgent,
    WindowEnumerator, ServiceManager, WiFiManager, DiskAnalyzer,
    StartupManager, SystemQuickInfo, ContentSearch,
    WindowFocuser
)
from .terminal import TerminalExecutor, SystemDashboard
from .web_fetcher import WebFetcher
from .deep_research import DeepResearchAgent
from .special_modes import DeepClean, GamingMode, GhostMode
from .memory import ClipboardManager
from .tools.stem import STEMCore
from .tools.info_hub import InfoHub

from .pre_router import PreRouter, HELP_TEXT
from .vision_agent import VisionAgent
from .prompts import CLASSIFY_PROMPT, CHAT_SYSTEM_MESSAGE  # noqa: F401 — re-export for gui_main
from . import policy
from .action_schemas import validate_llm_action, coerce_action_dict
from .rag_hints import recall_note_hints
from .fuzzy_match import best_match_against_templates

_log = logging.getLogger("sokol.dispatcher")



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Action Dispatcher — v7.2: with agentic_control
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ActionDispatcher:
    """Parse LLM classify response and dispatch to action modules."""

    ACTION_RE = re.compile(r":::ACTION:::\s*(\{.*?\})\s*:::END:::", re.DOTALL)
    CHAT_RE = re.compile(r":::CHAT:::", re.IGNORECASE)
    # Heuristics: follow-up dialogue / chess discussion should not go through classify → actions.
    _CONTINUATION_RE = re.compile(
        r"(ты\s+ошиб|ошиблась|ошибся|нельзя\s+так|неверн|противореч|"
        r"не\s+так|почему\s+ты|объясни|это\s+не\s+ход|не\s+твой\s+ход|"
        r"я\s+играю|очередь\s+|ход\s+бел|ход\s+чёрн|шахмат|дебют|партия|"
        r"ферзь|ладь[ья]|слон|конь|пешк)",
        re.IGNORECASE,
    )
    _CHESS_MOVE_RE = re.compile(
        r"\b(?:[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?|O-O(?:-O)?)\b",
        re.IGNORECASE,
    )
    CONTACTS = {}
    KNOWLEDGE_BASE = {}
    # Fuzzy-matched small-talk / identity corrections (avoid launch_app / messenger false positives)
    _CONVERSATIONAL_TEMPLATES = [
        "нет я челик",
        "я челик",
        "я чели",
        "чё бля",
        "че бля",
        "что бля",
        "бля что",
        "просто шучу",
        "не парься",
        "не понял",
        "зачем ты",
        "почему ты открыл",
    ]

    @classmethod
    def _load_kb(cls):
        """Load knowledge base from JSON."""
        if not cls.KNOWLEDGE_BASE:
            try:
                if os.path.exists(KNOWLEDGE_BASE_PATH):
                    with open(KNOWLEDGE_BASE_PATH, "r", encoding="utf-8") as f:
                        cls.KNOWLEDGE_BASE = json.load(f)
            except Exception:
                pass
        return cls.KNOWLEDGE_BASE

    @classmethod
    def _load_contacts(cls):
        """Load contacts from external JSON file."""
        if not cls.CONTACTS:
            try:
                if os.path.exists(CONTACTS_PATH):
                    with open(CONTACTS_PATH, "r", encoding="utf-8") as f:
                        cls.CONTACTS = json.load(f)
            except Exception:
                pass
        return cls.CONTACTS

    @classmethod
    def _normalize_contact_key(cls, text):
        s = (text or "").strip().lower().replace("ё", "е")
        s = re.sub(r"[^a-zа-я0-9]+", "", s, flags=re.IGNORECASE)
        # Basic Russian case endings for dative/accusative colloquial forms.
        for suf in ("у", "е", "ой", "ю", "а", "я"):
            if len(s) > 4 and s.endswith(suf):
                s = s[:-len(suf)]
                break
        return s

    @classmethod
    def parse_classify(cls, text):
        if not text:
            return "chat", None

        if cls.CHAT_RE.search(text):
            return "chat", None

        action = cls._parse_action_json(text)
        if action and "type" in action:
            return "action", action

        return "chat", None

    @classmethod
    def _extract_json_blob(cls, text):
        """Extract JSON object from noisy model output."""
        if not text:
            return None
        cleaned = text.strip()
        # Remove markdown fences if present.
        cleaned = re.sub(r"```(?:json)?", "", cleaned, flags=re.IGNORECASE).replace("```", "")

        # Prefer explicit ACTION marker block first.
        m = cls.ACTION_RE.search(cleaned)
        if m:
            return m.group(1).strip()

        # Robust fallback: find first/last JSON braces in full text.
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            return m.group(0).strip()
        return None

    @classmethod
    def _repair_json_string(cls, raw):
        """Repair common JSON issues from small LLMs."""
        if not raw:
            return raw
        fixed = raw.strip()
        # Single quotes -> double quotes (best-effort).
        fixed = re.sub(r"(?<!\\)'", '"', fixed)
        # Python literals -> JSON literals.
        fixed = re.sub(r"\bTrue\b", "true", fixed)
        fixed = re.sub(r"\bFalse\b", "false", fixed)
        fixed = re.sub(r"\bNone\b", "null", fixed)
        # Remove trailing commas before object/array close.
        fixed = re.sub(r",\s*([}\]])", r"\1", fixed)
        return fixed

    @classmethod
    def _parse_action_json(cls, text):
        raw = cls._extract_json_blob(text)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            repaired = cls._repair_json_string(raw)
            try:
                return json.loads(repaired)
            except (json.JSONDecodeError, TypeError, ValueError):
                return None

    @classmethod
    def _safe_cast(cls, value, target_type, default):
        """Safe type conversion for LLM-provided parameters."""
        try:
            if value is None:
                return default
            if target_type is bool:
                if isinstance(value, bool):
                    return value
                s = str(value).strip().lower()
                if s in {"1", "true", "yes", "y", "on"}:
                    return True
                if s in {"0", "false", "no", "n", "off"}:
                    return False
                return default
            if target_type is int:
                if isinstance(value, bool):
                    return default
                return int(float(str(value).strip().replace(",", ".")))
            if target_type is float:
                if isinstance(value, bool):
                    return default
                return float(str(value).strip().replace(",", "."))
            if target_type is str:
                return str(value)
            return target_type(value)
        except Exception:
            return default

    @classmethod
    def _is_explicit_power_intent(cls, user_input):
        text = (user_input or "").lower()
        # roots: выкл, сп(сон), отключ, shutdown
        return bool(re.search(r"(выкл|сп|отключ|shutdown)", text, re.IGNORECASE))

    @classmethod
    def _quick_answer(cls, user_input, gui):
        """
        Tier 1 (Instant): Knowledge Base + Regex-based FAST_MAP. 
        0ms latency, bypassing LLM.
        """
        q = (user_input or "").strip().lower()
        if not q:
            return None
        
        # 1. Knowledge Base Lookup (v8.0)
        kb = cls._load_kb()
        # Direct match or substring for simple questions
        for key, answer in kb.items():
            if q == key or (len(q) > 3 and q in key) or (len(key) > 3 and key in q):
                return answer

        name = gui.memory.pinned.get("user_name", "User")
        
        # Identity / Box-art card
        if q in ("кто ты", "identity", "кто такой сокол", "version", "версия"):
            display_name = name if name and name.lower() not in ("user", "челик", "") else "Неизвестный пользователь"
            return textwrap.dedent(f"""
                ┌──────────────────────────────────────┐
                │  ⌬ SOKOL ELITE v{VERSION:<18} │
                ├──────────────────────────────────────┤
                │  STATUS: OPTIMIZED / ACTIVE          │
                │  CORE:   3-TIER REACTOR              │
                │  USER:   {display_name:<27} │
                └──────────────────────────────────────┘
            """).strip()

        # Who am I (user identity) — tolerate ?!. and extra spaces; not only exact string match
        q_words = re.sub(r"[^\w\sа-яё]+", " ", q)
        q_words = re.sub(r"\s+", " ", q_words).strip()
        if re.search(
            r"\b(кто\s+я|как\s+меня\s+зовут|как\s+зовут\s+меня|какое\s+у\s+меня\s+имя|моё\s+имя|мое\s+имя|напомни\s+как\s+меня\s+зовут)\b",
            q_words,
        ):
            return f"Тебя зовут {name}."
        # Assistant name (not user) — chat, not messenger
        if re.search(r"\b(как\s+тебя\s+зовут|как\s+зовут\s+тебя)\b", q_words):
            return "Меня зовут Сокол. Я локальный ассистент на этом ПК."

        # Яндекс Музыка / настроение (URL only; настроение в приложении — вручную)
        if re.search(r"\b(яндекс\s*музык|yandex\s*music)\b", q):
            return {"type": "web_open", "params": {"url": "https://music.yandex.ru"}}
        _my_wave = "https://music.yandex.ru/radio/user/my-wave"
        if re.search(
            r"\b(музык\w*|поставь\s+музык|включи\s+музык|подбери\s+музык)\b.*\b(работа|учёба|учеба|спорт|отдых|сон|чилл|бой|боя)\b",
            q,
        ) or re.search(
            r"\b(работа|учёба|учеба|спорт|отдых|сон|чилл|бой|боя)\b.*\b(музык\w*|плейлист|волна)\b",
            q,
        ):
            return {"type": "web_open", "params": {"url": _my_wave}}

        # STEM: Atomic Masses & Constants
        STEM_FAST = {
            "h": "1.008", "o": "15.999", "c": "12.011", "n": "14.007", 
            "na": "22.99", "cl": "35.45", "fe": "55.845",
            "g": "9.80665 m/s²", "c": "299,792,458 m/s", "pi": "3.14159",
            "h_planck": "6.626e-34 J·s", "g_const": "6.674e-11"
        }
        # Check for single element or constant
        if q in STEM_FAST:
            return f"VALUE [{q.upper()}]: {STEM_FAST[q]}"
        
        # Common greetings
        if q in ("привет", "хай", "здравствуй", "hello", "hi"):
            if name and name.lower() not in ("user", "челик", ""):
                return f"На связи, {name}. Системы в норме."
            return "На связи. Системы в норме."
        
        if q in ("я — челик", "я челик", "привет я челик"):
            return "Принято. Ожидаю ввод."

        # Time/Date
        if re.search(r"\b(время|time|сколько\s*времени)\b", q):
            return datetime.now().strftime("ТЕКУЩЕЕ ВРЕМЯ: %H:%M:%S")
        if re.search(r"\b(дата|date|число)\b", q):
            return datetime.now().strftime("СЕГОДНЯ: %Y-%m-%d")

        # System Monitor (Fast)
        if q in ("статус пк", "pc status", "нагрузка"):
            try:
                import psutil
                cpu = psutil.cpu_percent()
                ram = psutil.virtual_memory().percent
                return f"SYSTEM LOAD: CPU {cpu}% | RAM {ram}% | ALL SYSTEMS NOMINAL"
            except ImportError:
                return "Ошибка: модуль psutil не установлен."

        # PreRouter patterns (v7.9 Upgrade)
        # History Vault
        if q in ("история", "history", "факт о россии", "вмв", "ww2"):
            return f"ИСТОРИЧЕСКАЯ СПРАВКА: {InfoHub.get_history_fact()}"

        # Physics: "F=ma" or "сила"
        if q in ("f=ma", "сила", "force"):
            return "ФОРМУЛА: F = m * a (Сила = масса * ускорение)"
        if q in ("e=mc2", "энергия"):
            return "ФОРМУЛА: E = m * c² (Энергия = масса * скорость света в квадрате)"

        # Translate: "переведи привет на английский"
        m = re.search(r"(?:переведи|translate)\s+(.+?)\s+(?:на|to)\s+(английский|english|русский|russian|немецкий|german|французский|french)", q)
        if m:
            text_to_translate = m.group(1).strip()
            target_lang = m.group(2).strip()
            return {"type": "translate", "params": {"text": text_to_translate, "target": target_lang}}

        # Search: "найди в ютубе как приготовить пиццу"
        m = re.search(r"(?:найди|поиск|search)\s+(?:в\s+)?(?:ютуб[еа]|youtube)\s+(.+)$", q)
        if m:
            query = m.group(1).strip()
            url = f"https://www.youtube.com/results?search_query={urllib.request.quote(query)}"
            return {"type": "web_open", "params": {"url": url}}

        # Quick Math
        expr = q.replace(",", ".")
        if re.fullmatch(r"[\d\.\+\-\*\/\(\)\s]+", expr) and any(c in expr for c in "+-*/"):
            try:
                node = ast.parse(expr, mode="eval")
                allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Load)
                if all(isinstance(n, allowed) for n in ast.walk(node)):
                    result = eval(compile(node, "<math>", "eval"), {"__builtins__": {}}, {})
                    return f"RESULT: {result}"
            except Exception: pass
            
        return None

    @classmethod
    def _conversational_guard(cls, user_input, gui):
        """
        Short identity / slang / frustration phrases → chat only (before PreRouter).
        """
        raw = (user_input or "").strip()
        if not raw or len(raw) > 200:
            return None
        if best_match_against_templates(raw, cls._CONVERSATIONAL_TEMPLATES, threshold=76):
            llm = cls._get_llm_client(gui)
            if llm is None:
                return None
            payload = cls._build_chat_payload(user_input, gui)
            return True, llm.chat(payload)
        tl = raw.lower()
        if tl.startswith("нет ") and len(raw) < 55:
            if not re.search(r"\b(открой|запусти|выключи|закрой|напиши|отправь|включи|убей)\b", tl):
                llm = cls._get_llm_client(gui)
                if llm is None:
                    return None
                return True, llm.chat(cls._build_chat_payload(user_input, gui))
        return None

    @classmethod
    def _route_tool_mode(cls, user_input):
        """
        Deterministic local routing without LLM for operational commands.
        Returns action dict or None.
        """
        text = (user_input or "").strip()
        text = re.sub(r"\bтлгрм\b", "телеграм", text, flags=re.IGNORECASE)
        text = re.sub(r"\bтелега\b", "телеграм", text, flags=re.IGNORECASE)
        tl = text.lower()

        # Set user name (memory)
        m = re.search(r"^(?:сокол[, ]*)?(?:меня\s+зовут|звать\s+меня)\s+(.+)$", text, re.IGNORECASE)
        if m:
            name = m.group(1).strip().strip("\"'«»")
            if name:
                return {"type": "memory_set_user_name", "params": {"user_name": name}}

        # «открой чат с Мамой и напиши я дома»
        m = re.search(
            r"(?:открой\s+чат\s+с|чат\s+с)\s+(.+?)\s+и\s+(?:напиши|отправь)\s+(.+)$",
            text, re.IGNORECASE | re.DOTALL,
        )
        if m:
            return {"type": "messenger_send", "params": {
                "app": "telegram",
                "contact": m.group(1).strip().strip("«»\"'"),
                "message": m.group(2).strip().strip("\"'"),
            }}

        # «перейди в чат с Васей и отправь здорово»
        m = re.search(
            r"(?:перейди\s+в\s+чат\s+с|открой\s+диалог\s+с)\s+(.+?)\s+и\s+(?:напиши|отправь)\s+(.+)$",
            text, re.IGNORECASE | re.DOTALL,
        )
        if m:
            return {"type": "messenger_send", "params": {
                "app": "telegram",
                "contact": m.group(1).strip().strip("«»\"'"),
                "message": m.group(2).strip().strip("\"'"),
            }}

        # «напиши в телеграм чат с Иваном — завтра встреча» (тире отделяет текст)
        m = re.search(
            r"(?:напиши|отправь)\s+(?:в\s+)?(?:телеграм\w*|telegram)\s+(?:чат\s+)?(?:с\s+)?(.+?)\s*[—\-–]\s*(.+)$",
            text, re.IGNORECASE | re.DOTALL,
        )
        if m:
            return {"type": "messenger_send", "params": {
                "app": "telegram",
                "contact": m.group(1).strip(),
                "message": m.group(2).strip().strip("\"'"),
            }}

        # «напиши в телеграм Маме что я дома» (до общего «… что …», иначе контакт съедается)
        m = re.search(
            r"(?:напиши|отправь)\s+(?:в\s+)?(?:телеграм\w*|telegram)\s+(.+?)\s+что\s+(.+)$",
            text, re.IGNORECASE | re.DOTALL,
        )
        if m:
            rest = m.group(2).strip().strip("\"'")
            return {"type": "messenger_send", "params": {
                "app": "telegram",
                "contact": m.group(1).strip().strip("«»\"'"),
                "message": f"что {rest}",
            }}

        # «напиши Маме что я скоро буду» — не «напиши что такое …»
        m = re.search(
            r"(?:напиши|отправь)\s+(?!что\b)(.+?)\s+что\s+(.+)$",
            text, re.IGNORECASE | re.DOTALL,
        )
        if m:
            rest = m.group(2).strip().strip("\"'")
            return {"type": "messenger_send", "params": {
                "app": "telegram",
                "contact": m.group(1).strip().strip("«»\"'"),
                "message": f"что {rest}",
            }}

        # "открой телеграм и напиши лёхе "тест""
        m = re.search(
            r"(?:открой|запусти)\s+(?:телеграм\w*|telegram)\s+(?:и\s+)?(?:напиши|отправь)\s+([^\s,.;:!?]+)\s+(.+)$",
            text, re.IGNORECASE
        )
        if m:
            return {"type": "messenger_send", "params": {
                "app": "telegram",
                "contact": m.group(1).strip(),
                "message": m.group(2).strip().strip("\"'"),
            }}

        # «в телеграмме напиши Лёхе привет»
        m = re.search(
            r"(?:в\s+)(?:телеграм\w*|telegram)\s+(?:напиши|отправь|набери)\s+([^\s,.;:!?]+)\s+(.+)$",
            text, re.IGNORECASE | re.DOTALL,
        )
        if m:
            return {"type": "messenger_send", "params": {
                "app": "telegram",
                "contact": m.group(1).strip().strip("«»\"'"),
                "message": m.group(2).strip().strip("\"'"),
            }}
        m = re.search(
            r"(?:телеграм\w*|telegram)\s+(?:напиши|отправь|набери)\s+([^\s,.;:!?]+)\s+(.+)$",
            text, re.IGNORECASE | re.DOTALL,
        )
        if m:
            return {"type": "messenger_send", "params": {
                "app": "telegram",
                "contact": m.group(1).strip().strip("«»\"'"),
                "message": m.group(2).strip().strip("\"'"),
            }}

        # "напиши лёхе в телеграмме тест"
        m = re.search(
            r"(?:напиши|отправь)\s+([^\s,.;:!?]+)\s+(?:в\s+)?(?:телеграм\w*|telegram)\s+(.+)$",
            text, re.IGNORECASE
        )
        if m:
            return {"type": "messenger_send", "params": {
                "app": "telegram",
                "contact": m.group(1).strip(),
                "message": m.group(2).strip().strip("\"'"),
            }}

        # "напиши лёхе тест"
        m = re.search(r"(?:напиши|отправь)\s+([^\s,.;:!?]+)\s+(.+)$", text, re.IGNORECASE)
        if m:
            contact = m.group(1).strip()
            msg = m.group(2).strip().strip("\"'")
            if not msg:
                return {"type": "error_response", "params": {"message": "Вы не ввели текст сообщения для отправки."}}
            return {"type": "messenger_send", "params": {
                "app": "telegram",
                "contact": contact,
                "message": msg,
            }}
        
        # Empty messenger_send attempt
        if re.search(r"^(?:напиши|отправь)\s+([^\s,.;:!?]+)$", text.lower().strip()):
            return {"type": "error_response", "params": {"message": "Нужно ввести имя контакта и текст сообщения."}}

        # Operational shortcuts that should never hit LLM.
        if re.search(r"\b(?:папк[ауи]|файл|буфер|clipboard|скриншот|status|статус|очистка|snippet|сниппет)\b", tl, re.IGNORECASE):
            return PreRouter.route(text)
        return None

    @classmethod
    def _is_silent_mode(cls, user_input):
        text = (user_input or "").strip().lower()
        if not text:
            return False
        words = [w for w in re.split(r"\s+", text) if w]
        if len(words) >= 3:
            return False
        return bool(re.search(r"(тихо|без\s*лишнего|silent|quiet)", text))

    @classmethod
    def _friendly_contact_name(cls, raw_name):
        cls._load_contacts()
        name_raw = (raw_name or "").strip().lower()
        name_norm = cls._normalize_contact_key(name_raw)
        if name_raw in cls.CONTACTS:
            return cls.CONTACTS[name_raw]["title"]
        for k, v in cls.CONTACTS.items():
            if cls._normalize_contact_key(k) == name_norm:
                return v["title"]
        mapping = {
            "лёхе": "Алексей",
            "лехе": "Алексей",
            "леха": "Алексей",
            "лёха": "Алексей",
            "маме": "Мама",
            "мама": "Мама",
            "брату": "Брат",
            "брат": "Брат",
            "денис": "Denis",
            "федя": "Feedka",
            "федка": "Feedka",
            "статист": "PhoenIX",
            "даркнессу": "Darkness",
            "даркнесс": "Darkness",
            "мосе": "MosyaShow",
            "мосе шоу": "MosyaShow",
        }
        if name_raw in mapping:
            return mapping[name_raw]

        # soft normalization: strip common RU case endings and extra symbols
        base = re.sub(r"[^a-zа-я0-9]+", " ", name_raw, flags=re.IGNORECASE).strip()
        for suf in ("у", "е", "ой", "ю", "а", "я"):
            if len(base) > 4 and base.endswith(suf):
                candidate = base[:-len(suf)]
                if candidate in mapping:
                    return mapping[candidate]
        return raw_name.strip() if raw_name else ""

    @classmethod
    def _resolve_memory_placeholder(cls, text, gui):
        t = text or ""
        if re.search(r"(то,\s*что\s*я\s*запомнил|то\s*что\s*я\s*запомнил|what\s*i\s*saved)", t, re.IGNORECASE):
            saved = getattr(gui, "memory", None).recall_text() if getattr(gui, "memory", None) else ""
            return saved if saved else t
        if re.fullmatch(r"(это|saved|saved text|запомненное)", t.strip(), re.IGNORECASE):
            saved = getattr(gui, "memory", None).recall_text() if getattr(gui, "memory", None) else ""
            return saved if saved else t
        return t

    @classmethod
    def _to_latin_guess(cls, text):
        table = {
            "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
            "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
            "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
            "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
            "ы": "y", "э": "e", "ю": "yu", "я": "ya",
        }
        out = []
        for ch in (text or "").lower():
            out.append(table.get(ch, ch))
        guess = "".join(out)
        return re.sub(r"\s+", " ", guess).strip()

    @classmethod
    def _contact_candidates(cls, contact_raw):
        cls._load_contacts()
        name_raw = (contact_raw or "").strip().lower()
        
                # This ensures we search by @username if it exists in the database
        target_username = ""
        if name_raw in cls.CONTACTS:
            target_username = cls.CONTACTS[name_raw].get("username", "")
        else:
            # Try to find by title if key doesn't match
            norm = cls._normalize_contact_key(name_raw)
            for k, v in cls.CONTACTS.items():
                if cls._normalize_contact_key(k) == norm:
                    target_username = v.get("username", "")
                    break
        
        primary = cls._friendly_contact_name(contact_raw)
        
        # Priority order: @username -> Title -> raw input -> latin guess
        candidates = [
            c for c in [target_username, primary, contact_raw, cls._to_latin_guess(contact_raw)]
            if c and c.strip()
        ]
        
        # basic dedupe, keep order
        seen = set()
        result = []
        for c in candidates:
            k = c.lower().strip()
            if k not in seen:
                seen.add(k)
                result.append(c.strip())
        return result

    @classmethod
    def _verify_chat_target(cls, contact_raw, candidate, attempts=2, delay=0.4):
        """
        OCR verification that active chat likely matches target contact.
        v7.8.1: Refined 'Add Link' detection to prevent false positives.
        """
        cls._load_contacts()
        probes = [
            (candidate or "").lower(),
            cls._to_latin_guess(candidate).lower() if candidate else "",
            (contact_raw or "").lower(),
            cls._to_latin_guess(contact_raw).lower() if contact_raw else "",
        ]
        d = cls.CONTACTS.get((contact_raw or "").lower(), None)
        if d:
            probes.extend([(d.get("title") or "").lower(), (d.get("username") or "").lower()])
        probes = [p for p in probes if p]
        probes_norm = [cls._normalize_contact_key(p) for p in probes if p]

        for _ in range(max(1, attempts)):
            time.sleep(delay)
            ok_ocr, _, elements = VisionLite.ocr_screen()
            if ok_ocr and elements:
                hay = " ".join(e.get("text", "") for e in elements[:150]).lower()
                
                # BUG FIX: Refined detection of "Add Link" (Добавить ссылку) dialog.
                # Must see BOTH "url" and "текст" (or specific header) to trigger closure.
                is_link_dialog = ("добавить ссылку" in hay) or ("url" in hay and "отмена" in hay)
                
                if is_link_dialog:
                    # Link dialog confirmed. Close it.
                    for _ in range(2):
                        GUIAutomation.press("esc")
                        time.sleep(0.1)
                    return False

                hay_norm = cls._normalize_contact_key(hay)
                if any(p in hay for p in probes) or any(p and p in hay_norm for p in probes_norm):
                    return True
        return False

    @classmethod
    def _sanitize_message(cls, msg):
        if not isinstance(msg, str):
            return msg
        # Hide local filesystem paths in UI-facing messages.
        sanitized = re.sub(r"[A-Za-z]:\\[^\n\r]+", "[локальный путь скрыт]", msg)
        return sanitized

    @classmethod
    def _style_success_message(cls, atype, msg, target=""):
        # v7.9 Upgrade: Ultra-neutral & brief responses (no technical details)
        friendly = {
            "launch_app": "Приложение запущено.",
            "open_app": "Приложение запущено.",
            "open_web": "Сервис открыт.",
            "messenger_send": "Сообщение отправлено.",
            "app_write": "Текст введён.",
            "memory_set_user_name": "Имя сохранено.",
            "memory_save_clipboard": "Записано в память.",
            "memory_save_text": "Записано в память.",
            "file_create_folder": "Папка создана.",
            "file_create": "Файл создан.",
            "file_append": "Добавлено.",
            "file_search_content": "Найдено.",
            "agentic_control": "Выполнено.",
            "system_tool": "Инструмент запущен.",
            "volume_mute": "Звук выключен.",
            "volume_up": "Громкость увеличена.",
            "volume_down": "Громкость уменьшена.",
        }
        if atype in friendly:
            return friendly[atype]
        return msg

    @classmethod
    def _finalize_response(cls, ok, msg, atype="", target=""):
        msg = cls._sanitize_message(msg)
        if ok:
            msg = cls._style_success_message(atype, msg, target=target)
        return ok, msg

    @classmethod
    def _get_llm_client(cls, gui):
        """
        Resolve LLM client from GUI object.
        Main GUI stores client as `ollama`; keep `llm` as backward-compatible fallback.
        """
        client = getattr(gui, "ollama", None)
        if client is not None:
            return client
        return getattr(gui, "llm", None)

    @classmethod
    def _prefer_chat_over_classify(cls, user_input, gui):
        text = (user_input or "").strip()
        if not text:
            return False
        low = text.lower()
        q_words = re.sub(r"[^\w\sа-яё]+", " ", low)
        q_words = re.sub(r"\s+", " ", q_words).strip()
        if re.search(
            r"\b(кто\s+я|как\s+меня\s+зовут|как\s+зовут\s+меня|какое\s+у\s+меня\s+имя|моё\s+имя|мое\s+имя|как\s+тебя\s+зовут)\b",
            q_words,
        ):
            return True
        turns = getattr(gui.memory, "session_turns", None) or []
        if turns and turns[-1].get("role") == "assistant":
            # Short imperatives after a reply can still be PC commands; long or "correction" text is chat.
            if len(text) > 360:
                return True
            if len(text) >= 80:
                return True
            if cls._CONTINUATION_RE.search(text):
                return True
            if cls._CHESS_MOVE_RE.search(text) and len(text) > 15:
                return True
        if len(text) > 360:
            return True
        if cls._CONTINUATION_RE.search(text):
            return True
        if cls._CHESS_MOVE_RE.search(text) and len(text) > 15:
            return True
        return False

    @classmethod
    def _build_chat_payload(cls, user_input, gui):
        note_ctx = recall_note_hints(gui.memory, user_input)
        sess = gui.memory.get_session_context()
        chat_payload = user_input
        if sess:
            chat_payload = f"[Недавний диалог]\n{sess}\n\n[Запрос]\n{user_input}"
        if note_ctx:
            chat_payload = chat_payload + "\n\n[Заметки пользователя]\n" + note_ctx
        return chat_payload

    @classmethod
    def _classify_user_message(cls, user_input, gui):
        sess = gui.memory.get_session_context(max_turns=4)
        tail = (user_input or "").strip()
        if sess:
            return f"Контекст недавнего диалога:\n{sess}\n\nТекущая реплика:\n{tail}"
        return tail

    @classmethod
    def dispatch(cls, user_input, gui):
        """
        Unified dispatch with instant pre-routing:
          1) quick local answers (time/date/math),
          2) regex PreRouter,
          3) LLM classify/chat fallback.
        """
        silent_mode = cls._is_silent_mode(user_input)

        quick = cls._quick_answer(user_input, gui)
        if quick is not None:
            if isinstance(quick, dict):
                quick = coerce_action_dict(quick)
                ok, msg = cls.execute_action(quick, gui, user_input=user_input)
                ok, msg = cls._finalize_response(
                    ok, msg, atype=quick.get("type", ""), target=quick.get("target", "")
                )
                if silent_mode and ok:
                    return True, "__SILENT__"
                return ok, msg
            if silent_mode:
                return True, "__SILENT__"
            return True, quick

        conv = cls._conversational_guard(user_input, gui)
        if conv is not None:
            _ok, cmsg = conv
            ok, msg = cls._finalize_response(True, cmsg, atype="chat")
            if silent_mode and ok:
                return True, "__SILENT__"
            return ok, msg

        tool_action = cls._route_tool_mode(user_input)
        if tool_action:
            tool_action = coerce_action_dict(tool_action)
            ok, msg = cls.execute_action(tool_action, gui, user_input=user_input)
            ok, msg = cls._finalize_response(
                ok, msg, atype=tool_action.get("type", ""), target=tool_action.get("target", "")
            )
            if silent_mode and ok:
                return True, "__SILENT__"
            return ok, msg

        pre_action = PreRouter.route(user_input)
        if pre_action:
            pre_action = coerce_action_dict(pre_action)
            ok, msg = cls.execute_action(pre_action, gui, user_input=user_input)
            ok, msg = cls._finalize_response(
                ok, msg, atype=pre_action.get("type", ""), target=pre_action.get("target", "")
            )
            if silent_mode and ok:
                return True, "__SILENT__"
            return ok, msg

        llm = cls._get_llm_client(gui)
        if llm is None:
            return False, "LLM unavailable."

        if cls._prefer_chat_over_classify(user_input, gui):
            chat_payload = cls._build_chat_payload(user_input, gui)
            ok, msg = cls._finalize_response(True, llm.chat(chat_payload), atype="chat")
            if silent_mode and ok:
                return True, "__SILENT__"
            return ok, msg

        classify_user = cls._classify_user_message(user_input, gui)
        classify_response = llm.classify(classify_user)
        rtype, action = cls.parse_classify(classify_response)
        if rtype == "action" and action:
            validated, verr = validate_llm_action(action)
            if verr:
                _log.warning("LLM action validation failed: %s", verr)
                rtype, action = "chat", None
            else:
                action = validated
        if rtype == "action" and action:
            ok, msg = cls.execute_action(action, gui, user_input=user_input)
            ok, msg = cls._finalize_response(
                ok, msg, atype=action.get("type", ""), target=action.get("target", "")
            )
            if silent_mode and ok:
                return True, "__SILENT__"
            return ok, msg
        chat_payload = cls._build_chat_payload(user_input, gui)
        ok, msg = cls._finalize_response(True, llm.chat(chat_payload), atype="chat")
        if silent_mode and ok:
            return True, "__SILENT__"
        return ok, msg

    @classmethod
    def execute_action(cls, action, gui, user_input=""):
        """Execute structured action. Returns (success, message)."""
        if not isinstance(action, dict):
            return False, "Некорректное действие."
        action = coerce_action_dict(action)
        atype = action.get("type", "").lower()
        target = action.get("target", "")
        params = action.get("params", {})

        try:
            sec = policy.prepare_security_confirmation(action, gui)
            if sec is not None:
                ok_sec, magic = sec
                return ok_sec, magic

            # ── Fast Errors ──
            if atype == "error_response":
                return False, params.get("message", "Произошла ошибка.")

            if atype == "translate":
                text = params.get("text", "")
                target_lang = params.get("target", "english")
                prompt = f"Переведи этот текст на {target_lang}: {text}. Ответь только переводом."
                res = gui.ollama.chat(prompt, one_shot=True)
                return True, res

            # ── Help ──
            if atype == "help":
                return True, HELP_TEXT

            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            # AGENTIC CONTROL (v7.2 — NEW)
            # Vision → Action loop for GUI automation
            # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            if atype == "agentic_control":
                gui.isChatMode = True # Set flag to block modal menus
                goal = params.get("goal", target)
                app_raw = params.get("app", "")
                # Translate Russian app name
                app_translated = RUS_APP_MAP.get(
                    app_raw.lower().strip(), app_raw
                ) if app_raw else None

                if not goal:
                    return False, "Agentic control needs a goal. Example: 'напиши в телеграм привет'"

                clean_goal = goal.strip()
                low_app = app_raw.lower().strip()
                if any(x in low_app for x in ["telegram", "телеграм", "ayugram", "аюграм"]):
                    goal = (
                        "focus Telegram window; use Ctrl+F to search contact; "
                        "type the contact name and press Enter; "
                        "IMMEDIATELY type the message into the text field (DO NOT click any icons or media); "
                        f"message to send: {clean_goal}; press Enter to send"
                    )
                elif "mspaint" in low_app or "paint" in low_app or "пейнт" in low_app:
                    goal = (
                        "open or focus Paint; choose suitable drawing tool; "
                        f"draw this: {clean_goal}"
                    )

                # Need LLM reference from GUI
                llm = cls._get_llm_client(gui)
                if llm is None:
                    return False, "LLM not available for agentic control."

                ok, msg = VisionAgent.run(
                    goal=goal,
                    app_name=app_translated,
                    llm=llm,
                    gui=gui,
                )
                gui.isChatMode = False # Reset flag
                gui.memory.record("agentic_control", {
                    "goal": goal, "app": app_raw, "success": ok
                })
                return ok, msg

            if atype == "memory_set_user_name":
                user_name = cls._safe_cast(params.get("user_name"), str, "").strip()
                if not user_name:
                    gui.isChatMode = False
                    return False, "Не указано имя. Пример: 'меня зовут Лёха'."
                gui.memory.pinned["user_name"] = user_name
                gui.memory._save_persistent()
                gui.isChatMode = False
                return True, f"Принято. Запомнил: {user_name}."

            if atype == "memory_save_clipboard":
                # Best effort: capture currently selected text before reading clipboard.
                try:
                    GUIAutomation.hotkey("ctrl", "c")
                    time.sleep(0.15)
                except Exception:
                    pass
                clip = ClipboardManager.read(gui.root)
                ok, msg = gui.memory.remember_text(clip or "", source="clipboard")
                if ok:
                    gui.memory.record("memory_save", {"source": "clipboard", "chars": len(clip or "")})
                return ok, msg

            if atype == "memory_save_text":
                text = cls._safe_cast(params.get("text"), str, "")
                ok, msg = gui.memory.remember_text(text, source="voice")
                if ok:
                    gui.memory.record("memory_save", {"source": "voice", "chars": len(text)})
                return ok, msg

            if atype == "app_write":
                app = cls._safe_cast(params.get("app"), str, "notepad")
                text = cls._safe_cast(params.get("text"), str, "")
                if not text:
                    return False, "Нет текста для ввода."
                SmartLauncher.launch(RUS_APP_MAP.get(app.lower().strip(), app))
                time.sleep(1.0)
                ok, msg = GUIAutomation.type_unicode(text) if any(ord(c) > 127 for c in text) else GUIAutomation.type_text(text)
                if ok:
                    gui.memory.record("app_write", {"app": app, "chars": len(text)})
                return ok, msg

            if atype == "messenger_focus":
                app_raw = cls._safe_cast(params.get("app"), str, "telegram")
                app_clean = app_raw.lower().replace("в ", "").strip()
                launch_target = RUS_APP_MAP.get(app_clean, app_clean)
                
                # Special handling for AyuGram
                if "аюграм" in app_clean or "ayugram" in app_clean:
                    launch_target = "ayugram"

                ok_launch, msg, path = SmartLauncher.launch(launch_target)
                if not ok_launch:
                    return False, f"Не удалось сфокусировать {app_raw}: {msg}"
                
                # Also open search by default for messengers (user expectation)
                if any(x in launch_target for x in ["telegram", "ayugram"]):
                    time.sleep(0.5)
                    GUIAutomation.hotkey_telegram_jump_chat()
                
                return True, f"Окно {app_raw} сфокусировано и поиск открыт."

            # ──# v8.0: Enhanced messenger_send with app_controller
            if atype == "messenger_send":
                gui.isChatMode = True
                app = cls._safe_cast(params.get("app"), str, "telegram")
                contact_raw = cls._safe_cast(params.get("contact"), str, "")
                message = cls._safe_cast(params.get("message"), str, "")
                message = cls._resolve_memory_placeholder(message, gui)
                
                if not contact_raw or not message:
                    gui.isChatMode = False
                    return False, "Need contact name and message text."

                # v8.0: Pronoun transformation (fallback if model didn't do it)
                final_message = message
                final_message = re.sub(r'\b(he|she|it) should\b', 'you should', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) must\b', 'you must', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) will\b', 'you will', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) can\b', 'you can', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) is\b', 'you are', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) has\b', 'you have', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) was\b', 'you were', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) said\b', 'you said', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) told\b', 'you told', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) asked\b', 'you asked', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) wants\b', 'you want', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) needs\b', 'you need', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) goes\b', 'you go', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) comes\b', 'you come', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) does\b', 'you do', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) did\b', 'you did', final_message, flags=re.IGNORECASE)
                # Russian pronouns
                final_message = re.sub(r'\b(he|she|it) should\b', 'you should', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) must\b', 'you must', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) will\b', 'you will', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) can\b', 'you can', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) is\b', 'you are', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) has\b', 'you have', final_message, flags=re.IGNORECASE)
                final_message = re.sub(r'\b(he|she|it) was\b', 'you were', final_message, flags=re.IGNORECASE)
                # Keep "I/my/me" as is
                # Keep "we/our/us" as is
                
                # AI text generation triggers
                ai_triggers = ["come up with something", "make something up", "something", "make up yourself", "some text"]
                if any(t in final_message.lower() for t in ai_triggers):
                    gui.root.after(0, gui._status, "SOKOL: generating text...")
                    prompt = (
                        f"User asked to send message to contact '{contact_raw}'.\n"
                        f"Their request: '{final_message}'.\n"
                        "Generate an appropriate, friendly and brief message from the user's perspective. "
                        "Respond with ONLY the message text, without extra words."
                    )
                    ai_text = gui.ollama.chat(prompt, one_shot=True)
                    if ai_text:
                        final_message = ai_text.strip().strip('"')

                # Try to get contact from advanced memory
                contact_username = contact_raw
                try:
                    if hasattr(gui, 'advanced_memory'):
                        contact_info = gui.advanced_memory.get_contact(contact_raw)
                        if contact_info:
                            contact_username = contact_info.get('telegram_username') or contact_info.get('alias', contact_raw)
                except:
                    pass

                # Use app_controller for improved reliability
                try:
                    app_controller = get_app_controller()
                    success, result_msg = app_controller.execute_command(
                        AppCommand(
                            action="send_message",
                            params={"contact": contact_username, "message": final_message},
                            target_app=AppType.TELEGRAM
                        )
                    )
                    
                    if success:
                        # Record in memory
                        gui.memory.record(
                            "messenger_send",
                            {"app": app, "contact": contact_username, "message": final_message},
                        )
                        
                        # Store in advanced memory if available
                        try:
                            if hasattr(gui, 'advanced_memory'):
                                gui.advanced_memory.add_conversation_turn(
                                    "user",
                                    f"Sent message to {contact_username}: {final_message}",
                                    intent="messenger_send",
                                    metadata={"app": app, "contact": contact_username}
                                )
                        except:
                            pass
                        
                        gui.isChatMode = False
                        return True, f"Message sent to {contact_username}: {final_message}"
                    else:
                        # Fallback to old method if app_controller fails
                        pass
                except:
                    pass

                # Fallback: Original automation method
                launch_target = RUS_APP_MAP.get(app.lower().strip(), app)
                is_telegram_like = any(x in (launch_target or "").lower() for x in ["telegram", "telégram", "ayugram", "ayugram"])
                
                messenger_ok = False
                for attempt in range(3):
                    ok_launch, _, _ = SmartLauncher.launch(launch_target)
                    if ok_launch or is_telegram_like:
                        # Check if window actually exists
                        title_candidates = ["Telegram Desktop", "Telegram", "Telégram", "AyuGram", "AyuGram Desktop", "AyuGram Max", "AyuGram MaxGround"]
                        for cand in title_candidates:
                            if GUIAutomation.focus_window(cand)[0]:
                                messenger_ok = True
                                break
                        if messenger_ok: break
                        
                        # Try by process
                        try:
                            from .tools import WindowFocuser
                            for proc_name in ["telegram", "ayugram"]:
                                if WindowFocuser.bring_to_front(proc_name)[0]:
                                    messenger_ok = True
                                    break
                        except:
                            pass
                        if messenger_ok: break
                        
                    time.sleep(1.5)
                
                if not messenger_ok:
                    gui.isChatMode = False
                    return False, "Error: Messenger not responding. Check if process is running."

                # Fast mode: optional bypass of EasyOCR
                fast_mode = bool(re.search(
                    r"\b(without ocr|no ocr)\b",
                    f"{(user_input or '')} {(final_message or '')}",
                    re.IGNORECASE
                ))

                # Phase 1: Search for contact (Ctrl+F)
                def _restore_sokol_window():
                    """Restore SOKOL window after messenger operation."""
                    try:
                        sokol_hwnd = GUIAutomation._get_sokol_hwnd()
                        if sokol_hwnd:
                            GUIAutomation.focus_window("SOKOL")
                    except:
                        pass

                try:
                    # v7.9.20: Extra Esc before Ctrl+F to clear any active popups
                    GUIAutomation.low_level_press(0x1B)  # VK_ESCAPE
                    time.sleep(0.3)

                    # --- STEP 2: Press Ctrl + F ---
                    GUIAutomation.hotkey_telegram_jump_chat()
                    time.sleep(1.2)

                    # --- STEP 3: Paste Username from contacts.json ---
                    ok_u, msg_u = GUIAutomation.type_unicode(contact_username)
                    if not ok_u: 
                        return False, f"Error typing name: {msg_u}"
                    time.sleep(2.5)

                    # --- STEP 4: Press Enter (to select the contact) ---
                    GUIAutomation.low_level_press(0x0D)
                    time.sleep(1.2)

                    # --- STEP 5: Paste the message text ---
                    gui.root.after(0, gui._status, f"Telegram: typing text...")
                    ok_t, msg_t = GUIAutomation.type_unicode(final_message)
                    if not ok_t: 
                        return False, f"Error typing message: {msg_t}"
                    time.sleep(0.5)

                    # --- STEP 6: Send it (Press Enter) ---
                    GUIAutomation.low_level_press(0x0D)
                    
                    gui.memory.record(
                        "messenger_send",
                        {"app": app, "contact": contact_username},
                    )
                    return True, f"Message sent: {final_message}"

                finally:
                    _restore_sokol_window()

            if atype == "file_create_folder":
                path = cls._safe_cast(params.get("path"), str, "").strip()
                if not path:
                    return False, "Не указан путь папки."
                ok, msg = FileAgent.create_folder(path)
                if ok:
                    gui.memory.record("file_create_folder", {"folder": path})
                return ok, msg

            if atype == "file_create":
                path = cls._safe_cast(params.get("path"), str, "").strip()
                content = cls._safe_cast(params.get("content"), str, "")
                if not path:
                    return False, "Не указан путь файла."
                ok, msg = FileAgent.create_file(path, content=content)
                if ok:
                    gui.memory.record("file_create", {"file": path})
                return ok, msg

            if atype == "file_append":
                path = cls._safe_cast(params.get("path"), str, "").strip()
                content = cls._safe_cast(params.get("content"), str, "")
                if not path:
                    return False, "Не указан путь файла."
                try:
                    existed = os.path.isfile(path)
                    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                    with open(path, "a", encoding="utf-8") as f:
                        f.write(("\n" if existed else "") + content)
                    gui.memory.record("file_append", {"file": path, "chars": len(content)})
                    return True, f"Updated: {path}"
                except Exception as e:
                    return False, f"Append failed: {e}"

            if atype == "file_read":
                path = cls._safe_cast(params.get("path"), str, "").strip()
                if not path:
                    return False, "Не указан путь файла."
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = f.read()
                    if not data:
                        return True, "(Пустой файл)"
                    return True, data[:6000]
                except Exception as e:
                    return False, f"Read failed: {e}"

            if atype == "file_search_content":
                query = cls._safe_cast(params.get("query"), str, "").strip()
                if not query:
                    return False, "Пустой поисковый запрос."
                root_dir = cls._safe_cast(params.get("root"), str, "")
                max_results = cls._safe_cast(params.get("max_results"), int, 40)
                return ContentSearch.search(
                    query=query,
                    root=root_dir or None,
                    max_results=max(5, min(max_results, 80)),
                )

            # ── Launch App ──
            if atype in ("launch_app", "open_app"):
                ok, msg, path = SmartLauncher.launch(target)
                if ok:
                    gui.memory.record("launch_app", {"app": target, "file": path})
                return ok, msg

            # ── Close App ──
            if atype == "close_app":
                ok, msg = ProcessKiller.kill(target)
                gui.memory.record("close_app", {"app": target})
                return ok, msg

            # ── System Tools ──
            if atype == "system_tool":
                ok, msg = SystemTools.launch(target)
                if ok:
                    gui.memory.record("system_tool", {"tool": target})
                    return True, msg
                try:
                    os.startfile(target)
                    gui.memory.record("system_tool", {"tool": target})
                    return True, f"Launched: {target}"
                except Exception:
                    return False, f"System tool not found: {target}"

            # ── Web ──
            if atype == "web_open":
                url = cls._safe_cast(params.get("url"), str, "").strip()
                if not url:
                    return False, "No URL in web_open action."
                import webbrowser

                webbrowser.open(url)
                gui.memory.record("open_web", {"target": url})
                return True, f"Opened: {url}"
            if atype == "open_web":
                url = cls._safe_cast(params.get("url"), str, "").strip()
                if url:
                    import webbrowser

                    webbrowser.open(url)
                    gui.memory.record("open_web", {"target": url})
                    return True, f"Opened: {url}"
                ok, msg = WebRouter.open_service(target)
                gui.memory.record("open_web", {"target": target})
                return ok, msg
            if atype == "web_search":
                ok, msg = WebRouter.web_search(target)
                gui.memory.record("web_search", {"query": target})
                return ok, msg
            if atype == "web_fetch":
                max_chars = cls._safe_cast(params.get("max_chars"), int, 5000)
                ok, text = WebFetcher.fetch_text(target, max_chars=max_chars)
                gui.memory.record("web_fetch", {"url": target})
                return ok, text
            if atype == "deep_research":
                # Start streaming research
                def stream_research():
                    try:
                        gui.isChatMode = True
                        for token in DeepResearchAgent.research(target, gui):
                            gui.ui_call(lambda t=token: gui.output.configure(state="normal"))
                            gui.ui_call(lambda t=token: gui.output.insert("end", t, "info"))
                            gui.ui_call(lambda t=token: gui.output.see("end"))
                            gui.ui_call(lambda t=token: gui.output.configure(state="disabled"))
                        gui.ui_call(lambda: gui._sep())
                        gui.ui_call(lambda: gui._set_busy(False))
                        gui.ui_call(lambda: gui._status("Ready"))
                        gui.isChatMode = False
                    except InterruptedError:
                        gui.ui_call(lambda: gui._append("\n✕ Research cancelled.", "error"))
                        gui.ui_call(lambda: gui._sep())
                        gui.isChatMode = False
                    except Exception as e:
                        gui.ui_call(lambda e=e: gui._append(f"\n❌ Research error: {e}", "error"))
                        gui.ui_call(lambda: gui._sep())
                        gui.isChatMode = False

                gui._append(f"Starting deep research on: {target}", "sokol")
                threading.Thread(target=stream_research, daemon=True).start()
                return True, "__SILENT__"

            # ── Media ──
            if atype == "media_play_pause":
                return True, MediaController.play_pause()
            if atype == "media_next":
                return True, MediaController.next_track()
            if atype == "media_prev":
                return True, MediaController.prev_track()
            if atype == "media_stop":
                return True, MediaController.stop()
            if atype == "volume_set":
                percent = cls._safe_cast(params.get("percent"), int, 50)
                return True, MediaController.set_volume(percent)
            if atype == "volume_up":
                steps = cls._safe_cast(params.get("steps"), int, 5)
                return True, MediaController.volume_up(steps)
            if atype == "volume_down":
                steps = cls._safe_cast(params.get("steps"), int, 5)
                return True, MediaController.volume_down(steps)
            if atype == "volume_mute":
                return True, MediaController.mute()

            # ── Power ──
            if atype == "power_shutdown":
                if not cls._is_explicit_power_intent(user_input):
                    seconds = cls._safe_cast(params.get("delay"), int, 60)
                    if seconds < 1:
                        seconds = 60
                    reminder_msg = (user_input or "Reminder").strip()
                    return True, gui.reminders.set_reminder(seconds, reminder_msg, gui)
                delay = cls._safe_cast(params.get("delay"), int, 30)
                return True, f"__CONFIRM_POWER__:shutdown:{delay}"
            if atype == "power_restart":
                delay = cls._safe_cast(params.get("delay"), int, 30)
                return True, f"__CONFIRM_POWER__:restart:{delay}"
            if atype == "power_sleep":
                return True, "__CONFIRM_POWER__:sleep:0"
            if atype == "power_lock":
                return True, PowerController.lock()
            if atype == "power_hibernate":
                return GUIAutomation.hibernate()
            if atype == "power_cancel":
                return True, PowerController.cancel_shutdown()

            # ── Desktop ──
            if atype == "empty_recycle_bin":
                return GUIAutomation.empty_recycle_bin()
            if atype == "open_disc_drive":
                return GUIAutomation.open_disc_drive()
            if atype == "close_disc_drive":
                return GUIAutomation.close_disc_drive()

            # ── Screenshot ──
            if atype == "screenshot":
                ok, msg, path = ScreenCapture.take()
                if path:
                    gui.memory.record("screenshot", {"file": path})
                return ok, msg

            # ── Window Management ──
            if atype == "show_desktop":
                return True, ScreenManager.show_desktop()
            if atype == "window_snap_left":
                return True, WindowManager.snap_left()
            if atype == "window_snap_right":
                return True, WindowManager.snap_right()
            if atype == "window_maximize":
                return True, WindowManager.maximize()
            if atype == "window_minimize":
                return True, WindowManager.minimize()
            if atype == "window_task_view":
                return True, WindowManager.task_view()
            if atype == "window_alt_tab":
                return True, WindowManager.alt_tab()
            if atype == "window_close":
                return True, WindowManager.close_window()

            # ── Clipboard ──
            if atype == "clipboard_read":
                return True, "__CLIPBOARD_READ__"
            if atype == "clipboard_transform":
                transform = params.get("transform", "fix_spelling")
                return True, f"__CLIPBOARD_TRANSFORM__:{transform}"

            # ── Network ──
            if atype == "network_ping":
                host = target if target else "8.8.8.8"
                return True, f"━━━ Ping {host} ━━━\n{NetworkDiag.ping(host)}\n━━━━━━━━━━━━━━"
            if atype == "network_info":
                return True, f"━━━ Network Info ━━━\n{NetworkDiag.get_ip_info()}\n━━━━━━━━━━━━━━"
            if atype == "network_speed":
                return True, NetworkDiag.speedtest_lite()
            if atype == "network_traceroute":
                return True, NetworkDiag.traceroute(target or "8.8.8.8")

            # ── System ──
            if atype == "system_status":
                return True, SystemTriage.get_report()
            if atype == "system_quick_status":
                return True, SystemQuickInfo.get_status()
            if atype == "system_dashboard":
                return True, SystemDashboard.get_full_report()
            if atype == "event_viewer":
                count = cls._safe_cast(params.get("count"), int, 15)
                return True, SystemDashboard.get_event_viewer_errors(count)

            # ── Reminders ──
            if atype == "reminder_set":
                seconds = cls._safe_cast(params.get("seconds"), int, 60)
                message = cls._safe_cast(params.get("message"), str, "")
                return True, gui.reminders.set_reminder(seconds, message, gui)
            if atype == "reminder_list":
                return True, gui.reminders.list_active()

            # ── Files ──
            if atype == "recent_files":
                folder_name = cls._safe_cast(params.get("folder"), str, "downloads")
                count = min(cls._safe_cast(params.get("count"), int, 10), 50)
                folder = FileMachine.resolve_folder(folder_name)
                if not folder:
                    return False, f"Folder not found: {folder_name}"
                files = FileMachine.recent_files(folder, count)
                gui.memory.record("recent_files", {"folder": folder})
                return True, FileMachine.format_report(folder_name, files)
            if atype == "open_folder":
                folder = FileMachine.resolve_folder(target) or target
                if os.path.isdir(folder):
                    os.startfile(folder)
                    gui.memory.record("open_folder", {"folder": folder})
                    return True, f"Opened folder: {folder}"
                return False, f"Folder not found: {target}"

            # ── Info panels ──
            if atype == "list_windows":
                return True, WindowEnumerator.format_report()
            if atype == "list_startup":
                return True, StartupManager.format_report()
            if atype == "wifi_passwords":
                return True, WiFiManager.get_all_passwords()
            if atype == "large_files":
                min_mb = cls._safe_cast(params.get("min_mb"), int, 50)
                files = DiskAnalyzer.find_large_files(
                    params.get("directory"), min_mb=min_mb)
                return True, DiskAnalyzer.format_report(files)

            # ── STEM & Info ──
            if atype == "stem_molar_mass":
                return True, STEMCore.get_molar_mass(params.get("formula", ""))
            if atype == "stem_constant":
                return True, STEMCore.get_constant(params.get("name", ""))
            if atype == "get_joke":
                return True, InfoHub.get_joke()
            if atype == "get_fact":
                return True, InfoHub.get_fact()
            if atype == "get_history":
                return True, InfoHub.get_history_fact()
            if atype == "coin_flip":
                res = random.choice(["Орёл", "Решка"])
                return True, f"Результат: {res}"

            # ── Terminal ──
            if atype == "terminal_ps":
                timeout = cls._safe_cast(params.get("timeout"), int, 30)
                ok, output = TerminalExecutor.run_powershell(target, timeout=timeout)
                gui.memory.record("terminal", {"command": target[:50]})
                return ok, f"━━━ PowerShell ━━━\n{output}\n━━━━━━━━━━━━━━"
            if atype == "terminal_cmd":
                timeout = cls._safe_cast(params.get("timeout"), int, 30)
                ok, output = TerminalExecutor.run_cmd(target, timeout=timeout)
                gui.memory.record("terminal", {"command": target[:50]})
                return ok, f"━━━ CMD ━━━\n{output}\n━━━━━━━━━━━━━━"

            # ── OCR ──
            if atype == "ocr_screen":
                # v8.0: Minimize SOKOL, read screen, restore
                ok, msg, elements = VisionLite.ocr_screen(minimize_first=True)
                if ok:
                    return True, VisionLite.ocr_report()
                return False, msg
            if atype == "ocr_click":
                return VisionLite.click_text(target)

            # ── Bulk File Ops ──
            if atype == "bulk_rename":
                return BulkFileOps.rename_batch(
                    params.get("folder", ""), params.get("pattern", ""), params.get("replacement", ""))
            if atype == "bulk_delete":
                return BulkFileOps.delete_by_extension(params.get("folder", ""), params.get("extension", ""))
            if atype == "bulk_zip":
                return BulkFileOps.zip_folder(params.get("folder", ""), params.get("output", None))
            if atype == "bulk_unzip":
                return BulkFileOps.unzip(params.get("file", ""), params.get("output", None))
            if atype == "bulk_move":
                return BulkFileOps.move_by_extension(
                    params.get("src", ""), params.get("dest", ""), params.get("extension", ""))

            # ── Steam and Discord Integration ──
            if atype == "steam_launch_game":
                game_name = cls._safe_cast(params.get("game"), str, "")
                if not game_name:
                    return False, "Need game name to launch"
                
                try:
                    app_controller = get_app_controller()
                    success, result_msg = app_controller.execute_command(
                        AppCommand(
                            action="launch_game",
                            params={"game": game_name},
                            target_app=AppType.STEAM
                        )
                    )
                    if success:
                        gui.memory.record("steam_launch_game", {"game": game_name})
                        return True, result_msg
                    else:
                        return False, result_msg
                except Exception as e:
                    return False, f"Steam error: {e}"
            
            # v8.0: Discord Integration
            if atype == "discord_send_message":
                channel = cls._safe_cast(params.get("channel"), str, "")
                message = cls._safe_cast(params.get("message"), str, "")
                if not channel or not message:
                    return False, "Need channel and message for Discord"
                
                try:
                    app_controller = get_app_controller()
                    success, result_msg = app_controller.execute_command(
                        AppCommand(
                            action="send_message",
                            params={"channel": channel, "message": message},
                            target_app=AppType.DISCORD
                        )
                    )
                    if success:
                        gui.memory.record("discord_send_message", {"channel": channel, "message": message})
                        return True, result_msg
                    else:
                        return False, result_msg
                except Exception as e:
                    return False, f"Discord error: {e}"

            # v8.0: App Status Check
            if atype == "app_status":
                app_name = cls._safe_cast(params.get("app"), str, "").lower()
                app_type = None
                
                if "telegram" in app_name or "ayugram" in app_name:
                    app_type = AppType.TELEGRAM
                elif "steam" in app_name:
                    app_type = AppType.STEAM
                elif "discord" in app_name:
                    app_type = AppType.DISCORD
                
                if app_type:
                    try:
                        app_controller = get_app_controller()
                        status = app_controller.get_app_status(app_type)
                        status_text = f"App: {app_name}\n"
                        status_text += f"Running: {'Yes' if status['running'] else 'No'}\n"
                        status_text += f"Available: {'Yes' if status['available'] else 'No'}"
                        return True, status_text
                    except Exception as e:
                        return False, f"Status check error: {e}"
                else:
                    return False, f"Unsupported app for status check: {app_name}"

            # ── Special Modes ──
            if atype == "system_cleanup":
                from .special_modes import SystemCleanup
                return True, SystemCleanup.run()

            if atype == "deep_clean":
                return True, DeepClean.full_clean()
            if atype == "gaming_mode_on":
                return True, GamingMode.activate()
            if atype == "gaming_mode_off":
                return True, GamingMode.deactivate()
            if atype == "ghost_mode_on":
                def ghost_alert(msg):
                    gui.root.after(0, gui._append, f"\n{msg}", "warning")
                    gui.root.after(0, gui._sep)
                return True, GhostMode.start(alert_callback=ghost_alert)
            if atype == "ghost_mode_off":
                return True, GhostMode.stop()
            if atype == "ghost_status":
                return True, GhostMode.get_status()

            # ── Services ──
            if atype == "service_list":
                services = ServiceManager.list_services(params.get("filter"))
                if not services:
                    return True, "No services found."
                lines = ["━━━ Windows Services ━━━"]
                for s in services[:30]:
                    lines.append(f"  [{s.get('state','?'):7}] {s.get('name','')}")
                lines.append("━" * 35)
                return True, "\n".join(lines)
            if atype == "service_start":
                return ServiceManager.start_service(target)
            if atype == "service_stop":
                return ServiceManager.stop_service(target)
            if atype == "service_restart":
                return ServiceManager.restart_service(target)

            # ── GUI Automation ──
            if atype == "gui_dictate":
                return GUIAutomation.type_dictation(params.get("text", ""))
            if atype == "gui_click":
                x = cls._safe_cast(params.get("x"), int, 0)
                y = cls._safe_cast(params.get("y"), int, 0)
                return GUIAutomation.click(x, y)
            if atype == "gui_type":
                t = params.get("text", "")
                if any(ord(c) > 127 for c in t):
                    return GUIAutomation.type_unicode(t)
                return GUIAutomation.type_text(t)
            if atype == "gui_hotkey":
                keys = params.get("keys", [])
                return GUIAutomation.hotkey(*keys) if keys else (False, "No keys.")
            if atype == "gui_scroll":
                clicks = cls._safe_cast(params.get("clicks"), int, 3)
                return GUIAutomation.scroll(clicks)

            # ── Quick Note ──
            if atype == "quick_note":
                return cls._save_note(params.get("text", ""), params.get("name", "note"))

            # ── Visual Snippet ──
            if atype == "visual_snippet":
                gui.isChatMode = True
                def _do_snippet():
                    try:
                        # 1. Capture screen with selection (simulated for now by full screen OCR)
                        # In real use, this would trigger a region selector GUI.
                        # For now, we take full screenshot and process it.
                        ok, msg, elements = VisionLite.ocr_screen()
                        if not ok:
                            gui.ui_call(lambda: gui._append(f"Snippet error: {msg}", "error"))
                            return
                        
                        text_found = "\n".join([e["text"] for e in elements])
                        if not text_found.strip():
                            gui.ui_call(lambda: gui._append("Текст не обнаружен.", "warning"))
                            return
                        
                        # 2. Save to Sokol_Notes.txt
                        with open(NOTES_PATH, "a", encoding="utf-8") as f:
                            f.write(f"\n--- Snippet {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")
                            f.write(text_found)
                            f.write("\n-----------------------------------\n")
                        
                        gui.ui_call(lambda: gui._append(f"Сниппет сохранен в {os.path.basename(NOTES_PATH)}", "success"))
                        
                        # 3. Check if it's a question (simple check)
                        if "?" in text_found or any(q in text_found.lower() for q in ["найти", "реши", "что такое", "как"]):
                            gui.ui_call(lambda: gui._append("Обнаружен вопрос. Отправляю в LLM...", "info"))
                            # Trigger Phase 2 (chat) with the found text
                            threading.Thread(target=gui._process, args=(text_found,), daemon=True).start()
                    finally:
                        gui.isChatMode = False
                
                threading.Thread(target=_do_snippet, daemon=True).start()
                return True, "__SILENT__"

            # ── Identity ──
            if atype == "identity":
                backend = SOKOL_GPU_BACKEND.upper()
                return True, (
                    f"SOKOL v{VERSION} — Autonomous OS Control Agent\n"
                    f"   Model:   {OLLAMA_MODEL}\n"
                    f"   Backend: Ollama @ {OLLAMA_API_BASE}\n"
                    "   Engine:  PreRouter + VisionAgent + LLM\n"
                    f"   GPU:     {backend}\n"
                    "\n   Type 'help' for full command list."
                )

            return False, f"Unknown action: {atype}"

        except InterruptedError:
            gui.isChatMode = False
            raise
        except Exception as e:
            gui.isChatMode = False
            return False, f"Action error: {e}"

    @classmethod
    def _save_note(cls, text, name="note"):
        from .config import USER_HOME
        from datetime import datetime
        notes_dir = os.path.join(USER_HOME, "Desktop", "Sokol_Notes")
        os.makedirs(notes_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(notes_dir, f"{name}_{ts}.txt")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text)
            return True, f"Note saved: {filepath}"
        except Exception as e:
            return False, f"Failed: {e}"
