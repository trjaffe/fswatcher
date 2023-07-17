import os
import logging
import time
from datetime import datetime
from typing import Optional
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from fswatcher.FileSystemHandlerConfig import get_config

# Get the configuration dataclass object
config = get_config()

# Configure loggings
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# Create log file handler if file log environment variable is set
if config.file_logging == True:
    log.info("File logging enabled")
    file_handler = logging.FileHandler("logs/fswatcher.log")
    file_handler.setLevel(logging.INFO)

    # Create formatter and add it to the handlers
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)

    # Add the handlers to the logger
    log.addHandler(file_handler)

# Configure boto3 logging to debug
if config.boto3_logging == True:
    log.info("Boto3 logging enabled")
    boto3_log = logging.getLogger("botocore")
    boto3_log.setLevel(logging.DEBUG)


def is_file_manifest(file_name: str) -> bool:
    """
    Check if a file is a manifest file
    :param file_name: The name of the file to check
    :type file_name: str
    :return: True if the file is a manifest file, False otherwise
    :rtype: bool
    """

    # Get the basename of the file
    base_name = os.path.basename(file_name)

    # Check if the file starts with file_manifest prefix
    return base_name.startswith("file_manifest")


def generate_file_pipeline_message(
    file_path: str, alert_type: Optional[str] = None
) -> str:
    """
    Function to generate file pipeline message
    """

    # Remove the watch/ prefix from the file path
    parsed_file_path = file_path.replace("/watch/", "")
    if alert_type is not "delete":
        # Get the file name
        alert = {
            "upload": f"File Uploaded to S3 - ( _{parsed_file_path}_ )",
            "error": f"File Upload Failed - ( _{parsed_file_path}_ )",
        }
        slack_message = f"Science File - ( _{parsed_file_path}_ )"

        if is_file_manifest(file_path):
            slack_message = f"Manifest File - ( _{parsed_file_path}_ )"
            with open(file_path, "r") as file:
                secondary_message = file.read()

            return (slack_message, secondary_message)

        if alert_type:
            slack_message = alert[alert_type]
        return slack_message
    else:
        slack_message = "File Deleted - ( _{parsed_file_path}_ )"


def get_slack_client(slack_token: str) -> WebClient:
    """
    Initialize a Slack client using the provided token.
    :param slack_token: The Slack API token
    :type slack_token: str
    :return: The initialized Slack WebClient
    :rtype: WebClient
    """
    # If the slack token is not set, try to get it from the environment
    if not slack_token:
        slack_token = os.environ.get("SLACK_TOKEN")

    # If the slack token is still not set, return None
    if not slack_token:
        log.error(
            {
                "status": "ERROR",
                "message": "Slack Token is not set",
            }
        )
        return None

    # Initialize the slack client
    slack_client = WebClient(token=slack_token)

    return slack_client


def send_slack_notification(
    slack_client: WebClient,
    slack_channel: str,
    slack_message: str,
    alert_type: Optional[str] = None,
    slack_max_retries: int = 5,
    slack_retry_delay: int = 5,
    thread_ts: Optional[str] = None,
) -> bool:
    log.debug(f"Sending Slack Notification to {slack_channel}")
    color = {
        "success": "#2ecc71",
        "error": "#ff0000",
        "delete": "#ff0000",
        "upload": "#3498db",
        "info": "#3498db",
        "warning": "#f1c40f",
        "orange": "#f39c12",
        "purple": "#9b59b6",
        "black": "#000000",
        "white": "#ffffff",
    }
    ct = datetime.now()
    ts = ct.strftime("%y-%m-%d %H:%M:%S")
    attachments = []
    # Check if slack_message is a tuple
    if isinstance(slack_message, tuple):
        text = slack_message[0]
        attachments = [
            {
                "color": color["purple"],
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{slack_message[1]}",
                        },
                    }
                ],
                "fallback": f"{slack_message[1]}",
            }
        ]
        pretext = slack_message[0]
    else:
        text = slack_message
        pretext = slack_message
        if alert_type:
            attachments = [
                {
                    "color": color[alert_type],
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"{slack_message}",
                            },
                        }
                    ],
                }
            ]
            text = f'`{ts}` -'

    for i in range(slack_max_retries):
        try:
            slack_client.chat_postMessage(
                channel=slack_channel,
                text=text,
                pretext=pretext,
                attachments=attachments,
                thread_ts=thread_ts,  # Include the thread_ts parameter
            )

            log.debug(f"Slack Notification Successfully Sent to {slack_channel}")

            return True

        except SlackApiError as e:
            if (
                i < slack_max_retries - 1
            ):  # If it's not the last attempt, wait and try again
                log.warning(
                    f"Error sending Slack Notification (attempt {i + 1}): {e}."
                    f"Retrying in {slack_retry_delay} seconds..."
                )
                time.sleep(slack_retry_delay)
            else:  # If it's the last attempt, log the error and exit the loop
                log.error(
                    {
                        "status": "ERROR",
                        "message": f"Error sending Slack Notification (attempt {i + 1}): {e}",
                    }
                )
                raise e


def get_message_ts(
    slack_client: WebClient, slack_channel: str, text: str
) -> Optional[str]:
    try:
        response = slack_client.conversations_history(channel=slack_channel)
        messages = response["messages"]

        for message in messages:
            if "text" in message and message["text"] == text:
                return message["ts"]

        return None
    except SlackApiError as e:
        # Handle the exception according to your needs
        print(f"Error retrieving message_ts: {e}")
        return None


def timestream_log(
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
        log.error({"status": "ERROR", "message": f"Error logging to Timestream: {e}"})
