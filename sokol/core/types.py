"""Core Pydantic models and types."""

from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel, Field


class AgentState(str, Enum):
    """Agent state machine states."""

    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    EXECUTING = "executing"
    WAITING_CONFIRM = "waiting_confirm"
    ERROR = "error"


class RiskLevel(str, Enum):
    """Tool risk levels."""

    READ = "read"  # Safe, read-only operations
    WRITE = "write"  # Modifies state, reversible
    DANGEROUS = "dangerous"  # Irreversible or high impact


class EventType(str, Enum):
    """Event types for agent event bus."""

    USER_INPUT = "user_input"
    STATE_CHANGE = "state_change"
    TOOL_EXECUTE = "tool_execute"
    TOOL_RESULT = "tool_result"
    CONFIRM_REQUEST = "confirm_request"
    CONFIRM_RESPONSE = "confirm_response"
    EMERGENCY_STOP = "emergency_stop"
    ERROR = "error"
    LOG = "log"


class AgentEvent(BaseModel):
    """Event for agent event bus."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: EventType
    timestamp: datetime = Field(default_factory=datetime.now)
    source: str = "unknown"
    data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


T = TypeVar("T")


class ToolResult(BaseModel, Generic[T]):
    """Result from tool execution."""

    success: bool
    data: T | None = None
    error: str | None = None
    undo_available: bool = False
    undo_info: dict[str, Any] = Field(default_factory=dict)
    execution_time: float = 0.0
    risk_level: RiskLevel = RiskLevel.READ


class MemoryEntry(BaseModel):
    """Base memory entry."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionMemory(MemoryEntry):
    """Session memory entry."""

    conversation: list[dict[str, Any]] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    active_tools: list[str] = Field(default_factory=list)


class UserProfile(MemoryEntry):
    """User profile memory."""

    name: str | None = None
    preferences: dict[str, Any] = Field(default_factory=dict)
    frequently_used_apps: list[str] = Field(default_factory=list)
    command_templates: dict[str, str] = Field(default_factory=dict)
    work_habits: dict[str, Any] = Field(default_factory=dict)


class LongTermMemory(MemoryEntry):
    """Long-term memory entry."""

    pattern_type: str = "general"
    pattern_data: dict[str, Any] = Field(default_factory=dict)
    usage_count: int = 0
    last_used: datetime | None = None


class ToolSchema(BaseModel):
    """Schema for tool definition."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema
    risk_level: RiskLevel
    undo_support: bool = False
    examples: list[str] = Field(default_factory=list)


class ConfirmationRequest(BaseModel):
    """Request for user confirmation."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    tool_name: str
    action_description: str
    risk_level: RiskLevel
    parameters: dict[str, Any]
    consequences: str
    timeout: float = 60.0  # seconds


class ConfirmationResponse(BaseModel):
    """User response to confirmation request."""

    request_id: str
    approved: bool
    reason: str | None = None


class TaskInfo(BaseModel):
    """Information about a running task."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    tool_name: str
    started_at: datetime = Field(default_factory=datetime.now)
    status: str = "running"  # running, completed, cancelled, failed
    is_background: bool = False
    cancellable: bool = True
    progress: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
