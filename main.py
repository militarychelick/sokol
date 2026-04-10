#!/usr/bin/env python3
"""
Sokol v2 - Voice AI Agent for Windows
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
    
    # Load configuration
    config = Config.load()
    
    print("=" * 60)
    print("Sokol v2 - Voice AI Agent for Windows")
    print("=" * 60)
    print()
    print("Type commands and press Enter to execute.")
    print("Examples:")
    print("  - открой chrome")
    print("  - открой youtube")
    print("  - найди документ")
    print("  - нажми ctrl+c")
    print()
    print("Press Ctrl+C to exit.")
    print("=" * 60)
    print()
    
    # Create and run agent
    agent = SokolAgent(config)
    
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        print("\nShutting down...")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
