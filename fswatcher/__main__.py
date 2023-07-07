"""
Main File for the AWS File System Watcher
"""
import sys
import time
from watchdog.observers import Observer
from fswatcher import config, log
from fswatcher.FileSystemHandler import FileSystemHandler


# Main Function
def main() -> None:
    """
    Main Function
    """

    # Initialize the FileSystemHandler
    event_handler = FileSystemHandler(config=config)

    if config.use_fallback == True:
        event_handler.fallback_directory_watcher()
        sys.exit(0)

    # Try to use the inotify observer
    try:
        # Initialize the Observer and start watching
        log.info("Starting observer")
        observer = Observer()
        observer.schedule(event_handler, config.path, recursive=True)

        observer.start()
        # If backtrack is enabled, run the initial scan
        if config.backtrack:
            log.info(
                "Backtracking enabled, backtracking (This might take awhile if a large amount of directories and files)..."
            )
            event_handler.backtrack(
                config.path, event_handler.parse_datetime(config.backtrack_date)
            )
            log.info("Backtracking complete")
            config.backtrack = False
        log.info(
            f"Watching for file events with INotify Observer in: {config.path}"
        )

    except OSError:
        # If inotify fails, use the polling observer
        log.warning(
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
