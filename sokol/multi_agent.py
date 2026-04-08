# -*- coding: utf-8 -*-
"""SOKOL v8.0 - Multi-Agent System Integration"""
import asyncio
import logging
from typing import Any, Dict, Optional

from .agents import (
    AgentOrchestrator,
    PlanningAgent,
    SystemAgent,
    VisionAgent,
    CodeAgent,
    SearchAgent
)
from .memory import VectorMemoryStore, get_embedding_provider

logger = logging.getLogger(__name__)


class MultiAgentSystem:
    """
    Main multi-agent system that coordinates all agents
    Implements hybrid planning + execution architecture
    """
    
    def __init__(self, enable_memory: bool = True, enable_vision: bool = True):
        self.logger = logging.getLogger("sokol.multi_agent")
        
        # Initialize memory store
        self.memory_store = None
        if enable_memory:
            try:
                embedding_provider = get_embedding_provider()
                self.memory_store = VectorMemoryStore(embedding_provider=embedding_provider)
                asyncio.create_task(self.memory_store.initialize())
                self.logger.info("Vector memory store initialized")
            except Exception as e:
                self.logger.warning(f"Memory store initialization failed: {e}")
        
        # Initialize agents
        self.agents = {
            "planning_agent": PlanningAgent(),
            "system_agent": SystemAgent(),
            "vision_agent": VisionAgent() if enable_vision else None,
            "code_agent": CodeAgent(),
            "search_agent": SearchAgent()
        }
        
        # Remove None agents
        self.agents = {k: v for k, v in self.agents.items() if v is not None}
        
        # Initialize orchestrator
        self.orchestrator = AgentOrchestrator(self.agents, self.memory_store)
        
        self.logger.info(f"Multi-agent system initialized with {len(self.agents)} agents")
    
    async def process_request(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Main entry point for processing user requests
        
        Args:
            user_input: Natural language user request
            context: Optional context information
            
        Returns:
            Response dictionary with results and metadata
        """
        try:
            # Prepare request
            request = {
                "text": user_input,
                "action": "process",
                "context": context or {}
            }
            
            # Process through orchestrator
            response = await self.orchestrator.process_request(request)
            
            # Convert to dictionary for return
            result = {
                "success": response.status.value == "success",
                "content": response.content,
                "data": response.data,
                "confidence": response.confidence,
                "execution_time": response.execution_time,
                "agent_id": response.agent_id,
                "next_actions": response.next_actions,
                "error_message": response.error_message
            }
            
            self.logger.info(f"Request processed successfully in {response.execution_time:.2f}s")
            return result
            
        except Exception as e:
            self.logger.error(f"Request processing failed: {e}")
            return {
                "success": False,
                "content": "Request processing failed",
                "data": {},
                "confidence": 0.0,
                "execution_time": 0.0,
                "agent_id": "system",
                "next_actions": [],
                "error_message": str(e)
            }
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get system status and agent information"""
        try:
            agent_status = {}
            for agent_id, agent in self.agents.items():
                agent_status[agent_id] = agent.get_info()
            
            memory_stats = {}
            if self.memory_store:
                memory_stats = await self.memory_store.get_memory_stats()
            
            return {
                "agents": agent_status,
                "memory": memory_stats,
                "orchestrator": {
                    "available_agents": self.orchestrator.list_available_agents(),
                    "agent_capabilities": self.orchestrator.get_agent_capabilities()
                }
            }
            
        except Exception as e:
            self.logger.error(f"Status check failed: {e}")
            return {"error": str(e)}
    
    async def warmup(self):
        """Warm up the multi-agent system"""
        try:
            self.logger.info("Warming up multi-agent system...")
            
            # Warm up planning agent
            planning_agent = self.agents.get("planning_agent")
            if planning_agent:
                await planning_agent.llm_client.warmup()
            
            # Warm up memory store
            if self.memory_store:
                await self.memory_store.initialize()
            
            self.logger.info("Multi-agent system warmup completed")
            
        except Exception as e:
            self.logger.error(f"Warmup failed: {e}")
    
    async def shutdown(self):
        """Shutdown the multi-agent system"""
        try:
            self.logger.info("Shutting down multi-agent system...")
            
            # Close memory store
            if self.memory_store:
                await self.memory_store.close()
            
            self.logger.info("Multi-agent system shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Shutdown failed: {e}")


# Global instance for easy access
_multi_agent_system: Optional[MultiAgentSystem] = None


def get_multi_agent_system(enable_memory: bool = True, enable_vision: bool = True) -> MultiAgentSystem:
    """Get or create global multi-agent system instance"""
    global _multi_agent_system
    if _multi_agent_system is None:
        _multi_agent_system = MultiAgentSystem(enable_memory, enable_vision)
    return _multi_agent_system


async def process_user_request(user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Convenience function to process user request"""
    system = get_multi_agent_system()
    return await system.process_request(user_input, context)
