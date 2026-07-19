"""Logging utilities for ANPR runtime observability."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from core.config import LoggingConfig


class FlushRotatingFileHandler(RotatingFileHandler):
    """Rotating handler that flushes on every emitted record."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


class Iso8601Formatter(logging.Formatter):
    """Formatter with ISO-8601 timestamp including milliseconds."""

    default_time_format = "%Y-%m-%dT%H:%M:%S"
    default_msec_format = "%s.%03d"


def build_runtime_logger(config: LoggingConfig, name: str = "anpr") -> logging.Logger:
    """Create and return configured logger for application runtime.

    Args:
        config: Logging settings from app config.
        name: Logger name.

    Returns:
        Configured logger instance.
    """
    config.log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    file_handler = FlushRotatingFileHandler(
        filename=str(config.log_dir / config.file_name),
        maxBytes=config.max_bytes,
        backupCount=config.backup_count,
        encoding="utf-8",
    )
    formatter = Iso8601Formatter("[%(asctime)s] %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


def close_logger(logger: logging.Logger) -> None:
    """Release all handlers attached to a logger."""
    for handler in list(logger.handlers):
        handler.flush()
        handler.close()
        logger.removeHandler(handler)


def get_log_file_path(config: LoggingConfig) -> Path:
    """Return active log file path for the runtime logger."""
    return config.log_dir / config.file_name
