# -*- coding: utf-8 -*-
"""
SOKOL v8.0 - Advanced Memory System
SQLite-based persistent memory with user profiles, conversation history, and preferences
"""
import sqlite3
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from threading import Lock

class SokolMemory:
    """
    Advanced memory system for SOKOL v8.0
    - Persistent storage via SQLite
    - User profile management
    - Conversation history with context
    - Application preferences
    - Contact management
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, 'initialized'):
            return
        
        self.db_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'sokol_memory.db'
        )
        self.initialized = True
        self._init_database()
    
    def _init_database(self):
        """Initialize database with all tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # User profile
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_profile (
                    id INTEGER PRIMARY KEY,
                    name TEXT DEFAULT 'User',
                    preferred_name TEXT,
                    timezone TEXT DEFAULT 'UTC',
                    language TEXT DEFAULT 'ru',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Conversation history
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,  -- 'user' or 'assistant'
                    message TEXT,
                    intent TEXT,  -- detected intent
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT  -- JSON with additional data
                )
            ''')
            
            # User preferences
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS preferences (
                    id INTEGER PRIMARY KEY,
                    category TEXT,
                    key TEXT UNIQUE,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Contact aliases (for messenger)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias TEXT UNIQUE,  -- "Лёха"
                    telegram_username TEXT,
                    telegram_id TEXT,
                    phone TEXT,
                    email TEXT,
                    notes TEXT,
                    usage_count INTEGER DEFAULT 0,
                    last_used TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Favorite/recent apps
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS favorite_apps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    app_name TEXT UNIQUE,
                    launch_count INTEGER DEFAULT 0,
                    last_launched TIMESTAMP,
                    is_favorite BOOLEAN DEFAULT 0
                )
            ''')
            
            # Reminders
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT,
                    fire_time TIMESTAMP,
                    is_recurring BOOLEAN DEFAULT 0,
                    recurrence_pattern TEXT,  -- daily, weekly, etc.
                    is_completed BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Macros (recorded sequences)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS macros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    description TEXT,
                    steps TEXT,  -- JSON array of steps
                    trigger_phrase TEXT,  -- voice/text trigger
                    usage_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Insert default profile if not exists
            cursor.execute(
                "INSERT OR IGNORE INTO user_profile (id, name) VALUES (1, 'User')"
            )
            
            conn.commit()
    
    # === USER PROFILE ===
    
    def get_user_name(self) -> str:
        """Get user's preferred name"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT preferred_name, name FROM user_profile WHERE id = 1")
            result = cursor.fetchone()
            if result:
                return result[0] or result[1] or "User"
            return "User"
    
    def set_user_name(self, name: str):
        """Set user's preferred name"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE user_profile 
                   SET preferred_name = ?, updated_at = CURRENT_TIMESTAMP 
                   WHERE id = 1""",
                (name,)
            )
            conn.commit()
    
    def get_user_profile(self) -> Dict[str, Any]:
        """Get complete user profile"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_profile WHERE id = 1")
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {}
    
    # === CONVERSATIONS ===
    
    def add_conversation_turn(self, role: str, message: str, intent: str = None, metadata: Dict = None):
        """Add a conversation turn"""
        session_id = time.strftime("%Y%m%d_%H%M%S")
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO conversations 
                   (session_id, role, message, intent, metadata)
                   VALUES (?, ?, ?, ?, ?)""",
                (session_id, role, message, intent, json.dumps(metadata or {}))
            )
            conn.commit()
    
    def get_recent_conversations(self, limit: int = 10) -> List[Dict]:
        """Get recent conversation history"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM conversations 
                   ORDER BY timestamp DESC LIMIT ?""",
                (limit,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in reversed(rows)]
    
    def get_conversation_context(self, max_turns: int = 5) -> str:
        """Get formatted conversation context for LLM"""
        conversations = self.get_recent_conversations(max_turns)
        lines = []
        for conv in conversations:
            role = "User" if conv['role'] == 'user' else "SOKOL"
            lines.append(f"{role}: {conv['message']}")
        return "\n".join(lines)
    
    # === CONTACTS ===
    
    def add_contact(self, alias: str, telegram_username: str = None, notes: str = None):
        """Add or update contact"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO contacts (alias, telegram_username, notes)
                   VALUES (?, ?, ?)
                   ON CONFLICT(alias) DO UPDATE SET
                   telegram_username = excluded.telegram_username,
                   notes = excluded.notes,
                   last_used = CURRENT_TIMESTAMP,
                   usage_count = usage_count + 1""",
                (alias, telegram_username, notes)
            )
            conn.commit()
    
    def get_contact(self, alias: str) -> Optional[Dict]:
        """Get contact by alias (fuzzy match)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Exact match first
            cursor.execute(
                "SELECT * FROM contacts WHERE alias = ? COLLATE NOCASE",
                (alias,)
            )
            row = cursor.fetchone()
            if row:
                # Update usage
                cursor.execute(
                    """UPDATE contacts 
                       SET usage_count = usage_count + 1, last_used = CURRENT_TIMESTAMP
                       WHERE id = ?""",
                    (row['id'],)
                )
                conn.commit()
                return dict(row)
            
            # Try fuzzy match
            cursor.execute("SELECT * FROM contacts")
            all_contacts = [dict(row) for row in cursor.fetchall()]
            
            from difflib import SequenceMatcher
            best_match = None
            best_ratio = 0
            
            for contact in all_contacts:
                ratio = SequenceMatcher(None, alias.lower(), contact['alias'].lower()).ratio()
                if ratio > best_ratio and ratio > 0.7:  # 70% similarity threshold
                    best_ratio = ratio
                    best_match = contact
            
            return best_match
    
    def get_all_contacts(self) -> List[Dict]:
        """Get all contacts ordered by usage"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM contacts ORDER BY usage_count DESC, last_used DESC"
            )
            return [dict(row) for row in cursor.fetchall()]
    
    # === PREFERENCES ===
    
    def set_preference(self, category: str, key: str, value: Any):
        """Store user preference"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO preferences (category, key, value)
                   VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                   value = excluded.value,
                   updated_at = CURRENT_TIMESTAMP""",
                (category, f"{category}.{key}", json.dumps(value))
            )
            conn.commit()
    
    def get_preference(self, category: str, key: str, default: Any = None) -> Any:
        """Get user preference"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value FROM preferences WHERE key = ?",
                (f"{category}.{key}",)
            )
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row[0])
                except:
                    return row[0]
            return default
    
    # === FAVORITE APPS ===
    
    def record_app_launch(self, app_name: str):
        """Record app launch for favorites tracking"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO favorite_apps (app_name, launch_count, last_launched)
                   VALUES (?, 1, CURRENT_TIMESTAMP)
                   ON CONFLICT(app_name) DO UPDATE SET
                   launch_count = launch_count + 1,
                   last_launched = CURRENT_TIMESTAMP""",
                (app_name,)
            )
            conn.commit()
    
    def get_favorite_apps(self, limit: int = 5) -> List[str]:
        """Get most frequently used apps"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """SELECT app_name FROM favorite_apps 
                   ORDER BY launch_count DESC, last_launched DESC
                   LIMIT ?""",
                (limit,)
            )
            return [row[0] for row in cursor.fetchall()]
    
    # === REMINDERS ===
    
    def add_reminder(self, message: str, fire_time: float, is_recurring: bool = False, 
                     recurrence_pattern: str = None) -> int:
        """Add reminder and return ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO reminders (message, fire_time, is_recurring, recurrence_pattern)
                   VALUES (?, ?, ?, ?)""",
                (message, datetime.fromtimestamp(fire_time), is_recurring, recurrence_pattern)
            )
            conn.commit()
            return cursor.lastrowid
    
    def get_pending_reminders(self) -> List[Dict]:
        """Get all pending (not fired and not completed) reminders"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """SELECT * FROM reminders 
                   WHERE is_completed = 0 AND fire_time > CURRENT_TIMESTAMP
                   ORDER BY fire_time"""
            )
            return [dict(row) for row in cursor.fetchall()]
    
    def complete_reminder(self, reminder_id: int):
        """Mark reminder as completed"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE reminders SET is_completed = 1 WHERE id = ?",
                (reminder_id,)
            )
            conn.commit()
    
    # === MACROS ===
    
    def save_macro(self, name: str, steps: List[Dict], trigger_phrase: str = None, 
                   description: str = None):
        """Save macro sequence"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO macros (name, description, steps, trigger_phrase)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                   description = excluded.description,
                   steps = excluded.steps,
                   trigger_phrase = excluded.trigger_phrase""",
                (name, description, json.dumps(steps), trigger_phrase)
            )
            conn.commit()
    
    def get_macro(self, name: str) -> Optional[Dict]:
        """Get macro by name"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM macros WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                macro = dict(row)
                macro['steps'] = json.loads(macro['steps'])
                return macro
            return None
    
    def get_all_macros(self) -> List[Dict]:
        """Get all macros"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM macros ORDER BY usage_count DESC")
            macros = []
            for row in cursor.fetchall():
                macro = dict(row)
                macro['steps'] = json.loads(macro['steps'])
                macros.append(macro)
            return macros
    
    def increment_macro_usage(self, name: str):
        """Increment macro usage counter"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE macros SET usage_count = usage_count + 1 WHERE name = ?",
                (name,)
            )
            conn.commit()


# Global instance
_memory_instance = None

def get_memory() -> SokolMemory:
    """Get global memory instance"""
    global _memory_instance
    if _memory_instance is None:
        _memory_instance = SokolMemory()
    return _memory_instance
