# Sokol v2

Voice AI Agent for Windows.

## Features

- **Voice-First Interface**: Speak to control your computer
- **Hybrid Intelligence**: Local LLM (Ollama) + Cloud (OpenAI)
- **Windows Automation**: Launch apps, control windows, manage files
- **Safety-First**: Dangerous actions require confirmation
- **Memory**: Learns your habits and preferences
- **Modern GUI**: PyQt6 control panel with system tray

## Requirements

- Windows 10/11
- Python 3.10+
- [Ollama](https://ollama.ai) (for local LLM)

## Installation

```bash
# Clone
git clone https://github.com/user/sokol.git
cd sokol

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Ollama model
ollama pull llama3

# Run
python main.py
```

## Configuration

Edit `config/default.yaml` to customize:
- Voice settings (TTS voice, STT model)
- LLM settings (local model, API keys)
- Safety preferences
- Memory options

## Usage

1. **Push-to-Talk**: Hold F12 and speak
2. **Text Input**: Type in the GUI panel
3. **Quick Actions**: Use system tray menu

### Example Commands

- "Open Chrome"
- "Play music on YouTube"
- "Search for documents"
- "Set up my workspace"
- "What time is it?"

## Architecture

See [Architecture Plan](.windsurf/plans/sokol-v2-architecture-f4dbc5.md) for details.

## License

MIT
