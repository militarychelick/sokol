"""Input unification layer - single entry point for all input sources."""

from typing import Literal
from dataclasses import dataclass

from sokol.observability.logging import get_logger
from sokol.perception import normalize_input

logger = get_logger("sokol.runtime.input")


@dataclass
class UnifiedInput:
    """Unified input data contract."""

    text: str
    source: Literal["ui", "voice", "screen"]
    metadata: dict | None = None


def submit_input(
    text: str,
    orchestrator,
    source: Literal["ui", "voice", "screen"] = "ui",
    metadata: dict | None = None,
) -> None:
    """
    Single entry point for all input sources.

    This function:
    1. Validates input (empty/whitespace guard)
    2. Normalizes text (using normalize_input)
    3. Logs input source
    4. Calls orchestrator.process_input()

    Args:
        text: Raw input text
        orchestrator: Orchestrator instance
        source: Input source ("ui", "voice", "screen")
        metadata: Optional metadata dictionary
    """
    # Validate input
    if not text or not text.strip():
        logger.debug(f"Empty input ignored from source: {source}")
        return

    # Normalize text
    text = normalize_input(text)

    # Log input source
    logger.info_data(
        "Input submitted",
        {"source": source, "text": text[:100], "metadata": metadata},
    )

    # Call orchestrator
    orchestrator.process_input(text, source=source)
