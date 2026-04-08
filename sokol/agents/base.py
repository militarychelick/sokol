# -*- coding: utf-8 -*-
"""SOKOL v8.0 - Agent Base Infrastructure with Pydantic Validation"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field, validator
import json
import time
import logging

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Agent execution status"""
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    WAITING = "waiting"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentCapability(BaseModel):
    """Agent capability description"""
    name: str = Field(..., description="Capability name")
    description: str = Field(..., description="Capability description")
    requires_vision: bool = Field(default=False, description="Requires vision input")
    requires_system: bool = Field(default=False, description="Requires system access")
    max_execution_time: int = Field(default=30, description="Max execution time in seconds")


class AgentResponse(BaseModel):
    """Standardized agent response with Pydantic validation"""
    agent_id: str = Field(..., description="Agent identifier")
    status: AgentStatus = Field(..., description="Execution status")
    content: str = Field(default="", description="Response content")
    data: Dict[str, Any] = Field(default_factory=dict, description="Structured response data")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score")
    execution_time: float = Field(default=0.0, description="Execution time in seconds")
    error_message: Optional[str] = Field(default=None, description="Error message if failed")
    next_actions: List[str] = Field(default_factory=list, description="Suggested next actions")
    
    @validator('confidence')
    def validate_confidence(cls, v):
        if not 0.0 <= v <= 1.0:
            raise ValueError('Confidence must be between 0.0 and 1.0')
        return v
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return self.model_dump()
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return self.model_dump_json()


class AgentBase(ABC):
    """Base class for all Sokol agents with Pydantic validation"""
    
    def __init__(self, agent_id: str, capabilities: List[AgentCapability]):
        self.agent_id = agent_id
        self.capabilities = capabilities
        self.status = AgentStatus.IDLE
        self.logger = logging.getLogger(f"sokol.agents.{agent_id}")
        self._start_time = 0.0
        
    @property
    def is_busy(self) -> bool:
        """Check if agent is currently busy"""
        return self.status in [AgentStatus.THINKING, AgentStatus.EXECUTING, AgentStatus.WAITING]
    
    def get_capability(self, name: str) -> Optional[AgentCapability]:
        """Get capability by name"""
        for cap in self.capabilities:
            if cap.name == name:
                return cap
        return None
    
    def list_capabilities(self) -> List[str]:
        """List all capability names"""
        return [cap.name for cap in self.capabilities]
    
    @abstractmethod
    async def process(self, request: Dict[str, Any]) -> AgentResponse:
        """
        Process agent request - must be implemented by subclasses
        
        Args:
            request: Dictionary containing request parameters
            
        Returns:
            AgentResponse with Pydantic validation
        """
        pass
    
    def _start_execution(self) -> None:
        """Mark execution start"""
        self.status = AgentStatus.THINKING
        self._start_time = time.time()
        self.logger.debug(f"Agent {self.agent_id} started processing")
    
    def _finish_execution(self, status: AgentStatus) -> float:
        """Mark execution finish and return execution time"""
        execution_time = time.time() - self._start_time
        self.status = status
        self.logger.debug(f"Agent {self.agent_id} finished with status {status} in {execution_time:.2f}s")
        return execution_time
    
    def _create_response(
        self,
        status: AgentStatus,
        content: str = "",
        data: Optional[Dict[str, Any]] = None,
        confidence: float = 0.0,
        error_message: Optional[str] = None,
        next_actions: Optional[List[str]] = None
    ) -> AgentResponse:
        """Create standardized AgentResponse"""
        execution_time = self._finish_execution(status)
        
        return AgentResponse(
            agent_id=self.agent_id,
            status=status,
            content=content,
            data=data or {},
            confidence=confidence,
            execution_time=execution_time,
            error_message=error_message,
            next_actions=next_actions or []
        )
    
    async def validate_request(self, request: Dict[str, Any]) -> bool:
        """
        Validate incoming request before processing
        Override in subclasses for custom validation
        """
        return isinstance(request, dict) and "action" in request
    
    def get_info(self) -> Dict[str, Any]:
        """Get agent information"""
        return {
            "agent_id": self.agent_id,
            "status": self.status.value,
            "capabilities": [cap.model_dump() for cap in self.capabilities],
            "is_busy": self.is_busy
        }
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(id='{self.agent_id}', status='{self.status.value}')>"
