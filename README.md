# FSWatcher Utility

This is a filewatcher system that can be configured to watch a directory for new files and then upload them to an S3 bucket. It also tags the objects with the creation and modified time, to keep that information on the cloud as well. This is useful for keeping a backup of files on the cloud, or for keeping a copy of files that are being created on a local machine. You also can configure the system to log the `CREATE`, `UPDATE`, `PUT` and `DELETE` events to a Timestream table, so you can keep track of the files that are being created, modified or deleted in near realtime. This will allow for extra visibility of the AWS SDC Pipeline from the SDC External Server to the S3 Bucket.

## Table of Contents
- [FSWatcher](#fswatcher)
  - [Table of Contents](#table-of-contents)
    - [Configurable Variables](#configurable-variables)
  - [Installation](#installation)
    - [Requirements](#requirements)
    - [Setup](#setup)
  - [Usage](#usage)
    - [Adding files](#adding-files)
    - [Modifying files](#modifying-files)
    - [Docker Usage](#docker-usage)
  - [Logs](#logs)
  - [Uninstall](#uninstall)
## Configurable Variables
There are a multitude of configurable variables that can be set in the `config.json` file or in the docker run command. The variables and what they represent are as follows:

* `SDC_SYSTEM_USER` is the user that will be used to run the script. It must have access keys set up to the `SDC_AWS_S3_BUCKET`, `SDC_AWS_TIMESTREAM_DB` and `SDC_AWS_TIMESTREAM_TABLE` without MFA.

* `SDC_AWS_S3_BUCKET` is the S3 bucket that will be used to store the files. (**Required**)

* `SDC_AWS_WATCH_PATH` is the directory that will be watched for new files. (**Required**)

* `SDC_AWS_TIMESTREAM_DB` is the Timestream database that will be used to store the logs. (*Optional*)

* `SDC_AWS_TIMESTREAM_TABLE` is the Timestream table that will be used to store the logs. (*Optional*)

* `SDC_AWS_TIMESTREAM_TABLE` is the Region the timestream db is located in. (*Required if above two are added*)

* `SDC_AWS_PROFILE` is the AWS Profile to use for authentication. (*Optional*)

* `SDC_AWS_CONCURRENCY_LIMIT` is the Concurrent uploads limit to S3. (*Optional*)

* `SDC_AWS_ALLOW_DELETE` is a flag to Delete files from S3 if they are deleted from the watch directory. (*Optional*)

## Installation
### Requirements
- Python 3.6+
- AWS CLI
- AWS SDC External Server
- AWS S3 Bucket
- Conda environment (optional)
- AWS Timestream Table (optional)


### Setup
1. Clone the repository

    ```git clone git@github.com:HERMES-SOC/fswatcher.git```

2. Install the requirements

    ```pip install -r requirements.txt```

3. Verify your AWS CLI is configured with access keys (Optional)

    ```aws configure```

    Note: It must have access to the S3 bucket and Timestream table without MFA(if you want to use it)

4. Configure the `config.json` file with your `SDC_SYSTEM_USER`, `SDC_AWS_S3_BUCKET`, `SDC_AWS_WATCH_PATH`, `SDC_AWS_TIMESTREAM_DB`, `SDC_AWS_TIMESTREAM_TABLE`. 


5. Run the install script

    ```sudo python install.py```

    Note: This will create a service called `fswatcher` that will run the `fswatcher.py` script on boot.

6. Verify the service is running

    ```sudo systemctl status fswatcher.service```

    Note: If the service is not running/errored out, you can check the logs with `sudo journalctl -u fswatcher.service -n 100`


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

### Docker Usage
1. Build the docker image

    ```docker build -t fswatcher .```

2. Run the docker image replacing the environment variables with your values and mounting the `SDC_AWS_WATCH_PATH` directory. The variable names match up with the ones found in configurable variables above. The only things that are required are the `SDC_AWS_S3_BUCKET` and `SDC_AWS_WATCH_PATH` variables. The rest are optional, and you can remove the line you don't want to use in the docker run command.

    ```bash
    docker run -d --restart=always \
    -e SDC_AWS_S3_BUCKET='-b <SDC_AWS_S3_BUCKET>' \
    -e SDC_AWS_TIMESTREAM_DB='-t <SDC_AWS_TIMESTREAM_DB>' \
    -e SDC_AWS_TIMESTREAM_TABLE='-tt <SDC_AWS_TIMESTREAM_TABLE>' \
    -e AWS_REGION='<SDC_AWS_TIMESTREAM_REGION>' \
    -e SDC_AWS_PROFILE='-p <SDC_AWS_PROFILE>' \
    -e SDC_AWS_CONCURRENCY_LIMIT='-c <SDC_AWS_CONCURRENCY_LIMIT>' \
    -e SDC_AWS_ALLOW_DELETE='-a <SDC_AWS_ALLOW_DELETE>' \
    -e SDC_AWS_SLACK_TOKEN='-s ' \
    -e SDC_AWS_SLACK_CHANNEL='-sc ' \
    -v /etc/passwd:/etc/passwd \
    -v <SDC_AWS_WATCH_PATH>:/watch \
    -v ${HOME}/.aws/credentials:/root/.aws/credentials:ro \
    fswatcher:latest
    ```

3. Verify the docker container is running

    ```docker ps```

## Logs
There are two ways to view the logs of the filewatcher system. You can view the logs in the directory which contains the script within the `hermes.log` file.

Or since it is installed as a service you can view the logs with `sudo journalctl -u fswatcher.service -n 100` or by viewing the logs in the `/var/log/fswatcher.log` file.

## Uninstall

1. Run the uninstall script

    ```sudo python uninstall.py```

2. Verify the service is not running

    ```sudo systemctl status fswatcher.service```

    Note: If the service is running/errored out, you can check the logs with `sudo journalctl -u sdc-aws-fswatcher.service -n 100`



