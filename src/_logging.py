import logging
import os
import sys
from typing import Any

import ecs_logging

# set up logging configurations
BASE_LOGGING_CONFIG = {
    "colorize": True,
    "backtrace": False,
    "diagnose": True,
    "catch": True,
}

# logging settings for the console logs
CONSOLE_LOGGING_CONFIG = {
    **BASE_LOGGING_CONFIG,  # type: ignore
    "level": "DEBUG",
    "sink": sys.stdout,
}

# logging settings for the log file
FILE_LOGGING_CONFIG = {
    **BASE_LOGGING_CONFIG,  # type: ignore
    "level": "DEBUG",
    "sink": "workbench.log",
    "rotation": "10 MB",
    "compression": "zip",
}

# Elastic Common Schema (ECS) logging sink
ecs_handler = logging.FileHandler("ecs_log.json")
ecs_handler.setFormatter(ecs_logging.StdlibFormatter())
ECS_LOGGING_CONFIG = {
    "sink": ecs_handler,
    "format": "{message}",
}

# Set up handlers list
HANDLERS: list[dict[str, Any]] = [FILE_LOGGING_CONFIG, CONSOLE_LOGGING_CONFIG]

if os.getenv("LOG_ECS_ENABLE", False):
    HANDLERS.append(ECS_LOGGING_CONFIG)


# disable Uvicorn's access logs for specified endpoints
class EndpointAccessFilter(logging.Filter):
    excluded_endpoints = {"/docs", "/openapi.json", "/health", "/metrics", "/robots.txt"}

    def filter(self, record: logging.LogRecord) -> bool:
        # complete query string (so parameter and other value included)
        query_string: str = record.args[2]  # type: ignore
        endpoint = query_string.split("?")[0]
        return endpoint not in self.excluded_endpoints


logging.getLogger("uvicorn.access").addFilter(EndpointAccessFilter())
