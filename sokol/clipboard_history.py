# -*- coding: utf-8 -*-
"""
SOKOL Smart Clipboard History
v8.0: Clipboard manager with history, search, and AI features
"""
import os
import json
import time
import hashlib
import threading
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
import ctypes
from ctypes import wintypes


@dataclass
class ClipboardItem:
    """Single clipboard entry."""
    content: str
    timestamp: str
    source: str  # 'manual', 'auto', 'sokol'
    content_hash: str = ""
    content_type: str = "text"  # text, url, code, etc.
    
    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.md5(self.content.encode('utf-8')).hexdigest()[:16]


class ClipboardHistory:
    """
    Manages clipboard history with persistence and search.
    v8.0: Stores last 50 clipboard entries, searchable by content/time.
    """
    
    MAX_HISTORY = 50
    SAVE_FILE = os.path.join(os.path.expanduser("~"), ".sokol", "clipboard_history.json")
    
    def __init__(self):
        self._history: List[ClipboardItem] = []
        self._lock = threading.Lock()
        self._last_clipboard_hash = ""
        self._ensure_dir()
        self._load()
    
    def _ensure_dir(self):
        """Ensure storage directory exists."""
        os.makedirs(os.path.dirname(self.SAVE_FILE), exist_ok=True)
    
    def _load(self):
        """Load history from disk."""
        try:
            if os.path.exists(self.SAVE_FILE):
                with open(self.SAVE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._history = [ClipboardItem(**item) for item in data[-self.MAX_HISTORY:]]
        except Exception:
            self._history = []
    
    def _save(self):
        """Save history to disk."""
        try:
            with open(self.SAVE_FILE, 'w', encoding='utf-8') as f:
                json.dump([asdict(item) for item in self._history], f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def add(self, content: str, source: str = "auto") -> bool:
        """Add item to history. Returns True if added (not duplicate)."""
        if not content or not content.strip():
            return False
        
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()[:16]
        
        with self._lock:
            # Check for duplicates (last 5 items)
            for item in self._history[-5:]:
                if item.content_hash == content_hash:
                    return False
            
            # Detect content type
            content_type = self._detect_content_type(content)
            
            item = ClipboardItem(
                content=content,
                timestamp=datetime.now().isoformat(),
                source=source,
                content_hash=content_hash,
                content_type=content_type
            )
            
            self._history.append(item)
            
            # Trim to max
            if len(self._history) > self.MAX_HISTORY:
                self._history = self._history[-self.MAX_HISTORY:]
            
            self._save()
            return True
    
    def _detect_content_type(self, content: str) -> str:
        """Detect type of clipboard content."""
        content = content.strip()
        
        # URL detection
        if content.startswith(('http://', 'https://', 'www.')):
            return "url"
        
        # Code detection (has common code patterns)
        code_patterns = ['def ', 'class ', 'import ', 'function', 'const ', 'var ', 'let ']
        if any(pattern in content for pattern in code_patterns):
            return "code"
        
        # File path detection
        if os.path.sep in content and (os.path.exists(content) or ':' in content):
            return "path"
        
        # Email detection
        if '@' in content and '.' in content.split('@')[-1]:
            return "email"
        
        return "text"
    
    def get_history(self, limit: int = 10) -> List[ClipboardItem]:
        """Get recent clipboard history."""
        with self._lock:
            return self._history[-limit:][::-1]  # Reverse for newest first
    
    def search(self, query: str, limit: int = 10) -> List[ClipboardItem]:
        """Search history by content."""
        query = query.lower()
        results = []
        with self._lock:
            for item in reversed(self._history):
                if query in item.content.lower():
                    results.append(item)
                    if len(results) >= limit:
                        break
        return results
    
    def search_by_time(self, time_description: str, limit: int = 10) -> List[ClipboardItem]:
        """
        Search by time description like 'yesterday', 'today', 'last hour', etc.
        """
        now = datetime.now()
        filtered = []
        
        with self._lock:
            for item in reversed(self._history):
                try:
                    item_time = datetime.fromisoformat(item.timestamp)
                    
                    # Parse time descriptions
                    if 'сегодня' in time_description or 'today' in time_description:
                        if item_time.date() == now.date():
                            filtered.append(item)
                    elif 'вчера' in time_description or 'yesterday' in time_description:
                        yesterday = now.date() - __import__('datetime').timedelta(days=1)
                        if item_time.date() == yesterday:
                            filtered.append(item)
                    elif 'час' in time_description or 'hour' in time_description:
                        hour_ago = now - __import__('datetime').timedelta(hours=1)
                        if item_time > hour_ago:
                            filtered.append(item)
                    elif 'минут' in time_description or 'minute' in time_description:
                        # Extract number if present
                        import re
                        num_match = re.search(r'(\d+)', time_description)
                        minutes = int(num_match.group(1)) if num_match else 10
                        minutes_ago = now - __import__('datetime').timedelta(minutes=minutes)
                        if item_time > minutes_ago:
                            filtered.append(item)
                    else:
                        # Default: search all
                        filtered.append(item)
                        
                    if len(filtered) >= limit:
                        break
                except Exception:
                    continue
        
        return filtered
    
    def get_by_index(self, index: int) -> Optional[ClipboardItem]:
        """Get item by index (0 = most recent)."""
        with self._lock:
            if 0 <= index < len(self._history):
                return self._history[-(index + 1)]
        return None
    
    def clear(self):
        """Clear all history."""
        with self._lock:
            self._history.clear()
            self._save()
    
    def format_history(self, limit: int = 10) -> str:
        """Format history as readable text."""
        items = self.get_history(limit)
        if not items:
            return "История буфера обмена пуста."
        
        lines = [f"━━━ История буфера (последние {len(items)}) ━━━"]
        
        for i, item in enumerate(items, 1):
            # Format timestamp
            try:
                dt = datetime.fromisoformat(item.timestamp)
                time_str = dt.strftime("%H:%M")
            except:
                time_str = "??:??"
            
            # Truncate content for display
            content_preview = item.content[:60].replace('\n', ' ')
            if len(item.content) > 60:
                content_preview += "..."
            
            icon = {
                "url": "🔗",
                "code": "💻",
                "path": "📁",
                "email": "📧",
                "text": "📄"
            }.get(item.content_type, "📄")
            
            lines.append(f"  {i}. [{time_str}] {icon} {content_preview}")
        
        lines.append("━" * 40)
        lines.append("Используй: 'вставь #3' или 'покажи историю буфера'")
        return "\n".join(lines)
    
    def format_search_results(self, query: str, items: List[ClipboardItem]) -> str:
        """Format search results."""
        if not items:
            return f'Ничего не найдено по запросу "{query}" в истории буфера.'
        
        lines = [f'━━━ Найдено по "{query}" ({len(items)} результатов) ━━━']
        
        for i, item in enumerate(items, 1):
            try:
                dt = datetime.fromisoformat(item.timestamp)
                time_str = dt.strftime("%d.%m %H:%M")
            except:
                time_str = "?"
            
            content_preview = item.content[:80].replace('\n', ' ')
            if len(item.content) > 80:
                content_preview += "..."
            
            lines.append(f"  {i}. [{time_str}] {content_preview}")
        
        lines.append("━" * 40)
        return "\n".join(lines)


class ClipboardWatcher:
    """
    Watches clipboard for changes and records to history.
    Runs in background thread.
    """
    
    def __init__(self, history: ClipboardHistory, interval: float = 1.0):
        self.history = history
        self.interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_content = ""
    
    def _get_clipboard_content(self) -> str:
        """Get current clipboard content (Windows)."""
        try:
            # Use ctypes for clipboard access
            CF_UNICODETEXT = 13
            
            if not ctypes.windll.user32.OpenClipboard(0):
                return ""
            
            try:
                handle = ctypes.windll.user32.GetClipboardData(CF_UNICODETEXT)
                if not handle:
                    return ""
                
                pointer = ctypes.windll.kernel32.GlobalLock(handle)
                if not pointer:
                    return ""
                
                try:
                    content = ctypes.wstring_at(pointer)
                    return content
                finally:
                    ctypes.windll.kernel32.GlobalUnlock(handle)
            finally:
                ctypes.windll.user32.CloseClipboard()
        except Exception:
            return ""
    
    def _watch_loop(self):
        """Background watching loop."""
        while self._running:
            try:
                content = self._get_clipboard_content()
                if content and content != self._last_content:
                    self._last_content = content
                    self.history.add(content, source="auto")
            except Exception:
                pass
            time.sleep(self.interval)
    
    def start(self):
        """Start watching clipboard."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Stop watching."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None


class SmartClipboardManager:
    """
    High-level clipboard manager with AI-like features.
    Combines history and watching functionality.
    """
    
    def __init__(self):
        self.history = ClipboardHistory()
        self.watcher: Optional[ClipboardWatcher] = None
        self._tk_root = None  # For GUI operations
    
    def start_watching(self, interval: float = 1.0):
        """Start automatic clipboard watching."""
        if self.watcher is None:
            self.watcher = ClipboardWatcher(self.history, interval)
        self.watcher.start()
    
    def stop_watching(self):
        """Stop clipboard watching."""
        if self.watcher:
            self.watcher.stop()
    
    def set_tk_root(self, root):
        """Set Tkinter root for clipboard operations."""
        self._tk_root = root
    
    def copy_to_clipboard(self, content: str) -> bool:
        """Copy content to clipboard and add to history."""
        success = False
        
        # Try using tkinter if available
        if self._tk_root:
            try:
                self._tk_root.clipboard_clear()
                self._tk_root.clipboard_append(content)
                self._tk_root.update()
                success = True
            except Exception:
                pass
        
        # Try Windows API
        if not success:
            try:
                CF_UNICODETEXT = 13
                GHND = 0x0042
                
                ctypes.windll.user32.OpenClipboard(0)
                ctypes.windll.user32.EmptyClipboard()
                
                data = content.encode('utf-16-le')
                size = len(data) + 2
                
                handle = ctypes.windll.kernel32.GlobalAlloc(GHND, size)
                ptr = ctypes.windll.kernel32.GlobalLock(handle)
                ctypes.memmove(ptr, data, len(data))
                ctypes.windll.kernel32.GlobalUnlock(handle)
                
                ctypes.windll.user32.SetClipboardData(CF_UNICODETEXT, handle)
                ctypes.windll.user32.CloseClipboard()
                success = True
            except Exception:
                pass
        
        if success:
            self.history.add(content, source="sokol")
        
        return success
    
    def paste_from_history(self, index: int = 0) -> Optional[str]:
        """Get content from history and copy to clipboard."""
        item = self.history.get_by_index(index)
        if item:
            self.copy_to_clipboard(item.content)
            return item.content
        return None
    
    def smart_search(self, query: str) -> str:
        """
        Smart search with natural language understanding.
        Handles queries like:
        - "вчетвером" → searches yesterday
        - "ссылка на гитхаб" → searches for URLs containing github
        - "код питона" → searches for Python code
        """
        query_lower = query.lower()
        
        # Time-based queries
        time_keywords = ['вчера', 'yesterday', 'сегодня', 'today', 
                        'час', 'hour', 'минут', 'minute']
        if any(kw in query_lower for kw in time_keywords):
            results = self.history.search_by_time(query, limit=10)
            return self.history.format_search_results(query, results)
        
        # Type-based queries
        if any(kw in query_lower for kw in ['ссылка', 'url', 'link', 'http']):
            all_items = self.history.get_history(50)
            results = [item for item in all_items if item.content_type == 'url']
            return self.history.format_search_results("URLs", results)
        
        if any(kw in query_lower for kw in ['код', 'code', 'python', 'питон']):
            all_items = self.history.get_history(50)
            results = [item for item in all_items if item.content_type == 'code']
            return self.history.format_search_results("code", results)
        
        # Default: content search
        results = self.history.search(query, limit=10)
        return self.history.format_search_results(query, results)
    
    def get_stats(self) -> str:
        """Get clipboard statistics."""
        history = self.history.get_history(50)
        
        if not history:
            return "История буфера пуста."
        
        types = {}
        for item in history:
            types[item.content_type] = types.get(item.content_type, 0) + 1
        
        lines = ["━━━ Статистика буфера обмена ━━━"]
        lines.append(f"Всего записей: {len(self.history._history)}")
        lines.append("")
        lines.append("По типам:")
        for t, count in sorted(types.items(), key=lambda x: -x[1]):
            icon = {"url": "🔗", "code": "💻", "path": "📁", "email": "📧", "text": "📄"}.get(t, "📄")
            lines.append(f"  {icon} {t}: {count}")
        
        lines.append("━" * 35)
        return "\n".join(lines)


# Global instance
_global_manager: Optional[SmartClipboardManager] = None


def get_clipboard_manager() -> SmartClipboardManager:
    """Get or create global clipboard manager."""
    global _global_manager
    if _global_manager is None:
        _global_manager = SmartClipboardManager()
    return _global_manager


# Convenience functions
def show_history(limit: int = 10) -> str:
    """Show clipboard history."""
    return get_clipboard_manager().history.format_history(limit)


def search_history(query: str) -> str:
    """Search clipboard history."""
    return get_clipboard_manager().smart_search(query)


def copy_and_remember(content: str) -> bool:
    """Copy to clipboard and save to history."""
    return get_clipboard_manager().copy_to_clipboard(content)


if __name__ == "__main__":
    # Test mode
    manager = SmartClipboardManager()
    print("Clipboard History Test Mode")
    print("===========================")
    print(manager.history.format_history())
    print("\nTest: Adding sample items...")
    manager.history.add("https://github.com/user/project", "test")
    manager.history.add("def hello(): print('world')", "test")
    manager.history.add("sample@email.com", "test")
    print(manager.history.format_history())
