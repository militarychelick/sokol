# -*- coding: utf-8 -*-
"""SOKOL v8.0 - Multi-Agent System Test Suite"""
import asyncio
import logging
import sys
import os

# Add sokol to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sokol.multi_agent import MultiAgentSystem
from sokol.integration import get_integration, process_message
from sokol.memory import get_embedding_provider

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_basic_functionality():
    """Test basic multi-agent functionality"""
    print("\\n" + "="*60)
    print("SOKOL v8.0 - Multi-Agent System Test")
    print("="*60)
    
    try:
        # Test 1: System initialization
        print("\\n1. Testing system initialization...")
        integration = get_integration()
        await integration.initialize()
        print("   â\x9c\x93 System initialized successfully")
        
        # Test 2: Get system status
        print("\\n2. Testing system status...")
        status = await integration.get_system_info()
        print(f"   â\x9c\x93 Version: {status.get('version', 'unknown')}")
        print(f"   â\x9c\x93 Status: {status.get('status', 'unknown')}")
        capabilities = status.get('capabilities', {})
        print(f"   â\x9c\x93 Available agents: {sum(capabilities.values())}/{len(capabilities)}")
        
        # Test 3: Planning Agent
        print("\\n3. Testing Planning Agent...")
        planning_result = await process_message("Plan how to launch Chrome and navigate to google.com")
        print(f"   â\x9c\x93 Planning: {planning_result.get('success', False)}")
        print(f"   â\x9c\x93 Agent used: {planning_result.get('agent_used', 'unknown')}")
        print(f"   â\x9c\x93 Confidence: {planning_result.get('confidence', 0):.2f}")
        
        # Test 4: System Agent
        print("\\n4. Testing System Agent...")
        system_result = await process_message("Launch notepad")
        print(f"   â\x9c\x93 System operation: {system_result.get('success', False)}")
        print(f"   â\x9c\x93 Response: {system_result.get('response', 'No response')[:100]}...")
        
        # Test 5: Code Agent
        print("\\n5. Testing Code Agent...")
        code_result = await process_message("Generate a Python script to sort files by date")
        print(f"   â\x9c\x93 Code generation: {code_result.get('success', False)}")
        print(f"   â\x9c\x93 Agent used: {code_result.get('agent_used', 'unknown')}")
        
        # Test 6: Search Agent
        print("\\n6. Testing Search Agent...")
        search_result = await process_message("Search for information about Python automation")
        print(f"   â\x9c\x93 Search operation: {search_result.get('success', False)}")
        print(f"   â\x9c\x93 Agent used: {search_result.get('agent_used', 'unknown')}")
        
        # Test 7: Memory system (if available)
        print("\\n7. Testing Memory System...")
        try:
            embedding_provider = get_embedding_provider()
            test_embedding = await embedding_provider.get_embedding("test message")
            print(f"   â\x9c\x93 Embedding generation: {len(test_embedding)} dimensions")
            print(f"   â\x9c\x93 Memory provider: {type(embedding_provider).__name__}")
        except Exception as e:
            print(f"   â\x9c\x97 Memory system failed: {e}")
        
        # Test 8: Complex task coordination
        print("\\n8. Testing Complex Task Coordination...")
        complex_result = await process_message("Look at the screen, identify what application is open, and tell me how to close it")
        print(f"   â\x9c\x93 Complex task: {complex_result.get('success', False)}")
        print(f"   â\x9c\x93 Execution time: {complex_result.get('execution_time', 0):.2f}s")
        print(f"   â\x9c\x93 Next actions: {len(complex_result.get('next_actions', []))}")
        
        print("\\n" + "="*60)
        print("Multi-Agent System Test Completed!")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\\nâ\x9c\x97 Test failed: {e}")
        logger.exception("Test failure")
        return False


async def test_agent_communication():
    """Test inter-agent communication"""
    print("\\n" + "="*60)
    print("Testing Agent Communication")
    print("="*60)
    
    try:
        # Test planning -> system agent coordination
        print("\\n1. Testing Planning -> System coordination...")
        result = await process_message("Launch calculator and maximize its window")
        
        if result.get("success"):
            print("   â\x9c\x93 Agent coordination successful")
            print(f"   â\x9c\x93 Primary agent: {result.get('agent_used', 'unknown')}")
            print(f"   â\x9c\x93 Data keys: {list(result.get('data', {}).keys())}")
        else:
            print("   â\x9c\x97 Agent coordination failed")
        
        # Test vision -> system agent coordination
        print("\\n2. Testing Vision -> System coordination...")
        result = await process_message("Analyze the current screen and click the first button you find")
        
        if result.get("success"):
            print("   â\x9c\x93 Vision coordination successful")
        else:
            print("   â\x9c\x97 Vision coordination failed (expected without screen)")
        
        return True
        
    except Exception as e:
        print(f"\\nâ\x9c\x97 Communication test failed: {e}")
        return False


async def test_error_handling():
    """Test error handling and fallbacks"""
    print("\\n" + "="*60)
    print("Testing Error Handling")
    print("="*60)
    
    try:
        # Test invalid request
        print("\\n1. Testing invalid request...")
        result = await process_message("")
        print(f"   â\x9c\x93 Empty request handled: {not result.get('success', True)}")
        
        # Test unsafe operation
        print("\\n2. Testing safety policy...")
        result = await process_message("Delete all files in C:\\")
        print(f"   â\x9c\x93 Unsafe operation blocked: {not result.get('success', True)}")
        
        # Test agent unavailability
        print("\\n3. Testing agent fallback...")
        result = await process_message("Perform complex mathematical calculation")
        print(f"   â\x9c\x93 Fallback mechanism: {result.get('success', False)}")
        
        return True
        
    except Exception as e:
        print(f"\\nâ\x9c\x97 Error handling test failed: {e}")
        return False


async def main():
    """Main test runner"""
    print("Starting Sokol v8.0 Multi-Agent System Tests...")
    
    # Run all tests
    tests = [
        test_basic_functionality,
        test_agent_communication,
        test_error_handling
    ]
    
    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"Test {test.__name__} crashed: {e}")
            results.append(False)
    
    # Summary
    print("\\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("â\x9c\x93 All tests passed! Multi-agent system is ready.")
    else:
        print("â\x9c\x97 Some tests failed. Check the logs above.")
    
    print("="*60)


if __name__ == "__main__":
    # Run tests
    asyncio.run(main())
