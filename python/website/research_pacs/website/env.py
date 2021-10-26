# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from research_pacs.shared.util import EnvVarList


def get_env():
  env = EnvVarList()
  
  # AWS region where your AWS resources reside
  env.add('region', 'AWS_REGION')
  
  # URL of the SQS queue
  env.add('queue_url', 'RPACS_SQS_QUEUE_URL')
  
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
  
  # Location of the YAML file that contains the definitons of user and group permissions
  env.add('permissions_file', 'RPACS_PERMISSIONS_FILE')
  
  # Location of the website access logs
  env.add('access_log_file', 'RPACS_LOG_FILE')
  
  # List of request path prefixes that should not be recorded into the access log file, separated 
  # by a comma. By default, requests to the healthcheck URL or the Orthanc Explorer static files 
  # are excluded
  env.add('log_excluded_prefixes', 'RPACS_LOG_EXCLUDED_PREFIXES', default="/healthcheck,/app/")
  
  # List of request path suffixes that should not be recorded into the access log file, separated 
  # by a comma. By default, requests to JS, CSS and ICO files are excluded
  env.add('log_excluded_suffixes', 'RPACS_LOG_EXCLUDED_SUFFIXES', default=".ico,.js,.css")

  # Name of the JWT claim that contains the username. Default is username
  env.add('claim_user', 'RPACS_COGNITO_CLAIM_USERNAME', default="username")
  
  # Name of the JWT claim that contains the username. Default is username
  env.add('claim_groups', 'RPACS_COGNITO_CLAIM_GROUPS', default="cognito:groups")

  # Number of instances displayed in each Search results page
  env.add('results_per_page', 'RPACS_RESULTS_PER_PAGE', cast=int, default=200)
  
  # List of top-level tag keywords, separated by a comma, to display for a Series header in the 
  # Search results page
  env.add('series_header_keywords', 'RPACS_SERIES_HEADER_KEYWORDS', default='Modality,StudyDescription,SeriesDescription')
  
  # List of top-level tag keywords, separated by a comma, to display for a Instance header in the 
  # Search results page
  env.add('instance_header_keywords', 'RPACS_INSTANCE_HEADER_KEYWORDS', default='InstanceNumber')

  # Link to the user guide
  env.add('user_guide_url', 'RPACS_USER_GUIDE_URL')

  # Amazon Cognito URL where users must be redirected after logout
  env.add('sign_out_url', 'RPACS_SIGN_OUT_URL')

  return env
