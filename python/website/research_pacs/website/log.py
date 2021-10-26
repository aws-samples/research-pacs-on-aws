# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler

from flask import request, g

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class AccessLogger:
  """
  Logs user activity to a log file.
  
  """
  
  def __init__(self, file_location, excluded_prefixes, excluded_suffixes):
    access_logger = logging.Logger('rpacs_access_logs')
    access_logger.propagate = False
    file_handler = RotatingFileHandler(file_location, maxBytes=10*1024*1024, backupCount=5)
    file_handler.setFormatter(logging.Formatter('%(message)s'))
    access_logger.addHandler(file_handler)
    self._access_logger = access_logger
    self._excluded_prefixes = excluded_prefixes
    self._excluded_suffixes = excluded_suffixes
  
  def _log_request(self, log_msg):
    """
    Add user information to `log_msg` and log the message.
    
    Args:
      log_msg (dict): Access log message
    
    """
    try:
      if not 'User' in log_msg:
        log_msg['User'] = {}
        
      if g.get('user') != None:
        log_msg['User'].update({
          'Authenticated': True,
          'UserName': g.user,
          'Groups': g.groups
        })
      else:
        log_msg['User'].update({
          'Authenticated': False
        })
        
      self._access_logger.info(json.dumps(log_msg))
      
    except:
      logger.warning('Failed to log an access log message')
  
  def log_http_request(self, response):
    """
    Log a HTTP request to the access log file.
    
    Args:
      response: Flask Response object
    
    """
    try:
      
      # The request is logged unless the request path starts with one of the excluded prefixes or 
      # ends with one of the excluded suffixes
      for prefix in self._excluded_prefixes.split(','):
        if request.path.startswith(prefix):
          return
      for suffix in self._excluded_suffixes.split(','):
        if request.path.endswith(suffix):
          return
      
      log_msg = {
        'Type': 'HttpRequest',
        'User': {
          'IpAddress': request.headers['X-Forwarded-For'] if 'X-Forwarded-For' in request.headers else request.remote_addr,
          'UserAgent': request.user_agent.string
        },
        'Request': {
          'Method': request.method,
          'Path': request.path,
          'QueryString': request.query_string.decode(),
          'RequestTime': datetime.now().isoformat()
        },
        'Response': {
          'StatusCode': response.status_code,
          'ContentType': response.content_type,
          'ContentLength': response.content_length,
          'ResponseTime': datetime.now().isoformat()
        }
      }
      self._log_request(log_msg)
        
    except:
      logger.warning('Failed to log an HTTP request')

  def log_new_export(self, parameters, task_id):
    """
    Log a new export task request.
    
    Args:
      paramaters (dict): Export task parameters
      task_id (int): Task ID in the database
      
    """
    try:
      log_msg = {
        'Type': 'NewExport',
        'Request': parameters,
        'Response': {
          'TaskId': task_id
        }
      }
      self._log_request(log_msg)
    
    except:
      logger.warning('Failed to log a new export task request')
      
  def log_search(self, action, query, jsonpath_query, nb_instances, nb_series):
    """
    Log a new search.
    
    Args:
      query (str): Query
      action (str): Display or export
      
    """
    try:
      log_msg = {
        'Type': 'Search',
        'Request': {
          'Query': query,
          'JSONPathQuery': jsonpath_query,
          'Action': action
        },
        'Response': {
          'NbInstances': nb_instances,
          'NbSeries': nb_series
        }
      }
      self._log_request(log_msg)
    
    except:
      logger.warning('Failed to log a new search request')
