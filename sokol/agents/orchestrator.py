# -*- coding: utf-8 -*-
"""SOKOL v8.0 - Agent Orchestrator for Multi-Agent Coordination"""
import asyncio
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging
from enum import Enum

from .base import AgentBase, AgentResponse, AgentStatus
from ..memory.vector_store import VectorMemoryStore

logger = logging.getLogger(__name__)


class OrchestratorMode(str, Enum):
    """Orchestration modes"""
    SEQUENTIAL = "sequential"  # Execute agents one by one
    PARALLEL = "parallel"     # Execute agents in parallel
    ADAPTIVE = "adaptive"     # Choose based on request


@dataclass
class ExecutionPlan:
    """Agent execution plan"""
    agents: List[str]  # Agent IDs in execution order
    mode: OrchestratorMode
    timeout: float
    requires_vision: bool = False
    requires_system: bool = False
    fallback_agents: List[str] = None  # Backup agents if primary fails


class AgentOrchestrator:
    """
    Multi-agent orchestrator for coordinating agent execution
    Implements hybrid planning + execution architecture
    """
    
    def __init__(self, agents: Dict[str, AgentBase], memory_store: Optional[VectorMemoryStore] = None):
        self.agents = agents
        self.memory_store = memory_store
        self.logger = logging.getLogger("sokol.orchestrator")
        self._execution_history: List[Dict[str, Any]] = []
        
    def get_agent(self, agent_id: str) -> Optional[AgentBase]:
        """Get agent by ID"""
        return self.agents.get(agent_id)
    
    def list_available_agents(self) -> List[str]:
        """List all available agent IDs"""
        return list(self.agents.keys())
    
    def get_agent_capabilities(self) -> Dict[str, List[str]]:
        """Get capabilities of all agents"""
        return {
            agent_id: agent.list_capabilities()
            for agent_id, agent in self.agents.items()
        }
    
    async def create_execution_plan(self, request: Dict[str, Any]) -> ExecutionPlan:
        """
        Create execution plan using Planning Agent
        Falls back to rule-based planning if Planning Agent unavailable
        """
        action = request.get("action", "").lower()
        
        # Try Planning Agent first
        planning_agent = self.get_agent("planning_agent")
        if planning_agent and not planning_agent.is_busy:
            try:
                plan_response = await planning_agent.process({"action": "plan", "request": request})
                if plan_response.status == AgentStatus.SUCCESS:
                    return self._parse_plan_from_response(plan_response.data)
            except Exception as e:
                self.logger.warning(f"Planning agent failed: {e}")
        
        # Fallback to rule-based planning
        return self._create_rule_based_plan(request)
    
    def _parse_plan_from_response(self, plan_data: Dict[str, Any]) -> ExecutionPlan:
        """Parse execution plan from Planning Agent response"""
        agents = plan_data.get("agents", ["system_agent"])
        mode = OrchestratorMode(plan_data.get("mode", "sequential"))
        timeout = float(plan_data.get("timeout", 30.0))
        requires_vision = plan_data.get("requires_vision", False)
        requires_system = plan_data.get("requires_system", True)
        fallback_agents = plan_data.get("fallback_agents", [])
        
        return ExecutionPlan(
            agents=agents,
            mode=mode,
            timeout=timeout,
            requires_vision=requires_vision,
            requires_system=requires_system,
            fallback_agents=fallback_agents
        )
    
    def _create_rule_based_plan(self, request: Dict[str, Any]) -> ExecutionPlan:
        """Create execution plan based on rules (fallback method)"""
        action = request.get("action", "").lower()
        
        # Vision-related requests
        if any(keyword in action for keyword in ["look", "see", "screen", "window", "interface"]):
            return ExecutionPlan(
                agents=["vision_agent", "system_agent"],
                mode=OrchestratorMode.SEQUENTIAL,
                timeout=20.0,
                requires_vision=True,
                requires_system=True,
                fallback_agents=["system_agent"]
            )
        
        # Code-related requests
        elif any(keyword in action for keyword in ["code", "script", "automate", "program"]):
            return ExecutionPlan(
                agents=["code_agent", "system_agent"],
                mode=OrchestratorMode.SEQUENTIAL,
                timeout=45.0,
                requires_system=True,
                fallback_agents=["system_agent"]
            )
        
        # Search-related requests
        elif any(keyword in action for keyword in ["search", "find", "lookup", "web"]):
            return ExecutionPlan(
                agents=["search_agent"],
                mode=OrchestratorMode.SEQUENTIAL,
                timeout=30.0,
                fallback_agents=[]
            )
        
        # Default: system agent only
        else:
            return ExecutionPlan(
                agents=["system_agent"],
                mode=OrchestratorMode.SEQUENTIAL,
                timeout=15.0,
                requires_system=True,
                fallback_agents=[]
            )
    
    async def execute_plan(self, plan: ExecutionPlan, request: Dict[str, Any]) -> AgentResponse:
        """
        Execute the agent execution plan
        Returns combined response from all agents
        """
        self.logger.info(f"Executing plan with agents: {plan.agents}")
        
        try:
            if plan.mode == OrchestratorMode.SEQUENTIAL:
                return await self._execute_sequential(plan, request)
            elif plan.mode == OrchestratorMode.PARALLEL:
                return await self._execute_parallel(plan, request)
            else:
                return await self._execute_adaptive(plan, request)
        except asyncio.TimeoutError:
            return self._create_timeout_response(plan)
        except Exception as e:
            self.logger.error(f"Plan execution failed: {e}")
            return self._create_error_response(str(e), plan)
    
    async def _execute_sequential(self, plan: ExecutionPlan, request: Dict[str, Any]) -> AgentResponse:
        """Execute agents sequentially"""
        responses = []
        accumulated_data = request.copy()
        
        for agent_id in plan.agents:
            agent = self.get_agent(agent_id)
            if not agent:
                continue
                
            if agent.is_busy:
                self.logger.warning(f"Agent {agent_id} is busy, skipping")
                continue
            
            try:
                response = await asyncio.wait_for(
                    agent.process(accumulated_data),
                    timeout=plan.timeout / len(plan.agents)
                )
                responses.append(response)
                
                # Accumulate data for next agent
                if response.data:
                    accumulated_data.update(response.data)
                
                # Stop on failure
                if response.status == AgentStatus.FAILED:
                    break
                    
            except asyncio.TimeoutError:
                self.logger.warning(f"Agent {agent_id} timed out")
                break
            except Exception as e:
                self.logger.error(f"Agent {agent_id} failed: {e}")
                break
        
        return self._combine_responses(responses, plan)
    
    async def _execute_parallel(self, plan: ExecutionPlan, request: Dict[str, Any]) -> AgentResponse:
        """Execute agents in parallel"""
        tasks = []
        
        for agent_id in plan.agents:
            agent = self.get_agent(agent_id)
            if not agent or agent.is_busy:
                continue
            
            task = asyncio.create_task(
                asyncio.wait_for(agent.process(request), timeout=plan.timeout)
            )
            tasks.append(task)
        
        if not tasks:
            return self._create_error_response("No available agents", plan)
        
        try:
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            valid_responses = [r for r in responses if isinstance(r, AgentResponse)]
            return self._combine_responses(valid_responses, plan)
        except Exception as e:
            return self._create_error_response(str(e), plan)
    
    async def _execute_adaptive(self, plan: ExecutionPlan, request: Dict[str, Any]) -> AgentResponse:
        """Adaptive execution based on agent availability and request type"""
        # For now, default to sequential
        return await self._execute_sequential(plan, request)
    
    def _combine_responses(self, responses: List[AgentResponse], plan: ExecutionPlan) -> AgentResponse:
        """Combine multiple agent responses into one"""
        if not responses:
            return self._create_error_response("No successful responses", plan)
        
        # Use the last successful response as primary
        primary_response = responses[-1]
        
        # Combine data from all responses
        combined_data = {}
        for response in responses:
            if response.data:
                combined_data.update(response.data)
        
        # Combine content
        combined_content = "\n".join(r.content for r in responses if r.content)
        
        # Calculate average confidence
        confidences = [r.confidence for r in responses if r.confidence > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Determine overall status
        has_failure = any(r.status == AgentStatus.FAILED for r in responses)
        status = AgentStatus.FAILED if has_failure else AgentStatus.SUCCESS
        
        return AgentResponse(
            agent_id="orchestrator",
            status=status,
            content=combined_content,
            data=combined_data,
            confidence=avg_confidence,
            execution_time=sum(r.execution_time for r in responses),
            next_actions=primary_response.next_actions
        )
    
    def _create_timeout_response(self, plan: ExecutionPlan) -> AgentResponse:
        """Create timeout response"""
        return AgentResponse(
            agent_id="orchestrator",
            status=AgentStatus.FAILED,
            content="Execution timed out",
            confidence=0.0,
            error_message=f"Plan execution timed out after {plan.timeout}s"
        )
    
    def _create_error_response(self, error_message: str, plan: ExecutionPlan) -> AgentResponse:
        """Create error response"""
        return AgentResponse(
            agent_id="orchestrator",
            status=AgentStatus.FAILED,
            content="Execution failed",
            confidence=0.0,
            error_message=error_message
        )
    
    async def process_request(self, request: Dict[str, Any]) -> AgentResponse:
        """
        Main entry point for processing requests
        Creates plan and executes it
        """
        try:
            # Store request in memory if available
            if self.memory_store:
                await self.memory_store.store_request(request)
            
            # Create execution plan
            plan = await self.create_execution_plan(request)
            
            # Execute plan
            response = await self.execute_plan(plan, request)
            
            # Store response in memory if available
            if self.memory_store:
                await self.memory_store.store_response(response)
            
            # Log execution
            self._execution_history.append({
                "timestamp": asyncio.get_event_loop().time(),
                "request": request,
                "plan": plan,
                "response": response.to_dict()
            })
            
            return response
            
        except Exception as e:
            self.logger.error(f"Request processing failed: {e}")
            return self._create_error_response(str(e), ExecutionPlan([], OrchestratorMode.SEQUENTIAL, 0))
    
    def get_execution_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent execution history"""
        return self._execution_history[-limit:]
