"""File operations tool - read, write files."""

import shutil
from pathlib import Path
from typing import Any

from sokol.core.types import RiskLevel
from sokol.observability.debug import dry_run_mode
from sokol.observability.logging import get_logger
from sokol.runtime.result import Result
from sokol.tools.base import Tool, ToolResult

logger = get_logger("sokol.tools.builtin.file_ops")


class FileOps(Tool[dict[str, Any]]):
    """File operations: read, write, list, delete."""

    @property
    def name(self) -> str:
        return "file_ops"

    @property
    def description(self) -> str:
        return "File operations: read, write, list, delete files"

    @property
    def risk_level(self) -> RiskLevel:
        return RiskLevel.WRITE  # Default, but can vary by action

    @property
    def undo_support(self) -> bool:
        # Write and move operations support undo
        # Delete operations cannot be reliably undone without proper trash integration
        return True

    @property
    def examples(self) -> list[str]:
        return [
            "read file C:/test.txt",
            "write to file C:/output.txt",
            "list files in C:/Documents",
        ]

    def get_schema(self) -> Result[dict]:
        return Result.ok({
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "write", "list", "delete", "copy", "move"],
                    "description": "File operation to perform",
                },
                "path": {
                    "type": "string",
                    "description": "File or directory path",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (for write action)",
                },
                "destination": {
                    "type": "string",
                    "description": "Destination path (for copy/move)",
                },
            },
            "required": ["action", "path"],
        })

    def execute(
        self,
        action: str,
        path: str,
        content: str | None = None,
        destination: str | None = None,
    ) -> Result[ToolResult[dict[str, Any]]]:
        """Execute file operation."""
        file_path = Path(path)

        # Determine risk level based on action
        risk = self._get_action_risk(action)

        # Validate path
        if action != "list" and not file_path.exists():
            if action in ("read", "delete", "move"):
                return Result.ok(
                    ToolResult(
                        success=False,
                        error=f"Path does not exist: {path}",
                        risk_level=risk,
                    )
                )

        # Dry run mode
        if dry_run_mode():
            logger.info(f"DRY RUN: Would {action} on {path}")
            return Result.ok(
                ToolResult(
                    success=True,
                    data={"action": action, "path": path, "dry_run": True},
                    risk_level=risk,
                )
            )

        try:
            if action in ("copy", "move") and not destination:
                return Result.ok(
                    ToolResult(
                        success=False,
                        error=f"Destination is required for action: {action}",
                        risk_level=risk,
                    )
                )

            if action == "read":
                return self._read_file(file_path)
            elif action == "write":
                return self._write_file(file_path, content or "")
            elif action == "list":
                return self._list_directory(file_path)
            elif action == "delete":
                return self._delete_file(file_path)
            elif action == "copy":
                return self._copy_file(file_path, Path(destination))
            elif action == "move":
                return self._move_file(file_path, Path(destination))
            else:
                return Result.ok(
                    ToolResult(
                        success=False,
                        error=f"Unknown action: {action}",
                        risk_level=risk,
                    )
                )

        except PermissionError:
            return Result.ok(
                ToolResult(
                    success=False,
                    error=f"Permission denied: {path}",
                    risk_level=risk,
                )
            )
        except Exception as e:
            logger.error_data("File operation failed", {"error": str(e)})
            return Result.ok(
                ToolResult(
                    success=False,
                    error=str(e),
                    risk_level=risk,
                )
            )

    def _get_action_risk(self, action: str) -> RiskLevel:
        """Get risk level for action."""
        if action in ("read", "list"):
            return RiskLevel.READ
        elif action in ("write", "copy", "move"):
            return RiskLevel.WRITE
        elif action == "delete":
            return RiskLevel.DANGEROUS
        return RiskLevel.WRITE

    def _read_file(self, path: Path) -> Result[ToolResult[dict[str, Any]]]:
        """Read file contents."""
        if not path.is_file():
            return Result.ok(
                ToolResult(
                    success=False,
                    error=f"Not a file: {path}",
                    risk_level=RiskLevel.READ,
                )
            )

        content = path.read_text(encoding="utf-8")
        return Result.ok(
            ToolResult(
                success=True,
                data={
                    "path": str(path),
                    "content": content,
                    "size": len(content),
                },
                risk_level=RiskLevel.READ,
            )
        )

    def _write_file(self, path: Path, content: str) -> Result[ToolResult[dict[str, Any]]]:
        """Write content to file."""
        # Store original for undo
        original_content = None
        if path.exists():
            original_content = path.read_text(encoding="utf-8")

        self._undo_info = {
            "path": str(path),
            "original_content": original_content,
            "existed": path.exists(),
        }

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(content, encoding="utf-8")

        return Result.ok(
            ToolResult(
                success=True,
                data={
                    "path": str(path),
                    "size": len(content),
                    "created": not self._undo_info["existed"],
                },
                undo_available=True,
                undo_info=self._undo_info,
                risk_level=RiskLevel.WRITE,
            )
        )

    def _list_directory(self, path: Path) -> Result[ToolResult[dict[str, Any]]]:
        """List directory contents."""
        if not path.exists():
            return Result.ok(
                ToolResult(
                    success=False,
                    error=f"Path does not exist: {path}",
                    risk_level=RiskLevel.READ,
                )
            )

        if not path.is_dir():
            return Result.ok(
                ToolResult(
                    success=False,
                    error=f"Not a directory: {path}",
                    risk_level=RiskLevel.READ,
                )
            )

        items = []
        for item in path.iterdir():
            items.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
            })

        return Result.ok(
            ToolResult(
                success=True,
                data={
                    "path": str(path),
                    "items": items,
                    "count": len(items),
                },
                risk_level=RiskLevel.READ,
            )
        )

    def _delete_file(self, path: Path) -> Result[ToolResult[dict[str, Any]]]:
        """Delete file or directory."""
        # Store context for auditing (delete is irreversible in current implementation)
        original_content = None
        if path.is_file():
            original_content = path.read_text(encoding="utf-8")

        self._undo_info = {
            "path": str(path),
            "was_file": path.is_file(),
            "was_dir": path.is_dir(),
            "original_content": original_content,
        }

        # Permanent delete (no trash integration in current implementation)
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)

        return Result.ok(
            ToolResult(
                success=True,
                data={"path": str(path), "deleted": True},
                undo_available=False,  # Can't truly undo delete
                risk_level=RiskLevel.DANGEROUS,
            )
        )

    def _copy_file(self, source: Path, dest: Path) -> Result[ToolResult[dict[str, Any]]]:
        """Copy file."""
        if not dest:
            return Result.ok(
                ToolResult(
                    success=False,
                    error="Destination required for copy",
                    risk_level=RiskLevel.WRITE,
                )
            )

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)

        return Result.ok(
            ToolResult(
                success=True,
                data={"source": str(source), "destination": str(dest)},
                risk_level=RiskLevel.WRITE,
            )
        )

    def _move_file(self, source: Path, dest: Path) -> Result[ToolResult[dict[str, Any]]]:
        """Move file."""
        if not dest:
            return Result.ok(
                ToolResult(
                    success=False,
                    error="Destination required for move",
                    risk_level=RiskLevel.WRITE,
                )
            )

        self._undo_info = {
            "original_path": str(source),
            "new_path": str(dest),
        }

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(dest))

        return Result.ok(
            ToolResult(
                success=True,
                data={"source": str(source), "destination": str(dest)},
                undo_available=True,
                undo_info=self._undo_info,
                risk_level=RiskLevel.WRITE,
            )
        )

    def undo(self, undo_info: dict[str, Any] | None = None) -> Result[ToolResult[bool]]:
        """Undo file operation."""
        undo_info = undo_info or self._undo_info
        if not undo_info:
            return Result.ok(ToolResult(success=False, error="No undo info"))

        try:
            # Undo write
            if "original_content" in undo_info:
                path = Path(undo_info["path"])
                if undo_info.get("existed"):
                    path.write_text(undo_info["original_content"], encoding="utf-8")
                else:
                    path.unlink()
                return Result.ok(ToolResult(success=True, data=True))

            # Undo move
            if "original_path" in undo_info:
                shutil.move(
                    str(undo_info["new_path"]),
                    str(undo_info["original_path"]),
                )
                return Result.ok(ToolResult(success=True, data=True))

            return Result.ok(ToolResult(success=False, error="Cannot undo this operation"))

        except Exception as e:
            return Result.ok(ToolResult(success=False, error=str(e)))
