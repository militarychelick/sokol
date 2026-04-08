# -*- coding: utf-8 -*-
"""Instant regex routing (PreRouter) and help text."""
import re
import textwrap

from .config import VERSION, SYSTEM_TOOLS, WEB_SERVICES, FOLDER_ALIASES, RUS_APP_MAP
from .fuzzy_match import best_match

HELP_TEXT = textwrap.dedent(f"""\
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   SOKOL v{VERSION} — Справка / Help
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  🚀 Приложения: «открой телеграм», «запусти стим»
     ✨ Новое: распознаёт 100+ игр и программ
     "роблокс", "варно", "кс", "дота", "гта", "майнкрафт"
  
  ❌ Закрытие: «закрой дискорд», «убей хром»
  
  🔧 Система: «диспетчер задач», «regedit»
  🌐 Веб: «открой ютуб», «загугли погоду»
  🎵 Медиа: «громкость 50%», «пауза», «следующий трек»
  
  📸 Скриншот: «скриншот», «screenshot», «сниппет»
  
  📁 Файлы: «покажи загрузки», «сожми в ZIP»
     ✨ Новое: создание файлов теперь с поддержкой прав администратора
  
  💻 Терминал: «выполни ipconfig», «powershell ...»
  
  📊 Система: «статус», «dashboard», «мониторинг»
     ✨ Новое: системный монитор CPU/RAM/GPU в реальном времени
  
  📋 Буфер обмена: «история буфера», «покажи буфер»
     ✨ Новое: история последних 50 копирований с поиском
  
  🌐 Сеть: «пинг», «мой IP», «пароли WiFi»
  ⏰ Таймеры: «напомни через 10 мин»
  
  🎮 Режимы: «gaming mode», «ghost mode», «deep clean»
  
  ⚡ Питание: «выключи ПК», «перезагрузка», «сон»
  
  👁 Зрение: «прочитай экран», «нажми на кнопку Ок»
     ✨ Автоматизация: «напиши в телеграм привет», «нарисуй в пейнте»
  
  🧪 STEM: «масса H2O», «константа c»
  
  ✨ Сокол v8.0:
     • Расширенный словарь: 100+ приложений и игр
     • Разделение Telegram / AyuGram
     • Улучшенная работа с файлами (UAC-aware)
     • Системный мониторинг ресурсов
     • История буфера обмена
     • Умный поиск приложений (LLM lookup)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")


class PreRouter:
    """
    Regex-based instant command routing.
    Runs BEFORE any LLM call. If a pattern matches, the command
    executes immediately with 0 latency.

    v7.2 FIX: "включи музыку" now correctly triggers media_play_pause
    instead of launching SmartLauncher (which found TLauncher via fuzzy match).
    """

    # ── Static patterns (no capture groups, fixed actions) ──
    STATIC_PATTERNS = [
        # === MUSIC FIX (v7.2) ===
        # These MUST be before OPEN_RE to prevent "включи музыку" → launch_app
        (r"\b(?:включи|вруби|врубай)\s+(?:музык|music|мелоди|песн|song|трек|track)", {"type": "media_play_pause"}),
        (r"\b(?:поставь|играй|запусти)\s+(?:музык|music|мелоди|песн|song|трек|track)", {"type": "media_play_pause"}),

        # Media control
        (r"(?:следующ\w*\s*(?:трек|песн|track|song)|next\s*track)", {"type": "media_next"}),
        (r"(?:предыдущ\w*\s*(?:трек|песн|track|song)|prev(?:ious)?\s*track)", {"type": "media_prev"}),
        (r"\b(?:пауза|pause|play\b|воспроизвед|плей|resume)\b", {"type": "media_play_pause"}),
        (r"\b(?:стоп|stop)\s*(?:музык|music|трек|track)?$", {"type": "media_stop"}),
        (r"\b(?:мут|mute|без\s*звук)", {"type": "volume_mute"}),
        (r"\b(?:громче|louder|volume\s*up|звук\s*(?:выше|больше|прибав))", {"type": "volume_up"}),
        (r"\b(?:тише|quieter|volume\s*down|звук\s*(?:ниже|меньше|убав))", {"type": "volume_down"}),

        # Desktop / Window management
        (r"\b(?:сверни\s*(?:окно|все)|minimize\s*window)\b", {"type": "window_minimize"}),
        (r"\b(?:разверни\s*(?:окно)|maximize\s*window)\b", {"type": "window_maximize"}),
        (r"\b(?:закрой\s*(?:окно)|close\s*window)\b", {"type": "window_close"}),
        (r"\b(?:очисти\s*корзину|empty\s*recycle\s*bin)\b", {"type": "empty_recycle_bin"}),
        (r"\b(?:открой\s*(?:дисковод|привод)|open\s*disc\s*drive)\b", {"type": "open_disc_drive"}),
        (r"\b(?:закрой\s*(?:дисковод|привод)|close\s*disc\s*drive)\b", {"type": "close_disc_drive"}),

        # System
        (r"\b(?:очистка|cleanup|clean\s*up|очисти\s*процессы)\b", {"type": "system_cleanup"}),
        (r"\b(?:скриншот|screenshot|снимок\s*экран)\b", {"type": "screenshot"}),
        (r"\b(?:рабочий\s*стол|show\s*desktop)\b", {"type": "show_desktop"}),
        (r"\b(?:заблокируй|lock\s*screen|блокировк|залочи)\b", {"type": "power_lock"}),
        (r"\b(?:выключи\s*(?:пк|комп|компьютер)|shutdown|shut\s*down)\b", {"type": "power_shutdown", "params": {"delay": 30}}),
        (r"\b(?:перезагру[зж]|restart|reboot)\b", {"type": "power_restart", "params": {"delay": 30}}),
        (r"\b(?:спящий|режим\s*сна|sleep|усни)\b", {"type": "power_sleep"}),
        (r"\b(?:гибернация|hibernate)\b", {"type": "power_hibernate"}),
        (r"\b(?:отмени\s*(?:выключен|перезагру|shutdown)|cancel\s*shutdown)\b", {"type": "power_cancel"}),

        # Fun / Social
        (r"\b(?:расскажи\s*шутку|пошути|joke)\b", {"type": "get_joke"}),
        (r"\b(?:расскажи\s*факт|интересный\s*факт|fact)\b", {"type": "get_fact"}),
        (r"\b(?:история|исторический\s*факт|history)\b", {"type": "get_history"}),
        (r"\b(?:брось\s*монетку|орел\s*или\s*решка|flip\s*a\s*coin)\b", {"type": "coin_flip"}),

        # Info
        (r"\b(?:статус|status|состояни[ея]\s*систем)\b", {"type": "system_status"}),
        (r"\b(?:cpu|процессор|нагрузк\w*\s*процессор|быстрый\s*статус)\b", {"type": "system_quick_status"}),
        (r"\b(?:dashboard|дашборд|полн\w*\s*отчёт)\b", {"type": "system_dashboard"}),
        (r"\b(?:event\s*viewer|ошибки\s*(?:систем|журнал)|критическ\w*\s*ошибк)\b", {"type": "event_viewer"}),
        (r"\b(?:буфер|clipboard|что\s*(?:в|на)\s*буфер)\b", {"type": "clipboard_read"}),
        (r"\b(?:deep\s*clean|глубок\w*\s*очистк|очисти\s*систем)\b", {"type": "deep_clean"}),
        (r"\b(?:gaming\s*mode|игров\w*\s*режим)\b", {"type": "gaming_mode_on"}),
        (r"\b(?:ghost\s*mode|призрач\w*\s*режим|фонов\w*\s*монитор)\b", {"type": "ghost_mode_on"}),
        (r"\b(?:help|справка|помощь|хелп)\b", {"type": "help"}),
        (r"(?:что\s*(?:ты\s*)?умеешь|твои\s*(?:функци|возможност|команд))", {"type": "help"}),
        (r"\b(?:кто\s*ты|who\s*are\s*you|identity)\b", {"type": "identity"}),
        (r"\b(?:мой\s*ip|my\s*ip|network\s*info|сетев\w*\s*инф)\b", {"type": "network_info"}),
        (r"\b(?:speed\s*test|скорость\s*(?:сети|интернет))\b", {"type": "network_speed"}),
        (r"\b(?:wifi\s*пароли?|пароли?\s*wifi|wifi\s*password)\b", {"type": "wifi_passwords"}),
        (r"\b(?:список\s*окон|list\s*windows|открыт\w*\s*окн)\b", {"type": "list_windows"}),
        (r"\b(?:автозагрузк|startup|автозапуск)\b", {"type": "list_startup"}),
        (r"\b(?:прочитай\s*экран|read\s*screen|ocr|распознай\s*текст)\b", {"type": "ocr_screen"}),
        (r"\b(?:alt\s*tab)\b", {"type": "window_alt_tab"}),
    ]

    # ── Dynamic patterns (with capture groups) ──
    DYNAMIC_PATTERNS = [
        # Memory commands
        (r"(?:сокол[, ]*)?(?:запомни\s*(?:это|текст)?|remember\s*this)\s*$",
         lambda m: {"type": "memory_save_clipboard", "params": {"source": "clipboard"}}),
        (r"(?:сокол[, ]*)?(?:запомни)\s+(.+)$",
         lambda m: {"type": "memory_save_text", "params": {"text": m.group(1).strip()}}),
        (r"(?:создай|create)\s+папк[ауи]?\s+(.+)$",
         lambda m: {"type": "file_create_folder", "params": {"path": m.group(1).strip()}}),
        (r"(?:создай|create)\s+файл\s+(.+?)\s+(?:с\s*текстом|with\s*text)\s+(.+)$",
         lambda m: {"type": "file_create", "params": {"path": m.group(1).strip(), "content": m.group(2).strip()}}),
        (r"(?:создай|create)\s+файл\s+(.+)$",
         lambda m: {"type": "file_create", "params": {"path": m.group(1).strip(), "content": ""}}),
        (r"(?:допиши|append)\s+в\s+файл\s+(.+?)\s+(.+)$",
         lambda m: {"type": "file_append", "params": {"path": m.group(1).strip(), "content": m.group(2).strip()}}),
        (r"(?:прочитай|read)\s+файл\s+(.+)$",
         lambda m: {"type": "file_read", "params": {"path": m.group(1).strip()}}),
        (r"(?:найди|поищи)\s+(?:где\s+я\s+писал\s+)?(?:про\s+)?(.+)$",
         lambda m: {"type": "file_search_content", "params": {"query": m.group(1).strip()}}),
        (r"(?:в\s+блокноте\s+напиши|notepad\s+type)\s+(.+)$",
         lambda m: {"type": "app_write", "params": {"app": "notepad", "text": m.group(1).strip()}}),

        # Messenger send (deterministic flow, no vision loop)
        (r"(?:открой\s+чат\s+с|чат\s+с)\s+(.+?)\s+и\s+(?:напиши|отправь)\s+(.+)$",
         lambda m: {"type": "messenger_send", "params": {
             "app": "telegram",
             "contact": m.group(1).strip().strip("«»\"'"),
             "message": m.group(2).strip(),
         }}),
        (r"(?:перейди\s+в\s+чат\s+с|открой\s+диалог\s+с)\s+(.+?)\s+и\s+(?:напиши|отправь)\s+(.+)$",
         lambda m: {"type": "messenger_send", "params": {
             "app": "telegram",
             "contact": m.group(1).strip().strip("«»\"'"),
             "message": m.group(2).strip(),
         }}),
        (r"(?:напиши|отправь)\s+(?:в\s+)?(?:телеграм\w*|telegram)\s+(?:чат\s+)?(?:с\s+)?(.+?)\s*[—\-–]\s*(.+)$",
         lambda m: {"type": "messenger_send", "params": {
             "app": "telegram",
             "contact": m.group(1).strip(),
             "message": m.group(2).strip(),
         }}),
        (r"(?:напиши|отправь)\s+(?:в\s+)?(?:телеграм\w*|telegram)\s+(.+?)\s+что\s+(.+)$",
         lambda m: {"type": "messenger_send", "params": {
             "app": "telegram",
             "contact": m.group(1).strip().strip("«»\"'"),
             "message": "что " + m.group(2).strip(),
         }}),
        # «напиши Маме что я дома» — не ловить «напиши что такое …»
        (r"(?:напиши|отправь)\s+(?!что\b)(.+?)\s+что\s+(.+)$",
         lambda m: {"type": "messenger_send", "params": {
             "app": "telegram",
             "contact": m.group(1).strip().strip("«»\"'"),
             "message": "что " + m.group(2).strip(),
         }}),
        (r"(?:напиши|отправь)\s+(?!в\b)([^\s,.;:!?]+)\s+(.+)",
         lambda m: {"type": "messenger_send", "params": {
             "app": "telegram",
             "contact": m.group(1).strip(),
             "message": m.group(2).strip()
         }}),
        (r"(?:напиши|отправь)\s+(?:в\s+)?(?:телеграм\w*|telegram)\s+([^\s,.;:!?]+)\s+(.+)",
         lambda m: {"type": "messenger_send", "params": {
             "app": "telegram",
             "contact": m.group(1).strip(),
             "message": m.group(2).strip()
         }}),
        (r"(?:открой|запусти)\s+(?:телеграм\w*|telegram)\s+(?:и\s+)?(?:напиши|отправь)\s+([^\s,.;:!?]+)\s+(.+)",
         lambda m: {"type": "messenger_send", "params": {
             "app": "telegram",
             "contact": m.group(1).strip(),
             "message": m.group(2).strip()
         }}),
        # «в телеграмме напиши Лёхе привет» / «telegram напиши Васе здорово»
        (r"(?:в\s+)(?:телеграм\w*|telegram)\s+(?:напиши|отправь|набери)\s+([^\s,.;:!?]+)\s+(.+)$",
         lambda m: {"type": "messenger_send", "params": {
             "app": "telegram",
             "contact": m.group(1).strip().strip("«»\"'"),
             "message": m.group(2).strip(),
         }}),
        (r"(?:телеграм\w*|telegram)\s+(?:напиши|отправь|набери)\s+([^\s,.;:!?]+)\s+(.+)$",
         lambda m: {"type": "messenger_send", "params": {
             "app": "telegram",
             "contact": m.group(1).strip().strip("«»\"'"),
             "message": m.group(2).strip(),
         }}),

        # === AGENTIC CONTROL (v7.2) ===
        # "напиши в телеграм привет" → vision-based typing
        (r"(?:напиши|набери|отправь|печатай)\s+(?:в\s+)?(телеграм\w*|аюграм\w*|дискорд\w*|ватсап\w*|вайбер\w*|слак\w*|тимс\w*)\s+(.+)",
         lambda m: {"type": "agentic_control", "params": {
             "app": m.group(1).strip(),
             "goal": f"find message input field, click on it, type: {m.group(2).strip()}, then press Enter to send"
         }}),

        # "нарисуй в пейнте круг" → vision-based drawing
        (r"(?:нарисуй|рисуй|draw|paint)\s+(?:в\s+)?(?:пейнт\w*|paint\w*)?\s*(.+)",
         lambda m: {"type": "agentic_control", "params": {
             "app": "mspaint",
             "goal": f"draw: {m.group(1).strip()}"
         }}),

        # "открой в телеграмме" (just focus)
        (r"^(?:открой|зайди)\s+(?:в\s+)?(телеграм\w*|telegram|аюграм\w*|ayugram)$",
         lambda m: {"type": "messenger_focus", "params": {"app": m.group(1).strip()}}),

        # Generic agentic — not «в телеграм напиши …» (handled by messenger_send above)
        (r"(?:в\s+)(телеграм\w*|хром\w*|дискорд\w*|пейнт\w*|блокнот\w*)\s+(?!напиши\b|отправь\b|набери\b)(.+)",
         lambda m: {"type": "agentic_control", "params": {
             "app": m.group(1).strip(),
             "goal": m.group(2).strip()
         }}),

        # Volume set: "громкость 50", "volume 80%"
        (r"(?:громкость|volume|звук)\s*(?:на\s*)?(\d+)\s*%?",
         lambda m: {"type": "volume_set", "params": {"percent": int(m.group(1))}}),

        # Timer minutes: "таймер 5 минут", "напомни через 10 мин"
        (r"(?:таймер|timer|напомни|remind)\s*(?:на|in|через)?\s*(\d+)\s*(?:мин|min|м\b)",
         lambda m: {"type": "reminder_set", "params": {"seconds": int(m.group(1)) * 60, "message": "Timer"}}),

        # Timer seconds: "таймер 30 сек"
        (r"(?:таймер|timer|напомни|remind)\s*(?:на|in|через)?\s*(\d+)\s*(?:сек|sec|с\b)",
         lambda m: {"type": "reminder_set", "params": {"seconds": int(m.group(1)), "message": "Timer"}}),

        # Ping: "пинг google.com"
        (r"(?:пинг|ping)\s+([\w\.\-]+)",
         lambda m: {"type": "network_ping", "target": m.group(1).strip()}),

        # Web search — avoid bare "search"/"google" (substring false positives); use word boundaries for EN
        (r"(?:загугли|погугли|искать)\s+(.+)",
         lambda m: {"type": "web_search", "target": m.group(1).strip()}),
        (r"(?:^|\s)(?:найди|поищи)\s+(.+)",
         lambda m: {"type": "web_search", "target": m.group(1).strip()}),
        (r"(?i)\b(?:google|search)\s+(.+)",
         lambda m: {"type": "web_search", "target": m.group(1).strip()}),

        # Read URL: "прочитай https://..."
        (r"(?:прочитай|read|fetch)\s+(https?://\S+)",
         lambda m: {"type": "web_fetch", "target": m.group(1).strip()}),

        # Deep Research: "собери всё по теме Александр I"
        (r"(?:собери|исследуй|исследование|research)\s+(?:всё\s+)?(?:по\s+теме\s+|про\s+)?(.+)",
         lambda m: {"type": "deep_research", "target": m.group(1).strip()}),

        # Terminal: "выполни ipconfig"
        (r"(?:выполни|execute|run\s*cmd|cmd)\s+(.+)",
         lambda m: {"type": "terminal_cmd", "target": m.group(1).strip()}),
        (r"powershell\s+(.+)",
         lambda m: {"type": "terminal_ps", "target": m.group(1).strip()}),

        # OCR click: "нажми на кнопку Ок"
        (r"(?:нажми\s*(?:на)?|click\s*(?:on)?)\s*(?:кнопк[уа]?\s*)?[\"']?(.+?)[\"']?\s*$",
         lambda m: {"type": "ocr_click", "target": m.group(1).strip()}),

        # Recent files: "покажи загрузки"
        (r"(?:покажи|show|последни[ех]?\s*файл)\s*(?:в\s*)?(?:папк[еу]\s*)?(загрузки?|downloads?|документы?|documents?|рабочий\s*стол|desktop)",
         lambda m: {"type": "recent_files", "params": {"folder": m.group(1).strip(), "count": 10}}),

        # STEM commands
        (r"(?:молярная\s*масса|масса|molar\s*mass|m)\s*(?:вещества|соединения)?\s*([a-z0-9]+)$",
         lambda m: {"type": "stem_molar_mass", "params": {"formula": m.group(1).strip()}}),
        (r"(?:константа|constant)\s+([a-z_]+)$",
         lambda m: {"type": "stem_constant", "params": {"name": m.group(1).strip()}}),

        # Dictation
        (r"(?:напечатай|набери|type|dictate)\s+(.+)$",
         lambda m: {"type": "gui_dictate", "params": {"text": m.group(1).strip()}}),
    ]

    # ── Open/Close patterns ──
    OPEN_RE = re.compile(
        r"^(?:открой|запусти|open|launch|start|run|включи|вруби|врубай)\s+(.+)$",
        re.IGNORECASE,
    )
    CLOSE_RE = re.compile(
        r"^(?:закрой|убей|close|kill|выключи|заверши|останови|вырубай|вырубить|выруби)\s+(.+)$",
        re.IGNORECASE,
    )

    @classmethod
    def route(cls, text):
        """
        Try to match user text against known patterns.
        Returns action dict if matched, None if LLM should handle it.
        """
        text = text.strip()
        tl = text.lower().strip()

        # 1. Static patterns (includes music fix)
        for pattern, action in cls.STATIC_PATTERNS:
            if re.search(pattern, tl, re.IGNORECASE):
                return action.copy()

        # Visual Snippet (Alt+S) shortcut (v8.0)
        if tl in ("снимок", "сниппет", "snippet", "visual snippet"):
            return {"type": "visual_snippet"}

        # 2. Dynamic patterns (includes agentic control)
        for pattern, action_fn in cls.DYNAMIC_PATTERNS:
            m = re.search(pattern, tl, re.IGNORECASE)
            if m:
                return action_fn(m)

        # 3. Open command: "открой X"
        m = cls.OPEN_RE.match(text)
        if m:
            target = m.group(1).strip()
            return cls._classify_open_target(target)

        # 4. Close command: "закрой X"
        m = cls.CLOSE_RE.match(text)
        if m:
            target = m.group(1).strip()
            return {"type": "close_app", "target": target}

        # No match — LLM will handle
        return None

    @classmethod
    def _classify_open_target(cls, target):
        """
        Smart classification for 'open X'.
        v7.2: Music keywords filtered BEFORE reaching here (static patterns).
        """
        tl = target.lower().strip()

        web_hit, _ = best_match(tl, list(WEB_SERVICES.keys()), threshold=80)
        if web_hit:
            return {"type": "open_web", "target": web_hit}

        # Translate Russian names (exact or fuzzy synonym)
        tl_check = tl
        for rus, eng in RUS_APP_MAP.items():
            if rus == tl:
                tl_check = eng
                break
        else:
            rk, _ = best_match(tl, list(RUS_APP_MAP.keys()), threshold=80)
            if rk:
                tl_check = str(RUS_APP_MAP[rk]).lower()

        # Check web services FIRST
        for svc in WEB_SERVICES:
            if svc == tl or svc == tl_check:
                return {"type": "open_web", "target": target}
            if len(tl) >= 3 and (tl in svc or svc in tl):
                return {"type": "open_web", "target": target}

        # Check system tools (exact match only)
        if tl in SYSTEM_TOOLS or tl_check in SYSTEM_TOOLS:
            return {"type": "system_tool", "target": target}
        for tool_name in SYSTEM_TOOLS:
            if tool_name == tl:
                return {"type": "system_tool", "target": target}

        # Check folder aliases
        if tl in FOLDER_ALIASES or tl_check in FOLDER_ALIASES:
            return {"type": "open_folder", "target": target}
        for alias in FOLDER_ALIASES:
            if alias == tl:
                return {"type": "open_folder", "target": target}

        # Default: launch app
        return {"type": "launch_app", "target": target}
