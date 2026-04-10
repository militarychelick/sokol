# Sokol - Windows AI Agent

Sokol is a production-ready Windows AI agent with voice-first interface, wake word detection, and UI automation.

## Features

- **Voice-First Interface**: Wake word "Sokol" with configurable alternatives
- **Text Fallback**: Full text-based interaction support
- **UI Automation**: Windows control via UI Automation (UIA) - primary method
- **Browser Automation**: DOM-based browser control (Playwright)
- **Safety First**: Dangerous actions require confirmation, emergency stop support
- **Memory System**: Session, profile, and long-term memory with privacy controls
- **Hybrid LLM**: Cloud (OpenAI, Anthropic) with local fallback (Ollama)

## Requirements

- Windows 10/11
- Python 3.11+
- API keys for cloud LLMs (optional)

## Installation

```bash
# Clone repository
git clone https://github.com/yourorg/sokol.git
cd sokol

# Create virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Install optional voice support
pip install -e ".[voice]"

# Install Playwright for browser automation
playwright install
```

## Configuration

Edit `config.toml` to customize:

```toml
[agent]
name = "Sokol"
wake_words = ["sokol", "cokol", "sockol"]
language = "ru"

[llm]
provider = "openai"  # openai, anthropic, ollama
fallback_provider = "ollama"

[llm.openai]
model = "gpt-4o"
api_key_env = "OPENAI_API_KEY"

[safety]
confirm_dangerous = true
dangerous_tools = ["file_delete", "file_write", "app_close", "system_shutdown"]

[ui]
theme = "dark"
start_minimized = false
```

Set API keys as environment variables:

```bash
set OPENAI_API_KEY=your-key-here
set ANTHROPIC_API_KEY=your-key-here
```

## Usage

### Start the Agent

```bash
python -m sokol.main
```

Or use the installed script:

```bash
sokol
```

### Basic Commands

- "Open notepad" - Launch applications
- "List windows" - Show open windows
- "Minimize chrome" - Window management
- "Read file C:/test.txt" - File operations
- "System info" - Get system information

### Emergency Stop

Press `Ctrl+Alt+Shift+Escape` or click the STOP button to immediately halt all activity.

### Voice Commands

1. Say wake word "Sokol"
2. Wait for listening indicator
3. Speak your command
4. Agent responds with brief voice output

## Architecture

```
sokol/
âââ core/           # Types, config, constants
âââ runtime/        # State machine, orchestrator, events, tasks
âââ safety/         # Risk assessment, confirmations, emergency stop
âââ tools/          # Tool registry and builtin tools
âââ memory/         # Session, profile, long-term memory
âââ integrations/   # LLM, voice, browser backends
âââ ui/             # PyQt6 GUI, tray, widgets
âââ observability/  # Logging, debug utilities
```

## Key Design Decisions

1. **UIA First**: Always try UI Automation before vision/OCR
2. **DOM First**: Always try DOM before mouse/keyboard for browser
3. **Safety**: Every tool declares risk level, dangerous requires confirm
4. **Emergency Stop**: Immediate cancellation of all tasks
5. **Memory Privacy**: Explicit opt-in for sensitive data

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=sokol

# Run specific test file
pytest tests/test_safety.py

# Run in debug mode
SOKOL_DEBUG=1 pytest -v
```

## Dry Run Mode

Test without real actions:

```bash
set SOKOL_DRY_RUN=1
python -m sokol.main
```

## Development

### Project Structure

- **core**: Shared types, configuration, constants
- **runtime**: Agent state machine, event loop, task management
- **safety**: Risk levels, confirmation flow, emergency stop
- **tools**: Tool registry with schema validation
- **memory**: SQLite-backed memory stores
- **integrations**: LLM providers with fallback
- **ui**: PyQt6 interface with tray support

### Adding a New Tool

1. Create file in `sokol/tools/builtin/`
2. Extend `Tool` base class
3. Implement `name`, `description`, `risk_level`, `get_schema()`, `execute()`
4. Tool auto-discovered by registry

```python
from sokol.tools.base import Tool, ToolResult
from sokol.core.types import RiskLevel

class MyTool(Tool[dict]):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "My custom tool"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.READ

    def get_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "param": {"type": "string"}
            },
            "required": ["param"]
        }

    def execute(self, param: str) -> ToolResult[dict]:
        # Tool logic here
        return ToolResult(success=True, data={"result": param})
```

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit pull request

## Status

**Core MVP Complete**: Runtime, safety, tools, memory, UI, LLM integration

**Future Phases**:
- Voice input with wake word detection
- Screen perception (UIA/Vision/OCR)
- Planning pipeline
- Windows automation via UIA
- Browser automation via Playwright
- MCP integration
