"""Transcript tool - audio/video transcription service."""

from typing import Any

from sokol.core.types import RiskLevel
from sokol.observability.logging import get_logger
from sokol.runtime.result import Result
from sokol.tools.base import Tool, ToolResult

logger = get_logger("sokol.tools.builtin.transcript")


class Transcript(Tool[dict[str, Any]]):
    """Transcribe audio/video to text."""

    @property
    def name(self) -> str:
        return "transcript_to_text"

    @property
    def description(self) -> str:
        return "Transcribe audio or video file to text"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.READ  # Read-only operation

    @property
    def examples(self) -> list[str]:
        return [
            "transcribe this audio file",
            "convert video to text",
            "transcript the recording",
        ]

    def get_schema(self) -> Result[dict]:
        return Result.ok({
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to audio or video file",
                },
                "language": {
                    "type": "string",
                    "description": "Language code (e.g., 'en', 'ru', 'auto')",
                },
            },
            "required": ["file_path"],
        })

    def execute(self, file_path: str = "", language: str = "auto") -> Result[ToolResult[dict[str, Any]]]:
        """Transcribe audio/video file to text."""
        try:
            # Explicitly fail while service is unconfigured (no fake success).
            logger.info_data(
                "Transcription unavailable",
                {"file_path": file_path[:50] if file_path else "none", "language": language},
            )

            return Result.ok(
                ToolResult(
                    success=False,
                    error="Transcription service is not configured in this build",
                    data={
                        "file_path": file_path,
                        "language": language,
                    },
                    risk_level=self.risk_level,
                )
            )

        except Exception as e:
            logger.error_data("Transcription failed", {"error": str(e)})
            return Result.ok(
                ToolResult(
                    success=False,
                    error=str(e),
                    risk_level=self.risk_level,
                )
            )
