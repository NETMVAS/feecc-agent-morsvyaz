import sys

# set up logging configurations
BASE_LOGGING_CONFIG = {
    "level": "DEBUG",
    "colorize": True,
    "backtrace": True,
    "diagnose": True,
    "catch": True,
    "rotation": "10 MB",
    "compression": "zip",
}

# logging settings for the console logs
CONSOLE_LOGGING_CONFIG = {**BASE_LOGGING_CONFIG, "sink": sys.stdout, "level": "INFO"}

# logging settings for the log file
FILE_LOGGING_CONFIG = {
    **BASE_LOGGING_CONFIG,
    "sink": "hub.log",
    "rotation": "10 MB",
    "compression": "zip",
}
