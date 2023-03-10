"""
Utility functions for fswatcher.
"""
import os
import logging

# Configure logging
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# Create log file handler if file log environment variable is set
if os.environ.get("FILE_LOGGING") == "true":
    log.info("File logging enabled")
    file_handler = logging.FileHandler("fswatcher.log")
    file_handler.setLevel(logging.INFO)

    # Create formatter and add it to the handlers
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)

    # Add the handlers to the logger
    log.addHandler(file_handler)

# Configure boto3 logging to debug
if os.environ.get("BOTO3_LOGGING") == "true":
    log.info("Boto3 logging enabled")
    boto3_log = logging.getLogger("botocore")
    boto3_log.setLevel(logging.DEBUG)
