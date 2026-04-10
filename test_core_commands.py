"""
Test 5 core commands for Sokol v2
"""

import asyncio
from sokol.core.agent import SokolAgent, Intent, ActionResult
from sokol.core.config import Config


async def test_dispatcher():
    """Test dispatcher with 5 core commands."""
    from sokol.executor.dispatcher import ActionDispatcher
    
    dispatcher = ActionDispatcher()
    
    # Test 1: launch_app
    print("Test 1: launch_app (chrome)")
    intent = Intent(
        action_type="launch_app",
        target="chrome",
        params={"app": "chrome"},
        safety_level=0,  # SAFE
        complexity=1,
        raw_text="открой chrome",
    )
    result = dispatcher.dispatch(intent)
    print(f"  Result: {result.success}, {result.message}")
    
    # Test 2: open_url
    print("\nTest 2: open_url (youtube)")
    intent = Intent(
        action_type="open_url",
        target="youtube.com",
        params={"url": "youtube.com"},
        safety_level=0,
        complexity=1,
        raw_text="открой youtube",
    )
    result = dispatcher.dispatch(intent)
    print(f"  Result: {result.success}, {result.message}")
    
    # Test 3: press_hotkey
    print("\nTest 3: press_hotkey (ctrl+c)")
    intent = Intent(
        action_type="press_hotkey",
        target="ctrl+c",
        params={"keys": ["ctrl", "c"]},
        safety_level=0,
        complexity=1,
        raw_text="нажми ctrl+c",
    )
    result = dispatcher.dispatch(intent)
    print(f"  Result: {result.success}, {result.message}")
    
    # Test 4: search_file
    print("\nTest 4: search_file (document)")
    intent = Intent(
        action_type="search_file",
        target=None,
        params={"query": "document"},
        safety_level=0,
        complexity=1,
        raw_text="найди документ",
    )
    result = dispatcher.dispatch(intent)
    print(f"  Result: {result.success}, {result.message}")
    
    # Test 5: manage_window (minimize - safer)
    print("\nTest 5: manage_window (minimize)")
    intent = Intent(
        action_type="manage_window",
        target="minimize",
        params={"window_action": "minimize"},
        safety_level=0,
        complexity=1,
        raw_text="сверни окно",
    )
    result = dispatcher.dispatch(intent)
    print(f"  Result: {result.success}, {result.message}")
    
    # Test 6: unknown action_type (fail-safe)
    print("\nTest 6: unknown action_type (fail-safe)")
    intent = Intent(
        action_type="unknown_action",
        target=None,
        params={},
        safety_level=0,
        complexity=1,
        raw_text="unknown command",
    )
    result = dispatcher.dispatch(intent)
    print(f"  Result: {result.success}, {result.message}")
    
    # Test 7: missing target (validation)
    print("\nTest 7: missing target (validation)")
    intent = Intent(
        action_type="launch_app",
        target=None,
        params={},
        safety_level=0,
        complexity=1,
        raw_text="открой",
    )
    result = dispatcher.dispatch(intent)
    print(f"  Result: {result.success}, {result.message}")


async def test_intent_parser():
    """Test intent parser with 5 core commands."""
    from sokol.intent.parser import IntentParser
    
    config = Config()
    parser = IntentParser(config)
    
    # Test Russian commands
    tests = [
        "открой chrome",
        "открой youtube",
        "нажми ctrl+c",
        "найди документ",
        "закрой окно",
    ]
    
    for text in tests:
        print(f"\nParsing: {text}")
        try:
            intent = await parser.parse(text)
            print(f"  action_type: {intent.action_type}")
            print(f"  target: {intent.target}")
            print(f"  params: {intent.params}")
            print(f"  complexity: {intent.complexity}")
        except Exception as e:
            print(f"  Error: {e}")


async def main():
    """Run tests."""
    print("=" * 60)
    print("Testing Sokol v2 - 5 Core Commands")
    print("=" * 60)
    
    print("\n--- Testing Dispatcher ---")
    await test_dispatcher()
    
    print("\n" + "=" * 60)
    print("--- Testing Intent Parser ---")
    print("=" * 60)
    await test_intent_parser()
    
    print("\n" + "=" * 60)
    print("All tests completed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
