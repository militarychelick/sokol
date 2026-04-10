"""
Test Sokol v2 - 5 core commands
"""

import asyncio
from sokol.core.config import Config
from sokol.core.agent import SokolAgent


async def test_commands():
    """Test 5 core commands."""
    config = Config.load()
    agent = SokolAgent(config)
    
    # Initialize agent
    await agent._initialize()
    
    # Test 1: launch_app
    print("Test 1: открой chrome")
    result = await agent.process_input("открой chrome")
    print(f"  Result: {result.success}, {result.message}")
    
    # Test 2: open_url
    print("\nTest 2: открой youtube")
    result = await agent.process_input("открой youtube")
    print(f"  Result: {result.success}, {result.message}")
    
    # Test 3: press_hotkey
    print("\nTest 3: нажми ctrl+c")
    result = await agent.process_input("нажми ctrl+c")
    print(f"  Result: {result.success}, {result.message}")
    
    # Test 4: search_file
    print("\nTest 4: найди документ")
    result = await agent.process_input("найди документ")
    print(f"  Result: {result.success}, {result.message}")
    
    # Test 5: manage_window
    print("\nTest 5: сверни окно")
    result = await agent.process_input("сверни окно")
    print(f"  Result: {result.success}, {result.message}")
    
    # Shutdown
    agent.shutdown()


if __name__ == "__main__":
    asyncio.run(test_commands())
