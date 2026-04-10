"""
LLM reasoning logic - Intent understanding and chain planning
"""

from __future__ import annotations

from typing import Any

from .llm import LLMClient
from .prompt import REASONING_PROMPT, SYSTEM_PROMPT
from ..core.config import Config


class LLMReasoning:
    """LLM-based reasoning for intent understanding and planning."""
    
    def __init__(self, config: Config, llm_client: LLMClient) -> None:
        self.config = config
        self.llm_client = llm_client
    
    async def understand_command(self, command: str) -> dict[str, Any]:
        """Understand user command and return structured intent."""
        prompt = REASONING_PROMPT.format(command=command)
        
        try:
            result = await self.llm_client.generate_json(
                prompt,
                system_prompt=SYSTEM_PROMPT,
                use_local=True,
            )
            return result
        except Exception as e:
            # Fallback to simple parsing
            return self._fallback_parse(command)
    
    def _fallback_parse(self, command: str) -> dict[str, Any]:
        """Fallback simple parsing if LLM fails."""
        command_lower = command.lower()
        
        if "открой" in command_lower or "open" in command_lower:
            if "youtube" in command_lower or "github" in command_lower:
                return {
                    "action": "open_url",
                    "params": {"url": self._extract_url(command)},
                    "safety_level": "safe",
                    "reasoning": "Detected URL open command",
                    "chain": [],
                }
            else:
                return {
                    "action": "launch_app",
                    "params": {"app": self._extract_app(command)},
                    "safety_level": "safe",
                    "reasoning": "Detected app launch command",
                    "chain": [],
                }
        elif "нажми" in command_lower or "press" in command_lower:
            return {
                "action": "press_hotkey",
                "params": {"keys": self._extract_hotkey(command)},
                "safety_level": "safe",
                "reasoning": "Detected hotkey command",
                "chain": [],
            }
        elif "найди" in command_lower or "find" in command_lower:
            return {
                "action": "search_file",
                "params": {"query": self._extract_query(command)},
                "safety_level": "safe",
                "reasoning": "Detected file search command",
                "chain": [],
            }
        else:
            return {
                "action": "chat",
                "params": {"message": command},
                "safety_level": "safe",
                "reasoning": "Chat interaction",
                "chain": [],
            }
    
    def _extract_url(self, command: str) -> str:
        """Extract URL from command."""
        sites = {
            "youtube": "https://youtube.com",
            "github": "https://github.com",
            "google": "https://google.com",
        }
        for name, url in sites.items():
            if name in command.lower():
                return url
        return "https://google.com"
    
    def _extract_app(self, command: str) -> str:
        """Extract app name from command."""
        words = command.lower().replace("открой", "").replace("open", "").strip()
        return words.split()[0] if words else "chrome"
    
    def _extract_hotkey(self, command: str) -> list[str]:
        """Extract hotkey from command."""
        keys = command.lower().replace("нажми", "").replace("press", "").strip()
        return keys.replace("+", " ").split()
    
    def _extract_query(self, command: str) -> str:
        """Extract search query from command."""
        query = command.lower().replace("найди", "").replace("find", "").strip()
        return query
