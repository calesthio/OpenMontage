"""Unified logging system for OpenMontage.

Provides a consistent logging interface across the entire project with:
- Multiple log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Console and optional file logging
- Structured log format
- Verbose mode support
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional, Union


# Global logger instance
_logger: Optional[logging.Logger] = None


def setup_logger(
    name: str = "openmontage",
    level: Union[int, str] = logging.INFO,
    log_file: Optional[Path] = None,
    verbose: bool = False,
) -> logging.Logger:
    """Setup and return a configured logger.
    
    Args:
        name: Logger name
        level: Logging level
        log_file: Optional log file path
        verbose: If True, set DEBUG level
    
    Returns:
        Configured logger instance
    """
    global _logger
    
    # Return existing logger if already configured
    if _logger is not None and _logger.name == name:
        return _logger
    
    # Create logger
    logger = logging.getLogger(name)
    
    # Clear existing handlers to avoid duplication
    if logger.handlers:
        logger.handlers.clear()
    
    # Set level
    if verbose:
        level = logging.DEBUG
    elif isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    
    logger.setLevel(level)
    
    # Log format
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if provided)
    if log_file:
        # Ensure parent directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """Get or create the global OpenMontage logger.
    
    Returns:
        The global logger instance
    """
    global _logger
    if _logger is None:
        _logger = setup_logger()
    return _logger


# Convenience functions for quick logging
def debug(msg: str, *args, **kwargs) -> None:
    """Log a debug message."""
    get_logger().debug(msg, *args, **kwargs)


def info(msg: str, *args, **kwargs) -> None:
    """Log an info message."""
    get_logger().info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs) -> None:
    """Log a warning message."""
    get_logger().warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs) -> None:
    """Log an error message."""
    get_logger().error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs) -> None:
    """Log a critical message."""
    get_logger().critical(msg, *args, **kwargs)