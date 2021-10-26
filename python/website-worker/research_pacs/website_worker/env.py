# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from research_pacs.shared.util import EnvVarList


def get_env():
  env = EnvVarList()

  # AWS region where your AWS resources reside
  env.add('region', 'AWS_REGION')
  
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
  
  # User name to use to connect to the PostgreSQL database
  env.add('pg_user', 'RPACS_POSTGRESQL_USERNAME')
  
  # Password to use to connect to the PostgreSQL database
  env.add('pg_pwd', 'RPACS_POSTGRESQL_PASSWORD', password=True)
  
  # Name of the database to use in the PostgreSQL database instance
  env.add('pg_db', 'RPACS_POSTGRESQL_DB_NAME')
  
  # Hostname of the Orthanc server that stores the de-identified DICOM files. Format: 
  # http[s]://hostname (don't include a trailing slash)
  env.add('orthanc_host', 'RPACS_ORTHANC_HOSTNAME')
  host_lower = env.orthanc_host.lower()
  assert host_lower.startswith('http://') or host_lower.startswith('https://'), 'Orthanc hostname format is incorrect'
  assert not host_lower.endswith('/'), 'Orthanc hostname format is incorrect'
  
  # User name to use to connect to the Orthanc server
  env.add('orthanc_user', 'RPACS_ORTHANC_USERNAME')
  
  # Password to use to connect to the Orthanc server
  env.add('orthanc_pwd', 'RPACS_ORTHANC_PASSWORD', password=True)
  
  return env
