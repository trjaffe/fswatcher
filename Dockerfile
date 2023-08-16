## Dockerfile for building a container that runs fswatcher

# Base image
FROM python:3.11

# Install Curl, Unzip, and PostgreSQL client library
RUN apt-get update  && \
    apt-get install --no-install-recommends -y curl unzip libpq-dev gcc && \
    # Clean up
    rm -rf /var/lib/apt/lists/*

# Install AWS CLI v2
RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" && \
    unzip awscliv2.zip && \
    ./aws/install

# Add files to the container
COPY . /fswatcher

# Set the working directory
WORKDIR /fswatcher

# Update pip and setuptools, also install setuptools_scm
RUN pip install --no-cache-dir --upgrade pip setuptools setuptools_scm && \
    # Clean up
    rm -rf /root/.cache/pip

# Install dependencies
RUN pip install --no-cache-dir --upgrade -r /fswatcher/requirements.txt && \
    # Clean up
    rm -rf /root/.cache/pip

# Install fswatcher
RUN pip install --no-cache-dir . && \
    # Clean up
    rm -rf /root/.cache/pip

# Run fswatcher
CMD python fswatcher/__main__.py -d /watch $SDC_AWS_S3_BUCKET $SDC_AWS_TIMESTREAM_DB $SDC_AWS_TIMESTREAM_TABLE $SDC_AWS_CONCURRENCY_LIMIT $SDC_AWS_ALLOW_DELETE $SDC_AWS_SLACK_TOKEN $SDC_AWS_SLACK_CHANNEL $SDC_AWS_BACKTRACK $SDC_AWS_BACKTRACK_DATE $SDC_AWS_AWS_REGION $SDC_AWS_FILE_LOGGING $SDC_AWS_CHECK_S3 $SDC_AWS_BOTO3_LOGGING $SDC_AWS_TEST_IAM_POLICY $SDC_AWS_USE_FALLBACK $SDC_AWS_PROFILE
