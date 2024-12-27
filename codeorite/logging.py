"""Logging configuration for Codeorite.

This module provides centralized logging configuration for the entire application.
It sets up logging handlers, formatters, and provides convenience functions for getting
loggers in other modules.

Usage:
    from codeorite.logging import get_logger
    logger = get_logger(__name__)
    logger.info("Processing started")
"""

import atexit
import logging
import os
import sys
import threading
import warnings
from pathlib import Path
from typing import Optional, Set

DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

VERBOSE_LEVEL = 15  # Between DEBUG and INFO
logging.addLevelName(VERBOSE_LEVEL, "VERBOSE")

_handlers: Set[logging.Handler] = set()
_handler_lock = threading.Lock()


def _cleanup_handlers():
    """Clean up logging handlers on exit.

    This function ensures all handlers are properly closed and removed,
    handling any errors that occur during cleanup without silently ignoring them.
    """
    with _handler_lock:
        for handler in _handlers.copy():
            try:
                handler.close()
            except (IOError, OSError) as e:
                # Log specific I/O errors that might occur during cleanup
                warnings.warn(
                    f"Error closing log handler {handler}: {e}", RuntimeWarning
                )
            except Exception as e:
                # Log unexpected errors without failing
                warnings.warn(
                    f"Unexpected error closing log handler {handler}: {e}",
                    RuntimeWarning,
                )
            finally:
                # Always remove the handler from our set, even if closing failed
                _handlers.discard(handler)


atexit.register(_cleanup_handlers)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_format: str = DEFAULT_LOG_FORMAT,
) -> None:
    """Configure the logging system.

    Args:
        log_level: Minimum logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for logging to file
        log_format: Format string for log messages
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    with _handler_lock:
        # Clean up existing handlers
        for handler in _handlers.copy():
            try:
                root_logger.removeHandler(handler)
                handler.close()
            except Exception as e:
                warnings.warn(
                    f"Error cleaning up handler {handler}: {e}", RuntimeWarning
                )
            finally:
                _handlers.discard(handler)

        formatter = logging.Formatter(log_format, DEFAULT_DATE_FORMAT)

        # Console handler (stdout for INFO and below)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(console_handler)
        _handlers.add(console_handler)

        # Error handler (stderr for WARNING and above)
        error_handler = logging.StreamHandler(sys.stderr)
        error_handler.setFormatter(formatter)
        error_handler.setLevel(logging.WARNING)
        root_logger.addHandler(error_handler)
        _handlers.add(error_handler)

        # File handler if specified
        if log_file:
            try:
                log_dir = os.path.dirname(log_file)
                if log_dir:
                    Path(log_dir).mkdir(parents=True, exist_ok=True)

                file_handler = logging.FileHandler(log_file, encoding="utf-8")
                file_handler.setFormatter(formatter)
                file_handler.setLevel(logging.DEBUG)
                root_logger.addHandler(file_handler)
                _handlers.add(file_handler)
            except (IOError, OSError) as e:
                warnings.warn(
                    f"Failed to set up log file {log_file}: {e}", RuntimeWarning
                )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the specified name.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
