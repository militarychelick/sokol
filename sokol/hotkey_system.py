# -*- coding: utf-8 -*-
"""SOKOL v8.0 - Alt+Space Hotkey System"""
import asyncio
import logging
import threading
import time
from typing import Any, Dict, Optional, Callable

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False
    keyboard = None

from sokol.automation import ScreenCapture

logger = logging.getLogger(__name__)


class AltSpaceHotkey:
    """
    Alt+Space hotkey system for instant context awareness
    Provides global hotkey binding and activation
    """
    
    def __init__(self):
        self.logger = logging.getLogger("sokol.hotkey")
        self.is_active = False
        self.activation_callback: Optional[Callable] = None
        self._hotkey_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
    def set_activation_callback(self, callback: Callable):
        """Set callback for Alt+Space activation"""
        self.activation_callback = callback
        
    def start(self) -> bool:
        """Start Alt+Space hotkey monitoring"""
        if not KEYBOARD_AVAILABLE:
            self.logger.warning("keyboard module not available - Alt+Space disabled")
            return False
            
        if self.is_active:
            return True
            
        try:
            self._stop_event.clear()
            
            # Start hotkey monitoring in separate thread
            self._hotkey_thread = threading.Thread(target=self._monitor_hotkey, daemon=True)
            self._hotkey_thread.start()
            
            self.is_active = True
            self.logger.info("Alt+Space hotkey monitoring started")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start hotkey monitoring: {e}")
            return False
    
    def stop(self):
        """Stop Alt+Space hotkey monitoring"""
        if not self.is_active:
            return
            
        self._stop_event.set()
        self.is_active = False
        
        if self._hotkey_thread:
            self._hotkey_thread.join(timeout=1.0)
            
        self.logger.info("Alt+Space hotkey monitoring stopped")
    
    def _monitor_hotkey(self):
        """Monitor Alt+Space hotkey in separate thread"""
        try:
            # Register hotkey
            keyboard.add_hotkey('alt+space', self._on_alt_space_pressed)
            
            # Keep thread alive
            while not self._stop_event.is_set():
                time.sleep(0.1)
                
            # Unregister hotkey
            keyboard.remove_hotkey('alt+space')
            
        except Exception as e:
            self.logger.error(f"Hotkey monitoring error: {e}")
    
    def _on_alt_space_pressed(self):
        """Handle Alt+Space keypress"""
        try:
            self.logger.debug("Alt+Space pressed")
            
            # Prevent multiple rapid activations
            if hasattr(self, '_last_activation_time'):
                if time.time() - self._last_activation_time < 1.0:
                    return
            
            self._last_activation_time = time.time()
            
            # Call activation callback or run default
            if self.activation_callback:
                # Run callback in thread to avoid blocking
                threading.Thread(target=self.activation_callback, daemon=True).start()
            else:
                # Default activation
                threading.Thread(target=self._default_activation, daemon=True).start()
                
        except Exception as e:
            self.logger.error(f"Alt+Space handler error: {e}")
    
    def _default_activation(self):
        """Default Alt+Space activation"""
        try:
            # Run async activation in new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(activate_context_awareness())
                self._handle_activation_result(result)
            finally:
                loop.close()
                
        except Exception as e:
            self.logger.error(f"Default activation failed: {e}")
    
    def _handle_activation_result(self, result: Dict[str, Any]):
        """Handle Alt+Space activation result"""
        try:
            if "error" in result:
                self.logger.error(f"Alt+Space activation failed: {result['error']}")
                return
            
            # Log successful activation
            analysis = result.get("analysis", {})
            suggestions = result.get("suggestions", [])
            
            self.logger.info(f"Alt+Space activated - Analysis: {analysis.get('description', 'N/A')[:50]}...")
            self.logger.info(f"Alt+Space suggestions: {len(suggestions)} available")
            
            # Could integrate with GUI here to show popup
            self._show_activation_notification(result)
            
        except Exception as e:
            self.logger.error(f"Result handling failed: {e}")
    
    def _show_activation_notification(self, result: Dict[str, Any]):
        """Show notification for Alt+Space activation (optional)"""
        try:
            # This could show a system notification or GUI popup
            # For now, just log the result
            analysis = result.get("analysis", {})
            suggestions = result.get("suggestions", [])
            
            print("\\n" + "="*60)
            print("SOKOL - Context Awareness (Alt+Space)")
            print("="*60)
            print(f"Screen: {analysis.get('description', 'Unknown')}")
            
            if suggestions:
                print("\\nSuggested actions:")
                for i, suggestion in enumerate(suggestions, 1):
                    print(f"  {i}. {suggestion}")
            
            print("="*60)
            
        except Exception as e:
            self.logger.error(f"Notification failed: {e}")


class ContextAwarenessManager:
    """
    Manages context awareness features including Alt+Space
    Integrates with multi-agent system for intelligent assistance
    """
    
    def __init__(self):
        self.logger = logging.getLogger("sokol.context_awareness")
        self.hotkey = AltSpaceHotkey()
        self.alt_space_activation = get_alt_space_activation()
        self.integration = get_integration()
        self.is_enabled = False
        
    async def initialize(self) -> bool:
        """Initialize context awareness system"""
        try:
            # Ensure integration is initialized
            await self.integration.initialize()
            
            # Set up hotkey callback
            self.hotkey.set_activation_callback(self._on_alt_space)
            
            # Start hotkey monitoring
            hotkey_started = self.hotkey.start()
            
            self.is_enabled = hotkey_started
            self.logger.info(f"Context awareness initialized: {'enabled' if self.is_enabled else 'disabled'}")
            
            return self.is_enabled
            
        except Exception as e:
            self.logger.error(f"Context awareness initialization failed: {e}")
            return False
    
    async def activate_context_awareness(self) -> Dict[str, Any]:
        """Manual context awareness activation"""
        try:
            result = await self.alt_space_activation.activate()
            
            # Process result through multi-agent system
            if "error" not in result:
                await self._process_context_result(result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Context awareness activation failed: {e}")
            return {"error": str(e)}
    
    def _on_alt_space(self):
        """Alt+Space hotkey callback"""
        try:
            # Take screenshot
            success, msg, screenshot_path = asyncio.get_event_loop().run_in_executor(
                None, ScreenCapture.take
            )
            # Run async activation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(self.activate_context_awareness())
                self._handle_activation_result(result)
            finally:
                loop.close()
                
        except Exception as e:
            self.logger.error(f"Alt+Space callback failed: {e}")
    
    async def _process_context_result(self, result: Dict[str, Any]):
        """Process context awareness result through multi-agent system"""
        try:
            analysis = result.get("analysis", {})
            suggestions = result.get("suggestions", [])
            
            # Create contextual prompt for agents
            description = analysis.get("description", "")
            
            if description:
                # Ask agents what to do with this context
                agent_prompt = f"Based on this screen analysis: '{description}', what should I help the user with?"
                
                agent_result = await self.integration.process_user_message(agent_prompt, {
                    "context": "alt_space_activation",
                    "screen_analysis": analysis,
                    "suggestions": suggestions
                })
                
                # Store in memory for future reference
                if hasattr(self.integration, 'multi_agent_system') and self.integration.multi_agent_system.memory_store:
                    from ..memory import MemoryItem, MemoryType
                    memory_item = MemoryItem.create_screenshot(description, analysis.get("confidence", 0.0))
                    await self.integration.multi_agent_system.memory_store.store_memory(memory_item)
                
        except Exception as e:
            self.logger.error(f"Context result processing failed: {e}")
    
    def _handle_activation_result(self, result: Dict[str, Any]):
        """Handle Alt+Space activation result"""
        try:
            if "error" in result:
                self.logger.error(f"Context awareness failed: {result['error']}")
                return
            
            # Show notification
            self.hotkey._show_activation_notification(result)
            
        except Exception as e:
            self.logger.error(f"Activation result handling failed: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get context awareness status"""
        return {
            "enabled": self.is_enabled,
            "hotkey_active": self.hotkey.is_active,
            "keyboard_available": KEYBOARD_AVAILABLE,
            "vision_status": self.alt_space_activation.vision_system.get_status()
        }
    
    def shutdown(self):
        """Shutdown context awareness system"""
        try:
            self.hotkey.stop()
            self.is_enabled = False
            self.logger.info("Context awareness system shutdown")
        except Exception as e:
            self.logger.error(f"Context awareness shutdown failed: {e}")


# Global instance
_context_manager: Optional[ContextAwarenessManager] = None


def get_context_awareness_manager() -> ContextAwarenessManager:
    """Get global context awareness manager"""
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextAwarenessManager()
    return _context_manager


async def initialize_context_awareness() -> bool:
    """Initialize context awareness system"""
    manager = get_context_awareness_manager()
    return await manager.initialize()


async def manual_context_activation() -> Dict[str, Any]:
    """Manual context awareness activation"""
    manager = get_context_awareness_manager()
    return await manager.activate_context_awareness()


def get_context_status() -> Dict[str, Any]:
    """Get context awareness status"""
    manager = get_context_awareness_manager()
    return manager.get_status()
