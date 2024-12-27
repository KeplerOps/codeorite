"""Tests for the logging module.

This module tests the logging configuration, handler management,
and error handling in the logging system.
"""

import io
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codeorite.logging import (
    DEFAULT_LOG_FORMAT,
    VERBOSE_LEVEL,
    _cleanup_handlers,
    _handlers,
    get_logger,
    setup_logging,
)


class TestLogging(unittest.TestCase):
    """Test suite for logging functionality."""

    def setUp(self):
        """Set up test environment."""
        # Clear any existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler)
        _handlers.clear()

        # Reset root logger level
        root_logger.setLevel(logging.WARNING)

    def tearDown(self):
        """Clean up after tests."""
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler)
        _handlers.clear()

    def test_get_logger(self):
        """Test logger creation and naming."""
        logger = get_logger("test_logger")
        self.assertEqual(logger.name, "test_logger")
        self.assertIsInstance(logger, logging.Logger)

    def test_setup_logging_default(self):
        """Test default logging setup."""
        setup_logging()
        root_logger = logging.getLogger()

        # Should have two handlers by default (stdout and stderr)
        self.assertEqual(len(root_logger.handlers), 2)
        self.assertEqual(len(_handlers), 2)

        # Verify handler types and levels
        stdout_handlers = [h for h in root_logger.handlers if h.stream == sys.stdout]
        stderr_handlers = [h for h in root_logger.handlers if h.stream == sys.stderr]
        self.assertEqual(len(stdout_handlers), 1)
        self.assertEqual(len(stderr_handlers), 1)
        self.assertEqual(stdout_handlers[0].level, logging.WARNING)
        self.assertEqual(stderr_handlers[0].level, logging.WARNING)

    def test_setup_logging_file(self):
        """Test logging to file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = os.path.join(temp_dir, "test.log")
            setup_logging(log_file=log_file)

            # Should have three handlers (stdout, stderr, and file)
            root_logger = logging.getLogger()
            self.assertEqual(len(root_logger.handlers), 3)
            self.assertEqual(len(_handlers), 3)

            # Verify file handler
            file_handlers = [
                h for h in root_logger.handlers if isinstance(h, logging.FileHandler)
            ]
            self.assertEqual(len(file_handlers), 1)
            self.assertEqual(file_handlers[0].baseFilename, log_file)

            # Test writing to log file
            logger = get_logger("test")
            test_message = "Test log message"
            logger.info(test_message)

            with open(log_file, "r") as f:
                log_content = f.read()
                self.assertIn(test_message, log_content)

    def test_setup_logging_invalid_file(self):
        """Test handling of invalid log file paths."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Try to create log file in non-existent directory with no write permissions
            no_access_dir = os.path.join(temp_dir, "noaccess")
            os.mkdir(no_access_dir)
            os.chmod(no_access_dir, 0o444)  # Read-only

            invalid_path = os.path.join(no_access_dir, "test.log")

            # Should warn but not fail
            with self.assertWarns(RuntimeWarning):
                setup_logging(log_file=invalid_path)

            # Should still have basic handlers
            root_logger = logging.getLogger()
            self.assertEqual(len(root_logger.handlers), 2)

            # Cleanup
            os.chmod(no_access_dir, 0o777)

    def test_verbose_level(self):
        """Test custom VERBOSE log level."""
        setup_logging(log_level="VERBOSE")
        logger = get_logger("test")

        # Capture stdout using a custom handler
        output = []
        handler = logging.StreamHandler(io.StringIO())
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(message)s"))
        handler.emit = lambda record: output.append(record.getMessage())

        logger.addHandler(handler)
        logger.log(VERBOSE_LEVEL, "Verbose message")

        self.assertIn("Verbose message", output)

    def test_multiple_setup_calls(self):
        """Test multiple calls to setup_logging."""
        setup_logging()
        initial_handlers = set(logging.getLogger().handlers)

        # Second setup should clean up old handlers
        setup_logging()
        new_handlers = set(logging.getLogger().handlers)

        # Should have same number of handlers but different instances
        self.assertEqual(len(initial_handlers), len(new_handlers))
        self.assertTrue(initial_handlers.isdisjoint(new_handlers))

    def test_cleanup_handlers(self):
        """Test handler cleanup."""
        setup_logging()

        # Get initial state
        root_logger = logging.getLogger()
        initial_handlers = set(root_logger.handlers)

        # Clean up handlers
        _cleanup_handlers()

        # Verify handlers are removed from both sets
        self.assertEqual(len(_handlers), 0)
        current_handlers = set(root_logger.handlers) & initial_handlers
        self.assertEqual(len(current_handlers), 0)

    def test_log_levels(self):
        """Test different log levels."""
        setup_logging()
        logger = get_logger("test")

        # Use custom handler to capture all messages
        output = []
        handler = logging.StreamHandler(io.StringIO())
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        handler.emit = lambda record: output.append(
            f"{record.levelname}: {record.getMessage()}"
        )

        logger.addHandler(handler)

        # Send test messages
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        # Verify messages
        self.assertIn("DEBUG: Debug message", output)
        self.assertIn("INFO: Info message", output)
        self.assertIn("WARNING: Warning message", output)
        self.assertIn("ERROR: Error message", output)

    def test_log_formatting(self):
        """Test log message formatting."""
        custom_format = "%(levelname)s - %(message)s"
        setup_logging(log_format=custom_format)
        logger = get_logger("test")

        # Use custom handler to capture formatted output
        output = []
        handler = logging.StreamHandler(io.StringIO())
        handler.setFormatter(logging.Formatter(custom_format))
        handler.emit = lambda record: output.append(handler.format(record))

        logger.addHandler(handler)
        logger.info("Test message")

        self.assertIn("INFO - Test message", output)

    def test_nested_log_directory_creation(self):
        """Test creation of nested log directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            nested_path = os.path.join(temp_dir, "logs", "nested", "test.log")
            setup_logging(log_file=nested_path)

            # Directory should be created
            self.assertTrue(os.path.exists(os.path.dirname(nested_path)))

            # Should have file handler
            root_logger = logging.getLogger()
            file_handlers = [
                h for h in root_logger.handlers if isinstance(h, logging.FileHandler)
            ]
            self.assertEqual(len(file_handlers), 1)

    def test_handler_cleanup_on_error(self):
        """Test handler cleanup when errors occur."""
        setup_logging()

        # Create a handler that raises an error on close
        bad_handler = logging.StreamHandler()

        def raise_error():
            raise IOError("Test error")

        bad_handler.close = raise_error

        _handlers.add(bad_handler)

        # Should warn but not fail
        with self.assertWarns(RuntimeWarning):
            _cleanup_handlers()

        # Handler should still be removed
        self.assertNotIn(bad_handler, _handlers)
