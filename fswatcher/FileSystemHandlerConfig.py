"""
File System Handler Configuration Module
"""

from argparse import ArgumentParser

import logging

log = logging.getLogger(__name__)


class FileSystemHandlerConfig:
    """
    Dataclass to hold the FileSystemHandler Configuration
    """

    def __init__(
        self,
        path: str,
        bucket_name: str,
        timestream_db: str = "",
        timestream_table: str = "",
        profile: str = "",
        concurrency_limit: int = 20,
        allow_delete: bool = False,
        slack_token: str = "",
        slack_channel: str = "",
        backtrack: bool = False,
        backtrack_date: str = "",
        use_fallback: bool = False,
        file_logging: bool = False,
        boto3_logging: bool = False,
        test_iam_policy: bool = False,
        check_s3: bool = False,
        aws_region: str = "us-east-1",
    ) -> None:
        """
        Class Constructor
        """

        self.path = path
        self.bucket_name = bucket_name
        self.timestream_db = timestream_db
        self.timestream_table = timestream_table
        self.profile = profile
        self.concurrency_limit = concurrency_limit
        self.allow_delete = allow_delete
        self.slack_token = slack_token
        self.slack_channel = slack_channel
        self.backtrack = backtrack
        self.backtrack_date = backtrack_date
        self.use_fallback = use_fallback
        self.file_logging = file_logging
        self.boto3_logging = boto3_logging
        self.test_iam_policy = test_iam_policy
        self.check_s3 = check_s3
        self.aws_region = aws_region


def create_argparse() -> ArgumentParser:
    """
    Function to initialize the Argument Parser with the arguments to be parsed and return the Arguments Parser

    :return: Argument Parser
    :rtype: argparse.ArgumentParser
    """
    # Initialize Argument Parser
    parser = ArgumentParser()

    # Add Argument to parse directory path to be watched
    parser.add_argument("-d", "--directory", help="Directory Path to be Watched")

    # Add Argument to parse S3 Bucket Name to upload files to
    parser.add_argument("-b", "--bucket_name", help="User name")

    # Add Argument to parse Timestream Database Name
    parser.add_argument("-t", "--timestream_db", help="Timestream Database Name")

    # Add Argument to parse Timestream Table Name
    parser.add_argument("-tt", "--timestream_table", help="Timestream Table Name")

    # Add Argument to profile to use when connecting to AWS
    parser.add_argument(
        "-p", "--profile", help="AWS Profile to use when connecting to AWS"
    )

    # Add Argument to parse the concurrency limit
    parser.add_argument(
        "-c",
        "--concurrency_limit",
        type=int,
        help="Concurrency Limit for the File System Watcher",
    )

    # Add Argument to parse the allow delete flag
    parser.add_argument(
        "-a",
        "--allow_delete",
        action="store_true",
        help="Allow Delete Flag for the File System Watcher",
    )

    # Add Argument to parse the backtrack flag
    parser.add_argument(
        "-bt",
        "--backtrack",
        action="store_true",
        help="Backtrack Flag for the File System Watcher",
    )

    # Add Argument to parse the backtrack datetime
    parser.add_argument(
        "-bd",
        "--backtrack_date",
        help="Backtrack Datetime for the File System Watcher",
    )

    # Add Argument to parse slack token
    parser.add_argument(
        "-s",
        "--slack_token",
        help="Token for Slack to send notifications",
    )

    # Add Argument to parse slack channel
    parser.add_argument(
        "-sc",
        "--slack_channel",
        help="Channel for Slack to send notifications",
    )

    # Add Argument to parse the fallback flag
    parser.add_argument(
        "-f",
        "--use_fallback",
        action="store_true",
        help="Use Fallback Flag for the File System Watcher",
    )

    # Add Argument to parse the file logging flag
    parser.add_argument(
        "-fl",
        "--file_logging",
        action="store_true",
        help="File Logging Flag for the File System Watcher",
    )

    # Add Argument to parse the boto3 logging flag
    parser.add_argument(
        "-bl",
        "--boto3_logging",
        action="store_true",
        help="Boto3 Logging Flag for the File System Watcher",
    )

    # Add Argument to parse the test IAM policy flag
    parser.add_argument(
        "-tp",
        "--test_iam_policy",
        action="store_true",
        help="Test IAM Policy Flag for the File System Watcher",
    )

    # Add Argument to parse the check S3 bucket flag
    parser.add_argument(
        "-cs",
        "--check_s3",
        action="store_true",
        help="Check S3 Bucket Flag for the File System Watcher",
    )

    # Add Argument to parse the AWS region
    parser.add_argument(
        "-ar",
        "--aws_region",
        help="AWS Region for the File System Watcher",
    )

    # Return the Argument Parser
    return parser


def parse_args(parser: ArgumentParser) -> dict:
    """
    Function to get the parsed arguments and return them as a dictionary

    :param parser: Arguments Parser
    :type parser: argparse.ArgumentParser
    :return: Dictionary of arguments
    :rtype: dict
    """
    # Parse the arguments
    args = parser.parse_args()

    # Initialize the arguments dictionary
    args_dict = {
        "path": args.directory,
        "bucket_name": args.bucket_name,
        "timestream_db": args.timestream_db,
        "timestream_table": args.timestream_table,
        "profile": args.profile,
        "concurrency_limit": args.concurrency_limit,
        "allow_delete": args.allow_delete,
        "slack_token": args.slack_token,
        "slack_channel": args.slack_channel,
        "backtrack": args.backtrack,
        "backtrack_date": args.backtrack_date,
        "use_fallback": args.use_fallback,
        "file_logging": args.file_logging,
        "boto3_logging": args.boto3_logging,
        "test_iam_policy": args.test_iam_policy,
        "check_s3": args.check_s3,
        "aws_region": args.aws_region,
    }

    # Return the arguments dictionary
    return args_dict


def validate_config(config: dict) -> bool:
    """
    Function to validate the configuration and return True if the configuration is valid, False otherwise

    :param config: Configuration dictionary
    :type config: dict
    :return: True if the configuration dictionary is valid, False otherwise
    :rtype: bool
    """
    return all(config.get(key) for key in ["path", "bucket_name"])


def get_config() -> FileSystemHandlerConfig:
    """
    Function to generate the FileSystemHandlerConfig object from the arguments. If the arguments are valid, the FileSystemHandlerConfig object is generated from the arguments. If the arguments are not valid, the program exits.

    :return: FileSystemHandlerConfig object
    :rtype: FileSystemHandlerConfig
    """
    # Get the arguments
    args = parse_args(create_argparse())

    if validate_config(args):
        config = FileSystemHandlerConfig(**args)
    else:
        log.error(
            "Invalid configuration, please provide a directory path and S3 bucket name"
        )
        exit(1)

    # Return the FileSystemHandlerConfig object
    return config
