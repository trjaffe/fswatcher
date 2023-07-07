#! /bin/bash

# Script to build and run the FSWatcher docker container

# Default config file
CONFIG_FILE="fswatcher.config"

# Parse the options
while getopts "c:" opt; do
    case $opt in
        c)
            CONFIG_FILE=$OPTARG
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2
            exit 1
            ;;
    esac
done

# Verify the config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Config file $CONFIG_FILE does not exist"
    exit 1
fi

# Get variables
source $CONFIG_FILE

# Verify that the directory to be watched exists
if [ ! -d "$WATCH_DIR" ]; then
    echo "Directory $WATCH_DIR does not exist"
    exit 1
fi

# If the script is not located in the scripts directory, then change the path to the scripts directory
if [ "$(basename $SCRIPT_PATH)" != "scripts" ]; then
    SCRIPT_PATH="$SCRIPT_PATH/scripts"
fi

# Print Script path
echo "Script path: $SCRIPT_PATH"

# Get path of the dockerfile which is in the upper directory
DOCKERFILE_PATH=$(dirname $SCRIPT_PATH)

# Print Dockerfile path
echo "Dockerfile path: $DOCKERFILE_PATH"

# Stop the docker container using the stop_docker_container.sh script
$SCRIPT_PATH/stop_docker_container.sh -c $CONFIG_FILE

# Build the docker image
echo "Building docker image $IMAGE_NAME"
docker build -t $IMAGE_NAME $DOCKERFILE_PATH

# Run the docker container
echo "Running docker container $CONTAINER_NAME"

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
    SDC_AWS_PROFILE="-p '$PROFILE'"
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

# Run the docker container in detached mode
docker run -d \
    --name $CONTAINER_NAME \
    --restart=always \
    -e SDC_AWS_S3_BUCKET="$SDC_AWS_S3_BUCKET" \
    -e SDC_AWS_CONCURRENCY_LIMIT="$SDC_AWS_CONCURRENCY_LIMIT" \
    -e SDC_AWS_TIMESTREAM_DB="$SDC_AWS_TIMESTREAM_DB" \
    -e SDC_AWS_TIMESTREAM_TABLE="$SDC_AWS_TIMESTREAM_TABLE" \
    -e SDC_AWS_SLACK_TOKEN="$SDC_AWS_SLACK_TOKEN" \
    -e SDC_AWS_SLACK_CHANNEL="$SDC_AWS_SLACK_CHANNEL" \
    -e SDC_AWS_ALLOW_DELETE="$SDC_AWS_ALLOW_DELETE" \
    -e SDC_AWS_BACKTRACK="$SDC_AWS_BACKTRACK" \
    -e SDC_AWS_BACKTRACK_DATE="$SDC_AWS_BACKTRACK_DATE" \
    -e SDC_AWS_AWS_REGION="$SDC_AWS_AWS_REGION" \
    -e SDC_AWS_FILE_LOGGING="$SDC_AWS_FILE_LOGGING" \
    -e SDC_AWS_CHECK_S3="$SDC_AWS_CHECK_S3" \
    -e SDC_AWS_BOTO3_LOGGING="$SDC_AWS_BOTO3_LOGGING" \
    -e SDC_AWS_TEST_IAM_POLICY="$SDC_AWS_TEST_IAM_POLICY" \
    -e SDC_AWS_USE_FALLBACK="$SDC_AWS_USE_FALLBACK" \
    -e SDC_AWS_PROFILE="$SDC_AWS_PROFILE" \
    -e AWS_SESSION_TOKEN="$AWS_SESSION_TOKEN" \
    -v /etc/passwd:/etc/passwd \
    -v $WATCH_DIR:/watch \
    -v $HOME/.aws/credentials:/root/.aws/credentials:ro \
    -v $LOG_DIR:/fswatcher/logs \
    $IMAGE_NAME

# Print the docker logs
echo "Docker logs"

# Docker ps
docker ps

# Path: scripts/run_docker_container.sh