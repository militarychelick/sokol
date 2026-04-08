# -*- coding: utf-8 -*-
"""SOKOL v8.0 - Complete Multi-Agent System Launcher"""
import asyncio
import logging
import sys
import os
from typing import Any, Dict, Optional

# Add sokol to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from sokol.multi_agent import MultiAgentSystem
from sokol.integration import get_integration
from sokol.memory import get_embedding_provider
from sokol.vision_system import get_hybrid_vision_system
from sokol.hotkey_system import get_context_awareness_manager
from sokol.optimization import get_optimization_manager
from sokol.config import VERSION

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SokolMultiAgentLauncher:
    """
    Complete launcher for Sokol v8.0 multi-agent system
    Integrates all components: agents, memory, vision, optimization
    """
    
    def __init__(self):
        self.logger = logging.getLogger("sokol.launcher")
        self.multi_agent_system: Optional[MultiAgentSystem] = None
        self.context_manager = None
        self.optimization_manager = None
        self.is_initialized = False
        
    async def initialize(self, 
                       enable_memory: bool = True,
                       enable_vision: bool = True,
                       enable_optimization: bool = True,
                       enable_hotkey: bool = True) -> bool:
        """Initialize complete multi-agent system"""
        try:
            self.logger.info("Initializing Sokol v8.0 Multi-Agent System...")
            
            # Step 1: Initialize core multi-agent system
            self.logger.info("Step 1: Initializing core multi-agent system...")
            integration = get_integration()
            await integration.initialize(enable_memory=enable_memory, enable_vision=enable_vision)
            self.multi_agent_system = integration.multi_agent_system
            
            # Step 2: Initialize optimization system
            if enable_optimization:
                self.logger.info("Step 2: Initializing optimization system...")
                self.optimization_manager = get_optimization_manager(self.multi_agent_system.memory_store)
                await self.optimization_manager.initialize()
            
            # Step 3: Initialize context awareness (Alt+Space)
            if enable_hotkey:
                self.logger.info("Step 3: Initializing context awareness...")
                self.context_manager = get_context_awareness_manager()
                await self.context_manager.initialize()
            
            # Step 4: Warmup models
            self.logger.info("Step 4: Warming up models...")
            await self._warmup_models()
            
            # Step 5: Store initial system info
            if self.multi_agent_system.memory_store:
                await self._store_system_info()
            
            self.is_initialized = True
            self.logger.info("â\x9c\x93 Sokol v8.0 Multi-Agent System initialized successfully!")
            
            # Display system status
            await self._display_system_status()
            
            return True
            
        except Exception as e:
            self.logger.error(f"â\x9c\x97 Initialization failed: {e}")
            return False
    
    async def _warmup_models(self):
        """Warmup models for optimal performance"""
        try:
            # Warmup planning agent model
            planning_agent = self.multi_agent_system.agents.get("planning_agent")
            if planning_agent and hasattr(planning_agent, 'llm_client'):
                await asyncio.get_event_loop().run_in_executor(
                    None, planning_agent.llm_client.warmup
                )
                self.logger.info("  â\x9c\x93 Planning agent model warmed up")
            
            # Warmup vision system
            vision_system = get_hybrid_vision_system()
            # Test vision system availability
            status = vision_system.get_status()
            self.logger.info(f"  â\x9c\x93 Vision system: Local={status.get('local_available')}, Cloud={status.get('cloud_available')}")
            
            # Warmup optimization models
            if self.optimization_manager:
                model_results = await self.optimization_manager.model_optimizer.warmup_models(["llama3.2:3b"])
                self.logger.info(f"  â\x9c\x93 Models warmed: {sum(model_results.values())}/{len(model_results)}")
            
        except Exception as e:
            self.logger.warning(f"Model warmup failed: {e}")
    
    async def _store_system_info(self):
        """Store initial system information in memory"""
        try:
            from sokol.memory import MemoryItem, MemoryType
            
            # Store system capabilities
            capabilities = {
                "planning": "planning_agent" in self.multi_agent_system.agents,
                "system_control": "system_agent" in self.multi_agent_system.agents,
                "vision": "vision_agent" in self.multi_agent_system.agents,
                "code_automation": "code_agent" in self.multi_agent_system.agents,
                "search": "search_agent" in self.multi_agent_system.agents,
                "vector_memory": self.multi_agent_system.memory_store is not None,
                "context_awareness": self.context_manager is not None,
                "optimization": self.optimization_manager is not None
            }
            
            capability_memory = MemoryItem(
                id="system_capabilities",
                type=MemoryType.CONTEXT,
                content=f"Sokol v{VERSION} capabilities: {capabilities}",
                metadata={"capabilities": capabilities, "version": VERSION}
            )
            
            await self.multi_agent_system.memory_store.store_memory(capability_memory)
            self.logger.info("  â\x9c\x93 System capabilities stored in memory")
            
        except Exception as e:
            self.logger.warning(f"System info storage failed: {e}")
    
    async def _display_system_status(self):
        """Display comprehensive system status"""
        try:
            print("\\n" + "="*80)
            print("SOKOL v8.0 - MULTI-AGENT SYSTEM STATUS")
            print("="*80)
            
            # Core system
            print(f"\\nâ\x9c\x93 Core System: {'Initialized' if self.is_initialized else 'Not Initialized'}")
            print(f"   Version: {VERSION}")
            print(f"   Agents: {len(self.multi_agent_system.agents)}")
            
            # Agent status
            print("\\nâ\x9c\x93 Active Agents:")
            for agent_id, agent in self.multi_agent_system.agents.items():
                status = agent.status.value if hasattr(agent, 'status') else 'unknown'
                print(f"   - {agent_id}: {status}")
            
            # Memory system
            if self.multi_agent_system.memory_store:
                memory_stats = await self.multi_agent_system.memory_store.get_memory_stats()
                print(f"\\nâ\x9c\x93 Vector Memory:")
                print(f"   - Total memories: {memory_stats.get('total_memories', 0)}")
                print(f"   - Embedding dimension: {memory_stats.get('embedding_dimension', 'unknown')}")
            
            # Vision system
            vision_system = get_hybrid_vision_system()
            vision_status = vision_system.get_status()
            print(f"\\nâ\x9c\x93 Vision System:")
            print(f"   - Local (Moondream2): {'Available' if vision_status.get('local_available') else 'Not Available'}")
            print(f"   - Cloud (Groq): {'Available' if vision_status.get('cloud_available') else 'Not Available'}")
            
            # Context awareness
            if self.context_manager:
                context_status = self.context_manager.get_status()
                print(f"\\nâ\x9c\x93 Context Awareness:")
                print(f"   - Alt+Space: {'Enabled' if context_status.get('enabled') else 'Disabled'}")
                print(f"   - Hotkey active: {context_status.get('hotkey_active', False)}")
            
            # Optimization
            if self.optimization_manager:
                opt_status = await self.optimization_manager.get_optimization_status()
                perf = opt_status.get('performance', {})
                print(f"\\nâ\x9c\x93 Optimization:")
                print(f"   - CPU usage: {perf.get('cpu_percent', 0):.1f}%")
                print(f"   - Memory usage: {perf.get('memory_percent', 0):.1f}%")
                print(f"   - GPU enabled: {opt_status.get('models', {}).get('gpu_enabled', False)}")
            
            print("\\n" + "="*80)
            print("SYSTEM READY FOR USE!")
            print("â\x9c\x93 Try: 'python -c \"import asyncio; from sokol.launcher import test_system; asyncio.run(test_system())\"'")
            print("â\x9c\x93 Press Alt+Space for instant context awareness")
            print("="*80)
            
        except Exception as e:
            self.logger.error(f"Status display failed: {e}")
    
    async def process_request(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process user request through complete system"""
        if not self.is_initialized:
            return {"error": "System not initialized"}
        
        try:
            # Process through multi-agent system
            result = await self.multi_agent_system.process_request(user_input, context)
            
            # Log interaction if memory available
            if self.multi_agent_system.memory_store:
                await self._log_interaction(user_input, result)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Request processing failed: {e}")
            return {"error": str(e)}
    
    async def _log_interaction(self, user_input: str, result: Dict[str, Any]):
        """Log user interaction in memory"""
        try:
            from sokol.memory import MemoryItem, MemoryType
            
            # Store user request
            request_memory = MemoryItem(
                id=f"request_{asyncio.get_event_loop().time()}",
                type=MemoryType.CONTEXT,
                content=user_input,
                metadata={"type": "user_request", "success": result.get("success", False)}
            )
            await self.multi_agent_system.memory_store.store_memory(request_memory)
            
        except Exception as e:
            self.logger.warning(f"Interaction logging failed: {e}")
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health report"""
        try:
            health = {
                "initialized": self.is_initialized,
                "version": VERSION,
                "timestamp": asyncio.get_event_loop().time()
            }
            
            # Agent health
            agent_health = {}
            for agent_id, agent in self.multi_agent_system.agents.items():
                agent_health[agent_id] = {
                    "status": agent.status.value if hasattr(agent, 'status') else 'unknown',
                    "busy": agent.is_busy if hasattr(agent, 'is_busy') else False
                }
            health["agents"] = agent_health
            
            # Memory health
            if self.multi_agent_system.memory_store:
                memory_stats = await self.multi_agent_system.memory_store.get_memory_stats()
                health["memory"] = memory_stats
            
            # Optimization health
            if self.optimization_manager:
                opt_status = await self.optimization_manager.get_optimization_status()
                health["optimization"] = opt_status
            
            return health
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {"error": str(e)}
    
    async def shutdown(self):
        """Shutdown complete system"""
        try:
            self.logger.info("Shutting down Sokol Multi-Agent System...")
            
            # Shutdown context awareness
            if self.context_manager:
                self.context_manager.shutdown()
            
            # Shutdown optimization
            if self.optimization_manager:
                self.optimization_manager.shutdown()
            
            # Shutdown multi-agent system
            if self.multi_agent_system:
                await self.multi_agent_system.shutdown()
            
            self.is_initialized = False
            self.logger.info("â\x9c\x93 Sokol Multi-Agent System shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Shutdown failed: {e}")


# Global launcher instance
_launcher: Optional[SokolMultiAgentLauncher] = None


def get_launcher() -> SokolMultiAgentLauncher:
    """Get global launcher instance"""
    global _launcher
    if _launcher is None:
        _launcher = SokolMultiAgentLauncher()
    return _launcher


async def initialize_sokol_multi_agent(**kwargs) -> bool:
    """Initialize complete Sokol multi-agent system"""
    launcher = get_launcher()
    return await launcher.initialize(**kwargs)


async def process_sokol_request(user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Process request through Sokol multi-agent system"""
    launcher = get_launcher()
    return await launcher.process_request(user_input, context)


async def get_sokol_health() -> Dict[str, Any]:
    """Get Sokol system health"""
    launcher = get_launcher()
    return await launcher.get_system_health()


async def test_system():
    """Test the complete multi-agent system"""
    print("\\nTesting Sokol v8.0 Multi-Agent System...")
    
    try:
        # Initialize system
        success = await initialize_sokol_multi_agent()
        if not success:
            print("â\x9c\x97 System initialization failed")
            return
        
        # Test basic requests
        test_requests = [
            "Plan how to launch Chrome and navigate to google.com",
            "Launch notepad",
            "Generate a Python script to sort files by date",
            "Search for information about Python automation"
        ]
        
        for i, request in enumerate(test_requests, 1):
            print(f"\\nTest {i}: {request}")
            result = await process_sokol_request(request)
            print(f"  Success: {result.get('success', False)}")
            print(f"  Agent: {result.get('agent_id', 'unknown')}")
            print(f"  Confidence: {result.get('confidence', 0):.2f}")
        
        # Test Alt+Space (manual)
        print(f"\\nTest 5: Context awareness (Alt+Space)")
        print("  Press Alt+Space to test context awareness...")
        
        # Get system health
        health = await get_sokol_health()
        print(f"\\nSystem Health: {len(health)} components checked")
        
        print("\\nâ\x9c\x93 All tests completed successfully!")
        
    except Exception as e:
        print(f"â\x9c\x97 Test failed: {e}")


if __name__ == "__main__":
    # Run system test
    asyncio.run(test_system())
