# -*- coding: utf-8 -*-
"""
SOKOL v8.0 — GUI Application
Two-phase pipeline: fast classify (1-3s) → execute OR full chat.
"""

import os
import re
import sys
import time
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext

try:
    import speech_recognition as sr
except ImportError:
    sr = None

from .config import (
    OLLAMA_MODEL, OLLAMA_API_BASE, VERSION, SOKOL_GPU_BACKEND,
    VOICE_INPUT_LANG,
    VOICE_AMBIENT_DURATION,
    VOICE_TIMEOUT,
    VOICE_PHRASE_TIME_LIMIT,
    VOICE_PAUSE_THRESHOLD,
    VOICE_NON_SPEAKING,
    VOICE_PHRASE_THRESHOLD,
    VOICE_DENOISE,
    VOICE_STT_BACKEND,
    ALLOW_CODE_EXEC,
    HAS_PSUTIL,
)
from .core import INTERRUPT, CodeExecutor
from .llm_hybrid import HybridLLMClient
from .memory import ContextMemory, ReminderSystem, ClipboardManager
from .memory_system import get_memory
from .windows_integration import get_windows_integration, notify, sound
from .policy import mark_action_confirmed
from .logging_config import audit_line
from .dispatcher import (
    ActionDispatcher, CLASSIFY_PROMPT, CHAT_SYSTEM_MESSAGE, HELP_TEXT,
)

class SokolGUI:
    """
    SOKOL v8.0 GUI — Two-phase LLM pipeline.

    Phase 1: classify() — compact prompt, 2048 ctx, 150 tokens → JSON action
    Phase 2: chat() — only for questions/code, 4096 ctx, 1024 tokens

    90% of commands never reach Phase 2 → massive speed improvement.
    """

    # ── Cyber Elite Theme ──
    BG          = "#0a0b10"
    BG_DARK     = "#050608"
    BG_PANEL    = "#0f111a"
    FG          = "#e0e6ed"
    ACCENT      = "#00f2ff"  # Cyber Cyan
    ACCENT_DIM  = "#0088cc"
    GREEN       = "#39ff14"  # Neon Green
    RED         = "#ff003c"  # Cyber Red
    YELLOW      = "#ffcc00"
    PURPLE      = "#bc13fe"
    CYAN        = "#00f2ff"
    ORANGE      = "#ff8c00"
    MUTED       = "#4a5568"
    ENTRY_BG    = "#12141d"
    BORDER      = "#1a1d2b"
    HIGHLIGHT   = "#161b22"
    FONT        = ("Consolas", 11)
    FONT_BOLD   = ("Consolas", 11, "bold")
    FONT_SMALL  = ("Consolas", 9)
    TITLE_FONT  = ("Segoe UI", 14, "bold")
    BTN_FONT    = ("Segoe UI", 9, "bold")

    MAX_AI_RETRIES = 2

    # Animation constants (v8.0)
    ANIM_SPEED = 20 # ms per character
    ANIM_CHUNK = 2  # characters per step

    HELP_TRIGGERS = {
        "help", "помощь", "справка", "что ты умеешь",
        "что умеешь", "команды", "commands", "возможности",
        "capabilities", "модули", "modules", "хелп",
    }

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"SOKOL ELITE v{VERSION}")
        self.root.configure(bg=self.BG)
        self.root.geometry("1000x800")
        self.root.minsize(520, 500)

        # v8.0: Transparency
        try:
            self.root.attributes("-alpha", 0.92) 
        except Exception:
            pass

        self.memory = ContextMemory()
        self.reminders = ReminderSystem()
        self.msg_count = 0
        self._pending_secure_action = None
        self._pending_route_text = ""
        
        # v8.0: Reminder scheduler
        self._active_reminders = []
        threading.Thread(target=self._reminder_checker, daemon=True).start()
        
        # v8.0: Advanced Memory System (SQLite)
        self.advanced_memory = get_memory()
        self.windows = get_windows_integration()
        
        # v8.0: Load user name from memory
        self._load_user_profile()
        
        # v8.0: Macro recording state
        self._macro_recording = False
        self._macro_steps = []
        self._current_macro_name = None

        # v8.0: Background clipboard listener for Math/Chemistry
        self._last_clip = ""
        threading.Thread(target=self._clipboard_monitor, daemon=True).start()

        # Two-phase client (Groq when GROQ_API_KEY set; else Ollama; vision always inner Ollama)
        self.ollama = HybridLLMClient(
            model=OLLAMA_MODEL,
            api_base=OLLAMA_API_BASE,
            system_message=CHAT_SYSTEM_MESSAGE,
            classify_prompt=CLASSIFY_PROMPT,
        )

        # Speech Recognition (Google), пороги — быстрее конец фразы и меньше «залипаний»
        if sr is None:
            self.recognizer = None
            self.microphone = None
        else:
            self.recognizer = sr.Recognizer()
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = VOICE_PAUSE_THRESHOLD
            self.recognizer.non_speaking_duration = VOICE_NON_SPEAKING
            if hasattr(self.recognizer, "phrase_threshold"):
                self.recognizer.phrase_threshold = VOICE_PHRASE_THRESHOLD
            self.microphone = sr.Microphone()

        self._build_ui()
        self._build_context_menu()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._show_welcome()
        
        # v8.0: Bind Alt+Space for context awareness
        try:
            self.root.bind("<Alt-space>", self._on_alt_space)
            self._append("Alt+Space hotkey bound", "success")
        except Exception as e:
            print(f"Alt+Space binding failed: {e}")
        
        threading.Thread(target=self._warmup_ollama, daemon=True).start()

    def _warmup_ollama(self):
        """Load Ollama model into VRAM so the first user message is not ~10–20s cold."""
        try:
            self.ollama.warmup()
        except Exception:
            pass

    # ━━━ UI Construction ━━━

    def _build_ui(self):
        # v8.0: Compact Status Bar (Top)
        top_bar = tk.Frame(self.root, bg=self.BG_DARK, height=25)
        top_bar.pack(side="top", fill="x")
        
        # GPU / CPU / Time / Timing
        self.gpu_var = tk.StringVar(value="GPU: --%")
        self.cpu_var = tk.StringVar(value="CPU: --%")
        self.time_var = tk.StringVar(value="00:00:00")
        self.timing_var = tk.StringVar(value="")
        
        tk.Label(top_bar, textvariable=self.gpu_var, font=self.FONT_SMALL, 
                 bg=self.BG_DARK, fg=self.CYAN).pack(side="left", padx=10)
        tk.Label(top_bar, textvariable=self.cpu_var, font=self.FONT_SMALL, 
                 bg=self.BG_DARK, fg=self.GREEN).pack(side="left", padx=10)
        tk.Label(top_bar, textvariable=self.timing_var, font=self.FONT_SMALL,
                 bg=self.BG_DARK, fg=self.ACCENT).pack(side="left", padx=10)
        tk.Label(top_bar, textvariable=self.time_var, font=self.FONT_SMALL, 
                 bg=self.BG_DARK, fg=self.FG).pack(side="right", padx=10)
        
        # v8.0: Memory Button
        self.mem_btn = tk.Button(
            top_bar, text=" MEMORY ", font=self.FONT_SMALL,
            bg=self.BG_PANEL, fg=self.ACCENT, activebackground=self.ACCENT,
            relief="flat", padx=5, pady=0, cursor="hand2",
            command=self._show_memory_list, bd=0
        )
        self.mem_btn.pack(side="right", padx=20)

        threading.Thread(target=self._status_bar_updater, daemon=True).start()

        # Header
        header = tk.Frame(self.root, bg=self.BG_DARK, pady=10)
        header.pack(side="top", fill="x")

        logo_frame = tk.Frame(header, bg=self.BG_DARK)
        logo_frame.pack(side="left", padx=20)
        tk.Label(logo_frame, text="⌬", font=("Segoe UI", 20),
                 bg=self.BG_DARK, fg=self.ACCENT).pack(side="left", padx=(0, 10))
        tk.Label(logo_frame, text=f"SOKOL ELITE v{VERSION}",
                 font=self.TITLE_FONT, bg=self.BG_DARK, fg=self.FG).pack(side="left")

        right_frame = tk.Frame(header, bg=self.BG_DARK)
        right_frame.pack(side="right", padx=15)

        self.help_btn = tk.Button(
            right_frame, text=" HELP ", font=self.BTN_FONT,
            bg=self.HIGHLIGHT, fg=self.ACCENT, activebackground=self.ACCENT,
            relief="flat", padx=10, pady=4, cursor="hand2",
            command=self._show_help, bd=1, highlightbackground=self.BORDER
        )
        self.help_btn.pack(side="right", padx=(10, 0))

        model_frame = tk.Frame(right_frame, bg=self.HIGHLIGHT, padx=10, pady=4, bd=1, relief="flat")
        model_frame.pack(side="right")
        tk.Label(model_frame, text=f"MODEL: {OLLAMA_MODEL.upper()}",
                 font=self.FONT_SMALL, bg=self.HIGHLIGHT, fg=self.ACCENT).pack()

        tk.Frame(self.root, bg=self.ACCENT, height=1).pack(side="top", fill="x")

        # Input
        input_outer = tk.Frame(self.root, bg=self.ACCENT, padx=1, pady=1)
        input_outer.pack(side="bottom", fill="x", padx=20, pady=(5, 15))
        input_frame = tk.Frame(input_outer, bg=self.ENTRY_BG)
        input_frame.pack(fill="x")

        self.entry = tk.Entry(input_frame, font=self.FONT,
                              bg=self.ENTRY_BG, fg=self.FG,
                              insertbackground=self.ACCENT, relief="flat", bd=0)
        self.entry.pack(side="left", fill="x", expand=True, ipady=10, padx=(10, 10))
        self.entry.bind("<Return>", self._on_submit)
        self.entry.bind("<Escape>", lambda e: self._on_cancel())
        self.entry.bind("<Up>", self._on_history_up)
        self.entry.bind("<Down>", self._on_history_down)
        self.entry.focus_set()

        self.cancel_btn = tk.Button(
            input_frame, text=" ✕ ", font=self.BTN_FONT,
            bg=self.BG_PANEL, fg=self.RED, activebackground=self.RED,
            activeforeground=self.FG, relief="flat", padx=10, pady=6,
            cursor="hand2", command=self._on_cancel, state="disabled"
        )
        self.cancel_btn.pack(side="right", padx=(0, 5), pady=5)

        self.send_btn = tk.Button(
            input_frame, text="EXECUTE", font=self.BTN_FONT,
            bg=self.ACCENT, fg=self.BG_DARK, activebackground=self.CYAN,
            relief="flat", padx=15, pady=6, cursor="hand2",
            command=self._on_submit,
        )
        self.send_btn.pack(side="right", padx=5, pady=5)

        self.voice_btn = tk.Button(
            input_frame, text=" 🎙 ", font=self.BTN_FONT,
            bg=self.BG_DARK, fg=self.ACCENT, activebackground=self.ACCENT,
            activeforeground=self.BG_DARK, relief="flat", padx=10, pady=6,
            cursor="hand2", command=self._on_voice_input
        )
        self.voice_btn.pack(side="right", padx=2, pady=5)

        # Quick Control Panel
        quick_frame = tk.Frame(self.root, bg=self.BG, pady=5)
        quick_frame.pack(side="bottom", fill="x", padx=20)

        for text, cmd in [
            ("⚡ STATUS", "system_status"), ("📂 FILES", "recent_downloads"),
            ("📸 SCRSHOT", "screenshot"), ("🧹 PURGE", "deep_clean"),
            ("🔇 MUTE", "mute"),
        ]:
            tk.Button(
                quick_frame, text=text, font=self.FONT_SMALL,
                bg=self.BG_PANEL, fg=self.MUTED,
                activebackground=self.HIGHLIGHT, activeforeground=self.ACCENT,
                relief="flat", padx=8, pady=3, cursor="hand2",
                command=lambda c=cmd: self._quick_action(c),
                bd=1, highlightbackground=self.BORDER
            ).pack(side="left", padx=3)

        # Output
        self.output = scrolledtext.ScrolledText(
            self.root, wrap="word", font=self.FONT,
            bg=self.BG, fg=self.FG, insertbackground=self.ACCENT,
            selectbackground=self.ACCENT, selectforeground=self.BG_DARK,
            relief="flat", padx=20, pady=15, state="disabled", cursor="arrow",
        )
        self.output.pack(side="top", fill="both", expand=True, padx=10, pady=(10, 0))

        for tag, cfg in [
            ("header", {"foreground": self.ACCENT, "font": ("Consolas", 13, "bold")}),
            ("user", {"foreground": self.GREEN, "font": self.FONT_BOLD}),
            ("sokol", {"foreground": self.ACCENT, "font": self.FONT_BOLD}),
            ("code", {"foreground": self.PURPLE, "background": self.BG_DARK}),
            ("error", {"foreground": self.RED}),
            ("success", {"foreground": self.GREEN}),
            ("info", {"foreground": self.CYAN}),
            ("warning", {"foreground": self.YELLOW}),
            ("separator", {"foreground": self.HIGHLIGHT}),
            ("dim", {"foreground": self.MUTED}),
            ("bubble_user", {"background": self.HIGHLIGHT}),
            ("bubble_sokol", {"background": self.BG_PANEL}),
        ]:
            self.output.tag_config(tag, **cfg)

        self._input_history = []
        self._history_idx = -1
        self.isChatMode = False  # Flag to track active chat/agentic operation
        self._modal_lock = threading.Lock() # Prevent concurrent modal windows

    def _build_context_menu(self):
        self.ctx_menu = tk.Menu(
            self.root, tearoff=0, bg=self.BG_PANEL, fg=self.FG,
            activebackground=self.ACCENT, activeforeground=self.BG_DARK,
            font=self.FONT_SMALL, relief="flat", bd=1,
        )
        self.ctx_menu.add_command(label="  📋  Copy", command=self._copy_selection)
        self.ctx_menu.add_command(label="  📥  Paste", command=self._paste_to_input)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="  🔍  Select All", command=self._select_all_output)
        self.ctx_menu.add_command(label="  🧹  Clear", command=self._clear_output)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="  💾  Save Log", command=self._save_log)

        self.input_ctx_menu = tk.Menu(
            self.root, tearoff=0, bg=self.BG_PANEL, fg=self.FG,
            activebackground=self.ACCENT, activeforeground=self.BG_DARK,
            font=self.FONT_SMALL, relief="flat", bd=1,
        )
        self.input_ctx_menu.add_command(label="  📋  Copy", command=self._copy_from_input)
        self.input_ctx_menu.add_command(label="  ✂️  Cut", command=self._cut_from_input)
        self.input_ctx_menu.add_command(label="  📥  Paste", command=self._paste_to_input)
        self.input_ctx_menu.add_separator()
        self.input_ctx_menu.add_command(label="  🔍  Select All", command=self._select_all_input)

        self.output.bind("<Button-3>", self._show_context_menu)
        self.output.bind("<Control-c>", lambda e: self._copy_selection())

        # Entry: clipboard + context menu (ПКМ)
        self.entry.bind("<Control-v>", lambda e: self._paste_to_input())
        self.entry.bind("<Control-V>", lambda e: self._paste_to_input())
        self.entry.bind("<Control-c>", lambda e: self._copy_from_input())
        self.entry.bind("<Control-C>", lambda e: self._copy_from_input())
        self.entry.bind("<Control-x>", lambda e: self._cut_from_input())
        self.entry.bind("<Control-X>", lambda e: self._cut_from_input())
        self.entry.bind("<Control-a>", lambda e: self._select_all_input())
        self.entry.bind("<Control-A>", lambda e: self._select_all_input())
        self.entry.bind("<Shift-Insert>", lambda e: self._paste_to_input())
        self.entry.bind("<Button-3>", self._show_input_context_menu)
        # Ctrl+C/V/X/A by keycode (works with Russian keyboard layout)
        self.entry.bind("<KeyPress>", self._entry_keyctrl_clipboard, add="+")

    def _entry_keyctrl_clipboard(self, event):
        if not (event.state & 0x4):
            return
        kc = event.keycode
        if kc in (67, 99):
            return self._copy_from_input()
        if kc in (86, 118):
            return self._paste_to_input()
        if kc in (88, 120):
            return self._cut_from_input()
        if kc in (65, 97):
            return self._select_all_input()

    # ━━━ Context Menu Actions ━━━

    def _show_input_context_menu(self, event):
        if self.isChatMode:
            return
        try:
            self.input_ctx_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.input_ctx_menu.grab_release()

    def _show_context_menu(self, event):
        if self.isChatMode:
            return # Block menu in chat mode
        try:
            self.ctx_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.ctx_menu.grab_release()

    def _copy_selection(self):
        try:
            self.output.configure(state="normal")
            selected = self.output.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.output.configure(state="disabled")
            if selected:
                self.root.clipboard_clear()
                self.root.clipboard_append(selected)
        except tk.TclError:
            self.output.configure(state="normal")
            all_text = self.output.get("1.0", tk.END).strip()
            self.output.configure(state="disabled")
            if all_text:
                self.root.clipboard_clear()
                self.root.clipboard_append(all_text)

    def _paste_to_input(self):
        """Paste clipboard into input field at cursor position."""
        try:
            text = self.root.clipboard_get()
            self.entry.insert(tk.INSERT, text)
            self.root.update_idletasks()
        except tk.TclError:
            pass
        return "break"

    def _copy_from_input(self):
        """Copy from input: selection if any, else whole line."""
        try:
            if self.entry.selection_present():
                selected = self.entry.selection_get()
            else:
                selected = self.entry.get()
            if selected:
                self.root.clipboard_clear()
                self.root.clipboard_append(selected)
                self.root.update_idletasks()
        except tk.TclError:
            pass
        return "break"

    def _cut_from_input(self):
        """Cut selection, or whole line if nothing selected."""
        try:
            if self.entry.selection_present():
                selected = self.entry.selection_get()
                self.root.clipboard_clear()
                self.root.clipboard_append(selected)
                self.entry.delete(tk.SEL_FIRST, tk.SEL_LAST)
            else:
                t = self.entry.get()
                if t:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(t)
                    self.entry.delete(0, tk.END)
            self.root.update_idletasks()
        except tk.TclError:
            pass
        return "break"
    
    def _select_all_input(self):
        """Select all text in input field."""
        self.entry.select_range(0, tk.END)
        self.entry.icursor(tk.END)
        return "break"

    def _select_all_output(self):
        self.output.configure(state="normal")
        self.output.tag_add(tk.SEL, "1.0", tk.END)
        self.output.configure(state="disabled")

    def _clear_output(self):
        self.output.configure(state="normal")
        self.output.delete("1.0", tk.END)
        self.output.configure(state="disabled")

    def _save_log(self):
        from datetime import datetime
        from .config import USER_HOME
        log_dir = os.path.join(USER_HOME, "Desktop", "Sokol_Logs")
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(log_dir, f"sokol_log_{ts}.txt")
        try:
            self.output.configure(state="normal")
            content = self.output.get("1.0", tk.END)
            self.output.configure(state="disabled")
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self._status(f"Log saved: {path}")
        except Exception as e:
            self._status(f"Save failed: {e}")

    # ━━━ Quick Actions ━━━

    def _quick_action(self, cmd):
        actions = {
            "system_status": "статус системы",
            "recent_downloads": "покажи загрузки",
            "screenshot": "скриншот",
            "deep_clean": "deep clean",
            "clipboard_read": "что в буфере",
            "mute": "mute",
        }
        text = actions.get(cmd, cmd)
        self.entry.delete(0, tk.END)
        self.entry.insert(0, text)
        self._on_submit()

    def _show_help(self):
        self._append(f"\nYou:  справка", "user")
        self._show_local(HELP_TEXT, "info")

    # ━━━ Welcome ━━━

    def _show_welcome(self):
        self._append("◆ SOKOL v" + VERSION + " — ONLINE", "header")
        self._append("")
        for line in [
            f"   СОКОЛ v{VERSION} в сети. Системы в норме. Слушаю вас.",
            f"   Engine:  Agentic router (instant | action | chat)",
            f"   Model:   {OLLAMA_MODEL} @ {OLLAMA_API_BASE}",
            f"   GPU:     {SOKOL_GPU_BACKEND.upper()} (Flash Attention)",
            f"   Speed:   instant <0.1s | routed actions first",
            f"",
            f"   [?] Справка  [✕] Отмена  [Send ▶] Выполнить",
        ]:
            self._append(line, "dim")
        self._sep()

    # ━━━ Output ━━━

    def _append(self, text, tag=None):
        self.output.configure(state="normal")
        
        # Filter technical paths from output
        text = self._filter_technical_info(text)
        
        # Simple "Bubble" simulation using tags and padding
        prefix = ""
        if tag == "user":
            prefix = " ⚡ YOU: "
            self.output.insert(tk.END, "\n", "separator")
        elif tag == "sokol":
            prefix = " ⌬ SOKOL: "
            t = (text or "").lstrip()
            for dup in ("⌬ SOKOL:", "SOKOL:", "Sokol:", "sokol:"):
                if t.startswith(dup):
                    t = t[len(dup) :].lstrip()
                    break
            text = t
            if not text:
                self.output.insert(tk.END, prefix, tag)
                self.output.configure(state="disabled")
                self.output.see(tk.END)
                return
        
        # ИСПРАВЛЕНИЕ: Мгновенная вставка вместо сломанной анимации
        full_text = prefix + text + "\n"
        self.output.insert(tk.END, full_text, tag)
        self.output.configure(state="disabled")
        self.output.see(tk.END)

    def _animate_append(self, text, tag, index=0):
        """Animates text character by character (v8.0)."""
        if index < len(text):
            self.output.configure(state="normal")
            chunk = text[index : index + self.ANIM_CHUNK]
            self.output.insert(tk.END, chunk, tag)
            self.output.configure(state="disabled")
            self.output.see(tk.END)
            self.root.after(self.ANIM_SPEED, lambda: self._animate_append(text, tag, index + self.ANIM_CHUNK))

    def _filter_technical_info(self, text):
        """Remove file paths and verbose 'Launched' logs from user view."""
        # Remove Windows paths
        text = re.sub(r'[a-zA-Z]:\\[^ \n]+', '[FILE]', text)
        # Simplify common verbose logs
        text = text.replace("Brought to front:", "Focused:")
        text = text.replace("Launched (cached):", "Resumed:")
        text = text.replace("Launched:", "Started:")
        return text

    def _sep(self):
        self._append("─" * 70, "separator")

    def ui_call(self, fn, timeout=8.0):
        """Run fn() on the Tk main thread from a worker thread (automation, etc.)."""
        if threading.current_thread() is threading.main_thread():
            fn()
            return
        done = threading.Event()

        def wrap():
            try:
                fn()
            finally:
                done.set()

        self.root.after(0, wrap)
        done.wait(timeout=timeout)

    def _set_busy(self, busy):
        if busy:
            self.entry.configure(state="disabled")
            self.send_btn.configure(state="disabled")
            self.cancel_btn.configure(state="normal")
        else:
            self.entry.configure(state="normal")
            self.send_btn.configure(state="normal")
            self.cancel_btn.configure(state="disabled")

    def _status(self, text):
        # Status bar removed - method kept for compatibility
        pass

    # ━━━ Input History ━━━

    def _on_history_up(self, event=None):
        if self._input_history:
            if self._history_idx < len(self._input_history) - 1:
                self._history_idx += 1
            self.entry.delete(0, tk.END)
            self.entry.insert(0, self._input_history[-(self._history_idx + 1)])
        return "break"

    def _on_history_down(self, event=None):
        if self._history_idx > 0:
            self._history_idx -= 1
            self.entry.delete(0, tk.END)
            self.entry.insert(0, self._input_history[-(self._history_idx + 1)])
        elif self._history_idx == 0:
            self._history_idx = -1
            self.entry.delete(0, tk.END)
        return "break"

    # ━━━ Event Handlers ━━━
    
    def _on_alt_space(self, event=None):
        """Alt+Space activation - analyze current screen"""
        try:
            self._append("\n⌬ SOKOL: Alt+Space activated - capturing screen...", "info")
            
            # Take screenshot
            from .automation import ScreenCapture
            success, msg, screenshot_path = ScreenCapture.take()
            
            if not success:
                self._append(f"Screenshot failed: {msg}", "error")
                return
            
            self._append(f"Screenshot saved: {screenshot_path}", "success")
            self._append("Analyzing screen content...", "info")
            
            # Process screenshot in background
            threading.Thread(target=self._analyze_screenshot, args=(screenshot_path,), daemon=True).start()
            
        except Exception as e:
            self._append(f"Alt+Space error: {e}", "error")
    
    def _analyze_screenshot(self, screenshot_path):
        """Analyze screenshot content using OCR"""
        try:
            # Try to extract text from screenshot using OCR
            try:
                import pytesseract
                from PIL import Image
                img = Image.open(screenshot_path)
                text = pytesseract.image_to_string(img, lang='rus+eng')
            except:
                text = ""
            
            # Create prompt based on OCR text or generic analysis
            if text.strip():
                prompt = f"I can see this text on the user's screen: '{text[:500]}'. What actions might they want to take based on this content?"
            else:
                prompt = "The user pressed Alt+Space to analyze their screen. Suggest some common actions they might want to take based on typical Windows usage."
            
            result = self.ollama.chat(prompt)
            if result:
                self.root.after(0, self._append, f"\n⌬ Screen Analysis:\n{result}", "sokol")
            else:
                self.root.after(0, self._append, "Could not analyze screenshot", "warning")
        except Exception as e:
            self.root.after(0, self._append, f"Analysis error: {e}", "error")

    def _on_cancel(self):
        INTERRUPT.set()
        self.root.after(0, self._append, "\n✕ CANCELLED", "error")
        self.root.after(0, self._sep)
        self.root.after(0, lambda: self._set_busy(False))
        self.root.after(0, lambda: self._status("Cancelled. Ready."))
        self.root.after(0, lambda: self.entry.focus_set())
        self.ollama.reset()
        self.root.after(500, INTERRUPT.clear)

    def _fuzzy_correct(self, text: str) -> str:
        """Correct common typos - STRICT: never change meaning or pronouns"""
        text_lower = text.lower().strip()
        
        # NEVER correct if text contains "я" (first person) - to avoid "кто я" -> "кто ты"
        if " я " in text_lower or text_lower.startswith("я ") or text_lower.endswith(" я"):
            return text
            
        # NEVER correct if text is very short (1-2 chars) - too risky
        if len(text_lower) <= 2:
            return text
            
        # EXACT typo matches only - no fuzzy similarity
        exact_corrections = {
            # Greetings - exact typos only
            "привт": "привет",
            "прив": "привет", 
            "првет": "привет",
            "превед": "привет",
            "пок": "пока",
            "пака": "пока",
            "спс": "спасибо",
            "спасиб": "спасибо",
            "спсибо": "спасибо",
            "хелп": "помощь",
            "хелп ми": "помощь",
            # Commands
            "выхд": "выход",
            "вхд": "выход",
            "выд": "выход",
            # English
            "helo": "hello",
            "hllo": "hello", 
            "hlo": "hello",
            "hlp": "help",
            "hel": "help",
            "hep": "help",
            "exi": "exit",
            "ext": "exit",
            "exitt": "exit",
        }
        
        # Direct match only
        if text_lower in exact_corrections:
            return exact_corrections[text_lower]
            
        # For phrases, use very strict matching (95% similarity required)
        phrase_corrections = {
            "кто ты": ["ктоты", "кто т"],
            "что ты умеешь": ["чтоумеешь", "что умееш"],
            "что ты можешь": ["чтоможешь", "что можеш"],
        }
        
        for correct, typos in phrase_corrections.items():
            if text_lower in typos:
                return correct
            # Strict similarity check (95% threshold)
            for typo in typos:
                if self._is_similar_strict(text_lower, typo, threshold=0.95):
                    return correct
                    
        return text
    
    def _is_similar_strict(self, a: str, b: str, threshold: float = 0.95) -> bool:
        """Very strict similarity check - only for obvious typos"""
        from difflib import SequenceMatcher
        # Require minimum length for comparison
        if len(a) < 4 or len(b) < 4:
            return False
        ratio = SequenceMatcher(None, a, b).ratio()
        return ratio >= threshold

    def _on_submit(self, event=None):
        text = self.entry.get().strip()
        if not text:
            return
        self.entry.delete(0, tk.END)
        
        # v8.0: Fuzzy matching for typos
        text = self._fuzzy_correct(text)

        if not self._input_history or self._input_history[-1] != text:
            self._input_history.append(text)
        self._history_idx = -1

        EXITS = {
            "exit", "quit", "bye", "close sokol",
            "выход", "выйти", "закройся", "пока", "выключись",
        }
        if text.lower().strip() in EXITS:
            self._append("\n◆ SOKOL shutting down. Goodbye!\n", "sokol")
            self.root.after(800, self._on_close)
            return

        self._append(f"\nYou:  {text}", "user")
        self.msg_count += 1

        # Local help interception — instant, no LLM
        if text.lower().strip() in self.HELP_TRIGGERS:
            self._show_local(HELP_TEXT, "info")
            return

        INTERRUPT.clear()
        self._set_busy(True)
        self._status("Phase 1: routing...")
        
        threading.Thread(target=self._process, args=(text,), daemon=True).start()

    def _on_voice_input(self):
        """Toggle voice input listening."""
        if sr is None or not self.recognizer or not self.microphone:
            self._append("⌬ SOKOL: Нет модуля speech_recognition / микрофона.", "error")
            return
        if getattr(self, "_is_listening", False):
            return
        
        self._is_listening = True
        self.voice_btn.configure(fg=self.RED)
        self._append("⌬ SOKOL: Слушаю вас...", "info")
        self._status("LISTENING...")

        def listen_thread():
            try:
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(
                        source, duration=VOICE_AMBIENT_DURATION
                    )
                    audio = self.recognizer.listen(
                        source,
                        timeout=VOICE_TIMEOUT,
                        phrase_time_limit=VOICE_PHRASE_TIME_LIMIT,
                    )
                audio = self._maybe_denoise_voice_audio(audio)
                if VOICE_STT_BACKEND == "whisper_local":
                    try:
                        text = self.recognizer.recognize_whisper(
                            audio, language="russian", model="base"
                        )
                    except Exception:
                        text = self.recognizer.recognize_google(
                            audio,
                            language=VOICE_INPUT_LANG,
                            show_all=False,
                        )
                else:
                    text = self.recognizer.recognize_google(
                        audio,
                        language=VOICE_INPUT_LANG,
                        show_all=False,
                    )
                self.root.after(0, lambda t=text: self._handle_voice_result(t))
            except sr.UnknownValueError:
                self.root.after(0, lambda: self._append("⌬ SOKOL: Не удалось распознать речь.", "warning"))
            except sr.RequestError as e:
                self.root.after(0, lambda: self._append(f"⌬ SOKOL: Ошибка сервиса распознавания: {e}", "error"))
            except Exception as e:
                self.root.after(0, lambda: self._append(f"⌬ SOKOL: Ошибка микрофона: {e}", "error"))
            finally:
                self._is_listening = False
                self.root.after(0, lambda: self.voice_btn.configure(fg=self.ACCENT))
                self.root.after(0, lambda: self._status("Ready"))

        threading.Thread(target=listen_thread, daemon=True).start()

    def _handle_voice_result(self, text):
        """Put recognized text into entry and submit."""
        if text:
            self.entry.delete(0, tk.END)
            self.entry.insert(0, text)
            self._on_submit()

    def _maybe_denoise_voice_audio(self, audio):
        """
        Опционально: noisereduce + numpy (pip install noisereduce numpy).
        Уменьшает постоянный фон (вентилятор, гул) перед отправкой в Google STT.
        """
        if not VOICE_DENOISE or sr is None:
            return audio
        try:
            import io
            import wave
            import numpy as np
            import noisereduce as nr
        except ImportError:
            return audio
        try:
            bio = io.BytesIO(audio.get_wav_data())
            with wave.open(bio, "rb") as wf:
                rate = wf.getframerate()
                sw = wf.getsampwidth()
                ch = wf.getnchannels()
                nframes = wf.getnframes()
                raw = wf.readframes(nframes)
            if ch != 1 or sw != 2:
                return audio
            data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            reduced = nr.reduce_noise(
                y=data, sr=rate, stationary=True, prop_decrease=0.78
            )
            out = (np.clip(reduced, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()
            return sr.AudioData(out, rate, sw)
        except Exception:
            return audio

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TWO-PHASE PROCESSING PIPELINE
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _process(self, text):
        """
        Unified dispatcher pipeline:
          1) instant local answers (time/date/math),
          2) regex pre-router actions,
          3) LLM classify/chat fallback.
        """
        try:
            INTERRUPT.check()
            self._pending_route_text = text
            t0 = time.time()
            self.root.after(0, self._status, "Routing...")
            
            # Step 1 & 2: Instant answers and PreRouter
            ok, msg = ActionDispatcher.dispatch(text, self)
            total = time.time() - t0
            INTERRUPT.check()

            if msg == "__SILENT__":
                self.root.after(0, lambda: self.timing_var.set(f"⚡ {total:.1f}s"))
                self.root.after(0, self._set_busy, False)
                self.root.after(0, self._status, "Ready")
                return

            if msg and isinstance(msg, str) and msg.startswith("__CONFIRM_POWER__:"):
                parts = msg.split(":")
                cmd = parts[1] if len(parts) > 1 else "shutdown"
                delay = int(parts[2]) if len(parts) > 2 else 30
                self.root.after(0, self._confirm_power, cmd, delay)
                return
            if msg == "__CONFIRM_TERMINAL__":
                self.root.after(0, self._confirm_terminal)
                return
            if msg == "__CONFIRM_WIFI__":
                self.root.after(0, self._confirm_wifi)
                return
            if msg == "__CONFIRM_MESSENGER__":
                self.root.after(0, self._confirm_messenger)
                return
            if msg == "__CONFIRM_DESTRUCTIVE__":
                self.root.after(0, self._confirm_destructive)
                return
            if msg == "__CONFIRM_SERVICE__":
                self.root.after(0, self._confirm_service)
                return
            if msg == "__CLIPBOARD_READ__":
                self.root.after(0, self._do_clipboard_read)
                return
            if msg and isinstance(msg, str) and msg.startswith("__CLIPBOARD_TRANSFORM__:"):
                transform = msg.split(":", 1)[1]
                threading.Thread(
                    target=self._do_clipboard_transform,
                    args=(transform,), daemon=True,
                ).start()
                return

            # If it's a regular string from dispatch (not CHAT signal)
            if msg is not None:
                tag = "success" if ok else "error"
                try:
                    self.memory.add_session_turn("user", text)
                    self.memory.add_session_turn("assistant", str(msg))
                except Exception:
                    pass
                self.root.after(0, self._show_local, msg, tag)
                return

            # Phase 2: Full chat with STREAMING
            self.root.after(0, self._status, "Sokol is thinking...")
            self.root.after(0, self._append, "", "sokol") # Start header
            
            try:
                full_response = ""
                for token in self.ollama.chat_stream(text):
                    INTERRUPT.check()
                    full_response += token
                    def update_ui(t=token):
                        self.output.configure(state="normal")
                        self.output.insert("end", t, "info")
                        self.output.see("end")
                        self.output.configure(state="disabled")
                    self.root.after(0, update_ui)
                
                self.root.after(0, self._sep)
                self.memory.record("conversation", {"topic": text[:50]})
                try:
                    self.memory.add_session_turn("user", text)
                    self.memory.add_session_turn("assistant", full_response)
                except Exception:
                    pass
            except InterruptedError:
                self.root.after(0, self._append, "\n✕ CANCELLED", "error")
                self.root.after(0, self._sep)
            except Exception as e:
                self.root.after(0, self._show_local, f"Chat error: {e}", "error")

            total = time.time() - t0
            self.root.after(0, lambda: self.timing_var.set(f"⚡ {total:.1f}s"))
            self.root.after(0, self._set_busy, False)
            self.root.after(0, self._status, "Ready")
            self.root.after(0, self.entry.focus_set)

        except InterruptedError:
            pass
        except Exception as e:
            self.root.after(0, self._show_local, f"Error: {e}", "error")

    def _do_phase2(self, text, t0, classify_time=0):
        # Deprecated by inline streaming in _process
        pass

    # ━━━ Code Execution ━━━

    def _handle_code_response(self, response_text, retry_count=0):
        parts = CodeExecutor.parse_response(response_text)
        display_parts = []
        has_error = False
        last_error = ""

        for kind, content in parts:
            INTERRUPT.check()
            if kind == "text":
                display_parts.append(("text", content))
            elif kind == "code":
                display_parts.append(("code", content))
                if not ALLOW_CODE_EXEC:
                    display_parts.append(
                        ("error_output", "Выполнение кода отключено (SOKOL_ALLOW_CODE_EXEC)."),
                    )
                    has_error = True
                    last_error = "code execution disabled"
                    continue
                self.root.after(0, self._status, "Executing code...")
                success, stdout, stderr = CodeExecutor.execute(content)
                if stdout:
                    display_parts.append(("output", stdout))
                if stderr:
                    display_parts.append(("error_output", stderr))
                if not success:
                    has_error = True
                    last_error = stderr or stdout

        if has_error and retry_count < self.MAX_AI_RETRIES:
            INTERRUPT.check()
            self.root.after(0, self._append,
                f"   ⚠ Error — auto-correcting "
                f"(attempt {retry_count + 1}/{self.MAX_AI_RETRIES})...",
                "warning",
            )
            correction = (
                f"Code error:\n```\n{last_error[:400]}\n```\n"
                f"Fix it. Output only corrected python code block."
            )
            response = self.ollama.chat(correction)
            INTERRUPT.check()
            if response:
                self._handle_code_response(response, retry_count + 1)
            return

        self.root.after(0, self._show_ai, display_parts, has_error)
        self.memory.record("code_execution", {"had_errors": has_error})

    # ━━━ Clipboard ━━━

    def _do_clipboard_read(self):
        content = ClipboardManager.read(self.root)
        if content:
            preview = ClipboardManager.describe(content, 500)
            self._show_local(f"Clipboard content:\n\n{preview}", "info")
        else:
            self._show_local("Clipboard is empty.", "info")

    def _do_clipboard_transform(self, transform):
        content_holder = [None]
        def read_clip():
            content_holder[0] = ClipboardManager.read(self.root)
        self.root.after(0, read_clip)
        time.sleep(0.15)
        content = content_holder[0]

        if not content:
            self.root.after(0, self._show_local, "Clipboard is empty.", "error")
            return

        prompts = {
            "fix_spelling": f"Fix spelling/grammar. Output ONLY corrected text:\n\n{content}",
            "make_list": f"Convert to bullet list. Output ONLY the list:\n\n{content}",
            "translate": f"Translate (RU↔EN). Output ONLY translation:\n\n{content}",
            "summarize": f"Summarize. Output ONLY summary:\n\n{content}",
        }
        prompt = prompts.get(transform, prompts["fix_spelling"])
        self.root.after(0, self._status, "AI transforming clipboard...")

        try:
            INTERRUPT.check()
            result_text = self.ollama.chat(prompt, one_shot=True)
            result_text = re.sub(r"^```(?:python|text|)?\s*\n?", "", result_text.strip())
            result_text = re.sub(r"\n?```\s*$", "", result_text.strip()).strip()
            if result_text:
                def write_and_show():
                    ClipboardManager.write(self.root, result_text)
                    self._show_local(
                        f"Clipboard updated!\n\n"
                        f"Before: {ClipboardManager.describe(content, 100)}\n"
                        f"After:  {ClipboardManager.describe(result_text, 100)}",
                        "success",
                    )
                self.root.after(0, write_and_show)
            else:
                self.root.after(0, self._show_local, "AI returned empty.", "error")
        except InterruptedError:
            pass
        except Exception as e:
            self.root.after(0, self._show_local, f"Transform error: {e}", "error")

    # ━━━ Power ━━━

    def _confirm_power(self, cmd, delay):
        from .tools import PowerController
        labels = {
            "shutdown": f"Shut down in {delay}s?",
            "restart": f"Restart in {delay}s?",
            "sleep": "Put PC to sleep?",
            "hibernate": "Hibernate?",
        }
        ok = messagebox.askyesno("Sokol — Power", labels.get(cmd, f"{cmd}?"), icon="warning")
        if ok:
            funcs = {
                "shutdown": lambda: PowerController.shutdown(delay),
                "restart": lambda: PowerController.restart(delay),
                "sleep": PowerController.sleep,
                "hibernate": PowerController.hibernate,
            }
            msg = funcs.get(cmd, lambda: "Unknown.")(  )
            self._show_local(msg, "success")
        else:
            self._show_local("Cancelled.", "info")

    def _run_confirmed_action(self, action):
        """Execute action after security dialog (must include _security_confirmed)."""
        route_text = getattr(self, "_pending_route_text", "") or ""
        try:
            INTERRUPT.check()
            ok, msg = ActionDispatcher.execute_action(action, self, user_input=route_text)
            if msg == "__SILENT__":
                self.root.after(0, self._set_busy, False)
                self.root.after(0, self._status, "Ready")
                return
            tag = "success" if ok else "error"
            self.root.after(0, self._show_local, msg, tag)
        except InterruptedError:
            self.root.after(0, self._set_busy, False)
        except Exception as e:
            self.root.after(0, self._show_local, f"Ошибка: {e}", "error")

    def _confirm_terminal(self):
        pending = getattr(self, "_pending_secure_action", None)
        if not pending:
            self._show_local("Нет команды для подтверждения.", "error")
            return
        atype = (pending.get("type") or "").lower()
        target = (pending.get("target") or "")[:900]
        label = "PowerShell" if atype == "terminal_ps" else "CMD"
        ok = messagebox.askyesno(
            "Сокол — Терминал",
            f"Выполнить команду ({label})?\n\n{target}",
            icon="warning",
        )
        if ok:
            audit_line(f"user_confirmed_terminal type={atype}")
            act = mark_action_confirmed(pending)
            self._pending_secure_action = None
            threading.Thread(target=self._run_confirmed_action, args=(act,), daemon=True).start()
        else:
            self._pending_secure_action = None
            self._show_local("Команда отменена.", "info")

    def _confirm_wifi(self):
        pending = getattr(self, "_pending_secure_action", None)
        if not pending:
            self._show_local("Нет действия.", "error")
            return
        ok = messagebox.askyesno(
            "Сокол — Wi‑Fi",
            "Показать сохранённые пароли Wi‑Fi?\n"
            "Убедитесь, что рядом нет посторонних.",
            icon="warning",
        )
        if ok:
            audit_line("user_confirmed_wifi_passwords")
            act = mark_action_confirmed(pending)
            self._pending_secure_action = None
            threading.Thread(target=self._run_confirmed_action, args=(act,), daemon=True).start()
        else:
            self._pending_secure_action = None
            self._show_local("Отменено.", "info")

    def _confirm_messenger(self):
        pending = getattr(self, "_pending_secure_action", None)
        if not pending:
            self._show_local("Нет сообщения.", "error")
            return
        params = pending.get("params") or {}
        contact = params.get("contact", "")
        body = (params.get("message", "") or "")[:400]
        ok = messagebox.askyesno(
            "Сокол — Мессенджер",
            f"Отправить сообщение?\nКому: {contact}\nТекст: {body}",
            icon="warning",
        )
        if ok:
            audit_line("user_confirmed_messenger_send")
            act = mark_action_confirmed(pending)
            self._pending_secure_action = None
            threading.Thread(target=self._run_confirmed_action, args=(act,), daemon=True).start()
        else:
            self._pending_secure_action = None
            self._show_local("Отменено.", "info")

    def _confirm_destructive(self):
        pending = getattr(self, "_pending_secure_action", None)
        if not pending:
            self._show_local("Нет действия.", "error")
            return
        atype = pending.get("type", "")
        ok = messagebox.askyesno(
            "Сокол — Опасное действие",
            f"Подтвердить выполнение «{atype}»?\nЭто может удалить данные или сильно изменить систему.",
            icon="warning",
        )
        if ok:
            audit_line(f"user_confirmed_destructive type={atype}")
            act = mark_action_confirmed(pending)
            self._pending_secure_action = None
            threading.Thread(target=self._run_confirmed_action, args=(act,), daemon=True).start()
        else:
            self._pending_secure_action = None
            self._show_local("Отменено.", "info")

    def _confirm_service(self):
        pending = getattr(self, "_pending_secure_action", None)
        if not pending:
            self._show_local("Нет действия.", "error")
            return
        atype = pending.get("type", "")
        target = pending.get("target", "")
        ok = messagebox.askyesno(
            "Сокол — Служба Windows",
            f"Выполнить {atype} для службы «{target}»?",
            icon="warning",
        )
        if ok:
            audit_line(f"user_confirmed_service {atype} name={target}")
            act = mark_action_confirmed(pending)
            self._pending_secure_action = None
            threading.Thread(target=self._run_confirmed_action, args=(act,), daemon=True).start()
        else:
            self._pending_secure_action = None
            self._show_local("Отменено.", "info")

    # ━━━ Display ━━━

    def _show_local(self, msg, tag):
        lines = msg.splitlines()
        if lines:
            self._append(lines[0], "sokol")
            for line in lines[1:]:
                self._append(f"   {line}", tag)
        self._sep()
        self._set_busy(False)
        self._status("Ready")
        self.entry.focus_set()

    def _show_ai(self, parts, had_errors):
        if not parts:
            self._append("Done.", "sokol")
        else:
            first_sokol_done = False
            for kind, content in parts:
                if kind == "text":
                    ls = content.splitlines()
                    if not ls:
                        continue
                    if not first_sokol_done:
                        self._append(ls[0], "sokol")
                        first_sokol_done = True
                        for line in ls[1:]:
                            self._append(f"   {line}", None)
                    else:
                        for line in ls:
                            self._append(f"   {line}", None)
                elif kind == "code":
                    if not first_sokol_done:
                        self._append("Code executed:", "sokol")
                        first_sokol_done = True
                    else:
                        self._append("   Code executed:", "code")
                    for line in content.splitlines()[:30]:
                        self._append(f"     {line}", "code")
                elif kind == "output":
                    for line in content.splitlines()[:25]:
                        self._append(f"   ▸ {line}", "success")
                elif kind == "error_output":
                    for line in content.splitlines()[:25]:
                        self._append(f"   ▸ {line}", "error")
        if had_errors:
            self._append("\n   ⚠ Errors in output.", "error")
        self._sep()
        self._set_busy(False)
        self._status("Ready")
        self.entry.focus_set()

    # ━━━ Cleanup ━━━

    def _on_close(self):
        INTERRUPT.set()
        try:
            self.reminders.cancel_all()
        except Exception:
            pass
        from .special_modes import GhostMode
        try:
            GhostMode.stop()
        except Exception:
            pass
        self.root.destroy()
        sys.exit(0)

    # ━━━ v8.0 NEW FEATURES ━━━

    def _status_bar_updater(self):
        """Update top status bar every 2 seconds."""
        try:
            import psutil
            has_psutil = True
        except ImportError:
            has_psutil = False
            
        while True:
            try:
                # CPU (if psutil available)
                if has_psutil:
                    cpu = psutil.cpu_percent()
                    self.cpu_var.set(f"CPU: {cpu:.0f}%")
                else:
                    self.cpu_var.set("CPU: --")
                
                # Time
                self.time_var.set(time.strftime("%H:%M:%S"))
                
                # GPU usage detection
                gpu_usage = self._get_gpu_usage()
                self.gpu_var.set(gpu_usage)
                
            except Exception:
                pass
            time.sleep(2)
    
    def _get_gpu_usage(self) -> str:
        """Get GPU usage for AMD/NVIDIA"""
        try:
            # Try NVIDIA first
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                usage = float(result.stdout.strip())
                return f"GPU: {usage:.0f}%"
        except:
            pass
        
        # For AMD, check if Ollama is using GPU
        try:
            result = subprocess.run(
                ["ollama", "ps"], capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and "GPU" in result.stdout:
                # Extract GPU usage if available
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'GPU' in line and '%' in line:
                        # Try to parse GPU percentage
                        parts = line.split()
                        for part in parts:
                            if '%' in part:
                                return f"GPU: {part}"
                return "GPU: ACTIVE"
            elif result.returncode == 0 and "100% CPU" in result.stdout:
                return "GPU: CPU MODE"
        except:
            pass
        
        # Default to backend name
        return f"GPU: {SOKOL_GPU_BACKEND.upper()}"

    def _show_memory_list(self):
        """Open a window with last captured OCR/Memory data."""
        notes = self.memory.pinned.get("notes", [])
        if not notes:
            messagebox.showinfo("Memory", "No captured data yet.")
            return
            
        mem_win = tk.Toplevel(self.root)
        mem_win.title("SOKOL MEMORY")
        mem_win.geometry("600x400")
        mem_win.configure(bg=self.BG_DARK)
        
        txt = scrolledtext.ScrolledText(mem_win, bg=self.BG_PANEL, fg=self.FG, font=self.FONT_SMALL)
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        
        for item in reversed(notes):
            txt.insert(tk.END, f"[{item['saved_at']}] Source: {item['source']}\n", "header")
            txt.insert(tk.END, f"{item['text']}\n", "info")
            txt.insert(tk.END, "-"*40 + "\n", "dim")
            
        txt.tag_config("header", foreground=self.ACCENT)
        txt.tag_config("info", foreground=self.FG)
        txt.tag_config("dim", foreground=self.MUTED)
        txt.configure(state="disabled")

    def _clipboard_monitor(self):
        """Background thread to monitor clipboard for Math/Chemistry (v8.0)."""
        import math
        from .tools.stem import STEMCore
        
        while True:
            try:
                content = self.root.clipboard_get().strip()
                if content and content != self._last_clip:
                    self._last_clip = content
                    
                    # 1. Check for Math Expression
                    # Simple regex for math (must contain at least one operator)
                    if re.match(r"^[\d\.\+\-\*\/\(\)\s\^]+$", content) and any(c in content for c in "+-*/^"):
                        try:
                            # Clean expression for eval
                            expr = content.replace("^", "**").replace(",", ".")
                            # Safe eval (very basic)
                            res = eval(expr, {"__builtins__": {}, "math": math})
                            self.ui_call(lambda: self._append(f"Smart Clipboard: {content} = {res}", "success"))
                        except Exception:
                            pass
                    
                    # 2. Check for Chemical Formula (e.g. H2SO4)
                    elif re.match(r"^[A-Z][a-z0-9]*([A-Z][a-z0-9]*)*$", content):
                        # Use STEMCore to check molar mass
                        res = STEMCore.get_molar_mass(content)
                        if "not found" not in res.lower():
                            self.ui_call(lambda: self._append(f"Smart Clipboard: {res}", "success"))
            except Exception:
                pass
            time.sleep(1.5)

    def _reminder_checker(self):
        """Background thread to check and fire reminders"""
        import time
        from datetime import datetime
        
        while True:
            try:
                current_time = time.time()
                
                # Check all active reminders
                for reminder in self._active_reminders[:]:
                    if current_time >= reminder['fire_time']:
                        # Fire the reminder
                        self.ui_call(lambda msg=reminder['message']: self._fire_reminder(msg))
                        self._active_reminders.remove(reminder)
                        
            except Exception as e:
                print(f"Reminder checker error: {e}")
                
            time.sleep(1)  # Check every second
    
    def _fire_reminder(self, message):
        """Display fired reminder"""
        self._append(f"\n🔔 REMINDER: {message}", "warning")
        self._sep()
        
        # Try to show Windows notification
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except:
            pass
    
    def add_reminder(self, seconds: int, message: str):
        """Add a new reminder"""
        import time
        fire_time = time.time() + seconds
        self._active_reminders.append({
            'fire_time': fire_time,
            'message': message,
            'created': time.time()
        })
        
        # Show confirmation
        when = time.strftime("%H:%M:%S", time.localtime(fire_time))
        self._append(f"⏰ Reminder set for {when}", "info")
        self._append(f"   Message: {message}", "dim")

    # ━━━ v8.0 ADVANCED FEATURES ━━━
    
    def _load_user_profile(self):
        """Load user name and preferences from advanced memory"""
        try:
            user_name = self.advanced_memory.get_user_name()
            if user_name and user_name != "User":
                # Update legacy memory for compatibility
                self.memory.pinned["user_name"] = user_name
                # Show personalized welcome
                self._append(f"Welcome back, {user_name}!", "success")
        except Exception as e:
            print(f"Failed to load user profile: {e}")
    
    def _save_user_name(self, name: str):
        """Save user name to memory"""
        try:
            self.advanced_memory.set_user_name(name)
            self.memory.pinned["user_name"] = name
            self._append(f"Nice to meet you, {name}! I'll remember your name.", "success")
            # Store in conversation
            self.advanced_memory.add_conversation_turn(
                "system", 
                f"User identified themselves as {name}",
                intent="identity",
                metadata={"user_name": name}
            )
        except Exception as e:
            print(f"Failed to save user name: {e}")
    
    # ━━━ Weather Integration ━━━
    
    def _get_weather(self, city: str = None) -> str:
        """
        Get weather for a city using Open-Meteo API (free, no key needed)
        """
        try:
            import urllib.request
            import json
            
            # Default to Moscow if no city specified
            if not city:
                city = "Moscow"
            
            # Geocoding API to get coordinates
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=ru&format=json"
            
            with urllib.request.urlopen(geo_url, timeout=5) as response:
                geo_data = json.loads(response.read().decode())
            
            if not geo_data.get("results"):
                return f"City '{city}' not found."
            
            location = geo_data["results"][0]
            lat = location["latitude"]
            lon = location["longitude"]
            timezone = location.get("timezone", "UTC")
            
            # Weather API
            weather_url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}"
                f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m"
                f"&timezone={timezone}"
            )
            
            with urllib.request.urlopen(weather_url, timeout=5) as response:
                weather_data = json.loads(response.read().decode())
            
            current = weather_data.get("current", {})
            temp = current.get("temperature_2m", "N/A")
            feels_like = current.get("apparent_temperature", "N/A")
            humidity = current.get("relative_humidity_2m", "N/A")
            wind = current.get("wind_speed_10m", "N/A")
            code = current.get("weather_code", 0)
            
            # Weather codes to descriptions
            weather_codes = {
                0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
                45: "Fog", 48: "Depositing rime fog",
                51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
                61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
                71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
                95: "Thunderstorm", 96: "Thunderstorm with hail"
            }
            
            desc = weather_codes.get(code, "Unknown")
            
            result = (
                f"🌤 Weather in {location['name']}, {location.get('country', '')}:\n"
                f"   Temperature: {temp}°C (feels like {feels_like}°C)\n"
                f"   Condition: {desc}\n"
                f"   Humidity: {humidity}%\n"
                f"   Wind: {wind} km/h"
            )
            
            return result
            
        except Exception as e:
            return f"Weather service unavailable: {e}"
    
    # ━━━ Macro System ━━━
    
    def _start_macro_recording(self, name: str):
        """Start recording a macro sequence"""
        self._macro_recording = True
        self._macro_steps = []
        self._current_macro_name = name
        self._append(f"🔴 Recording macro '{name}'... Perform actions, then say 'stop recording'", "info")
    
    def _stop_macro_recording(self):
        """Stop recording and save macro"""
        if not self._macro_recording:
            return False, "Not recording"
        
        if not self._macro_steps:
            self._macro_recording = False
            return False, "No actions recorded"
        
        try:
            self.advanced_memory.save_macro(
                self._current_macro_name,
                self._macro_steps,
                trigger_phrase=None
            )
            self._macro_recording = False
            return True, f"Macro '{self._current_macro_name}' saved with {len(self._macro_steps)} steps"
        except Exception as e:
            return False, f"Failed to save macro: {e}"
    
    def _play_macro(self, name: str):
        """Execute a saved macro"""
        try:
            macro = self.advanced_memory.get_macro(name)
            if not macro:
                return False, f"Macro '{name}' not found"
            
            self._append(f"▶ Playing macro '{name}'...", "info")
            
            for step in macro['steps']:
                action = step.get('action')
                params = step.get('params', {})
                
                if action == 'type':
                    GUIAutomation.type_text(params.get('text', ''))
                elif action == 'hotkey':
                    GUIAutomation.hotkey(*params.get('keys', []))
                elif action == 'click':
                    GUIAutomation.click(params.get('x'), params.get('y'))
                elif action == 'sleep':
                    time.sleep(params.get('seconds', 1))
                elif action == 'launch_app':
                    SmartLauncher.launch(params.get('app', ''))
                
                time.sleep(0.5)  # Delay between steps
            
            self.advanced_memory.increment_macro_usage(name)
            return True, f"Macro '{name}' completed"
            
        except Exception as e:
            return False, f"Macro execution failed: {e}"
    
    def _add_macro_step(self, action: str, params: dict):
        """Add a step to current macro recording"""
        if self._macro_recording:
            self._macro_steps.append({
                'action': action,
                'params': params,
                'timestamp': time.time()
            })
    
    def _list_macros(self) -> str:
        """List all saved macros"""
        try:
            macros = self.advanced_memory.get_all_macros()
            if not macros:
                return "No macros saved yet."
            
            lines = ["📋 Saved Macros:"]
            for macro in macros:
                lines.append(f"   • {macro['name']} - {macro.get('description', 'No description')} (used {macro.get('usage_count', 0)}x)")
            
            return "\n".join(lines)
        except:
            return "Error loading macros"
    
    # ━━━ Enhanced Reminders ━━━
    
    def _fire_reminder(self, message):
        """Display fired reminder with Windows notification"""
        self._append(f"\n🔔 REMINDER: {message}", "warning")
        self._sep()
        
        # Windows notification
        try:
            self.windows.show_notification("SOKOL Reminder", message, duration=10)
            self.windows.play_sound("reminder")
            self.windows.flash_window(count=3)
        except:
            pass
        
        # Store as completed
        self.advanced_memory.add_conversation_turn(
            "system",
            f"Reminder fired: {message}",
            intent="reminder_fired"
        )
    
    # ━━━ Smart Contact Management ━━━
    
    def _get_contact(self, alias: str) -> str:
        """Get contact info from smart memory with fuzzy matching"""
        try:
            contact = self.advanced_memory.get_contact(alias)
            if contact:
                return contact.get('telegram_username') or contact.get('alias')
            return alias  # Return original if not found
        except:
            return alias
    
    def _add_contact(self, alias: str, telegram: str = None, notes: str = None):
        """Add contact to smart memory"""
        try:
            self.advanced_memory.add_contact(alias, telegram, notes)
            self._append(f"👤 Contact '{alias}' added to memory", "success")
        except Exception as e:
            print(f"Failed to add contact: {e}")
    
    # ━━━ Weather Quick Command ━━━
    
    def _quick_weather(self):
        """Quick weather check"""
        # Try to get preferred city from memory
        city = self.advanced_memory.get_preference("weather", "default_city", "Moscow")
        weather = self._get_weather(city)
        self._append(f"\n{weather}", "info")
    
    # ━━━ System Integration ━━━
    
    def _toggle_startup(self):
        """Toggle Windows startup registration"""
        try:
            current = self.windows.is_startup_enabled()
            if self.windows.register_startup(not current):
                status = "enabled" if not current else "disabled"
                self._append(f"Startup {status}", "success")
            else:
                self._append("Failed to toggle startup", "error")
        except Exception as e:
            self._append(f"Startup error: {e}", "error")

    def run(self):
        self.root.mainloop()
