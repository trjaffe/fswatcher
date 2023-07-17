"""
File System Handler Module for SDC AWS File System Watcher
"""

import sys
import os
import time
from datetime import datetime
from urllib import parse
from pathlib import Path
import subprocess
import boto3
import botocore
from boto3.s3.transfer import TransferConfig, S3Transfer
from slack_sdk.errors import SlackApiError
from fswatcher import (
    log,
    is_file_manifest,
    generate_file_pipeline_message,
    get_message_ts,
    get_slack_client,
    send_slack_notification,
    timestream_log,
)
from fswatcher.FileSystemHandlerEvent import FileSystemHandlerEvent
from fswatcher.FileSystemHandlerConfig import FileSystemHandlerConfig
from watchdog.events import (
    FileSystemEvent,
    FileOpenedEvent,
    FileClosedEvent,
    FileSystemEventHandler,
    FileMovedEvent,
    FileDeletedEvent,
)
from typing import List, Optional, Union, Dict, Any, Tuple


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

        # Initialize the config
        self.config = config

        # Initialize the allow S3 delete flag
        self.allow_delete = config.allow_delete

        # Initialize the concurrency_limit (Max number of concurrent S3 Uploads)
        self.concurrency_limit = config.concurrency_limit

        # Time since last refresh
        self.last_refresh_time = time.time()

        # Check if bucket name is and accessible using boto
        try:
            # Initialize Boto3 Session
            self.boto3_session = (
                boto3.session.Session(
                    profile_name=config.profile, region_name=config.aws_region
                )
                if config.profile != ""
                else boto3.session.Session(region_name=config.aws_region)
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
        if config.check_s3 == True:
            self.check_with_s3 = True
        else:
            self.check_with_s3 = False

        # Initialize the slack client
        if config.slack_token is not None:
            try:
                # Initialize the slack client
                self.slack_client = get_slack_client(slack_token=config.slack_token)

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

        if config.test_iam_policy == True:
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

        # Skip closed events
        if isinstance(event, FileOpenedEvent):
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
            # Get the log message
            log_message = event.get_log_message()

            # Capital Case Action Type
            log.info(log_message)

            if event.action_type != "DELETE":
                # Send Slack Notification about the event
                if self.slack_client is not None:
                    try:
                        slack_message = generate_file_pipeline_message(event.get_path())
                        send_slack_notification(
                            slack_client=self.slack_client,
                            slack_channel=self.slack_channel,
                            slack_message=slack_message,
                        )
                    except Exception as e:
                        log.error(e)

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
                    try:
                        if not is_file_manifest(event.get_path()):
                            slack_message = generate_file_pipeline_message(
                                event.get_path()
                            )
                            # Get ts of the slack message
                            ts = get_message_ts(
                                slack_client=self.slack_client,
                                slack_channel=self.slack_channel,
                                text=slack_message,  # Pass the message_ts instead of slack_message
                            )

                            action_type = "upload"
                            slack_message = generate_file_pipeline_message(
                                event.get_path(), alert_type=action_type
                            )

                            # Send Slack Notification about the event within thread
                            send_slack_notification(
                                slack_client=self.slack_client,
                                slack_channel=self.slack_channel,
                                slack_message=slack_message,
                                alert_type=action_type,
                                thread_ts=ts,
                            )
                    except Exception as e:
                        log.error(e)

            elif event.action_type == "DELETE" and self.allow_delete:
                # Delete from S3 Bucket if allowed
                self._delete_from_s3_bucket(
                    bucket_name=event.bucket_name,
                    file_key=event.get_parsed_path(),
                )

            # Log to Timestream
            if self.timestream_db and self.timestream_table:
                timestream_log(
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
            # If time since self.last_refresh is greater than 15 minutes refresh the boto session
            if time.time() - self.last_refresh_time >= 900:  # 900 seconds = 15 minutes
                self._refresh_boto_session()
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
            self._refresh_boto_session()
            log.error(
                {"status": "ERROR", "message": f"Error uploading to S3 Bucket: {e}"}
            )
            try:
                send_slack_notification(
                    slack_client=self.slack_client,
                    slack_channel=self.slack_channel,
                    slack_message=f"FSWatcher: Error uploading file to {bucket_name} - ({file_key}) :file_folder:",
                    alert_type="error",
                )
            except Exception as e:
                log.error(e)

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
                if (
                    time.time() - self.last_refresh_time >= 900
                ):  # 900 seconds = 15 minutes
                    self._refresh_boto_session()
                self.s3_client.delete_object(Bucket=bucket_name, Key=file_key)

                log.info(
                    f"Object ({file_key}) - Successfully deleted from S3 Bucket ({bucket_name})"
                )
        except botocore.exceptions.ClientError as e:
            log.error(
                {"status": "ERROR", "message": f"Error deleting from S3 Bucket: {e}"}
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
                self._refresh_boto_session()
                timestream_log(
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
        self._refresh_boto_session()
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
        self._refresh_boto_session()
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

    def process_files(self, new_files, old_files):
        deleted_files = old_files - new_files

        new_files = new_files - old_files

        return new_files, deleted_files

    def check_path_exists(self, path):
        if not Path(path).exists():
            log.info(f"Path {path} does not exist")
            return False
        return True

    def walk_directory_find(
        self, path, excluded_files=None, excluded_exts=None, within_timestamp=None
    ):
        all_files = []
        find_command = ["find", path, "-type", "f", "-not", "-path", "'*/\.*'"]
        if within_timestamp:
            find_command += [
                "-newermt",
                within_timestamp,
            ]
        result = subprocess.run(find_command, stdout=subprocess.PIPE)
        output_lines = result.stdout.decode().splitlines()

        for file_path in output_lines:
            if (excluded_files and file_path in excluded_files) or (
                excluded_exts and os.path.splitext(file_path)[1] in excluded_exts
            ):
                continue

            try:
                all_files.append((file_path))
            except FileNotFoundError:
                log.info(f"File {file_path} not found")

        return set(all_files)

    def fallback_directory_watcher(self):
        path = "/watch"

        last_run_timestamp_str = None

        # Initialize excluded_files and excluded_exts as empty lists
        excluded_files = []
        excluded_exts = []
        if self.check_with_s3:
            log.info("Checking S3 bucket for existing files...")
            s3_set = set(self._get_s3_keys(self.bucket_name))
            log.info(
                f"Found {len(s3_set)} files in S3 bucket. Adding to db of existing files..."
            )
        log.info("Starting directory watcher...")
        if not self.check_path_exists(path):
            log.info("Path does not exist, exiting...")
            return
        else:
            log.info(f"Monitoring path: {path}")

        log.info("Get initial Files")
        start = time.time()

        # Get list of all files in directory
        all_files = self.walk_directory_find(
            path, excluded_files=excluded_files, excluded_exts=excluded_exts
        )

        if self.check_with_s3:
            new_files, deleted_files = self.process_files(all_files, s3_set)
        else:
            new_files, deleted_files = self.process_files(all_files, set())

        deleted_files = []

        self._dispatch_events(list(new_files), deleted_files)
        log.info(f"New files: {len(new_files)}")
        log.info(f"Deleted files: {len(deleted_files)}")

        end = time.time()
        log.info(
            f"Time taken to walk directory: {end - start} seconds, files: {len(all_files)}"
        )
        log.info("Get initial Files - Done")
        log.info("\nStarting loop...")

        # Loop starts
        while True:
            if last_run_timestamp_str:
                # Get list of all files in directory
                modified_files = self.walk_directory_find(
                    path,
                    excluded_files=excluded_files,
                    excluded_exts=excluded_exts,
                    within_timestamp=last_run_timestamp_str,
                )
            else:
                modified_files = set()

            # Get list of all files in directory
            files = self.walk_directory_find(
                path,
                excluded_files=excluded_files,
                excluded_exts=excluded_exts,
            )
            new_files, deleted_files = self.process_files(files, all_files)

            # Add modified files to new_files set
            new_files = new_files.union(modified_files)
            timestamp = int(time.time())
            last_run_timestamp_str = time.strftime(
                "%Y-%m-%dT%H:%M:%S", time.localtime(timestamp)
            )
            self._dispatch_events(list(new_files), deleted_files)
            # Remove deleted files from all_files
            all_files = all_files - deleted_files
            # Add new files to all_files
            all_files = all_files.union(new_files)

            # Sleep for 5 seconds
            time.sleep(5)

    def _refresh_boto_session(self):
        config = self.config
        try:
            self.boto3_session = (
                boto3.session.Session(
                    profile_name=config.profile, region_name=self.config.aws_region
                )
                if config.profile != ""
                else boto3.session.Session(region_name=self.config.aws_region)
            )
            botocore_config = botocore.config.Config(
                max_pool_connections=self.concurrency_limit
            )
            self.s3_client = self.boto3_session.client("s3", config=botocore_config)
            transfer_config = TransferConfig(
                use_threads=True,
                max_concurrency=self.concurrency_limit,
            )
            self.s3t = S3Transfer(self.s3_client, transfer_config)
            self.last_refresh_time = time.time()
        except botocore.exceptions.ClientError as e:
            error_code = int(e.response["Error"]["Code"])
            if error_code == 404:
                log.error(
                    {
                        "status": "ERROR",
                        "message": f"Bucket ({config.bucket_name}) does not exist",
                    }
                )
                sys.exit(1)
