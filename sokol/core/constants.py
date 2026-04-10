"""Constants and configuration paths."""

from pathlib import Path

from sokol.core.types import AgentState

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.toml"
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# State machine transitions: {current_state: [allowed_next_states]}
STATE_TRANSITIONS: dict[AgentState, list[AgentState]] = {
    AgentState.IDLE: [
        AgentState.LISTENING,
        AgentState.THINKING,
        AgentState.ERROR,
    ],
    AgentState.LISTENING: [
        AgentState.IDLE,
        AgentState.THINKING,
        AgentState.ERROR,
    ],
    AgentState.THINKING: [
        AgentState.EXECUTING,
        AgentState.WAITING_CONFIRM,
        AgentState.IDLE,
        AgentState.ERROR,
    ],
    AgentState.EXECUTING: [
        AgentState.IDLE,
        AgentState.THINKING,
        AgentState.ERROR,
    ],
    AgentState.WAITING_CONFIRM: [
        AgentState.EXECUTING,
        AgentState.IDLE,
        AgentState.ERROR,
    ],
    AgentState.ERROR: [
        AgentState.IDLE,
    ],
}

# Emergency stop hotkey
EMERGENCY_STOP_HOTKEY = "ctrl+alt+shift+escape"

# Wake words (Russian transliterations for better recognition)
DEFAULT_WAKE_WORDS = ["sokol", "cokol", "sockol", "sokal"]

# Voice response max length (characters)
VOICE_RESPONSE_MAX_LENGTH = 300

# Tool execution timeouts
DEFAULT_TOOL_TIMEOUT = 30.0
DANGEROUS_TOOL_TIMEOUT = 60.0

# Memory settings
SESSION_MEMORY_TTL = 3600  # seconds
MAX_CONVERSATION_HISTORY = 100

# UI settings
MAIN_WINDOW_MIN_WIDTH = 400
MAIN_WINDOW_MIN_HEIGHT = 500
TRAY_TOOLTIP_IDLE = "Sokol: Idle"
TRAY_TOOLTIP_LISTENING = "Sokol: Listening..."
TRAY_TOOLTIP_THINKING = "Sokol: Thinking..."
TRAY_TOOLTIP_EXECUTING = "Sokol: Executing..."
TRAY_TOOLTIP_ERROR = "Sokol: Error"

# Automation priorities (higher = better)
UIA_PRIORITY = 100
VISION_PRIORITY = 50
OCR_PRIORITY = 10

DOM_PRIORITY = 100
MOUSE_PRIORITY = 10
