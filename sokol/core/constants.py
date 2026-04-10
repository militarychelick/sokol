"""
Constants and enums for Sokol v2
"""

from enum import Enum, auto
from typing import FrozenSet


class SafetyLevel(Enum):
    """Safety classification for actions."""
    SAFE = "safe"           # Execute immediately
    CAUTION = "caution"     # Ask for confirmation
    DANGEROUS = "dangerous" # Require explicit approval + audit


class ActionCategory(Enum):
    """Categories of actions the agent can perform."""
    APP_LAUNCH = "app_launch"
    APP_CLOSE = "app_close"
    APP_SWITCH = "app_switch"
    FILE_OPEN = "file_open"
    FILE_SEARCH = "file_search"
    FILE_DELETE = "file_delete"
    FILE_MODIFY = "file_modify"
    FILE_COPY = "file_copy"
    FILE_MOVE = "file_move"
    SYSTEM_SETTINGS = "system_settings"
    SYSTEM_POWER = "system_power"  # shutdown, restart, sleep
    CODE_EXECUTION = "code_execution"
    BROWSER_OPEN = "browser_open"
    BROWSER_NAVIGATE = "browser_navigate"
    BROWSER_TAB = "browser_tab"
    HOTKEY = "hotkey"
    MEDIA_CONTROL = "media_control"
    WINDOW_MANAGE = "window_manage"
    SEARCH_WEB = "search_web"
    UNKNOWN = "unknown"


class IntentType(Enum):
    """Types of user intents."""
    COMMAND = "command"       # Direct action request
    QUERY = "query"           # Question/information request
    WORKFLOW = "workflow"     # Multi-step task
    CONVERSATION = "conversation"  # General chat
    CLARIFICATION = "clarification"  # Asking for clarification
    CANCEL = "cancel"         # Cancel current action
    UNKNOWN = "unknown"


class AgentState(Enum):
    """Agent operational states."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    PLANNING = "planning"
    EXECUTING = "executing"
    SPEAKING = "speaking"
    WAITING_CONFIRMATION = "waiting_confirmation"
    ERROR = "error"


class LLMProvider(Enum):
    """LLM backend providers."""
    OLLAMA = "ollama"
    OPENAI = "openai"
    AUTO = "auto"  # Router decides


# Safety mappings: ActionCategory -> SafetyLevel
DEFAULT_SAFETY_MAP: dict[ActionCategory, SafetyLevel] = {
    ActionCategory.APP_LAUNCH: SafetyLevel.SAFE,
    ActionCategory.APP_SWITCH: SafetyLevel.SAFE,
    ActionCategory.APP_CLOSE: SafetyLevel.CAUTION,
    ActionCategory.FILE_OPEN: SafetyLevel.SAFE,
    ActionCategory.FILE_SEARCH: SafetyLevel.SAFE,
    ActionCategory.FILE_DELETE: SafetyLevel.DANGEROUS,
    ActionCategory.FILE_MODIFY: SafetyLevel.CAUTION,
    ActionCategory.FILE_COPY: SafetyLevel.SAFE,
    ActionCategory.FILE_MOVE: SafetyLevel.CAUTION,
    ActionCategory.SYSTEM_SETTINGS: SafetyLevel.DANGEROUS,
    ActionCategory.SYSTEM_POWER: SafetyLevel.DANGEROUS,
    ActionCategory.CODE_EXECUTION: SafetyLevel.DANGEROUS,
    ActionCategory.BROWSER_OPEN: SafetyLevel.SAFE,
    ActionCategory.BROWSER_NAVIGATE: SafetyLevel.CAUTION,
    ActionCategory.BROWSER_TAB: SafetyLevel.SAFE,
    ActionCategory.HOTKEY: SafetyLevel.CAUTION,
    ActionCategory.MEDIA_CONTROL: SafetyLevel.SAFE,
    ActionCategory.WINDOW_MANAGE: SafetyLevel.SAFE,
    ActionCategory.SEARCH_WEB: SafetyLevel.SAFE,
    ActionCategory.UNKNOWN: SafetyLevel.CAUTION,
}

# Hard-restricted paths that cannot be modified/deleted
RESTRICTED_PATHS: FrozenSet[str] = frozenset({
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "C:\\ProgramData",
    "C:\\Users\\Public",
})

# File patterns that are always dangerous
DANGEROUS_PATTERNS: FrozenSet[str] = frozenset({
    "*.sys",
    "*.dll",
    "*.exe",
    "*.bat",
    "*.cmd",
    "*.ps1",
    "*.vbs",
    "*.reg",
    "*password*",
    "*credential*",
    "*secret*",
    "*.key",
    "*.pem",
})
