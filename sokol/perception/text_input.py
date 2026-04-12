"""Text input adapter - minimal normalization and cleanup."""

import re
from typing import Optional

from sokol.observability.logging import get_logger

logger = get_logger("sokol.perception.text_input")


class TextInputAdapter:
    """
    Minimal text input adapter for normalization and cleanup.

    Prepares text input for IntentRouter.
    """

    def __init__(self) -> None:
        logger.info("Text input adapter initialized")

    def normalize(self, text: str) -> str:
        """
        Normalize text input.

        - Remove extra whitespace
        - Trim leading/trailing spaces
        - Handle special characters

        Returns normalized text.
        """
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)
        # Trim
        text = text.strip()
        return text

    def cleanup(self, text: str) -> str:
        """
        Clean up text input.

        - Remove control characters
        - Normalize line breaks

        Returns cleaned text.
        """
        # Remove control characters except newline
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        # Normalize line breaks
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"\r", "\n", text)
        return text

    def process(self, text: str) -> str:
        """
        Process text input through normalization and cleanup.

        Returns processed text ready for IntentRouter.
        """
        text = self.cleanup(text)
        text = self.normalize(text)
        return text


def normalize_input(text: str) -> str:
    """
    Convenience function to normalize text input.

    Returns normalized text.
    """
    adapter = TextInputAdapter()
    return adapter.process(text)
