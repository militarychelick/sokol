# -*- coding: utf-8 -*-
"""SOKOL v8.0 - Vision Language Model Integration"""
import asyncio
import logging
import base64
from typing import Any, Dict, List, Optional, Union
from io import BytesIO
import json

from sokol.core import OllamaClient
from sokol.config import OLLAMA_API_BASE, SCREENSHOTS_DIR
from sokol.agents.base import AgentBase, AgentResponse, AgentStatus

logger = logging.getLogger(__name__)


class VisionLanguageModel:
    """Abstract base class for Vision Language Models"""
    
    async def analyze_image(self, image_path: str, prompt: str) -> Dict[str, Any]:
        """Analyze image with given prompt"""
        raise NotImplementedError


class Moondream2VLM(VisionLanguageModel):
    """Local Moondream2 Vision Language Model"""
    
    def __init__(self):
        self.client = OllamaClient(
            model="moondream2",
            system_message=self._get_system_prompt(),
            classify_prompt=""
        )
        self.logger = logging.getLogger("sokol.vision.moondream2")
        
    def _get_system_prompt(self) -> str:
        return """You are a vision AI assistant. Analyze images and provide clear, concise descriptions of what you see. Focus on UI elements, text, and actionable items."""
    
    async def analyze_image(self, image_path: str, prompt: str) -> Dict[str, Any]:
        """Analyze image using local Moondream2"""
        try:
            # Encode image for Ollama
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode()
            
            # Build vision prompt
            vision_prompt = f"{prompt}\n\nImage: {image_data}"
            
            # Get response
            response = self.client.chat(vision_prompt, one_shot=True)
            
            # Try to parse as JSON
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {
                    "description": response,
                    "elements": [],
                    "confidence": 0.7,
                    "model": "moondream2"
                }
                
        except Exception as e:
            self.logger.error(f"Moondream2 analysis failed: {e}")
            return {"error": str(e), "model": "moondream2"}


class GroqVisionVLM(VisionLanguageModel):
    """Groq Llama-3-Vision API"""
    
    def __init__(self):
        self.api_key = None
        self.logger = logging.getLogger("sokol.vision.groq")
        
        # Check for Groq API key
        import os
        self.api_key = os.environ.get("GROQ_API_KEY")
        if not self.api_key:
            self.logger.warning("Groq API key not found")
    
    async def analyze_image(self, image_path: str, prompt: str) -> Dict[str, Any]:
        """Analyze image using Groq Vision API"""
        if not self.api_key:
            return {"error": "Groq API key not available", "model": "groq_vision"}
        
        try:
            # This would implement Groq Vision API call
            # For now, return mock response
            return {
                "description": "Groq Vision analysis (not implemented)",
                "elements": [],
                "confidence": 0.8,
                "model": "groq_vision"
            }
            
        except Exception as e:
            self.logger.error(f"Groq Vision analysis failed: {e}")
            return {"error": str(e), "model": "groq_vision"}


class HybridVisionSystem:
    """
    Hybrid Vision System with local and fallback models
    Prioritizes local Moondream2, falls back to Groq Vision
    """
    
    def __init__(self):
        self.local_vlm = Moondream2VLM()
        self.cloud_vlm = GroqVisionVLM()
        self.logger = logging.getLogger("sokol.vision.hybrid")
        self._local_available = True
        
    async def analyze_image(self, image_path: str, prompt: str, prefer_local: bool = True) -> Dict[str, Any]:
        """Analyze image with hybrid approach"""
        if prefer_local and self._local_available:
            try:
                result = await self.local_vlm.analyze_image(image_path, prompt)
                if "error" not in result:
                    self.logger.debug("Used local Moondream2 for vision analysis")
                    return result
                else:
                    self.logger.warning(f"Local VLM failed: {result['error']}")
                    self._local_available = False
            except Exception as e:
                self.logger.error(f"Local VLM error: {e}")
                self._local_available = False
        
        # Fallback to cloud VLM
        try:
            result = await self.cloud_vlm.analyze_image(image_path, prompt)
            if "error" not in result:
                self.logger.debug("Used cloud VLM for vision analysis")
                return result
            else:
                self.logger.warning(f"Cloud VLM failed: {result['error']}")
        except Exception as e:
            self.logger.error(f"Cloud VLM error: {e}")
        
        # Final fallback
        return {
            "description": "Vision analysis unavailable",
            "elements": [],
            "confidence": 0.1,
            "error": "All vision models failed",
            "model": "fallback"
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get vision system status"""
        return {
            "local_available": self._local_available,
            "cloud_available": self.cloud_vlm.api_key is not None,
            "local_model": "moondream2",
            "cloud_model": "groq_vision"
        }


class AltSpaceActivation:
    """
    Alt+Space activation system for instant context awareness
    Captures screen and analyzes current context
    """
    
    def __init__(self, vision_system: HybridVisionSystem):
        self.vision_system = vision_system
        self.logger = logging.getLogger("sokol.alt_space")
        
    async def activate(self) -> Dict[str, Any]:
        """Activate Alt+Space context awareness"""
        try:
            # Take screenshot
            screenshot_path = await self._capture_screenshot()
            if not screenshot_path:
                return {"error": "Failed to capture screenshot"}
            
            # Analyze screen
            analysis_prompt = (
                "Analyze this screen and tell me: "
                "1. What application is open? "
                "2. What is the current state/view? "
                "3. What actions can the user take? "
                "4. Are there any important UI elements?"
            )
            
            analysis = await self.vision_system.analyze_image(screenshot_path, analysis_prompt)
            
            # Generate contextual suggestions
            suggestions = await self._generate_suggestions(analysis)
            
            return {
                "screenshot_path": screenshot_path,
                "analysis": analysis,
                "suggestions": suggestions,
                "timestamp": asyncio.get_event_loop().time()
            }
            
        except Exception as e:
            self.logger.error(f"Alt+Space activation failed: {e}")
            return {"error": str(e)}
    
    async def _capture_screenshot(self) -> Optional[str]:
        """Capture screenshot"""
        try:
            from ..automation import take_screenshot
            import os
            
            # Ensure directory exists
            os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
            
            # Take screenshot
            screenshot_path = await asyncio.get_event_loop().run_in_executor(
                None, take_screenshot
            )
            
            if screenshot_path and os.path.exists(screenshot_path):
                return screenshot_path
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Screenshot capture failed: {e}")
            return None
    
    async def _generate_suggestions(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate contextual suggestions based on screen analysis"""
        try:
            description = analysis.get("description", "").lower()
            elements = analysis.get("elements", [])
            
            suggestions = []
            
            # Application-specific suggestions
            if "browser" in description or "chrome" in description or "firefox" in description:
                suggestions.extend([
                    "Navigate to specific website",
                    "Search for information",
                    "Bookmark current page",
                    "Take screenshot of page"
                ])
            
            elif "code" in description or "editor" in description or "ide" in description:
                suggestions.extend([
                    "Run current code",
                    "Debug program",
                    "Search in code",
                    "Format code"
                ])
            
            elif "game" in description or "launcher" in description:
                suggestions.extend([
                    "Start game",
                    "Check settings",
                    "View achievements",
                    "Browse store"
                ])
            
            elif "file" in description or "explorer" in description:
                suggestions.extend([
                    "Open file",
                    "Create new folder",
                    "Search files",
                    "Organize files"
                ])
            
            # Element-based suggestions
            for element in elements:
                element_type = element.get("type", "").lower()
                if "button" in element_type:
                    suggestions.append(f"Click {element.get('text', 'button')}")
                elif "input" in element_type or "field" in element_type:
                    suggestions.append("Type in input field")
                elif "menu" in element_type:
                    suggestions.append("Open menu")
            
            # Generic suggestions
            if not suggestions:
                suggestions = [
                    "Take screenshot",
                    "Analyze screen elements",
                    "Get help with current application"
                ]
            
            return suggestions[:5]  # Limit to 5 suggestions
            
        except Exception as e:
            self.logger.error(f"Suggestion generation failed: {e}")
            return ["Take screenshot", "Analyze screen"]


# Global instances
_hybrid_vision_system: Optional[HybridVisionSystem] = None
_alt_space_activation: Optional[AltSpaceActivation] = None


def get_hybrid_vision_system() -> HybridVisionSystem:
    """Get global hybrid vision system"""
    global _hybrid_vision_system
    if _hybrid_vision_system is None:
        _hybrid_vision_system = HybridVisionSystem()
    return _hybrid_vision_system


def get_alt_space_activation() -> AltSpaceActivation:
    """Get global Alt+Space activation"""
    global _alt_space_activation
    if _alt_space_activation is None:
        vision_system = get_hybrid_vision_system()
        _alt_space_activation = AltSpaceActivation(vision_system)
    return _alt_space_activation


async def activate_context_awareness() -> Dict[str, Any]:
    """Convenience function for Alt+Space activation"""
    activation = get_alt_space_activation()
    return await activation.activate()


async def analyze_screen_image(image_path: str, prompt: str) -> Dict[str, Any]:
    """Convenience function for image analysis"""
    vision_system = get_hybrid_vision_system()
    return await vision_system.analyze_image(image_path, prompt)
