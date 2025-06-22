"""
Centralized logging configuration for ADK Multi-Agent system.

This module provides file-based logging with rotation support and
different log levels for different components.
"""

import logging
import logging.handlers
import os
from pathlib import Path
from datetime import datetime
import structlog


def setup_logging(
    log_file: str = "logs/adk_agent.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    console_level: str = "INFO",
    file_level: str = "DEBUG"
) -> None:
    """
    Setup centralized logging configuration.
    
    Args:
        log_file: Path to log file
        max_bytes: Maximum size of each log file before rotation
        backup_count: Number of backup files to keep
        console_level: Log level for console output
        file_level: Log level for file output
    """
    # Ensure log directory exists
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    root_logger.handlers = []
    
    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(getattr(logging, file_level))
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, console_level))
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    # Configure specific loggers
    configure_component_loggers()
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer() if os.getenv("ENV") == "development" else structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized - File: {log_file}, Console Level: {console_level}, File Level: {file_level}")


def configure_component_loggers():
    """Configure log levels for specific components."""
    
    # External API responses at DEBUG level
    logging.getLogger("integrations.hdw").setLevel(logging.INFO)
    logging.getLogger("integrations.hdw.responses").setLevel(logging.DEBUG)
    
    logging.getLogger("integrations.exa_websets").setLevel(logging.INFO)
    logging.getLogger("integrations.exa_websets.responses").setLevel(logging.DEBUG)
    
    logging.getLogger("integrations.firecrawl").setLevel(logging.INFO)
    logging.getLogger("integrations.firecrawl.responses").setLevel(logging.DEBUG)
    
    # Agent components at INFO level with verbose options
    logging.getLogger("agents.adk_base_agent").setLevel(logging.INFO)
    logging.getLogger("agents.adk_icp_agent").setLevel(logging.INFO)
    logging.getLogger("agents.adk_prospect_agent").setLevel(logging.INFO)
    logging.getLogger("agents.adk_research_agent").setLevel(logging.INFO)
    
    # Memory services with detailed logging
    logging.getLogger("services.vertex_memory_service").setLevel(logging.INFO)
    logging.getLogger("services.mock_memory_service").setLevel(logging.INFO)
    
    # Orchestrator with verbose logging
    logging.getLogger("adk_main").setLevel(logging.INFO)
    
    # Web interface
    logging.getLogger("web_interface").setLevel(logging.INFO)
    
    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("gradio").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_api_response(logger: logging.Logger, api_name: str, response_data: any, truncate: int = 500):
    """
    Log API response at debug level with truncation.
    
    Args:
        logger: Logger instance
        api_name: Name of the API
        response_data: Response data to log
        truncate: Maximum characters to log (0 for no truncation)
    """
    response_str = str(response_data)
    if truncate > 0 and len(response_str) > truncate:
        response_str = response_str[:truncate] + "... (truncated)"
    
    logger.debug(f"{api_name} API Response: {response_str}")


def log_data_transformation(logger: logging.Logger, stage: str, before: any, after: any):
    """
    Log data transformation for debugging data loss issues.
    
    Args:
        logger: Logger instance
        stage: Description of the transformation stage
        before: Data before transformation
        after: Data after transformation
    """
    logger.debug(f"Data transformation at {stage}")
    logger.debug(f"  Before: {before}")
    logger.debug(f"  After: {after}")