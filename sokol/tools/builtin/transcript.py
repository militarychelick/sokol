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
            "required": [],
        })

    def execute(self, file_path: str = "", language: str = "auto") -> Result[ToolResult[dict[str, Any]]]:
        """Transcribe audio/video file to text."""
        try:
            # Placeholder implementation - actual transcription requires API key
            # For now, return a message indicating transcription service is not configured
            logger.info_data(
                "Transcription placeholder",
                {"file_path": file_path[:50] if file_path else "none", "language": language},
            )

            # Dummy transcription: return a placeholder message
            transcript_text = f"[Transcription not configured] File: {file_path or 'not specified'}"

            return Result.ok(
                ToolResult(
                    success=True,
                    data={
                        "file_path": file_path,
                        "language": language,
                        "transcript_text": transcript_text,
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
