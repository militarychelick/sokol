# -*- coding: utf-8 -*-
"""SOKOL v8.0 - Planning Agent for Task Decomposition"""
import asyncio
import json
import logging
from typing import Any, Dict, List

from ..core import OllamaClient
from ..config import GROQ_MODEL_DEFAULT, OLLAMA_MODEL
from .base import AgentBase, AgentResponse, AgentStatus, AgentCapability

logger = logging.getLogger(__name__)


class PlanningAgent(AgentBase):
    """
    Planning Agent - Main brain for task decomposition
    Breaks down user requests into executable steps using Groq/Llama-3
    """
    
    def __init__(self):
        capabilities = [
            AgentCapability(
                name="plan",
                description="Decompose user requests into executable steps",
                max_execution_time=15
            ),
            AgentCapability(
                name="analyze",
                description="Analyze request complexity and requirements",
                max_execution_time=10
            ),
            AgentCapability(
                name="coordinate",
                description="Coordinate multi-agent execution plans",
                max_execution_time=5
            )
        ]
        
        super().__init__("planning_agent", capabilities)
        
        # Initialize LLM client
        self.llm_client = OllamaClient(
            model=OLLAMA_MODEL,
            system_message=self._get_system_prompt(),
            classify_prompt=self._get_classify_prompt()
        )
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for planning agent"""
        return """You are Sokol's Planning Agent - the main brain that breaks down user requests into executable steps.

Your job is to analyze user requests and create execution plans that other agents can follow.

RULES:
1. Break complex requests into simple, sequential steps
2. Identify which agents are needed for each step
3. Estimate execution time and complexity
4. Consider safety and system permissions
5. Prioritize speed and efficiency

AVAILABLE AGENTS:
- system_agent: Launch apps, manage windows, control processes, file operations
- vision_agent: Analyze screenshots, recognize UI elements, OCR text
- code_agent: Write and execute Python/Bash scripts for automation
- search_agent: Web search, external information lookup

RESPONSE FORMAT (JSON):
{
  "analysis": "Brief analysis of what the user wants",
  "agents": ["agent1", "agent2"],
  "mode": "sequential|parallel",
  "timeout": 30.0,
  "requires_vision": false,
  "requires_system": true,
  "steps": [
    {"step": 1, "agent": "system_agent", "action": "Launch application", "details": "..."},
    {"step": 2, "agent": "vision_agent", "action": "Analyze screen", "details": "..."}
  ],
  "fallback_agents": ["system_agent"],
  "confidence": 0.9
}

Be concise and practical. Focus on Windows automation and system control."""
    
    def _get_classify_prompt(self) -> str:
        """Get classification prompt for quick routing"""
        return """Classify the user request type. Respond with JSON:

{
  "type": "system|vision|code|search|mixed",
  "complexity": "simple|medium|complex",
  "agents_needed": ["agent1", "agent2"],
  "estimated_time": 15
}

Types:
- system: Launch apps, manage windows, file operations
- vision: Screen analysis, UI recognition
- code: Script writing, automation
- search: Web lookup, information gathering
- mixed: Multiple agent types needed"""
    
    async def process(self, request: Dict[str, Any]) -> AgentResponse:
        """Process planning request"""
        self._start_execution()
        
        try:
            action = request.get("action", "").lower()
            
            if action == "plan":
                return await self._create_execution_plan(request)
            elif action == "analyze":
                return await self._analyze_request(request)
            elif action == "coordinate":
                return await self._coordinate_agents(request)
            else:
                return await self._classify_and_route(request)
                
        except Exception as e:
            self.logger.error(f"Planning failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _create_execution_plan(self, request: Dict[str, Any]) -> AgentResponse:
        """Create detailed execution plan"""
        user_request = request.get("request", {})
        user_text = user_request.get("text", str(user_request))
        
        # Build planning prompt
        prompt = f"""User request: "{user_text}"

Create an execution plan for this request. Consider:
1. What needs to be done step by step
2. Which agents should handle each step
3. Whether vision analysis is needed
4. System permissions required
5. Fallback options if primary agents fail

Respond with JSON plan format."""
        
        try:
            # Get plan from LLM
            plan_text = await self._get_llm_response(prompt)
            
            # Parse JSON response
            try:
                plan_data = json.loads(plan_text)
            except json.JSONDecodeError:
                # Fallback to simple plan
                plan_data = self._create_fallback_plan(user_text)
            
            # Validate plan structure
            validated_plan = self._validate_plan(plan_data)
            
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content=f"Created execution plan with {len(validated_plan.get('steps', []))} steps",
                data=validated_plan,
                confidence=validated_plan.get("confidence", 0.7)
            )
            
        except Exception as e:
            self.logger.error(f"Plan creation failed: {e}")
            # Return fallback plan
            fallback_plan = self._create_fallback_plan(user_text)
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content="Created fallback execution plan",
                data=fallback_plan,
                confidence=0.5
            )
    
    async def _analyze_request(self, request: Dict[str, Any]) -> AgentResponse:
        """Analyze request complexity and requirements"""
        user_text = request.get("text", str(request))
        
        prompt = f"""Analyze this request: "{user_text}"

Provide analysis in JSON:
{{
  "type": "system|vision|code|search|mixed",
  "complexity": "simple|medium|complex",
  "estimated_time": 15,
  "requires_vision": false,
  "requires_system": true,
  "safety_concerns": [],
  "agents_needed": ["agent1", "agent2"]
}}"""
        
        try:
            analysis_text = await self._get_llm_response(prompt)
            analysis_data = json.loads(analysis_text)
            
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content="Request analysis completed",
                data=analysis_data,
                confidence=0.8
            )
            
        except Exception as e:
            self.logger.error(f"Analysis failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _coordinate_agents(self, request: Dict[str, Any]) -> AgentResponse:
        """Coordinate multi-agent execution"""
        # This would handle dynamic coordination during execution
        # For now, return basic coordination info
        return self._create_response(
            status=AgentStatus.SUCCESS,
            content="Agent coordination ready",
            data={"coordination_mode": "sequential"},
            confidence=0.9
        )
    
    async def _classify_and_route(self, request: Dict[str, Any]) -> AgentResponse:
        """Quick classification for routing"""
        user_text = request.get("text", str(request))
        
        prompt = f"""Classify: "{user_text}"

Respond with classification JSON."""
        
        try:
            classification_text = await self._get_llm_response(prompt, use_fast_mode=True)
            classification_data = json.loads(classification_text)
            
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content=f"Classified as {classification_data.get('type', 'unknown')}",
                data=classification_data,
                confidence=0.8
            )
            
        except Exception as e:
            self.logger.error(f"Classification failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _get_llm_response(self, prompt: str, use_fast_mode: bool = False) -> str:
        """Get response from LLM"""
        try:
            if use_fast_mode:
                # Use classify method for fast responses
                return self.llm_client.classify(prompt)
            else:
                # Use full chat for complex planning
                return self.llm_client.chat(prompt, one_shot=True)
        except Exception as e:
            self.logger.error(f"LLM response failed: {e}")
            raise
    
    def _validate_plan(self, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and fix plan structure"""
        validated = {
            "agents": plan_data.get("agents", ["system_agent"]),
            "mode": plan_data.get("mode", "sequential"),
            "timeout": float(plan_data.get("timeout", 30.0)),
            "requires_vision": bool(plan_data.get("requires_vision", False)),
            "requires_system": bool(plan_data.get("requires_system", True)),
            "steps": plan_data.get("steps", []),
            "fallback_agents": plan_data.get("fallback_agents", ["system_agent"]),
            "confidence": float(plan_data.get("confidence", 0.7))
        }
        
        # Ensure timeout is reasonable
        validated["timeout"] = max(5.0, min(120.0, validated["timeout"]))
        
        # Ensure confidence is in valid range
        validated["confidence"] = max(0.0, min(1.0, validated["confidence"]))
        
        return validated
    
    def _create_fallback_plan(self, user_text: str) -> Dict[str, Any]:
        """Create simple fallback plan"""
        # Simple keyword-based routing
        text_lower = user_text.lower()
        
        if any(keyword in text_lower for keyword in ["look", "see", "screen", "window"]):
            agents = ["vision_agent", "system_agent"]
            requires_vision = True
        elif any(keyword in text_lower for keyword in ["code", "script", "automate"]):
            agents = ["code_agent", "system_agent"]
            requires_vision = False
        elif any(keyword in text_lower for keyword in ["search", "find", "web"]):
            agents = ["search_agent"]
            requires_vision = False
        else:
            agents = ["system_agent"]
            requires_vision = False
        
        return {
            "agents": agents,
            "mode": "sequential",
            "timeout": 30.0,
            "requires_vision": requires_vision,
            "requires_system": True,
            "steps": [{"step": 1, "agent": agents[0], "action": "Execute request", "details": user_text}],
            "fallback_agents": ["system_agent"],
            "confidence": 0.5
        }
