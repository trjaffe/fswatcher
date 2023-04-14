"""
Main File for the AWS File System Watcher
"""
import os
import sys
import time
import logging
from watchdog.observers import Observer
from fswatcher.FileSystemHandler import FileSystemHandler
from fswatcher.FileSystemHandlerConfig import get_config

# Configure logging
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)


# Main Function
def main() -> None:
    """
    Main Function
    """

    # Get the configuration dataclass object
    config = get_config()

    # Initialize the FileSystemHandler
    event_handler = FileSystemHandler(config=config)

    if os.environ.get("USE_FALLBACK") == "true":
        event_handler.fallback_directory_watcher()
        sys.exit(0)

    # Try to use the inotify observer
    try:
        # Initialize the Observer and start watching
        logging.info("Starting observer")
        observer = Observer()
        observer.schedule(event_handler, config.path, recursive=True)

        observer.start()
        # If backtrack is enabled, run the initial scan
        if config.backtrack:
            logging.info(
                "Backtracking enabled, backtracking (This might take awhile if a large amount of directories and files)..."
            )
            event_handler.backtrack(
                config.path, event_handler.parse_datetime(config.backtrack_date)
            )
            logging.info("Backtracking complete")
            config.backtrack = False
        logging.info(
            f"Watching for file events with INotify Observer in: {config.path}"
        )

    except OSError:
        # If inotify fails, use the polling observer
        logging.warning(
            "INotify Limit Reached, falling back to slower method walking method.\nWe suggest you increase the inotify limit for better performance."
        )

        event_handler.fallback_directory_watcher()

    try:
        while True:
            time.sleep(1)
    finally:
        observer.stop()
        observer.join()


# Main Function
if __name__ == "__main__":
    main()
