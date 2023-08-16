#!/bin/bash -x
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# if test -d "$SCRIPT_DIR/../venv";
# then
#     rm -rf "$SCRIPT_DIR/../venv"
# fi

pip install virtualenv
virtualenv venv
. $SCRIPT_DIR/../venv/bin/activate


pip install -r ../requirements.txt
pip install --no-cache-dir ../



# Environmental Variables for FSWatcher Docker Deployment

# ========================
# Docker configurations
# ========================
# Docker Container name
CONTAINER_NAME=fswatcher

# Docker Image name
IMAGE_NAME=fswatcher

# ========================
# AWS configurations
# ========================
# S3 bucket name (Note:Support directories as well s3-bucket-name/directory)
S3_BUCKET_NAME=dh-fornaxdev-public/Test/

# AWS region (Used for Timestream Database)
AWS_REGION="us-east-1"

# Concurrency limit (Limit of concurrent uploads)
CONCURRENCY_LIMIT=100

# IAM Policy Test - when enabled runs a push/delete with a generated test file to ensure policy is set correctly
TEST_IAM_POLICY=false

# ========================
# Directory to watch
# ========================
# Filepath to the directory to be watched (Needs to be created/existing before running)
WATCH_DIR=/home/phoenix/fswatcher/test

# Get path of current working directory (where the script is located)
SCRIPT_PATH=$(pwd)

# Allow Delete of files to match Watch Directory
ALLOW_DELETE=false

# Allow Backtrack of files to match Watch Directory
BACKTRACK=true

# Date to Backtrack to (Optional)
# BACKTRACK_DATE="2021-01-01"

# Check Against S3 when Backtracking
CHECK_S3=true

# Fallback Watcher (Linux Only), uses a slower directory walking and db lookup method. But should work better for larger filesystems and files that might not cause any FSEvents to be created
USE_FALLBACK=false

# ========================
# Logging configurations
# ========================
# File Logging (If you'd like to store a log file within the container)
# FILE_LOGGING=false

# Log Directory (If you'd like to persist the log to your host system)
# LOG_DIR=~/fswatcher_log

# Boto3 Logging, enables Botocore logging for more in depth logs
# BOTO3_LOGGING=false

# ========================
# TimeStream configurations (optional)
# ========================
# TimeStream database name (optional)
# TIMESTREAM_DB=""

# TimeStream table name (optional)
# TIMESTREAM_TABLE=""

# ========================
# Slack configurations (optional)
# ========================
# Slack token (optional)
# SLACK_TOKEN=slack_token

# Slack channel (optional)
# SLACK_CHANNEL=slack_channel_id

# Unset all the environment variables
unset SDC_AWS_S3_BUCKET
unset SDC_AWS_CONCURRENCY_LIMIT
unset SDC_AWS_TIMESTREAM_DB
unset SDC_AWS_TIMESTREAM_TABLE
unset SDC_AWS_SLACK_TOKEN
unset SDC_AWS_SLACK_CHANNEL
unset SDC_AWS_ALLOW_DELETE
unset SDC_AWS_BACKTRACK
unset SDC_AWS_BACKTRACK_DATE
unset SDC_AWS_AWS_REGION
unset SDC_AWS_FILE_LOGGING
unset SDC_AWS_BOTO3_LOGGING
unset SDC_AWS_TEST_IAM_POLICY
unset SDC_AWS_BACKTRACK
unset SDC_AWS_BACKTRACK_DATE
unset SDC_AWS_USE_FALLBACK
unset SDC_AWS_CHECK_S3
unset SDC_AWS_PROFILE

# Docker environment variables
SDC_AWS_S3_BUCKET="-b $S3_BUCKET_NAME"

SDC_AWS_CONCURRENCY_LIMIT="-c $CONCURRENCY_LIMIT"

# If TimeStream database name is not "", then add it to the environment variables else make it empty
if [ "$TIMESTREAM_DB" != "" ]; then
    SDC_AWS_TIMESTREAM_DB="-t $TIMESTREAM_DB"
else
    SDC_AWS_TIMESTREAM_DB=""
fi


# If Timestream table name is not "", then add it to the environment variables else make it empty
if [ "$TIMESTREAM_TABLE" != "" ]; then
    SDC_AWS_TIMESTREAM_TABLE="-tt $TIMESTREAM_TABLE"
else
    SDC_AWS_TIMESTREAM_TABLE=""
fi

# If Slack token is not "", then add it to the environment variables else make it empty
if [ "$SLACK_TOKEN" != "" ]; then
    SDC_AWS_SLACK_TOKEN="-s $SLACK_TOKEN"
else
    SDC_AWS_SLACK_TOKEN=""
fi

# If Slack channel is not "", then add it to the environment variables else make it empty
if [ "$SLACK_CHANNEL" != "" ]; then
    SDC_AWS_SLACK_CHANNEL="-sc $SLACK_CHANNEL"
else
    SDC_AWS_SLACK_CHANNEL=""
fi

# If ALLOW_DELETE is true, then add it to the environment variables else make it empty
if [ "$ALLOW_DELETE" = true ]; then
    SDC_AWS_ALLOW_DELETE="-a"
else
    SDC_AWS_ALLOW_DELETE=""
fi

# If BACKTRACK is true, then add it to the environment variables else make it empty
if [ "$BACKTRACK" = true ]; then
    SDC_AWS_BACKTRACK="-bt"
else
    SDC_AWS_BACKTRACK=""
fi

# If Slack channel is not "", then add it to the environment variables else make it empty
if [ "$BACKTRACK_DATE" != "" ]; then
    SDC_AWS_BACKTRACK_DATE="-bd '$BACKTRACK_DATE'"
else
    SDC_AWS_BACKTRACK_DATE=""
fi

# If FILE_LOGGING is true, then add it to the environment variables else make it empty
if [ "$FILE_LOGGING" = true ]; then
    SDC_AWS_FILE_LOGGING="-fl"
else
    SDC_AWS_FILE_LOGGING=""
fi

# If BOTO3_LOGGING is true, then add it to the environment variables else make it empty
if [ "$BOTO3_LOGGING" = true ]; then
    SDC_AWS_BOTO3_LOGGING="-bl"
else
    SDC_AWS_BOTO3_LOGGING=""
fi

# If TEST_IAM_POLICY is true, then add it to the environment variables else make it empty
if [ "$TEST_IAM_POLICY" = true ]; then
    SDC_AWS_TEST_IAM_POLICY="-tp"
else
    SDC_AWS_TEST_IAM_POLICY=""
fi

# If USE_FALLBACK is true, then add it to the environment variables else make it empty
if [ "$USE_FALLBACK" = true ]; then
    SDC_AWS_USE_FALLBACK="-f"
else
    SDC_AWS_USE_FALLBACK=""
fi

# If CHECK_S3 is true, then add it to the environment variables else make it empty
if [ "$CHECK_S3" = true ]; then
    SDC_AWS_CHECK_S3="-cs"
else
    SDC_AWS_CHECK_S3=""
fi


# If AWS_REGION is not "", then add it to the environment variables else make it empty
if [ "$AWS_REGION" != "" ]; then
    SDC_AWS_AWS_REGION="-ar $AWS_REGION"
else
    SDC_AWS_AWS_REGION="-ar us-east-1"
fi

# If PROFILE is not "", then add it to the environment variables else make it empty
if [ "$PROFILE" != "" ]; then
    SDC_AWS_PROFILE="-p $PROFILE"
else
    SDC_AWS_PROFILE=""
fi

# Print all the environment variables
echo "Passed Arguments:"
echo "SDC_AWS_S3_BUCKET: $SDC_AWS_S3_BUCKET"
echo "SDC_AWS_CONCURRENCY_LIMIT: $SDC_AWS_CONCURRENCY_LIMIT"
echo "SDC_AWS_TIMESTREAM_DB: $SDC_AWS_TIMESTREAM_DB"
echo "SDC_AWS_TIMESTREAM_TABLE: $SDC_AWS_TIMESTREAM_TABLE"
echo "SDC_AWS_SLACK_TOKEN: $SDC_AWS_SLACK_TOKEN"
echo "SDC_AWS_SLACK_CHANNEL: $SDC_AWS_SLACK_CHANNEL"
echo "SDC_AWS_ALLOW_DELETE: $SDC_AWS_ALLOW_DELETE"
echo "SDC_AWS_AWS_REGION: $SDC_AWS_AWS_REGION"
echo "SDC_AWS_FILE_LOGGING: $SDC_AWS_FILE_LOGGING"
echo "SDC_AWS_BOTO3_LOGGING: $SDC_AWS_BOTO3_LOGGING"
echo "SDC_AWS_TEST_IAM_POLICY: $SDC_AWS_TEST_IAM_POLICY"
echo "SDC_AWS_BACKTRACK: $SDC_AWS_BACKTRACK"
echo "SDC_AWS_BACKTRACK_DATE: $SDC_AWS_BACKTRACK_DATE"
echo "SDC_AWS_USE_FALLBACK: $SDC_AWS_USE_FALLBACK"
echo "SDC_AWS_CHECK_S3: $SDC_AWS_CHECK_S3"
echo "SDC_AWS_PROFILE: $SDC_AWS_PROFILE"

python3 ../fswatcher/__main__.py -d $WATCH_DIR $SDC_AWS_S3_BUCKET $SDC_AWS_TIMESTREAM_DB $SDC_AWS_TIMESTREAM_TABLE $SDC_AWS_CONCURRENCY_LIMIT $SDC_AWS_ALLOW_DELETE $SDC_AWS_SLACK_TOKEN $SDC_AWS_SLACK_CHANNEL $SDC_AWS_BACKTRACK $SDC_AWS_BACKTRACK_DATE $SDC_AWS_AWS_REGION $SDC_AWS_FILE_LOGGING $SDC_AWS_CHECK_S3 $SDC_AWS_BOTO3_LOGGING $SDC_AWS_TEST_IAM_POLICY $SDC_AWS_USE_FALLBACK $SDC_AWS_PROFILE
