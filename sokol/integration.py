# -*- coding: utf-8 -*-
"""SOKOL v8.0 - Multi-Agent Integration Layer"""
import asyncio
import logging
from typing import Any, Dict, Optional

from .multi_agent import MultiAgentSystem, process_user_request
from .config import VERSION

logger = logging.getLogger(__name__)


class SokolMultiAgentIntegration:
    """
    Integration layer for connecting multi-agent system with existing Sokol GUI
    Provides backward compatibility while adding new multi-agent capabilities
    """
    
    def __init__(self):
        self.multi_agent_system: Optional[MultiAgentSystem] = None
        self.logger = logging.getLogger("sokol.integration")
        self._initialized = False
        
    async def initialize(self, enable_memory: bool = True, enable_vision: bool = True):
        """Initialize the multi-agent system"""
        if self._initialized:
            return
            
        try:
            self.multi_agent_system = MultiAgentSystem(enable_memory, enable_vision)
            await self.multi_agent_system.warmup()
            self._initialized = True
            self.logger.info("Sokol v8.0 multi-agent system initialized")
        except Exception as e:
            self.logger.error(f"Multi-agent initialization failed: {e}")
            raise
    
    async def process_user_message(self, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process user message through multi-agent system
        Compatible with existing GUI interface
        """
        if not self._initialized:
            await self.initialize()
        
        if not self.multi_agent_system:
            return {
                "success": False,
                "content": "Multi-agent system not available",
                "data": {},
                "confidence": 0.0
            }
        
        try:
            # Process through multi-agent system
            result = await self.multi_agent_system.process_request(message, context)
            
            # Convert to legacy format for GUI compatibility
            legacy_response = self._convert_to_legacy_format(result)
            
            return legacy_response
            
        except Exception as e:
            self.logger.error(f"Message processing failed: {e}")
            return {
                "success": False,
                "content": f"Processing failed: {str(e)}",
                "data": {},
                "confidence": 0.0
            }
    
    def _convert_to_legacy_format(self, multi_agent_result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert multi-agent result to legacy Sokol format"""
        return {
            "response": multi_agent_result.get("content", ""),
            "data": multi_agent_result.get("data", {}),
            "confidence": multi_agent_result.get("confidence", 0.0),
            "agent_used": multi_agent_result.get("agent_id", "unknown"),
            "execution_time": multi_agent_result.get("execution_time", 0.0),
            "success": multi_agent_result.get("success", False),
            "next_actions": multi_agent_result.get("next_actions", []),
            "error": multi_agent_result.get("error_message")
        }
    
    async def get_system_info(self) -> Dict[str, Any]:
        """Get system information for GUI display"""
        if not self._initialized:
            return {"status": "not_initialized", "version": VERSION}
        
        try:
            status = await self.multi_agent_system.get_system_status()
            return {
                "status": "initialized",
                "version": VERSION,
                "multi_agent": status,
                "capabilities": {
                    "planning": "planning_agent" in self.multi_agent_system.agents,
                    "system_control": "system_agent" in self.multi_agent_system.agents,
                    "vision": "vision_agent" in self.multi_agent_system.agents,
                    "code_automation": "code_agent" in self.multi_agent_system.agents,
                    "search": "search_agent" in self.multi_agent_system.agents,
                    "vector_memory": self.multi_agent_system.memory_store is not None
                }
            }
        except Exception as e:
            self.logger.error(f"System info failed: {e}")
            return {"status": "error", "error": str(e), "version": VERSION}
    
    async def handle_alt_space_activation(self) -> Dict[str, Any]:
        """
        Handle Alt+Space activation - take screenshot and analyze
        Key feature for instant context awareness
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # Take screenshot and analyze through vision agent
            result = await self.multi_agent_system.process_request(
                "Analyze current screen and suggest actions",
                context={"trigger": "alt_space"}
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Alt+Space activation failed: {e}")
            return {
                "success": False,
                "content": f"Screen analysis failed: {str(e)}",
                "data": {},
                "confidence": 0.0
            }
    
    async def shutdown(self):
        """Shutdown the multi-agent system"""
        if self.multi_agent_system:
            await self.multi_agent_system.shutdown()
        self._initialized = False


# Global integration instance
_integration: Optional[SokolMultiAgentIntegration] = None


def get_integration() -> SokolMultiAgentIntegration:
    """Get global integration instance"""
    global _integration
    if _integration is None:
        _integration = SokolMultiAgentIntegration()
    return _integration


# Convenience functions for backward compatibility
async def process_message(message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Process message through multi-agent system (backward compatible)"""
    integration = get_integration()
    return await integration.process_user_message(message, context)


async def get_sokol_status() -> Dict[str, Any]:
    """Get Sokol system status"""
    integration = get_integration()
    return await integration.get_system_info()


async def activate_context_awareness() -> Dict[str, Any]:
    """Activate context awareness (Alt+Space)"""
    integration = get_integration()
    return await integration.handle_alt_space_activation()
