"""Structured logging infrastructure."""

import json
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from sokol.core.constants import LOG_DIR
from sokol.observability.debug import is_debug_mode


class StructuredFormatter(logging.Formatter):
    """JSON structured log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data["data"] = record.extra_data

        # Add exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class TextFormatter(logging.Formatter):
    """Human-readable text formatter."""

    FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    DEBUG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(module)s:%(funcName)s:%(lineno)d | %(message)s"

    def format(self, record: logging.LogRecord) -> str:
        fmt = self.DEBUG_FORMAT if is_debug_mode() else self.FORMAT
        formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


class SokolLogger(logging.Logger):
    """Custom logger with structured logging support."""

    def log_with_data(
        self,
        level: int,
        msg: str,
        data: dict[str, Any] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Log with structured data."""
        if data:
            kwargs.setdefault("extra", {})["extra_data"] = data
        self.log(level, msg, *args, **kwargs)

    def info_data(self, msg: str, data: dict[str, Any] | None = None) -> None:
        self.log_with_data(logging.INFO, msg, data)

    def error_data(self, msg: str, data: dict[str, Any] | None = None) -> None:
        self.log_with_data(logging.ERROR, msg, data)

    def debug_data(self, msg: str, data: dict[str, Any] | None = None) -> None:
        self.log_with_data(logging.DEBUG, msg, data)

    def warning_data(self, msg: str, data: dict[str, Any] | None = None) -> None:
        self.log_with_data(logging.WARNING, msg, data)


# Set custom logger class
logging.setLoggerClass(SokolLogger)

# Logger registry for tracking
_loggers: dict[str, SokolLogger] = {}


def setup_logging(
    level: str = "INFO",
    log_file: str | None = None,
    max_size: int = 10485760,
    backup_count: int = 5,
    use_json: bool = False,
) -> None:
    """Setup logging configuration."""
    # Ensure log directory exists
    LOG_DIR.mkdir(exist_ok=True)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if is_debug_mode() else logging.INFO)
    console_handler.setFormatter(TextFormatter())
    root_logger.addHandler(console_handler)

    # File handler
    if log_file:
        log_path = Path(log_file)
        if not log_path.is_absolute():
            log_path = LOG_DIR / log_path
        log_path.parent.mkdir(exist_ok=True)

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max_size,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            StructuredFormatter() if use_json else TextFormatter()
        )
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> SokolLogger:
    """Get or create a logger by name."""
    if name not in _loggers:
        _loggers[name] = logging.getLogger(name)  # type: ignore[assignment]
    return _loggers[name]
