# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from research_pacs.shared.util import EnvVarList


def get_env():
  env = EnvVarList()

  # AWS region where your AWS resources reside
  env.add('region', 'AWS_REGION')
  
  # AWS region where the Amazon Rekognition endpoint is used. It may differ from `AWS_REGION` 
  # because Amazon Rekognition is not available in every region
  env.add('rekognition_region', 'RPACS_REKOGNITION_REGION', default=env.region)
  
  # URL of the SQS queue
  env.add('queue_url', 'RPACS_SQS_QUEUE_URL')
  
  # Number of seconds during which Amazon SQS prevents other consumers from receiving and 
  # processing the current message
  env.add('queue_timeout', 'RPACS_SQS_VISIBILITY_TIMEOUT', cast=int, default=120)
  
  # Number of times a message can be received and attempted to be processed before it is removed 
  # from the queue
  env.add('queue_max_attemps', 'RPACS_SQS_MAX_ATTEMPTS', cast=int, default=3)
  
  # DNS hostname or IP address of the PostgreSQL database instance
  env.add('pg_host', 'RPACS_POSTGRESQL_HOSTNAME')
  
  # TCP port of the PostgreSQL database instance
  env.add('pg_port', 'RPACS_POSTGRESQL_PORT', cast=int, default=5432)
  
  # User name to use to connect to the PostgreSQL database instance
  env.add('pg_user', 'RPACS_POSTGRESQL_USERNAME')
  
  # Password to use to connect to the PostgreSQL database instance
  env.add('pg_pwd', 'RPACS_POSTGRESQL_PASSWORD', password=True)
  
  # Name of the database to use in the PostgreSQL database instance
  env.add('pg_db', 'RPACS_POSTGRESQL_DB_NAME')
  
  # Hostname of the Orthanc server that stores the original DICOM files. Format: 
  # http[s]://hostname (do not include a trailing slash)
  env.add('src_orthanc_host', 'RPACS_SOURCE_ORTHANC_HOSTNAME')
  host_lower = env.src_orthanc_host.lower()
  assert host_lower.startswith('http://') or host_lower.startswith('https://'), 'Orthanc hostname format is incorrect'
  assert not host_lower.endswith('/'), 'Orthanc hostname format is incorrect'
  
  # User name to use to connect to the Orthanc server
  env.add('src_orthanc_user', 'RPACS_SOURCE_ORTHANC_USERNAME')
  
  # Password to use to connect to the Orthanc server
  env.add('src_orthanc_pwd', 'RPACS_SOURCE_ORTHANC_PASSWORD', password=True)
  
  # Hostname of the Orthanc server that stores the de-identified DICOM files. Format: 
  # http[s]://hostname (do not include a trailing slash)
  env.add('dst_orthanc_host', 'RPACS_DESTINATION_ORTHANC_HOSTNAME')
  host_lower = env.dst_orthanc_host.lower()
  assert host_lower.startswith('http://') or host_lower.startswith('https://'), 'Orthanc hostname format is incorrect'
  assert not host_lower.endswith('/'), 'Orthanc hostname format is incorrect'
  
  # User name to use to connect to the Orthanc server
  env.add('dst_orthanc_user', 'RPACS_DESTINATION_ORTHANC_USERNAME')
  
  # Password to use to connect to the Orthanc server
  env.add('dst_orthanc_pwd', 'RPACS_DESTINATION_ORTHANC_PASSWORD', password=True)
  
  # Default location of the config file (file containing labelling, filtering and 
  # transformation rules). Can be a S3 object (s3://bucket/key) or a local file
  env.add('config_file', 'RPACS_DEFAULT_CONFIG_FILE')
  
  # Indicates whether the original files are preserved after de-identification, or left in the 
  # Orthanc server and you are responsible for their deletion if needed
  env.add('preserve_files', 'RPACS_PRESERVE_ORIGINAL_FILES', default='no')
  
  return env
