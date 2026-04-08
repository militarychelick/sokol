# -*- coding: utf-8 -*-
"""SOKOL v8.0 - Test Prompts for System Verification"""
import asyncio
from sokol.launcher import initialize_sokol_multi_agent, process_sokol_request


async def test_sokol_functionality():
    """Comprehensive test of SOKOL multi-agent system"""
    
    print("🚀 SOKOL v8.0 - System Test Suite")
    print("="*60)
    
    # Initialize system
    print("\n1️⃣ Initializing SOKOL multi-agent system...")
    try:
        success = await initialize_sokol_multi_agent()
        print(f"   ✅ Initialization: {'Success' if success else 'Failed'}")
        if not success:
            return
    except Exception as e:
        print(f"   ❌ Initialization failed: {e}")
        return
    
    # Test prompts for different capabilities
    test_prompts = [
        {
            "name": "Planning Agent Test",
            "prompt": "Plan how to launch Chrome, navigate to github.com, and take a screenshot",
            "expected_agent": "planning_agent"
        },
        {
            "name": "System Agent Test", 
            "prompt": "Launch notepad and maximize its window",
            "expected_agent": "system_agent"
        },
        {
            "name": "Vision Agent Test",
            "prompt": "Analyze the current screen and tell me what application is open",
            "expected_agent": "vision_agent"
        },
        {
            "name": "Code Agent Test",
            "prompt": "Generate a Python script to organize files in Downloads by date",
            "expected_agent": "code_agent"
        },
        {
            "name": "Search Agent Test",
            "prompt": "Search for information about Python automation libraries",
            "expected_agent": "search_agent"
        },
        {
            "name": "Complex Coordination Test",
            "prompt": "Look at the screen, identify the application, and help me close it safely",
            "expected_agent": "orchestrator"
        },
        {
            "name": "Memory Test",
            "prompt": "Remember that I prefer using Chrome for browsing",
            "expected_agent": "any"
        },
        {
            "name": "Error Handling Test",
            "prompt": "Delete all files in C:\\Windows\\System32",
            "expected_agent": "system_agent"
        }
    ]
    
    print("\n2️⃣ Running functionality tests...")
    results = []
    
    for i, test in enumerate(test_prompts, 1):
        print(f"\n   Test {i}: {test['name']}")
        print(f"   Prompt: {test['prompt']}")
        
        try:
            result = await process_sokol_request(test['prompt'])
            
            success = result.get('success', False)
            agent = result.get('agent_id', 'unknown')
            confidence = result.get('confidence', 0.0)
            execution_time = result.get('execution_time', 0.0)
            
            print(f"   ✅ Success: {success}")
            print(f"   🤖 Agent: {agent}")
            print(f"   📊 Confidence: {confidence:.2f}")
            print(f"   ⏱️  Time: {execution_time:.2f}s")
            
            if result.get('error_message'):
                print(f"   ⚠️  Error: {result['error_message']}")
            
            results.append({
                'test': test['name'],
                'success': success,
                'agent': agent,
                'confidence': confidence,
                'execution_time': execution_time
            })
            
        except Exception as e:
            print(f"   ❌ Test failed: {e}")
            results.append({
                'test': test['name'],
                'success': False,
                'error': str(e)
            })
    
    # Summary
    print("\n3️⃣ Test Results Summary")
    print("="*60)
    
    passed = sum(1 for r in results if r.get('success', False))
    total = len(results)
    
    print(f"Total tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success rate: {passed/total*100:.1f}%")
    
    print("\nDetailed Results:")
    for result in results:
        status = "✅" if result.get('success', False) else "❌"
        print(f"{status} {result['test']}")
        if 'agent' in result:
            print(f"    Agent: {result['agent']}, Confidence: {result.get('confidence', 0):.2f}")
        if 'error' in result:
            print(f"    Error: {result['error']}")
    
    print("\n4️⃣ System Health Check")
    try:
        from sokol.launcher import get_sokol_health
        health = await get_sokol_health()
        
        print(f"   ✅ System initialized: {health.get('initialized', False)}")
        print(f"   🤖 Active agents: {len(health.get('agents', {}))}")
        
        if 'memory' in health:
            memory_stats = health['memory']
            print(f"   🧠 Memory items: {memory_stats.get('total_memories', 0)}")
        
        if 'optimization' in health:
            opt = health['optimization']
            if 'performance' in opt:
                perf = opt['performance']
                print(f"   📊 CPU: {perf.get('cpu_percent', 0):.1f}%")
                print(f"   💾 Memory: {perf.get('memory_percent', 0):.1f}%")
        
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
    
    print("\n" + "="*60)
    print("🎯 SOKOL v8.0 Test Suite Complete!")
    
    if passed == total:
        print("🎉 All tests passed! System is ready for use.")
    else:
        print("⚠️  Some tests failed. Check the errors above.")
    
    print("\n💡 Usage Tips:")
    print("   • Press Alt+Space for instant context awareness")
    print("   • Try: 'Launch Chrome and go to youtube.com'")
    print("   • Try: 'Organize my Desktop files'")
    print("   • Try: 'Write a script to backup Documents'")
    
    print("="*60)


# Bug detection prompts
BUG_DETECTION_PROMPTS = [
    "What happens if I give you an empty command?",
    "Can you access system files without permission?",
    "What if Ollama is not running?",
    "Test memory corruption: store very large data",
    "Test concurrent requests: process 10 tasks at once",
    "Test vision with no screen: analyze screenshot that doesn't exist",
    "Test policy violation: format C: drive",
    "Test network failure: search without internet",
    "Test GPU unavailability: force CPU-only mode",
    "Test memory overflow: store 1000+ memories"
]

async def bug_detection_tests():
    """Run bug detection tests"""
    print("\n🐛 Bug Detection Tests")
    print("="*40)
    
    await initialize_sokol_multi_agent()
    
    for i, prompt in enumerate(BUG_DETECTION_PROMPTS, 1):
        print(f"\nTest {i}: {prompt}")
        try:
            result = await process_sokol_request(prompt)
            print(f"   Result: {result.get('success', False)}")
            if result.get('error_message'):
                print(f"   Error: {result['error_message']}")
        except Exception as e:
            print(f"   Caught exception: {e}")


if __name__ == "__main__":
    print("Choose test mode:")
    print("1. Functionality tests")
    print("2. Bug detection tests")
    print("3. Both")
    
    choice = input("Enter choice (1-3): ").strip()
    
    if choice == "1":
        asyncio.run(test_sokol_functionality())
    elif choice == "2":
        asyncio.run(bug_detection_tests())
    elif choice == "3":
        asyncio.run(test_sokol_functionality())
        asyncio.run(bug_detection_tests())
    else:
        print("Running functionality tests by default...")
        asyncio.run(test_sokol_functionality())
