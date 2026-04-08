# SOKOL v8.0 - Multi-Agent System Documentation

## Overview

SOKOL v8.0 is a complete multi-agent AI system for Windows automation and assistance. It features specialized agents, vector memory, vision analysis, and context awareness.

## Architecture

### Core Components

1. **Multi-Agent System**: Coordinates specialized agents for different tasks
2. **Vector Memory**: ChromaDB-based memory for context and learning
3. **Vision System**: Hybrid VLM (Moondream2 + Groq) for screen analysis
4. **Context Awareness**: Alt+Space hotkey for instant screen understanding
5. **Optimization**: Performance monitoring and resource management

### Agents

- **Planning Agent**: Task decomposition and coordination
- **System Agent**: Windows automation and process control
- **Vision Agent**: Screen analysis and UI understanding
- **Code Agent**: Script generation and execution
- **Search Agent**: Web search and information retrieval

## Quick Start

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install Ollama
# Visit: https://ollama.com
ollama pull llama3.2:3b
ollama pull moondream2  # Optional for vision
```

### Basic Usage

```python
import asyncio
from sokol.launcher import initialize_sokol_multi_agent, process_sokol_request

async def main():
    # Initialize system
    await initialize_sokol_multi_agent()
    
    # Process requests
    result = await process_sokol_request("Launch Chrome and navigate to google.com")
    print(result)

asyncio.run(main())
```

### Alt+Space Context Awareness

Press `Alt+Space` anywhere to:
- Take screenshot
- Analyze current screen
- Get contextual suggestions
- Store screen context in memory

## Features

### 1. Multi-Agent Coordination

```python
# Complex task coordination
result = await process_sokol_request(
    "Look at the screen, identify the application, and help me close it"
)
```

### 2. Vector Memory System

```python
# Memory stores and retrieves context
from sokol.memory import VectorMemoryStore, MemoryItem

# Store application info
memory_item = MemoryItem.create_application(
    "Chrome", 
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "Web browser"
)
await memory_store.store_memory(memory_item)
```

### 3. Vision Analysis

```python
# Screen analysis
from sokol.vision_system import analyze_screen_image

result = await analyze_screen_image(
    "screenshot.png",
    "What buttons are visible and what do they do?"
)
```

### 4. Code Automation

```python
# Generate and execute scripts
result = await process_sokol_request(
    "Create a Python script to sort files in Downloads by date"
)
```

### 5. System Control

```python
# System operations
result = await process_sokol_request("Launch notepad and maximize window")
result = await process_sokol_request("List running processes")
result = await process_sokol_request("Organize files on Desktop")
```

## Configuration

### Environment Variables

```bash
# GPU Optimization
OLLAMA_NUM_GPU=99

# Groq API (optional)
GROQ_API_KEY=your_api_key

# Code Execution
SOKOL_ALLOW_CODE_EXEC=1

# Vision Settings
SOKOL_EASYOCR_GPU=1
```

### Agent Configuration

```python
# Enable/disable components
await initialize_sokol_multi_agent(
    enable_memory=True,
    enable_vision=True,
    enable_optimization=True,
    enable_hotkey=True
)
```

## API Reference

### Core Functions

- `initialize_sokol_multi_agent()`: Initialize the system
- `process_sokol_request(text, context)`: Process user requests
- `get_sokol_health()`: Get system health status

### Agent Methods

Each agent supports specific actions:

#### Planning Agent
- `plan`: Create execution plans
- `analyze`: Analyze request complexity
- `coordinate`: Coordinate multi-agent tasks

#### System Agent
- `launch_app`: Launch applications
- `manage_windows`: Window operations
- `process_control`: Process management
- `file_operations`: File system operations

#### Vision Agent
- `analyze_screen`: Screen analysis
- `ocr_text`: Text extraction
- `find_elements`: UI element detection
- `describe_screen`: Screen description

#### Code Agent
- `generate_script`: Script generation
- `execute_code`: Code execution
- `file_automation`: File automation
- `text_processing`: Text manipulation

#### Search Agent
- `web_search`: Web search
- `fetch_url`: URL content retrieval
- `lookup_info`: Information lookup
- `summarize`: Content summarization

## Memory Types

- `COMMAND`: Executed commands
- `APPLICATION`: Application paths and info
- `FOLDER`: Frequently used folders
- `SCREENSHOT`: Screen analysis results
- `PREFERENCE`: User preferences
- `CONTEXT`: Contextual information

## Performance Optimization

### GPU Acceleration

```python
# Enable GPU for maximum performance
os.environ["OLLAMA_NUM_GPU"] = "99"
```

### Memory Management

```python
# Automatic optimization
from sokol.optimization import run_optimization_cycle

results = await run_optimization_cycle()
```

### Caching

```python
# Response caching for speed
from sokol.optimization import get_optimization_manager

manager = get_optimization_manager()
cache_stats = manager.cache_manager.get_cache_stats()
```

## Safety and Security

### Policy Enforcement

All system operations go through `policy.py` for safety validation:

```python
from sokol.policy import check_system_action

# Check if operation is safe
if check_system_action("delete_files", {"path": "C:\\Windows"}):
    # Execute operation
    pass
```

### Restricted Operations

- Mass file deletion requires confirmation
- System setting changes need approval
- Network operations are monitored
- Code execution is controlled by environment variables

## Troubleshooting

### Common Issues

1. **Ollama Connection Failed**
   ```bash
   # Check Ollama status
   ollama list
   
   # Restart Ollama
   ollama serve
   ```

2. **Vision Model Not Available**
   ```bash
   # Pull vision model
   ollama pull moondream2
   ```

3. **Memory Issues**
   ```python
   # Run optimization
   await run_optimization_cycle()
   ```

4. **Hotkey Not Working**
   ```python
   # Install keyboard module
   pip install keyboard
   
   # Check status
   from sokol.hotkey_system import get_context_status
   status = get_context_status()
   ```

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Examples

### Example 1: Application Automation

```python
# Launch Chrome and navigate to website
result = await process_sokol_request(
    "Launch Chrome, maximize window, and navigate to github.com"
)
```

### Example 2: File Organization

```python
# Organize downloads folder
result = await process_sokol_request(
    "Organize files in Downloads folder by file type"
)
```

### Example 3: Screen Analysis

```python
# Analyze current screen
result = await process_sokol_request(
    "Look at the screen and tell me what application is open"
)
```

### Example 4: Code Generation

```python
# Generate automation script
result = await process_sokol_request(
    "Write a Python script to backup Documents folder to Downloads"
)
```

### Example 5: System Information

```python
# Get system status
result = await process_sokol_request(
    "Check system performance and running processes"
)
```

## Advanced Usage

### Custom Agents

```python
from sokol.agents.base import AgentBase, AgentCapability

class CustomAgent(AgentBase):
    def __init__(self):
        capabilities = [
            AgentCapability(
                name="custom_task",
                description="Custom task description",
                max_execution_time=30
            )
        ]
        super().__init__("custom_agent", capabilities)
    
    async def process(self, request):
        # Custom processing logic
        return self._create_response(
            status=AgentStatus.SUCCESS,
            content="Custom task completed"
        )
```

### Memory Integration

```python
# Store custom memories
from sokol.memory import MemoryItem, MemoryType

custom_memory = MemoryItem(
    id="custom_001",
    type=MemoryType.CONTEXT,
    content="Custom context information",
    metadata={"source": "user_input"}
)
await memory_store.store_memory(custom_memory)
```

### Performance Monitoring

```python
# Monitor system performance
from sokol.optimization import get_optimization_manager

manager = get_optimization_manager()
status = await manager.get_optimization_status()

print(f"CPU: {status['performance']['cpu_percent']:.1f}%")
print(f"Memory: {status['performance']['memory_percent']:.1f}%")
```

## Integration with Existing GUI

```python
from sokol.gui_multi_agent import integrate_multi_agent

# Integrate with existing SokolGUI
multi_agent_gui = integrate_multi_agent(existing_gui_instance)
await multi_agent_gui.initialize()
```

## Testing

```bash
# Run comprehensive tests
python test_multi_agent.py

# Test specific components
python -c "
import asyncio
from sokol.launcher import test_system
asyncio.run(test_system())
"
```

## Version History

- **v8.0**: Complete multi-agent system with vision, memory, and optimization
- **v7.2**: Streaming Ollama client with true cancel
- **v7.1**: Basic agent framework
- **v7.0**: Initial multi-agent architecture

## Support

For issues and support:
1. Check troubleshooting section
2. Run system health check: `await get_sokol_health()`
3. Enable debug logging
4. Review agent logs

## License

SOKOL v8.0 - Multi-Agent AI System for Windows
Copyright 2026 - All rights reserved
