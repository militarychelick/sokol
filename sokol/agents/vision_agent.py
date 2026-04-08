# -*- coding: utf-8 -*-
"""SOKOL v8.0 - Vision Agent for Screen Analysis"""
import asyncio
import logging
from typing import Any, Dict, List, Optional
import base64
from io import BytesIO

from ..core import OllamaClient
from ..config import OLLAMA_MODEL, SCREENSHOTS_DIR
from ..automation import ScreenCapture
from ..vision_system import get_hybrid_vision_system, analyze_screen_image
from .base import AgentBase, AgentResponse, AgentStatus, AgentCapability

logger = logging.getLogger(__name__)


class VisionAgent(AgentBase):
    """
    Vision Agent - Analyzes screenshots through VLM
    Understands what's happening on screen (e.g., "click Play button in launcher")
    """
    
    def __init__(self):
        capabilities = [
            AgentCapability(
                name="analyze_screen",
                description="Analyze screenshot and identify UI elements",
                requires_vision=True,
                max_execution_time=15
            ),
            AgentCapability(
                name="ocr_text",
                description="Extract text from screen using OCR",
                requires_vision=True,
                max_execution_time=10
            ),
            AgentCapability(
                name="find_elements",
                description="Find specific UI elements on screen",
                requires_vision=True,
                max_execution_time=12
            ),
            AgentCapability(
                name="describe_screen",
                description="Describe current screen content",
                requires_vision=True,
                max_execution_time=8
            )
        ]
        
        super().__init__("vision_agent", capabilities)
        
        # Initialize hybrid vision system
        self.hybrid_vision = get_hybrid_vision_system()
        self.logger.info("Vision Agent initialized with hybrid VLM system")
        
    def _get_local_vlm_client(self):
        """Get local VLM client (Moondream2)"""
        if self.local_vlm_client is None:
            try:
                # Try to use local vision model
                self.local_vlm_client = OllamaClient(
                    model="moondream2",  # Local lightweight vision model
                    system_message=self._get_vision_system_prompt(),
                    classify_prompt=""
                )
                logger.info("Using local Moondream2 for vision")
            except Exception as e:
                logger.warning(f"Local VLM not available: {e}")
                self._use_local = False
        return self.local_vlm_client
    
    def _get_groq_vision_client(self):
        """Get Groq vision client"""
        if self.groq_vision_client is None:
            try:
                import os
                if os.environ.get("GROQ_API_KEY"):
                    # Would set up Groq client here
                    logger.info("Using Groq Llama-3-Vision")
                else:
                    raise Exception("Groq API key not available")
            except Exception as e:
                logger.warning(f"Groq Vision not available: {e}")
        return self.groq_vision_client
    
    def _get_vision_system_prompt(self) -> str:
        """Get system prompt for vision analysis"""
        return """You are Sokol's Vision Agent. Analyze screenshots and identify UI elements.

Your job:
1. Describe what you see on the screen
2. Identify buttons, text fields, menus, and other interactive elements
3. Read text content using OCR capabilities
4. Suggest actions the user might want to take

RESPONSE FORMAT (JSON):
{
  "description": "Brief description of the screen",
  "elements": [
    {"type": "button", "text": "Play", "position": "center", "actionable": true},
    {"type": "text", "content": "Welcome", "position": "top"},
    {"type": "input", "placeholder": "Enter name", "position": "middle"}
  ],
  "suggested_actions": ["click Play button", "type in search field"],
  "confidence": 0.9,
  "context": "game_launcher, main_menu"
}

Be concise and focus on actionable elements."""
    
    async def process(self, request: Dict[str, Any]) -> AgentResponse:
        """Process vision agent request"""
        self._start_execution()
        
        try:
            action = request.get("action", "").lower()
            
            if action == "analyze_screen":
                return await self._analyze_screen(request)
            elif action == "ocr_text":
                return await self._extract_text(request)
            elif action == "find_elements":
                return await self._find_elements(request)
            elif action == "describe_screen":
                return await self._describe_screen(request)
            elif action == "screenshot":
                return await self._take_screenshot(request)
            else:
                return await self._handle_vision_request(request)
                
        except Exception as e:
            self.logger.error(f"Vision analysis failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _analyze_screen(self, request: Dict[str, Any]) -> AgentResponse:
        """Analyze screenshot and identify UI elements"""
        try:
            # Take screenshot
            screenshot_path = await self._capture_screenshot()
            if not screenshot_path:
                return self._create_response(
                    status=AgentStatus.FAILED,
                    error_message="Failed to capture screenshot"
                )
            
            # Analyze with VLM
            analysis = await self._analyze_with_vlm(screenshot_path, "Analyze this screen and identify all UI elements")
            
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content="Screen analysis completed",
                data={
                    "screenshot_path": screenshot_path,
                    "analysis": analysis
                },
                confidence=analysis.get("confidence", 0.7)
            )
            
        except Exception as e:
            self.logger.error(f"Screen analysis failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _extract_text(self, request: Dict[str, Any]) -> AgentResponse:
        """Extract text from screen using OCR"""
        try:
            # Take screenshot
            screenshot_path = await self._capture_screenshot()
            if not screenshot_path:
                return self._create_response(
                    status=AgentStatus.FAILED,
                    error_message="Failed to capture screenshot"
                )
            
            # Extract text with VLM
            text_analysis = await self._analyze_with_vlm(screenshot_path, "Extract all text visible on this screen. Return the text exactly as it appears.")
            
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content="Text extraction completed",
                data={
                    "screenshot_path": screenshot_path,
                    "extracted_text": text_analysis.get("extracted_text", ""),
                    "text_regions": text_analysis.get("text_regions", [])
                },
                confidence=text_analysis.get("confidence", 0.8)
            )
            
        except Exception as e:
            self.logger.error(f"Text extraction failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _find_elements(self, request: Dict[str, Any]) -> AgentResponse:
        """Find specific UI elements on screen"""
        element_type = request.get("element_type", "")
        element_text = request.get("element_text", "")
        
        try:
            # Take screenshot
            screenshot_path = await self._capture_screenshot()
            if not screenshot_path:
                return self._create_response(
                    status=AgentStatus.FAILED,
                    error_message="Failed to capture screenshot"
                )
            
            # Build search prompt
            search_prompt = f"Find {element_type}"
            if element_text:
                search_prompt += f" with text '{element_text}'"
            search_prompt += " on this screen. Return their positions and descriptions."
            
            # Search with VLM
            search_result = await self._analyze_with_vlm(screenshot_path, search_prompt)
            
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content=f"Found {len(search_result.get('elements', []))} elements",
                data={
                    "screenshot_path": screenshot_path,
                    "elements": search_result.get("elements", []),
                    "element_type": element_type,
                    "element_text": element_text
                },
                confidence=search_result.get("confidence", 0.7)
            )
            
        except Exception as e:
            self.logger.error(f"Element search failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _describe_screen(self, request: Dict[str, Any]) -> AgentResponse:
        """Describe current screen content"""
        try:
            # Take screenshot
            screenshot_path = await self._capture_screenshot()
            if not screenshot_path:
                return self._create_response(
                    status=AgentStatus.FAILED,
                    error_message="Failed to capture screenshot"
                )
            
            # Describe with VLM
            description = await self._analyze_with_vlm(screenshot_path, "Describe what you see on this screen. What application is this? What is the current state?")
            
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content="Screen description completed",
                data={
                    "screenshot_path": screenshot_path,
                    "description": description.get("description", ""),
                    "application": description.get("application", "unknown"),
                    "state": description.get("state", "unknown")
                },
                confidence=description.get("confidence", 0.8)
            )
            
        except Exception as e:
            self.logger.error(f"Screen description failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _take_screenshot(self, request: Dict[str, Any]) -> AgentResponse:
        """Take screenshot only"""
        try:
            screenshot_path = await self._capture_screenshot()
            if screenshot_path:
                return self._create_response(
                    status=AgentStatus.SUCCESS,
                    content="Screenshot captured",
                    data={"screenshot_path": screenshot_path},
                    confidence=1.0
                )
            else:
                return self._create_response(
                    status=AgentStatus.FAILED,
                    error_message="Failed to capture screenshot"
                )
        except Exception as e:
            self.logger.error(f"Screenshot failed: {e}")
            return self._create_response(
                status=AgentStatus.FAILED,
                error_message=str(e)
            )
    
    async def _handle_vision_request(self, request: Dict[str, Any]) -> AgentResponse:
        """Handle general vision requests"""
        text = request.get("text", str(request)).lower()
        
        # Try to interpret natural language vision requests
        if "look" in text or "see" in text or "screen" in text:
            return await self._describe_screen(request)
        elif "find" in text or "search" in text:
            return await self._find_elements(request)
        elif "read" in text or "text" in text:
            return await self._extract_text(request)
        else:
            return self._create_response(
                status=AgentStatus.SUCCESS,
                content="Vision agent ready. Available operations: analyze_screen, ocr_text, find_elements, describe_screen",
                data={"available_operations": self.list_capabilities()},
                confidence=0.7
            )
    
    async def _capture_screenshot(self) -> Optional[str]:
        """Capture screenshot and return path"""
        try:
            # Ensure screenshots directory exists
            import os
            os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
            
            # Take screenshot
            success, msg, screenshot_path = await asyncio.get_event_loop().run_in_executor(
                None, ScreenCapture.take
            )
            
            if screenshot_path and os.path.exists(screenshot_path):
                self.logger.debug(f"Screenshot captured: {screenshot_path}")
                return screenshot_path
            else:
                self.logger.error("Screenshot capture returned invalid path")
                return None
                
        except Exception as e:
            self.logger.error(f"Screenshot capture failed: {e}")
            return None
    
    async def _analyze_with_vlm(self, image_path: str, prompt: str) -> Dict[str, Any]:
        """Analyze image with hybrid Vision Language Model"""
        try:
            # Use hybrid vision system
            result = await analyze_screen_image(image_path, prompt)
            
            # Ensure result has expected structure
            if "error" in result:
                self.logger.error(f"VLM analysis failed: {result['error']}")
                return self._create_fallback_analysis(image_path)
            
            # Add confidence if not present
            if "confidence" not in result:
                result["confidence"] = 0.7
            
            return result
            
        except Exception as e:
            self.logger.error(f"VLM analysis failed: {e}")
            return self._create_fallback_analysis(image_path)
    
    def _create_fallback_analysis(self, image_path: str) -> Dict[str, Any]:
        """Create fallback analysis when VLM is unavailable"""
        return {
            "description": "Vision analysis unavailable - using fallback",
            "elements": [],
            "confidence": 0.1,
            "error": "VLM services unavailable",
            "screenshot_path": image_path
        }
