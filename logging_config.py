# logging_config.py
import logging
import os
from logging.config import dictConfig
from logging.handlers import RotatingFileHandler

from config import settings


def setup_logging():
    # --- Create logs directory if it doesn't exist ---
    log_directory = "logs"
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)

    log_file_path = os.path.join(log_directory, "app.log")

    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            # Formatter for console output
            "console_formatter": {
                "()": "uvicorn.logging.DefaultFormatter",
                "fmt": "%(levelprefix)s %(asctime)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            # Formatter for file output
            "file_formatter": {
                "format": "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            # Console handler (keeps logging to the terminal)
            "console_handler": {
                "formatter": "console_formatter",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
            },
            # File handler (for writing to logs/app.log)
            "file_handler": {
                "formatter": "file_formatter",
                "class": "logging.handlers.RotatingFileHandler",
                "filename": log_file_path,
                "maxBytes": 10 * 1024 * 1024,  # 10 MB
                "backupCount": 5,  # Keep 5 backup files
                "encoding": "utf8",
            },
        },
        "loggers": {
            "root": {
                # Send logs to BOTH the console and the file
                "handlers": ["console_handler", "file_handler"],
                "level": settings.log_level.upper(),
            },
        },
    }
    dictConfig(log_config)
