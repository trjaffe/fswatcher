"""
File System Handler Module for SDC AWS File System Watcher
"""

import sys
import os
import time
from datetime import datetime
from urllib import parse
from pathlib import Path
import sqlite3
import boto3
import botocore
from boto3.s3.transfer import TransferConfig, S3Transfer
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from fswatcher.FileSystemHandlerEvent import FileSystemHandlerEvent
from fswatcher.FileSystemHandlerConfig import FileSystemHandlerConfig
from watchdog.events import (
    FileSystemEvent,
    FileClosedEvent,
    FileSystemEventHandler,
    FileMovedEvent,
    FileDeletedEvent,
)
from typing import List
from fswatcher import log


class FileSystemHandler(FileSystemEventHandler):
    """
    Subclass to handle file system events
    """

    events: List[FileSystemHandlerEvent] = []
    dead_letter_queue: List[dict] = []

    def __init__(
        self,
        config: FileSystemHandlerConfig,
    ) -> None:
        """
        Overloaded Constructor
        """
        # Initialize the allow S3 delete flag
        self.allow_delete = config.allow_delete

        # Initialize the concurrency_limit (Max number of concurrent S3 Uploads)
        self.concurrency_limit = config.concurrency_limit

        # Check if bucket name is and accessible using boto
        try:
            # Initialize Boto3 Session
            self.boto3_session = (
                boto3.session.Session(
                    profile_name=config.profile, region_name=os.getenv("AWS_REGION")
                )
                if config.profile != ""
                else boto3.session.Session(region_name=os.getenv("AWS_REGION"))
            )

            # Initialize S3 Transfer Manager with concurrency limit
            botocore_config = botocore.config.Config(
                max_pool_connections=self.concurrency_limit
            )
            self.s3_client = self.boto3_session.client("s3", config=botocore_config)
            transfer_config = TransferConfig(
                use_threads=True,
                max_concurrency=self.concurrency_limit,
            )
            self.s3t = S3Transfer(self.s3_client, transfer_config)

        except botocore.exceptions.ClientError as e:
            # If a client error is thrown, then check that it was a 404 error.
            # If it was a 404 error, then the bucket does not exist.
            error_code = int(e.response["Error"]["Code"])
            if error_code == 404:
                log.error(
                    {
                        "status": "ERROR",
                        "message": f"Bucket ({config.bucket_name}) does not exist",
                    }
                )

                sys.exit(1)

        # Initialize the bucket name
        self.bucket_name = config.bucket_name

        # Initialize the timestream db
        self.timestream_db = config.timestream_db

        # Initialize the timestream table
        self.timestream_table = config.timestream_table

        # Check s3
        if os.getenv("CHECK_S3") == "true":
            self.check_with_s3 = True
        else:
            self.check_with_s3 = False

        # Initialize the slack client
        if config.slack_token is not None:
            try:
                # Initialize the slack client
                self.slack_client = WebClient(token=config.slack_token)

                # Initialize the slack channel
                self.slack_channel = config.slack_channel

            except SlackApiError as e:
                error_code = int(e.response["Error"]["Code"])
                if error_code == 404:
                    log.error(
                        {
                            "status": "ERROR",
                            "message": f"Slack Token ({config.slack_token}) is invalid",
                        }
                    )
        else:
            self.slack_client = None

        # Validate the path
        if not os.path.exists(config.path):
            log.error(
                {"status": "ERROR", "message": f"Path ({config.path}) does not exist"}
            )

            sys.exit(1)

        # Path to watch
        self.path = config.path

        if os.getenv("TEST_IAM_POLICY") == "true":
            log.info("Performing Push/Remove Test Run")
            self._test_iam_policy()

    def on_any_event(self, event: FileSystemEvent) -> None:
        """
        Overloaded Function to deal with any event
        """
        # Filter the event
        filtered_event = self._filter_event(event)

        if filtered_event is None:
            return

        # Append the event to the list of events
        self.events.append(filtered_event)

        # Handle the event
        self._handle_event(filtered_event)

    def _filter_event(self, event: FileSystemEvent) -> FileSystemHandlerEvent or None:
        """
        Function to filter events
        """
        # Skip if file is hermes.log file
        if "hermes.log" in event.src_path:
            return None

        # Skip closed events
        if isinstance(event, FileClosedEvent):
            return None

        # Skip if directory
        if event.is_directory:
            return None

        # Initialize the file system event
        file_system_event = FileSystemHandlerEvent(
            event=event,
            watch_path=self.path,
            bucket_name=self.bucket_name,
        )

        # Skip if duplicate event
        if file_system_event in self.events:
            return None

        return file_system_event

    def _handle_event(self, event: FileSystemHandlerEvent) -> None:
        """
        Function to handle file events and upload to S3
        """
        try:
            # Send Slack Notification about the event
            if self.slack_client is not None:
                if event.action_type == "CREATE":
                    slack_message = f"FSWatcher: New file in watch directory - ({event.get_parsed_path()}) :file_folder:"
                elif event.action_type == "UPDATE":
                    slack_message = f"FSWatcher: File modified in watch directory - ({event.get_parsed_path()}) :file_folder:"
                elif event.action_type == "PUT":
                    slack_message = f"FSWatcher: File moved in watch directory - ({event.get_parsed_path()}) :file_folder:"
                elif event.action_type == "DELETE":
                    slack_message = f"FSWatcher: File deleted from watch directory - ({event.get_parsed_path()}) :file_folder:"
                else:
                    slack_message = f"FSWatcher: Unknown file event in watch directory - ({event.get_parsed_path()}) :file_folder:"

                self._send_slack_notification(
                    slack_client=self.slack_client,
                    slack_channel=self.slack_channel,
                    slack_message=slack_message,
                )

            # Get the log message
            log_message = event.get_log_message()

            # Capital Case Action Type
            log.info(log_message)

            if event.action_type != "DELETE":
                # Generate Object Tags String
                tags = self._generate_object_tags(
                    event=event,
                )

                # Upload to S3 Bucket
                self._upload_to_s3_bucket(
                    src_path=event.get_path(),
                    bucket_name=event.bucket_name,
                    file_key=event.get_parsed_path(),
                    tags=tags,
                )

                # Send Slack Notification about the event
                if self.slack_client is not None:
                    slack_message = f"FSWatcher: File successfully uploaded to {event.bucket_name} - ({event.get_parsed_path()}) :file_folder:"
                    self._send_slack_notification(
                        slack_client=self.slack_client,
                        slack_channel=self.slack_channel,
                        slack_message=slack_message,
                    )

            elif event.action_type == "DELETE" and self.allow_delete:
                # Delete from S3 Bucket if allowed
                self._delete_from_s3_bucket(
                    bucket_name=event.bucket_name,
                    file_key=event.get_parsed_path(),
                )

            # Log to Timestream
            if self.timestream_db and self.timestream_table:
                self._log(
                    boto3_session=self.boto3_session,
                    action_type=event.action_type,
                    file_key=event.get_path(),
                    new_file_key=event.get_parsed_path(),
                    source_bucket="External Server",
                    destination_bucket=None
                    if event.action_type == "DELETE"
                    else event.bucket_name,
                    timestream_db=self.timestream_db,
                    timestream_table=self.timestream_table,
                )

            # Remove the event from the list
            self.events.remove(event)

        except Exception as e:
            log.error(e)
            log.error(
                {
                    "status": "ERROR",
                    "message": f"Error handling file skipping to next: {e}",
                }
            )

    @staticmethod
    def _generate_object_tags(event: FileSystemHandlerEvent) -> str:
        """
        Function to generate object tags and return as a url encoded string
        """
        log.debug(f"Object ({event.get_parsed_path()}) - Generating S3 Object Tags")
        try:
            # Get Object Stats
            object_stats = os.stat(event.get_path())

            stat_list = dir(object_stats)

            tags = {}

            # Create Tags Dictionary
            for stat in stat_list:
                if stat in [
                    "st_mode",
                    "st_ino",
                    "st_uid",
                    "st_gid",
                    "st_size",
                    "st_atime",
                    "st_mtime",
                    "st_ctime",
                    "st_type",
                    "st_creator",
                ]:
                    tags[stat] = object_stats.__getattribute__(stat)

            # Log Object Creation and Modification Times
            log.debug(f"Object ({event.get_parsed_path()}) - Stats: {tags}")

            return parse.urlencode(tags)

        except Exception as e:
            log.error(
                {"status": "ERROR", "message": f"Error generating object tags: {e}"}
            )

    def _upload_to_s3_bucket(self, src_path, bucket_name, file_key, tags):
        """
        Function to Upload a file to an S3 Bucket
        """
        log.debug(f"Object ({file_key}) - Uploading file to S3 Bucket ({bucket_name})")

        # If bucket name includes directories remove them from bucket_name and append to the file_key
        if "/" in bucket_name:
            bucket_name, folder = bucket_name.split("/", 1)
            if folder != "" and folder[-1] != "/":
                folder = f"{folder}/"
            upload_file_key = f"{folder}{file_key}"
        else:
            upload_file_key = file_key
            folder = ""

        try:
            # Upload to S3 Bucket
            self.s3t.upload_file(
                src_path,
                bucket_name,
                upload_file_key,
                extra_args={"Tagging": tags},
            )

            if folder != "" and folder[0] != "/":
                folder = f"/{folder}"
            log.info(
                f"Object ({file_key}) - Successfully Uploaded to S3 Bucket ({bucket_name}{folder})"
            )

        except boto3.exceptions.RetriesExceededError:
            log.error(
                {
                    "status": "ERROR",
                    "message": f"Error uploading to S3 Bucket ({bucket_name}): Retries Exceeded",
                }
            )
            time.sleep(5)
            self.dead_letter_queue.append(
                {
                    "src_path": src_path,
                    "bucket_name": bucket_name,
                    "file_key": file_key,
                    "tags": tags,
                }
            )
            log.info(self.dead_letter_queue)

        except botocore.exceptions.ClientError as e:
            log.error(
                {"status": "ERROR", "message": f"Error uploading to S3 Bucket: {e}"}
            )
            self._send_slack_notification(
                slack_client=self.slack_client,
                slack_channel=self.slack_channel,
                slack_message=f"FSWatcher: Error uploading file to {bucket_name} - ({file_key}) :file_folder:",
                alert_type="error",
            )

    def _delete_from_s3_bucket(self, bucket_name, file_key):
        """
        Function to delete a file from an S3 bucket
        """
        # If bucket name includes directories remove them from bucket_name and append to the file_key
        if "/" in bucket_name:
            bucket_name, folder = bucket_name.split("/", 1)
            if folder != "" and folder[-1] != "/":
                folder = f"{folder}/"
            file_key = f"{folder}{file_key}"

        log.debug(f"Object ({file_key}) - Deleting file from S3 Bucket ({bucket_name})")

        try:
            if self.allow_delete:
                self.s3_client.delete_object(Bucket=bucket_name, Key=file_key)

                log.info(
                    f"Object ({file_key}) - Successfully deleted from S3 Bucket ({bucket_name})"
                )
        except botocore.exceptions.ClientError as e:
            log.error(
                {"status": "ERROR", "message": f"Error deleting from S3 Bucket: {e}"}
            )

    @staticmethod
    def _send_slack_notification(
        slack_client,
        slack_channel: str,
        slack_message: str,
        alert_type: str = "success",
    ) -> None:
        """
        Function to send a Slack Notification
        """
        log.debug(f"Sending Slack Notification to {slack_channel}")
        try:
            color = {
                "success": "#3498db",
                "error": "#ff0000",
            }
            ct = datetime.now()
            ts = ct.strftime("%y-%m-%d %H:%M:%S")
            slack_client.chat_postMessage(
                channel=slack_channel,
                text=f"{ts} - {slack_message}",
                attachments=[
                    {
                        "color": color[alert_type],
                        "blocks": [
                            {
                                "type": "section",
                                "text": {
                                    "type": "plain_text",
                                    "text": f"{ts} - {slack_message}",
                                },
                            }
                        ],
                    }
                ],
            )

        except SlackApiError as e:
            log.error(
                {"status": "ERROR", "message": f"Error sending Slack Notification: {e}"}
            )

    @staticmethod
    def _log(
        boto3_session,
        action_type,
        file_key,
        new_file_key=None,
        source_bucket=None,
        destination_bucket=None,
        timestream_db=None,
        timestream_table=None,
    ):
        """
        Function to Log to Timestream
        """
        log.debug(f"Object ({new_file_key}) - Logging Event to Timestream")
        CURRENT_TIME = str(int(time.time() * 1000))
        try:
            # Initialize Timestream Client
            timestream = boto3_session.client("timestream-write")

            if not source_bucket and not destination_bucket:
                raise ValueError("A Source or Destination Buckets is required")

            # Write to Timestream
            timestream.write_records(
                DatabaseName=timestream_db if timestream_db else "sdc_aws_logs",
                TableName=timestream_table
                if timestream_table
                else "sdc_aws_s3_bucket_log_table",
                Records=[
                    {
                        "Time": CURRENT_TIME,
                        "Dimensions": [
                            {"Name": "action_type", "Value": action_type},
                            {
                                "Name": "source_bucket",
                                "Value": source_bucket or "N/A",
                            },
                            {
                                "Name": "destination_bucket",
                                "Value": destination_bucket or "N/A",
                            },
                            {"Name": "file_key", "Value": file_key},
                            {
                                "Name": "new_file_key",
                                "Value": new_file_key or "N/A",
                            },
                            {
                                "Name": "current file count",
                                "Value": "N/A",
                            },
                        ],
                        "MeasureName": "timestamp",
                        "MeasureValue": str(datetime.utcnow().timestamp()),
                        "MeasureValueType": "DOUBLE",
                    },
                ],
            )

            log.debug(
                (f"Object ({new_file_key}) - Event Successfully Logged to Timestream")
            )

        except botocore.exceptions.ClientError as e:
            log.error(
                {"status": "ERROR", "message": f"Error logging to Timestream: {e}"}
            )

    # Recursively get all file in the specified directory as a list with optional date filter (datetime) also print out how long it took to get the files and the number of files
    def _get_files(self, path, date_filter=None):
        files = []
        start_time = time.time()
        for root, _, file in os.walk(path):
            for f in file:
                file_path = os.path.join(root, f)
                if date_filter:
                    if self._check_date(file_path, date_filter):
                        files.append(file_path)
                else:
                    files.append(file_path)

        end_time = time.time()
        log.info(
            f"Found {len(files)} files in {round(end_time - start_time, 2)} seconds"
        )

        # If Check with S3 is enabled, call the function to get all keys and compare with the files
        if self.check_with_s3:
            log.info("Checking files with S3 (This may take a while) ...")

            keys = self._get_s3_keys(bucket_name=self.bucket_name)

            log.info("Now comparing files with S3 keys ...")

            # Remove files that are already in S3
            files = list(set(files) - set(keys))
            # Log the first 10 files
            log.info(f"First 10 files: {files[:10]}")

            # Log the first 10 keys
            log.info(f"First 10 keys: {keys[:10]}")
            # Log the number of files that are not in S3
            log.info(f"Found {len(files)} files that are not in S3")

        return files

    # Check if the file is newer than the date filter
    def _check_date(self, file, date_filter):
        # Change date_filter from datetime to match modified time
        date_filter = datetime.timestamp(date_filter)

        if os.path.getmtime(file) > date_filter:
            return True
        return False

    # Go through the list of files and check if they are in the S3 bucket
    def _check_files(self, files, bucket_name):
        for file in files:
            file_key = file.replace(self.base_path, "")
            if not self.s3t.exists(bucket_name, file_key):
                self._upload_to_s3_bucket(
                    file,
                    bucket_name,
                    file_key,
                    tags=self.tags,
                )
                self._log(
                    boto3_session=self.boto3_session,
                    action_type="PUT",
                    file_key=file_key,
                    source_bucket=self.base_path,
                    destination_bucket=bucket_name,
                )

    # Go through the list of files and create a FileMovedEvent then dispatch it
    def _dispatch_events(self, files, deleted_files=None):
        for file in files:
            event = FileMovedEvent(file, file)
            self.dispatch(event)

        if deleted_files:
            for file in deleted_files:
                event = FileDeletedEvent(file)
                self.dispatch(event)

    # Backtrack the directory tree
    def backtrack(self, path, date_filter=None):
        self._dispatch_events(self._get_files(path, date_filter))

    # Get all of the keys in an S3 bucket and return them as a list also support pagination if required, use s3 client instead of s3t because s3t does not support pagination
    def _get_s3_keys(self, bucket_name):
        keys = []
        start_time = time.time()
        s3 = self.boto3_session.client("s3")
        paginator = s3.get_paginator("list_objects_v2")
        # If bucket name includes directories remove them from bucket_name and append to the file_key
        if "/" in bucket_name:
            bucket_name, folder = bucket_name.split("/", 1)
            if folder != "" and folder[-1] != "/":
                folder = f"{folder}/"
        else:
            folder = ""

        operation_parameters = {"Bucket": bucket_name, "Prefix": folder}
        page_iterator = paginator.paginate(**operation_parameters)

        for page in page_iterator:
            if "Contents" in page:
                for obj in page["Contents"]:
                    keys.append(f'/watch/{obj["Key"].replace(folder, "")}')
        end_time = time.time()
        log.info(f"Found {len(keys)} keys in {round(end_time - start_time, 2)} seconds")
        return keys

    def parse_datetime(self, date_string):
        if date_string is None or date_string == "":
            return None
        date_string = date_string.replace("'", "")
        date_string = f"{date_string} 00:00:00"
        return datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")

    # Perform IAM Policy Configuration Test
    def _test_iam_policy(self):
        # Create a file to test
        test_filename = "fswatcher_test_file.txt"
        test_file = os.path.join(self.path, test_filename)
        test_event = FileMovedEvent(test_file, test_file)
        file_system_event = FileSystemHandlerEvent(
            event=test_event,
            watch_path=self.path,
            bucket_name=self.bucket_name,
        )

        # Create the file
        with open(test_file, "w") as f:
            f.write("This is a test file")

        # Generate tags
        tags = self._generate_object_tags(file_system_event)

        # Upload the file to S3
        self._upload_to_s3_bucket(
            test_file,
            self.bucket_name,
            test_filename,
            tags,
        )

        # If bucket name includes directories remove them from bucket_name and append to the file_key
        if "/" in self.bucket_name:
            bucket_name, folder = self.bucket_name.split("/", 1)
            if folder != "" and folder[-1] != "/":
                folder = f"{folder}/"
            file_key = f"{folder}{test_filename}"
        else:
            bucket_name = self.bucket_name
            file_key = test_filename
            folder = ""

        # Wait for the file to be deleted
        log.info("Waiting for file to be added...")
        time.sleep(5)
        log.info(f"Bucket Name: {bucket_name}")
        log.info(f"File Key: {file_key}")

        # Check if the file exists in S3 using s3 client
        s3 = self.boto3_session.client("s3")

        try:
            s3.get_object(
                Bucket=bucket_name,
                Key=file_key,
            )
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                log.error("Test Failed - Check IAM Policy Configuration")
                sys.exit(1)
            else:
                log.error("Test Failed - Check IAM Policy Configuration")
                sys.exit(1)

        # Delete the file
        os.remove(test_file)

        if self.allow_delete:
            # Delete the file from S3
            self._delete_from_s3_bucket(
                self.bucket_name,
                test_filename,
            )

            # Check if the file exists in S3 using s3 client
            try:
                # Wait for the file to be deleted
                log.info("Waiting for file to be deleted...")
                time.sleep(5)

                s3.get_object(
                    Bucket=bucket_name,
                    Key=file_key,
                )

                log.error(
                    f"Test Failed - Check IAM Policy Configuration, also clean up the test file in S3 bucket ({self.bucket_name})"
                )
                sys.exit(1)

            except botocore.exceptions.ClientError as e:
                if e.response["Error"]["Code"] == "NoSuchKey":
                    log.info("Test Passed - IAM Policy Configuration is correct")
                else:
                    log.error(
                        f"Test Failed - Check IAM Policy Configuration, also clean up the test file in S3 bucket ({self.bucket_name})"
                    )
                    sys.exit(1)
        else:
            log.info("Test Passed - IAM Policy Configuration is correct")
            log.warning(
                "Since allow_delete is set to False, the test file will not be deleted from S3, please delete it manually"
            )

    def init_db(self):
        conn = sqlite3.connect("fswatcher.db")
        return conn

    def update_files_info(self, conn, cur, file_info):
        cur.execute(
            "REPLACE INTO files (file_path, modified_time) VALUES (?, ?)",
            (file_info["file_path"], file_info["modified_time"]),
        )
        conn.commit()

    def delete_file_info(self, conn, cur, file_path):
        cur.execute("DELETE FROM files WHERE file_path=?", (file_path,))
        conn.commit()

    def get_files_info(self, cur):
        cur.execute("SELECT file_path, modified_time FROM files")
        return {row[0]: row[1] for row in cur.fetchall()}

    def check_for_changes(self, conn, cur, current_files_info):
        new_files = []
        deleted_files = []
        previous_files_info = self.get_files_info(cur)

        for file, mtime in current_files_info.items():
            if file not in previous_files_info or mtime > previous_files_info[file]:
                new_files.append(file)
                self.update_files_info(
                    conn, cur, {"file_path": file, "modified_time": mtime}
                )

        for file in previous_files_info:
            if file not in current_files_info:
                deleted_files.append(file)
                self.delete_file_info(conn, cur, file)

        conn.commit()  # Commit the changes after all operations are complete
        return new_files, deleted_files

    def process_files(self, conn, cur, all_files, s3=False):
        if s3:
            # Compatible modification time for S3 in float
            datetime_now = datetime.now().timestamp()
            current_files_info = {file_path: datetime_now for file_path in all_files}
        else:
            current_files_info = {file_path: mtime for file_path, mtime in all_files}
        new_files, deleted_files = self.check_for_changes(conn, cur, current_files_info)
        return new_files, deleted_files

    def check_path_exists(self, path):
        if not Path(path).exists():
            log.info(f"Path {path} does not exist")
            return False
        return True

    def walk_directory(self, path, excluded_files=None, excluded_exts=None):
        all_files = []
        for root, _, files in os.walk(path):
            for file in files:
                file_path = os.path.join(root, file)
                if (excluded_files and file_path in excluded_files) or (
                    excluded_exts and os.path.splitext(file)[1] in excluded_exts
                ):
                    continue
                try:
                    file_mtime = os.path.getmtime(file_path)
                    all_files.append((file_path, file_mtime))
                except FileNotFoundError:
                    log.info(f"File {file_path} not found")

        return all_files

    def fallback_directory_watcher(self):
        path = "/watch"
        check_interval = 5

        # Create the table if it doesn't exist
        conn = self.init_db()
        cur = conn.cursor()
        cur.execute(
            """CREATE TABLE IF NOT EXISTS files (
                        file_path TEXT PRIMARY KEY,
                        modified_time REAL)"""
        )
        conn.commit()

        # Initialize excluded_files and excluded_exts as empty lists
        excluded_files = []
        excluded_exts = []
        if self.check_with_s3:
            log.info("Checking S3 bucket for existing files...")
            s3_keys = self._get_s3_keys(self.bucket_name)
            log.info(
                f"Found {len(s3_keys)} files in S3 bucket. Adding to db of existing files..."
            )
            self.process_files(conn, cur, s3_keys, True)

        log.info("Starting directory watcher...")
        if not self.check_path_exists(path):
            log.info("Path does not exist, exiting...")
            return
        else:
            log.info(f"Monitoring path: {path}")

        while True:
            time.sleep(
                check_interval
            )  # Wait for 60 seconds before checking for new files again
            start = time.time()
            # Get list of all files in directory
            all_files = self.walk_directory(
                path, excluded_files=excluded_files, excluded_exts=excluded_exts
            )
            end = time.time()
            log.info(f"Time taken to walk directory: {end - start} seconds")

            start = time.time()
            log.info("Processing files...")
            # Check for new, updated, and deleted files
            new_files, deleted_files = self.process_files(conn, cur, all_files)
            end = time.time()
            log.info(f"Time taken to process files: {end - start} seconds")
            log.info(f"New files: {len(new_files)}")
            log.info(f"Deleted files: {len(deleted_files)}")
            # Size in megabytes of db
            log.info(f"DB size: {os.path.getsize('fswatcher.db') / 1000000} MB")

            start = time.time()
            # Dispatch events
            log.info("Dispatching events...")
            self._dispatch_events(new_files, deleted_files)
            end = time.time()
            log.info(f"Time taken to dispatch events: {end - start} seconds")
