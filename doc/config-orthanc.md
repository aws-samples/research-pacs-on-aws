# Orthanc Configuration

The Docker image built as part of this solution using this [Dockerfile](../dockerfile/orthanc.Dockerfile) extends the [Osimis Orthanc Docker](https://book.orthanc-server.com/users/docker-osimis.html) image (see [Docker Hub repository](https://hub.docker.com/r/osimis/orthanc)) and uses the [Cloud Object Storage plugin](https://book.orthanc-server.com/plugins/object-storage.html) for Amazon S3.

## How it works

Before the Docker image starts the Orthanc server, a custom Python script `/orthanc-s3.py` is executed as a custom script (environment variable `BEFORE_ORTHANC_STARTUP_SCRIPT`).

If the environment variables `RPACS_S3_DICOM_BUCKET_NAME` and `RPACS_S3_DICOM_AWS_REGION` are specified, the script will enable the Cloud Object Storage plugin and modifies the Orthanc configuration file to configure the S3 plugin.

If the environment variables `RPACS_S3_CONFIG_BUCKET_NAME` and `RPACS_S3_CONFIG_AWS_REGION` are specified, the script will download the S3 objects to a local folder `/s3-files`. For example, if `RPACS_S3_CONFIG_KEY_PREFIX` equals `config/orthanc1`, and the bucket contains an object at `s3://{bucket}/config/orthanc1/key.pem`, it will download the PEM file in `/s3-files/key.pem`. You can use this to store configuration files (SSL certificate, etc.) outside of the Docker image whose storage is ephemeral only.

## Configuration file

When you deploy the solution using AWS CloudFormation, one SSM parameter is created for each Orthanc server (see the **Orthanc1Config** and **Orthanc2Config** output values). You can modify the value of the SSM parameter to customize the configuration of an Orthanc server.

## Environment variables

In addition to the environment variables supported by the original Docker image, the solution's Orthanc Docker image supports the following environment variables:

Environment variable name | Environment variable description | Default value
---- | ---- | ----
RPACS_S3_DICOM_BUCKET_NAME | To store DICOM files in Amazon S3, you must specify the name of the S3 bucket | *No default value*
RPACS_S3_DICOM_AWS_REGION | To store DICOM files in Amazon S3, you must specify the region of the S3 bucket | *No default value*
RPACS_S3_DICOM_KEY_PREFIX | [Optional] Key prefix for DICOM files stored in Amazon S3 | Empty string (no prefix)
RPACS_S3_CONFIG_BUCKET_NAME | To retrieve configuration files from Amazon S3, you must specify the name of the S3 bucket | *No default value*
RPACS_S3_CONFIG_AWS_REGION | To retrieve configuration files from Amazon S3, you must specify the region of the S3 bucket | *No default value*
RPACS_S3_CONFIG_KEY_PREFIX | [Optional] Key prefix for configuration files stored in Amazon S3 | Empty string (no prefix)

You should not use the environment variable `BEFORE_ORTHANC_STARTUP_SCRIPT` as it is already used in the solution to run a custom script.
