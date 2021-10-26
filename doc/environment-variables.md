# Environment Variables

This page references the environment variables to pass to the Docker containers of the solution.

## Change pooler

Environment variable name |Environment variable description | Default value
---- | ---- | ----
AWS_REGION | AWS Region name where your AWS resources reside. Example: `us-east-1` | *No default value*
RPACS_SQS_QUEUE_URL | URL of the SQS queue to which messages are published | *No default value*
RPACS_POSTGRESQL_HOSTNAME | DNS hostname or IP address of the PostgreSQL database instance | *No default value*
RPACS_POSTGRESQL_PORT | [Optional] TCP port of the PostgreSQL database | 5432
RPACS_POSTGRESQL_USERNAME | User name to use to connect to the PostgreSQL database | *No default value*
RPACS_POSTGRESQL_PASSWORD | Password to use to connect to the PostgreSQL database | *No default value*
RPACS_POSTGRESQL_DB_NAME | Name of the database to use in the PostgreSQL database instance | *No default value*
RPACS_ORTHANC_HOSTNAME | Hostname of the Orthanc server from which changes should be detected. The value you provide must start with `http://` or `https://` and must not end with `/` | *No default value*
RPACS_ORTHANC_USERNAME | User name to use to connect to the Orthanc server | *No default value*
RPACS_ORTHANC_PASSWORD | Password to use to connect to the Orthanc server | *No default value*
RPACS_LOG_LEVEL | Logging level. See possible variable in the [logging](https://docs.python.org/3/library/logging.html#logging-levels) module documentation | INFO
RPACS_LOG_RECORD_TIME | Preprend the log messages with the date and time if this variable equals `yes` | no
RPACS_LOG_FUNCTION_NAME | Prepend the log messages with the Python package and function names if this variable equals `yes` | no

## De-identifier

Environment variable name |Environment variable description | Default value
---- | ---- | ----
AWS_REGION | AWS Region name where the AWS resources reside. Example: `us-east-1` | *No default value*
RPACS_REKOGNITION_REGION | AWS region where the Amazon Rekognition endpoint is used. It may differ from `AWS_REGION` because Amazon Rekognition is not available in every region | Same value than `AWS_REGION`
RPACS_SQS_QUEUE_URL | URL of the SQS queue to which messages are published | *No default value*
RPACS_SQS_VISIBILITY_TIMEOUT | [Optional] Number of seconds during which Amazon SQS prevents other consumers from receiving and processing the current message | 120
RPACS_SQS_MAX_ATTEMPTS | [Optional] Number of times a message can be received and attempted to be processed before it is removed from the queue. The message returns to the queue if a Python exception is raised while it is processed | 3
RPACS_POSTGRESQL_HOSTNAME | DNS hostname or IP address of the PostgreSQL database instance | *No default value*
RPACS_POSTGRESQL_PORT | [Optional] TCP port of the PostgreSQL database | 5432
RPACS_POSTGRESQL_USERNAME | User name to use to connect to the PostgreSQL database | *No default value*
RPACS_POSTGRESQL_PASSWORD | Password to use to connect to the PostgreSQL database | *No default value*
RPACS_POSTGRESQL_DB_NAME | Name of the database to use in the PostgreSQL database instance | *No default value*
RPACS_SOURCE_ORTHANC_HOSTNAME | Hostname of the Orthanc server that stores the original DICOM instances. The value you provide must start with `http://` or `https://` and must not end with `/` | *No default value*
RPACS_SOURCE_ORTHANC_USERNAME | User name to use to connect to the Orthanc server | *No default value*
RPACS_SOURCE_ORTHANC_PASSWORD | Password to use to connect to the Orthanc server | *No default value*
RPACS_DESTINATION_ORTHANC_HOSTNAME | Hostname of the Orthanc server that stores the de-identified DICOM instances. The value you provide must start with `http://` or `https://` and must not end with `/` | *No default value*
RPACS_DESTINATION_ORTHANC_USERNAME | User name to use to connect to the Orthanc server | *No default value*
RPACS_DESTINATION_ORTHANC_PASSWORD | Password to use to connect to the Orthanc server | *No default value*
RPACS_DEFAULT_CONFIG_FILE | Location of the YAML file that contains the default labelling, forwarding and transformation rules. You can provide a location to a S3 object with `s3://bucket/key` or to a local or locally-mounted file | *No default value*
RPACS_PRESERVE_ORIGINAL_FILES | Indicates whether the original DICOM files are removed from the Orthanc server after de-identification (`no`, default behavior), or left in the Orthanc server and you are responsible for deleting them if needed (`yes`) | no
RPACS_LOG_LEVEL | Logging level. See possible variable in the [logging](https://docs.python.org/3/library/logging.html#logging-levels) module documentation | INFO
RPACS_LOG_RECORD_TIME | Preprend the log messages with the date and time if this variable equals `yes` | no
RPACS_LOG_FUNCTION_NAME | Prepend the log messages with the Python package and function names if this variable equals `yes` | no

## Website

Environment variable name |Environment variable description | Default value
---- | ---- | ----
AWS_REGION | AWS Region name where the AWS resources reside. Example: `us-east-1` | *No default value*
RPACS_SQS_QUEUE_URL | URL of the SQS queue to which messages are published | *No default value*
RPACS_POSTGRESQL_HOSTNAME | DNS hostname or IP address of the PostgreSQL database instance | *No default value*
RPACS_POSTGRESQL_PORT | [Optional] TCP port of the PostgreSQL database | 5432
RPACS_POSTGRESQL_USERNAME | User name to use to connect to the PostgreSQL database | *No default value*
RPACS_POSTGRESQL_PASSWORD | Password to use to connect to the PostgreSQL database | *No default value*
RPACS_POSTGRESQL_DB_NAME | Name of the database to use in the PostgreSQL database instance | *No default value*
RPACS_ORTHANC_HOSTNAME | Hostname of the Orthanc server that stores the de-identified DICOM instances. The value you provide must start with `http://` or `https://` and must not end with `/` | *No default value*
RPACS_ORTHANC_USERNAME | User name to use to connect to the Orthanc server | *No default value*
RPACS_ORTHANC_PASSWORD | Password to use to connect to the Orthanc server | *No default value*
RPACS_PERMISSIONS_FILE | Location of the YAML file that contains the profile definitions and the mapping between users, groups and profiles. You can provide a location to a S3 object with `s3://bucket/key` or to a local or locally-mounted file | *No default value*
RPACS_LOG_FILE | Location of the file where access logs are appended. You must provide a local or locally-mounted file | *No default value*
RPACS_LOG_EXCLUDED_PREFIXES | [Optional] List of request path prefixes, separated by a comma, that are not recorded into the access log file. By default, requests to the healthcheck URL or to the Orthanc Explorer static files are not recorded | /healthcheck,/app/
RPACS_LOG_EXCLUDED_SUFFIXES | [Optional] List of request path suffixes, separated by a comma, that are not recorded into the access log file. By default, requests to JS, CSS and ICO files are excluded | .ico,.js,.css
RPACS_COGNITO_CLAIM_USERNAME | [Optional] Name of the claim in the OpenID tokens (ID token or access token) that contains the username | username
RPACS_COGNITO_CLAIM_GROUPS | [Optional] Name of the claim in the OpenID tokens (ID token or access token) that contains the list of user groups | cognito:groups
RPACS_RESULTS_PER_PAGE | [Optional] Number of DICOM instances displayed in each Search results page | 200
RPACS_SERIES_HEADER_KEYWORDS | [Optional] List of top-level tag keywords, separated by a comma, to display for a Series header in the Search results page | Modality,StudyDescription,SeriesDescription
RPACS_INSTANCE_HEADER_KEYWORDS | [Optional] List of top-level tag keywords, separated by a comma, to display for a Instance header in the Search results page | InstanceNumber
RPACS_USER_GUIDE_URL | [Optional] URL of the user guide (button "Read the User Guide" in the home page). Default is the User Guide in the GitHub repository | *No default value*
RPACS_SIGN_OUT_URL | Amazon Cognito URL where users must be redirected after logout. This will usually be `https://[name].auth.eu-west-1.amazoncognito.com/logout?client_id=[client_id]&logout_uri=[alb_url]` | *No default value*
RPACS_LOG_LEVEL | Logging level. See possible variable in the [logging](https://docs.python.org/3/library/logging.html#logging-levels) module documentation | INFO
RPACS_LOG_RECORD_TIME | Preprend the log messages with the date and time if this variable equals `yes` | no
RPACS_LOG_FUNCTION_NAME | Prepend the log messages with the Python package and function names if this variable equals `yes` | no

## Website worker

Environment variable name |Environment variable description | Default value
---- | ---- | ----
AWS_REGION | AWS Region name where the AWS resources reside. Example: `us-east-1` | *No default value*
RPACS_SQS_QUEUE_URL | URL of the SQS queue to which messages are published | *No default value*
RPACS_SQS_VISIBILITY_TIMEOUT | [Optional] Number of seconds during which Amazon SQS prevents other consumers from receiving and processing the current message | 120
RPACS_SQS_MAX_ATTEMPTS | [Optional] Number of times a message can be received and attempted to be processed before it is removed from the queue. The message returns to the queue if a Python exception is raised while it is processed | 3
RPACS_POSTGRESQL_HOSTNAME | DNS hostname or IP address of the PostgreSQL database instance | *No default value*
RPACS_POSTGRESQL_PORT | [Optional] TCP port of the PostgreSQL database | 5432
RPACS_POSTGRESQL_USERNAME | User name to use to connect to the PostgreSQL database | *No default value*
RPACS_POSTGRESQL_PASSWORD | Password to use to connect to the PostgreSQL database | *No default value*
RPACS_POSTGRESQL_DB_NAME | Name of the database to use in the PostgreSQL database instance | *No default value*
RPACS_ORTHANC_HOSTNAME | Hostname of the Orthanc server that stores the de-identified DICOM instances. The value you provide must start with `http://` or `https://` and must not end with `/` | *No default value*
RPACS_ORTHANC_USERNAME | User name to use to connect to the Orthanc server | *No default value*
RPACS_ORTHANC_PASSWORD | Password to use to connect to the Orthanc server | *No default value*
RPACS_LOG_LEVEL | Logging level. See possible variable in the [logging](https://docs.python.org/3/library/logging.html#logging-levels) module documentation | INFO
RPACS_LOG_RECORD_TIME | Preprend the log messages with the date and time if this variable equals `yes` | no
RPACS_LOG_FUNCTION_NAME | Prepend the log messages with the Python package and function names if this variable equals `yes` | no

# Orthanc

See the [Orthanc Configuration](config-orthanc.md) page.
