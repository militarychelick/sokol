# -*- coding: utf-8 -*-
"""
SOKOL v7 — Memory & State Management
ContextMemory, ReminderSystem, ClipboardManager
"""
import json
import threading
import os
from datetime import datetime, timedelta
import tkinter as tk
class ContextMemory:
    """
    Short-term memory for follow-up commands.
    Tracks recent actions, current directory, last opened app/file.
    """
    def __init__(self):
        self.history = []
        self.current_dir = None
        self.last_app = None
        self.last_file = None
        self.last_folder = None
        self.last_action = None
        self.last_url = None
        self.last_search = None
        self.max_items = 30
        self.memory_file = os.path.join(os.path.dirname(__file__), "memory.json")
        self.pinned = {
            "last_saved_text": "", 
            "saved_at": "", 
            "notes": [],
            "user_name": "User",
            "user_gender": "neutral"
        }
        self._load_persistent()
        self.session_turns = []
        self.session_max = 40

    def add_session_turn(self, role, content):
        c = (content or "").strip()
        if not c:
            return
        self.session_turns.append({"role": role, "content": c[:8000]})
        if len(self.session_turns) > self.session_max:
            self.session_turns = self.session_turns[-self.session_max :]

    def get_session_context(self, max_turns=8):
        if not self.session_turns:
            return ""
        lines = []
        for t in self.session_turns[-max_turns:]:
            lines.append(f"{t['role']}: {t['content']}")
        return "\n".join(lines)

    def record(self, action, details=None):
        details = details or {}
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "action": action,
            "details": details,
        }
        self.history.append(entry)
        if len(self.history) > self.max_items:
            self.history = self.history[-self.max_items:]
        self.last_action = action
        if "folder" in details:
            self.current_dir = details["folder"]
            self.last_folder = details["folder"]
        if "app" in details:
            self.last_app = details["app"]
        if "file" in details:
            self.last_file = details["file"]
        if "directory" in details:
            self.current_dir = details["directory"]
        if "url" in details:
            self.last_url = details["url"]
        if "query" in details:
            self.last_search = details["query"]
    def get_context_summary(self):
        lines = []
        if self.current_dir:
            lines.append(f"Current directory: {self.current_dir}")
        if self.last_app:
            lines.append(f"Last opened app: {self.last_app}")
        if self.last_file:
            lines.append(f"Last file: {self.last_file}")
        if self.last_folder:
            lines.append(f"Last folder: {self.last_folder}")
        if self.last_url:
            lines.append(f"Last URL: {self.last_url}")
        recent = self.history[-5:] if self.history else []
        if recent:
            actions = "; ".join(
                f"{h['action']}({json.dumps(h['details'], ensure_ascii=False)[:60]})"
                for h in recent
            )
            lines.append(f"Recent: {actions}")
        return "\n".join(lines) if lines else ""
    def clear(self):
        self.history.clear()
        self.current_dir = None
        self.last_app = None
        self.last_file = None
        self.last_folder = None
        self.last_action = None
        self.last_url = None
        self.last_search = None
        self._save_persistent()

    def _load_persistent(self):
        try:
            if not os.path.isfile(self.memory_file):
                return
            with open(self.memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self.pinned.update({
                    "last_saved_text": data.get("last_saved_text", "") or "",
                    "saved_at": data.get("saved_at", "") or "",
                    "notes": data.get("notes", []) if isinstance(data.get("notes", []), list) else [],
                    "user_name": data.get("user_name", "User"),
                    "user_gender": data.get("user_gender", "neutral"),
                })
        except Exception:
            # Non-critical: memory persistence should never crash app startup.
            pass

    def _save_persistent(self):
        try:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.pinned, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def remember_text(self, text, source="manual"):
        txt = (text or "").strip()
        if not txt:
            return False, "Нечего запоминать."
        self.pinned["last_saved_text"] = txt
        self.pinned["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notes = self.pinned.get("notes", [])
        notes.append({
            "text": txt[:3000],
            "source": source,
            "saved_at": self.pinned["saved_at"],
        })
        self.pinned["notes"] = notes[-50:]
        self._save_persistent()
        return True, "Запомнил."

    def recall_text(self):
        txt = self.pinned.get("last_saved_text", "").strip()
        if not txt:
            return ""
        return txt
class ReminderSystem:
    """Timer and reminder management with GUI notifications."""
    def __init__(self):
        self.active = []
        self._lock = threading.Lock()
    def set_reminder(self, seconds, message, gui):
        end_time = datetime.now() + timedelta(seconds=seconds)
        timer = threading.Timer(seconds, self._fire, args=(message, gui))
        timer.daemon = True
        timer.start()
        with self._lock:
            self.active.append({
                "timer": timer, "message": message, "end_time": end_time
            })
        return (
            f"Reminder set for {self._fmt(seconds)}.\n"
            f"   Fire at: {end_time.strftime('%H:%M:%S')}\n"
            f"   Message: {message or '(timer)'}"
        )
    def _fire(self, message, gui):
        from tkinter import messagebox
        display = message if message else "Timer is up!"
        gui.root.after(0, gui._append, f"\nREMINDER: {display}", "error")
        gui.root.after(0, gui._sep)
        gui.root.after(0, lambda: messagebox.showinfo("Sokol — Reminder", display))
        with self._lock:
            self.active = [
                r for r in self.active if r["end_time"] > datetime.now()
            ]
    def list_active(self):
        with self._lock:
            now = datetime.now()
            live = [r for r in self.active if r["end_time"] > now]
        if not live:
            return "No active reminders."
        lines = ["━━━ Active Reminders ━━━"]
        for i, r in enumerate(live, 1):
            remaining = (r["end_time"] - now).total_seconds()
            lines.append(
                f"  {i}. In {self._fmt(remaining)} — {r['message'] or '(timer)'}"
            )
        return "\n".join(lines)
    def cancel_all(self):
        with self._lock:
            for r in self.active:
                r["timer"].cancel()
            self.active.clear()
        return "All reminders cancelled."
    @staticmethod
    def _fmt(seconds):
        seconds = int(seconds)
        if seconds >= 3600:
            h, m = seconds // 3600, (seconds % 3600) // 60
            return f"{h}h {m}m" if m else f"{h}h"
        elif seconds >= 60:
            m, s = seconds // 60, seconds % 60
            return f"{m}m {s}s" if s else f"{m}m"
        return f"{seconds}s"
class ClipboardManager:
    """Read/write system clipboard via tkinter."""
    @staticmethod
    def read(root):
        try:
            return root.clipboard_get()
        except tk.TclError:
            return None
    @staticmethod
    def write(root, text):
        root.clipboard_clear()
        root.clipboard_append(text)
        root.update()
    @staticmethod
    def describe(text, max_len=300):
        if not text:
            return "(clipboard is empty)"
        preview = text[:max_len]
        if len(text) > max_len:
            preview += f"... (+{len(text) - max_len} chars)"
        return preview