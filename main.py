#!/usr/bin/env python3
"""
Sokol v2 - LLM-powered Voice AI Agent for Windows
Entry point
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def main() -> int:
    """Main entry point."""
    from sokol.core.agent import SokolAgent
    from sokol.core.config import Config
    from sokol.input.text import TextIO
    
    # Load configuration
    config = Config.load()
    
    print("=" * 60)
    print("Sokol v2 - LLM-powered Voice AI Agent for Windows")
    print("=" * 60)
    print()
    print("Wake word: Сокол (not implemented yet, use text)")
    print()
    print("Type commands and press Enter to execute.")
    print("Examples:")
    print("  - открой chrome")
    print("  - открой youtube")
    print("  - нажми ctrl+c")
    print("  - сверни окно")
    print("  - привет (chat)")
    print()
    print("Press Ctrl+C to exit.")
    print("=" * 60)
    print()
    
    # Create agent
    agent = SokolAgent(config)
    
    # Start text input
    text_io = TextIO()
    asyncio.create_task(text_io.start_stdin_reader())
    
    try:
        # Run agent
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        print("\nShutting down...")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        asyncio.run(text_io.stop_stdin_reader())
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
