# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import logging
import sys

from research_pacs.shared.util import EnvVarList


def get_logger():
  """
  Create and return a logger that logs to the screen.
  
  """
  try:
    env = EnvVarList()
    
    # Log level. Default is INFO
    env.add('log_level', 'RPACS_LOG_LEVEL', default='INFO')
    
    # Include in each record line the current date and time if set to `yes`
    env.add('log_time', 'RPACS_LOG_RECORD_TIME', default='no')
    
    # Include in each record line the current function name if set to `yes`
    env.add('log_funcname', 'RPACS_LOG_FUNCTION_NAME', default='no')
    
  except Exception as e:
    print(f'Failed to initialize the program - {e}')
    sys.exit(1)

  # Create the logger
  logger = logging.getLogger('research_pacs')
  level = logging.getLevelName(env.log_level)
  logger.setLevel(level)
  
  # Set the log format
  log_format = '%(levelname)s '
  if env.log_time.lower() == 'yes':
    log_format += '%(asctime)s '
  if env.log_funcname.lower() == 'yes':
    log_format += '%(name)s:%(funcName)s '
  log_format += '%(message)s'
  formatter = logging.Formatter(log_format)
  
  # Create a handler to print logs to the screen
  stream_handler = logging.StreamHandler()
  stream_handler.setFormatter(formatter)
  logger.addHandler(stream_handler)
  
  return logger
