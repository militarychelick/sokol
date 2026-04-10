"""
Path helpers
"""

import os
from pathlib import Path


def get_data_dir() -> Path:
    """Get data directory."""
    # Use APPDATA on Windows
    app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
    data_dir = Path(app_data) / "sokol"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_config_dir() -> Path:
    """Get config directory."""
    # Use project config directory
    project_root = Path(__file__).parent.parent.parent
    config_dir = project_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir
