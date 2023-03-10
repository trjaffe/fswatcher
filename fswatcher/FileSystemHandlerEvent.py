"""
File System Handler Event Module
"""

from watchdog.events import (
    FileSystemEvent,
    FileCreatedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileDeletedEvent,
)


class FileSystemHandlerEvent:
    """
    Dataclass to hold the FileSystemHandler Configuration
    It is frozen to make it immutable
    """

    watch_path: str
    src_path: str
    bucket_name: str
    dest_path: str = ""
    action_type: str = ""
    completed: bool = False

    def __init__(
        self, event: FileSystemEvent, bucket_name: str, watch_path: str
    ) -> None:
        """
        Class Constructor
        """
        # Set the Watch Path
        self.watch_path = watch_path

        # Set the Source Path
        self.src_path = event.src_path

        # Set the Bucket Name
        self.bucket_name = bucket_name

        # Handle File Creation Event if it is a FileCreatedEvent
        if isinstance(event, FileCreatedEvent):
            self.action_type = "CREATE"

        # Handle File Modification Event
        elif isinstance(event, FileModifiedEvent):
            self.action_type = "UPDATE"

        # Handle File Move Event
        elif isinstance(event, FileMovedEvent):
            self.action_type = "PUT"

            # Set the Destination Path
            self.dest_path = event.dest_path

        # Handle File Deletion Event
        elif isinstance(event, FileDeletedEvent):
            self.action_type = "DELETE"

    # String Representation of the Class
    def __repr__(self) -> str:
        """
        String Representation of the Class
        """

        return f"FileSystemHandlerEvent(src_path={self.src_path}, bucket_name={self.bucket_name}, dest_path={self.dest_path}, action_type={self.action_type}, completed={self.completed})"

    # Comparison Function
    def __eq__(self, other: object) -> bool:
        """
        Comparison Function
        """

        # Check if the other object is of the same type
        if not isinstance(other, FileSystemHandlerEvent):
            raise ValueError("The other object is not of the same type")

        # Check if the Source Path, Bucket Name, Destination Path and Action Type are the same
        return (
            self.src_path == other.src_path
            and self.bucket_name == other.bucket_name
            and self.dest_path == other.dest_path
            and self.action_type == other.action_type
        )

    def get_log_message(self) -> str:
        """
        Function to get the log message
        """

        return f"Object ({self.get_parsed_path()}) - File {self.get_capitalized_action_type()}: {self.get_parsed_path() + (f' to {self.dest_path}' if self.dest_path != '' else self.dest_path)}"

    # Function to check if the event is completed
    def is_completed(self) -> bool:
        """
        Function to check if the event is completed
        """

        return self.completed

    # Function to get Capitilized Action Type
    def get_capitalized_action_type(self) -> str:
        """
        Function to get Capitilized Action Type
        """

        return self.action_type.capitalize()

    def get_path(self) -> str:
        """
        Function to return path
        """

        return self.src_path if self.dest_path == "" else self.dest_path

    # Function to get the parsed Source Path
    def get_parsed_path(self) -> str:
        """
        Function to return parsed src path
        """
        path = self.get_path()

        # Strip first occurence of watch_path from src_path by splitting on the path by src_path
        parsed_src_path = path.split(self.watch_path, 1)

        merged_path = "".join(parsed_src_path)

        # Strip the first slash from the path
        if merged_path[0] == "/":
            merged_path = merged_path[1:]

        return merged_path
