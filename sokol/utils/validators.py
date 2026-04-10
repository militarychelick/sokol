"""
Input validators
"""

import re
from pathlib import Path


def validate_path(path: str) -> bool:
    """Validate file path."""
    try:
        Path(path)
        return True
    except Exception:
        return False


def validate_url(url: str) -> bool:
    """Validate URL."""
    pattern = re.compile(
        r'https?://[^\s<>"{}|\\^`\[\]]+'
    )
    return bool(pattern.match(url))


def validate_app_name(app: str) -> bool:
    """Validate application name."""
    if not app or len(app) > 100:
        return False
    return True
