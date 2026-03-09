"""Unit tests for logging utilities."""

import logging
import tempfile
from pathlib import Path

import pytest

from src.utils.logging import get_logger, setup_logging


class TestSetupLogging:
    """Test logging setup functions."""

    def test_setup_logging_basic(self):
        """Test basic logger setup."""
        logger = setup_logging("test_logger")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_logger"

    def test_setup_logging_level(self):
        """Test logger setup with custom level."""
        logger = setup_logging("test_logger", level=logging.DEBUG)
        assert logger.level == logging.DEBUG

    def test_setup_logging_with_file(self):
        """Test logger setup with file handler."""
        with tempfile.TemporaryDirectory() as tmpdir:
            logger_name = f"test_file_logger_{id(tmpdir)}"
            logger = setup_logging(
                logger_name,
                log_file="test.log",
                log_dir=tmpdir,
            )
            assert isinstance(logger, logging.Logger)

            # Verify log directory was created
            log_dir = Path(tmpdir)
            assert log_dir.exists()

            # Test logging to file
            logger.info("Test message")
            log_file = log_dir / "test.log"
            assert log_file.exists()
            
            # Clean up handlers to allow temp directory deletion
            for handler in list(logger.handlers):
                handler.close()
                logger.removeHandler(handler)
            
            # Remove logger from registry
            if logger_name in logging.Logger.manager.loggerDict:
                del logging.Logger.manager.loggerDict[logger_name]

    def test_setup_logging_creates_log_directory(self):
        """Test that log directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_dir = Path(tmpdir) / "new_logs"
            assert not log_dir.exists()

            logger_name = f"test_dir_logger_{id(tmpdir)}"
            logger = setup_logging(
                logger_name,
                log_file="test.log",
                log_dir=str(log_dir),
            )

            assert log_dir.exists()
            
            # Clean up handlers to allow temp directory deletion
            for handler in list(logger.handlers):
                handler.close()
                logger.removeHandler(handler)
            
            # Remove logger from registry
            if logger_name in logging.Logger.manager.loggerDict:
                del logging.Logger.manager.loggerDict[logger_name]

    def test_setup_logging_console_handler(self):
        """Test that console handler is added."""
        logger = setup_logging("test_console_logger")
        handlers = logger.handlers
        assert len(handlers) >= 1
        assert isinstance(handlers[0], logging.StreamHandler)

    def test_get_logger(self):
        """Test getting existing logger."""
        # First setup a logger
        setup_logging("test_get_logger")
        # Then get it
        logger = get_logger("test_get_logger")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_get_logger"

    def test_get_logger_nonexistent(self):
        """Test getting a logger that doesn't exist yet."""
        logger = get_logger("nonexistent_logger")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "nonexistent_logger"

    def test_multiple_loggers(self):
        """Test setting up multiple loggers."""
        logger1 = setup_logging("logger1")
        logger2 = setup_logging("logger2")

        assert logger1.name == "logger1"
        assert logger2.name == "logger2"
        assert logger1 is not logger2