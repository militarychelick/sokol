# -*- coding: utf-8 -*-
"""SOKOL v8.0 - GUI Integration with Multi-Agent System"""
import asyncio
import logging
from typing import Any, Dict, Optional, Callable
import tkinter as tk
from tkinter import messagebox

from .integration import get_integration, process_message, get_sokol_status, activate_context_awareness
from .config import VERSION

logger = logging.getLogger(__name__)


class SokolMultiAgentGUI:
    """
    GUI integration layer for multi-agent system
    Handles Alt+Space activation and displays agent responses
    """
    
    def __init__(self, parent_gui):
        self.parent_gui = parent_gui  # Reference to main SokolGUI
        self.integration = get_integration()
        self.logger = logging.getLogger("sokol.gui_multi_agent")
        
        # GUI elements for multi-agent features
        self.agent_status_label = None
        self.agent_info_text = None
        
        # Alt+Space binding
        self.alt_space_bound = False
        
    async def initialize(self):
        """Initialize multi-agent GUI integration"""
        try:
            await self.integration.initialize()
            await self._setup_gui_elements()
            await self._bind_hotkeys()
            self.logger.info("Multi-agent GUI integration initialized")
        except Exception as e:
            self.logger.error(f"GUI integration failed: {e}")
            messagebox.showerror("Multi-Agent Error", f"Failed to initialize: {e}")
    
    async def _setup_gui_elements(self):
        """Setup GUI elements for multi-agent features"""
        try:
            # Add agent status to GUI
            if hasattr(self.parent_gui, 'status_frame'):
                # Create agent status label
                self.agent_status_label = tk.Label(
                    self.parent_gui.status_frame,
                    text="Agents: Ready",
                    fg="green"
                )
                self.agent_status_label.pack(side=tk.LEFT, padx=5)
            
            # Add agent info panel (optional)
            if hasattr(self.parent_gui, 'notebook'):
                # Create new tab for agent info
                agent_frame = tk.Frame(self.parent_gui.notebook)
                self.parent_gui.notebook.add(agent_frame, text="AI Agents")
                
                # Agent info text
                self.agent_info_text = tk.Text(agent_frame, wrap=tk.WORD, height=15)
                scrollbar = tk.Scrollbar(agent_frame, orient=tk.VERTICAL, command=self.agent_info_text.yview)
                self.agent_info_text.configure(yscrollcommand=scrollbar.set)
                
                self.agent_info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                
                # Update agent info
                await self._update_agent_info()
                
        except Exception as e:
            self.logger.error(f"GUI setup failed: {e}")
    
    async def _bind_hotkeys(self):
        """Bind Alt+Space for context awareness"""
        try:
            if hasattr(self.parent_gui, 'root'):
                self.parent_gui.root.bind('<Alt-space>', self._on_alt_space)
                self.alt_space_bound = True
                self.logger.info("Alt+Space hotkey bound for context awareness")
        except Exception as e:
            self.logger.error(f"Hotkey binding failed: {e}")
    
    def _on_alt_space(self, event):
        """Handle Alt+Space keypress"""
        try:
            # Run async function in thread
            asyncio.create_task(self._handle_alt_space_activation())
        except Exception as e:
            self.logger.error(f"Alt+Space handler failed: {e}")
    
    async def _handle_alt_space_activation(self):
        """Handle Alt+Space activation"""
        try:
            # Update status
            if self.agent_status_label:
                self.agent_status_label.config(text="Agents: Analyzing...", fg="orange")
            
            # Activate context awareness
            result = await activate_context_awareness()
            
            # Display result
            await self._display_agent_response(result)
            
            # Update status
            if self.agent_status_label:
                status = "Success" if result.get("success", False) else "Failed"
                color = "green" if result.get("success", False) else "red"
                self.agent_status_label.config(text=f"Agents: {status}", fg=color)
                
        except Exception as e:
            self.logger.error(f"Alt+Space activation failed: {e}")
            if self.agent_status_label:
                self.agent_status_label.config(text="Agents: Error", fg="red")
    
    async def process_user_input(self, user_input: str) -> Dict[str, Any]:
        """
        Process user input through multi-agent system
        Compatible with existing GUI message handling
        """
        try:
            # Update status
            if self.agent_status_label:
                self.agent_status_label.config(text="Agents: Processing...", fg="orange")
            
            # Process message
            result = await process_message(user_input)
            
            # Display result
            await self._display_agent_response(result)
            
            # Update status
            if self.agent_status_label:
                status = "Ready" if result.get("success", False) else "Error"
                color = "green" if result.get("success", False) else "red"
                self.agent_status_label.config(text=f"Agents: {status}", fg=color)
            
            return result
            
        except Exception as e:
            self.logger.error(f"User input processing failed: {e}")
            if self.agent_status_label:
                self.agent_status_label.config(text="Agents: Error", fg="red")
            return {"success": False, "content": str(e)}
    
    async def _display_agent_response(self, result: Dict[str, Any]):
        """Display agent response in GUI"""
        try:
            # Add to main chat if available
            if hasattr(self.parent_gui, 'add_message'):
                agent_name = result.get("agent_used", "AI Assistant")
                content = result.get("response", result.get("content", ""))
                confidence = result.get("confidence", 0.0)
                
                # Format message with agent info
                formatted_content = f"[{agent_name}] ({confidence:.0%})\\n{content}"
                
                # Add next actions if available
                next_actions = result.get("next_actions", [])
                if next_actions:
                    formatted_content += f"\\n\\nSuggested actions:\\n" + "\\n".join(f"- {action}" for action in next_actions)
                
                self.parent_gui.add_message(formatted_content, "assistant")
            
            # Update agent info panel
            if self.agent_info_text:
                await self._update_agent_info()
                
        except Exception as e:
            self.logger.error(f"Response display failed: {e}")
    
    async def _update_agent_info(self):
        """Update agent information panel"""
        try:
            if not self.agent_info_text:
                return
            
            # Get system status
            status = await get_sokol_status()
            
            # Format agent info
            info_text = f"SOKOL v{VERSION} - Multi-Agent System\\n\\n"
            info_text += f"Status: {status.get('status', 'unknown')}\\n\\n"
            
            # Agent capabilities
            capabilities = status.get('capabilities', {})
            info_text += "Available Agents:\\n"
            for agent, available in capabilities.items():
                status_icon = "â\x9c\x93" if available else "â\x9c\x97"
                info_text += f"  {status_icon} {agent.replace('_', ' ').title()}\\n"
            
            # Multi-agent details
            multi_agent = status.get('multi_agent', {})
            if multi_agent:
                info_text += "\\nAgent Details:\\n"
                agents = multi_agent.get('agents', {})
                for agent_id, agent_info in agents.items():
                    agent_status = agent_info.get('status', 'unknown')
                    info_text += f"  {agent_id}: {agent_status}\\n"
            
            # Memory info
            memory = multi_agent.get('memory', {})
            if memory:
                info_text += f"\\nVector Memory:\\n"
                info_text += f"  Total memories: {memory.get('total_memories', 0)}\\n"
                info_text += f"  Embedding dimension: {memory.get('embedding_dimension', 'unknown')}\\n"
            
            # Update text widget
            self.agent_info_text.delete(1.0, tk.END)
            self.agent_info_text.insert(1.0, info_text)
            
        except Exception as e:
            self.logger.error(f"Agent info update failed: {e}")
    
    def get_agent_capabilities(self) -> Dict[str, bool]:
        """Get current agent capabilities for GUI"""
        try:
            # This would return capabilities for GUI display
            return {
                "planning": True,
                "system_control": True,
                "vision": True,
                "code_automation": True,
                "search": True,
                "vector_memory": True,
                "context_awareness": self.alt_space_bound
            }
        except Exception as e:
            self.logger.error(f"Capabilities check failed: {e}")
            return {}
    
    async def shutdown(self):
        """Shutdown multi-agent GUI integration"""
        try:
            await self.integration.shutdown()
            self.logger.info("Multi-agent GUI integration shutdown")
        except Exception as e:
            self.logger.error(f"GUI shutdown failed: {e}")


# Integration function for existing GUI
def integrate_multi_agent(gui_instance):
    """
    Integrate multi-agent system with existing Sokol GUI
    
    Args:
        gui_instance: Existing SokolGUI instance
        
    Returns:
        SokolMultiAgentGUI instance
    """
    multi_agent_gui = SokolMultiAgentGUI(gui_instance)
    return multi_agent_gui
