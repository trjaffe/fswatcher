# FSWatcher Utility

This is a filewatcher system that can be configured to watch a directory for new files and then upload them to an [AWS S3 bucket](https://aws.amazon.com/s3/). It supports two modes of functionality for finding new/modified/deleted files, the filesystem notification utilizing the python [watchdog](https://pypi.org/project/watchdog/) package, or a fallback function (Linux Only) which utilizes the find Linux Subsystem.

FSWatcher also tags the objects with the creation and modified time, to keep that information on the cloud as well. This is useful for keeping a backup of files on the cloud, or for keeping a copy of files that are being created on a local machine. 

You also can configure the system to log the `CREATE`, `UPDATE`, `PUT` and `DELETE` events to a Timestream table, so you can keep track of the files that are being created, modified or deleted in near realtime. This will allow for extra visibility of the AWS SDC Pipeline from the SDC External Server to the S3 Bucket.

As well as the ability to configure slack notification for when new Files are detected and if there is a manifest file it lists the content of the file in the slack message.

## Table of Contents
- [FSWatcher](#fswatcher)
  - [Table of Contents](#table-of-contents)
    - [Configurable Variables](#configurable-variables)
  - [Installation](#installation)
    - [Requirements](#requirements)
    - [Example configuration file](#example-configuration-file)
    - [Setup](#setup)
  - [Usage](#usage)
    - [Adding files](#adding-files)
    - [Modifying files](#modifying-files)
    - [Docker Usage](#docker-usage)
  - [Logs](#logs)
  - [Uninstall](#uninstall)
  - [License](#license)
  - [Contributing](#contributing)
  - [Code of Conduct](#code-of-conduct)
  - [Acknowledgements](#acknowledgements)
  - [Public Domain](#public-domain)


## Configurable Variables
There are a multitude of configurable environmental variables that can be set in the `scripts/fswatcher.config` file or in the docker run command. The variables and what they represent are as follows:

* `CONTAINER_NAME` - Name of the Docker Container.
* `IMAGE_NAME` - Name of the Docker Image.
* `S3_BUCKET_NAME` - The AWS S3 bucket that will be used to store the files. You can also specify directories in the bucket.
* `AWS_REGION` - The AWS region for the Timestream database.
* `CONCURRENCY_LIMIT` - The limit for concurrent uploads to S3.
* `TEST_IAM_POLICY` - If enabled, it runs a push/delete with a generated test file to ensure the IAM policy is set correctly.
* `WATCH_DIR` - The directory that will be watched for new files. The directory should exist before running.
* `SCRIPT_PATH` - The path of the current working directory (where the script is located).
* `ALLOW_DELETE` - A flag to allow the deletion of files from S3 if they are deleted from the watch directory.
* `BACKTRACK` - A flag to allow backtracking of files to match the watch directory.
* `BACKTRACK_DATE` - The date to backtrack to. (Optional)
* `CHECK_S3` - If enabled, it checks against S3 when backtracking.
* `USE_FALLBACK` - If enabled, it uses a fallback watcher. This is Linux-only and uses a slower directory walking and DB lookup method. It might work better for larger filesystems and files that might not cause any FSEvents to be created.
* `FILE_LOGGING` - If enabled, it stores a log file within the container.
* `LOG_DIR` - The directory for logging if you'd like to persist the log to your host system.
* `BOTO3_LOGGING` - If enabled, it activates Botocore logging for more in-depth logs.
* `TIMESTREAM_DB` - The name of the Timestream database. (Optional)
* `TIMESTREAM_TABLE` - The name of the Timestream table. (Optional)
* `SLACK_TOKEN` - The Slack token for sending logs to Slack. (Optional)
* `SLACK_CHANNEL` - The Slack channel for sending logs to Slack. (Optional)

## Installation
### Requirements
- Python 3.6+
- AWS CLI
- AWS S3 Bucket
- Docker
- AWS Timestream Table (optional)
- Slack OAuth Token and Channel (optional)

### Example configuration file
```
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
S3_BUCKET_NAME=s3_bucket_name

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
WATCH_DIR=~/fswatcher/test

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
USE_FALLBACK=true

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
```
### Setup
1. Clone the repository

    ```git clone git@github.com:HERMES-SOC/fswatcher.git```

2. Configure the `fswatcher.config` in the `scripts` folder. Look at [Configurable Variables](#configurable-variables) for more information on the variables.

3. Verify your AWS CLI is configured with access keys (Optional)

    ```aws configure```

    Note: It must have access to the S3 bucket and Timestream table without MFA(if you want to use it)


4. Run the container run script

    ```cd scripts && ./run_docker_container```

    Note: This will build and run the docker container in detached mode with your container running

5. Verify the service is running

    ```docker logs <name-of-container>```


## Usage
### Adding files
1. Add a file to the `SDC_AWS_WATCH_PATH` directory

    ```touch /path/to/SDC_AWS_WATCH_PATH/test.txt```

2. Verify the file was uploaded to the `SDC_AWS_S3_BUCKET` bucket

    ```aws s3 ls s3://SDC_AWS_S3_BUCKET/```

3. Verify the file was tagged with the creation and modified time

    ```aws s3api head-object --bucket SDC_AWS_S3_BUCKET --key test.txt```

4. Verify the file was logged to the `SDC_AWS_TIMESTREAM_TABLE` table (optional)

    ```aws timestream-query query --query-string "SELECT * FROM SDC_AWS_TIMESTREAM_DB.SDC_AWS_TIMESTREAM_TABLE"```

### Modifying files
1. Modify the file in the `SDC_AWS_WATCH_PATH` directory

    ```echo "test" >> /path/to/SDC_AWS_WATCH_PATH/test.txt```

2. Verify the file was uploaded to the `SDC_AWS_S3_BUCKET` bucket

    ```aws s3 ls s3://SDC_AWS_S3_BUCKET/```

3. Verify the file was tagged with the creation and modified time

    ```aws s3api head-object --bucket SDC_AWS_S3_BUCKET --key test.txt```

4. Verify the file was logged to the `SDC_AWS_TIMESTREAM_TABLE` table (optional)

    ```aws timestream-query query --query-string "SELECT * FROM SDC_AWS_TIMESTREAM_DB.SDC_AWS_TIMESTREAM_TABLE"```

## Logs
There are two ways to view the logs of the filewatcher system. You can view the logs in the directory within the container which contains the script within the `fswatcher.log` file (If you have set file logging on). Also if you choose to persist it to your host directory you can view it wherever you define in the config file.

Or if you'd like to see the logs of the docker container you can also run:
    
    docker logs <name-of-fswatcher-container> 

## Uninstall
Script:
1. Run the uninstall script

    ```cd scripts && ./stop_docker_container```

2. Verify the service is not running

    ```docker ps```


Manually:

1. Stop Container with Docker

    ```docker stop <name-of-fswatcher-container>```

2. Remove Container with Docker

    ```docker rm <name-of-fswatcher-container>```

3. Remove Image with Docker

    ```docker image rm <image-name>```

## License
FSWatcher is licensed under the MIT License. Please check the [LICENSE](LICENSE) file in the repo for more information.

## Contributing

We love contributions! This project is open source,
built on open source, and we'd love to have you hang out in our community.

**Imposter syndrome disclaimer**: We want your help. No, really.

There may be a little voice inside your head that is telling you that you're not
ready to be an open source contributor; that your skills aren't nearly good
enough to contribute. What could you possibly offer a project like this one?

We assure you - the little voice in your head is wrong. If you can write code at
all, you can contribute code to open source. Contributing to open source
projects is a fantastic way to advance one's coding skills. Writing perfect code
isn't the measure of a good developer (that would disqualify all of us!); it's
trying to create something, making mistakes, and learning from those
mistakes. That's how we all improve, and we are happy to help others learn.

Being an open source contributor doesn't just mean writing code, either. You can
help out by writing documentation, tests, or even giving feedback about the
project (and yes - that includes giving feedback about the contribution
process). Some of these contributions may be the most valuable to the project as
a whole, because you're coming to the project with fresh eyes, so you can see
the errors and assumptions that seasoned contributors have glossed over.

Note: This disclaimer was originally written by
`Adrienne Lowe <https://github.com/adriennefriend>`_ for a
`PyCon talk <https://www.youtube.com/watch?v=6Uj746j9Heo>`_, and was adapted by
by this project based on its use in the README file for the
`MetPy project <https://github.com/Unidata/MetPy>`_.

## Code of Conduct
When you are interacting with the HERMES-SOC community you are asked to follow
our `Code of Conduct <https://github.com/HERMES-SOC/code-of-conduct/blob/main/CODE_OF_CONDUCT.md>`_.

## Acknowledgements

The package template utilizes the [watchdog](https://pypi.org/project/watchdog/) python package. 

## Public Domain
This project constitutes a work of the United States Government and is not subject to domestic copyright protection under `17 USC § 105 <https://www.govinfo.gov/app/details/USCODE-2010-title17/USCODE-2010-title17-chap1-sec105>`__. Additionally, we waive copyright and related rights in the work worldwide through the `CC0 1.0 Universal public domain dedication <https://creativecommons.org/publicdomain/zero/1.0/>`__.

All contributions to this project will be released under the CC0
dedication. By submitting a pull request, you are agreeing to comply
with this waiver of copyright interest.