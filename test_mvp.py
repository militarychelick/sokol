"""
Test Sokol v2 MVP
"""

import asyncio
from sokol.core.config import Config
from sokol.core.agent import SokolAgent


async def test_mvp():
    """Test MVP with text input."""
    config = Config.load()
    agent = SokolAgent(config)
    
    # Initialize
    await agent._initialize()
    
    # Test commands
    commands = [
        "открой youtube",
        "нажми ctrl+c",
        "сверни окно",
        "привет",
    ]
    
    for cmd in commands:
        print(f"\nTest: {cmd}")
        try:
            result = await agent.process_input(cmd)
            print(f"Result: {result}")
        except Exception as e:
            print(f"Error: {e}")
    
    # Shutdown
    agent.shutdown()


if __name__ == "__main__":
    asyncio.run(test_mvp())
