# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import os
import re
import logging
import signal
from threading import Event

import boto3
import yaml

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def load_file(location, aws_region, content_type='str', s3_credentials=None):
  """
  Load and return a file either from Amazon S3 or from a local (or locally mounted) file system.
  
  Args:
    location (str): File location in the format `s3://bucket/key` if the file is stored in Amazon 
      S3
    aws_region (str): AWS region where the S3 bucket resides
    content_type (str): Can be `str` to return a string, `bytes` to return encoded bytes, `json` to 
      parse a JSON document and return a dic, `yaml` to parse a YAML document and return a dict
    s3_credentials (dict): Optional S3 credentials passed to the boto3 S3 client. If no 
      credentials are provided, we use the EC2 role or task role
      
  """
  try:
    logger.debug(f'Load the file "{location}" as "{content_type}"')
    match = re.search('^s3:\/\/([^\/]+)\/(.+)$', location)
    
    # Log the file from S3 if the location matches the S3 pattern
    if match != None:
      if s3_credentials != None:
        s3 = boto3.client('s3', region_name=aws_region, **s3_credentials)
      else:
        s3 = boto3.client('s3', region_name=aws_region)
      s3_response = s3.get_object(Bucket=match.group(1), Key=match.group(2))
      content_bytes = s3_response['Body'].read()
      
    # Otherwise, load the file from the local system, or locally-mounted file system
    else:
      with open(location, 'rb') as f:
        content_bytes = f.read()
        
    if content_type == 'bytes':
      return content_bytes
    elif content_type == 'str':
      return content_bytes.decode()
    elif content_type == 'json':
      return json.loads(content_bytes.decode())
    elif content_type == 'yaml':
      return yaml.safe_load(content_bytes.decode())

  except Exception as e:
    msg_err = f'Failed to load the file {location} as "{content_type}" - {e}'
    logger.debug(msg_err)
    raise Exception(msg_err)


def write_file(content, location, aws_region, content_type='str', s3_credentials=None):
  """
  Write a file either to Amazon S3 or to a local (or locally mounted) file system.
  
  Args:
    content: Can either by a bytes, str, JSON object
    location (str): File location in the format `s3://bucket/key` if the file is stored in Amazon 
      S3
    aws_region (str): AWS region where the S3 bucket resides
    content_type (str): Type of `content` (`str`, `bytes` or `json`)
    s3_credentials (dict): Optional S3 credentials passed to the boto3 S3 client. If no 
      credentials are provided, we use the EC2 role or task role
      
  """
  logger.debug(f'Write the file "{location}" as "{content_type}"')
  try:
    if content_type == 'bytes':
      content_bytes = content
    elif content_type == 'str':
      content_bytes.encode()
    elif content_type == 'json':
      content_bytes = json.dumps(content, indent=4, sort_keys=True).encode()
    
    match = re.search('^s3:\/\/([^\/]+)\/(.+)$', location)
    
    # Save to S3 if the location matches the S3 pattern
    if match != None:
      if s3_credentials != None:
        s3 = boto3.client('s3', region_name=aws_region, **s3_credentials)
      else:
        s3 = boto3.client('s3', region_name=aws_region)
      s3_response = s3.put_object(Body=content_bytes, Bucket=match.group(1), Key=match.group(2))
      
    # Otherwise, save it to the local system
    else:
      with open(location, 'wb') as f:
        f.write(content_bytes)

  except Exception as e:
    msg_err = f'Failed to write the "{content_type}" input to {location} - {e}'
    logger.debug(msg_err)
    raise Exception(msg_err)

  
class EnvVarList:
  """
  Retrieve and store environment variables. Environment variable values are accessible as  
  attributes of the object.
  
  """
  
  def __init__(self):
    self.region = None
  
  
  def add(self, attr_name, var_name, cast=None, default=None, password=False):
    """
    Add a class attribute that contains the value of an environment variable. The application 
    exits if the environment variable is unset, unless a default value is provided.
    
    Args:
      attr_name (str): Attribute name
      var_name (str): Name of the environment variable
      cast (type, Optional): Type to cast the environment variable value
      default (Optional): Default value if the environment variable is unset
      password (bool, Optional): Hide the value when displaying debug logs
      
    """
    value = os.getenv(var_name)
    if value is None and default != None:
      value = default

    # Cast the value
    if cast != None and value != None:
      try:
        value = cast(value)
      except Exception as e:
        msg_err = f'Unable to cast {var_name} to {cast}'
        logger.debug(msg_err)
        raise Exception(msg_err)
    
    # Return the value or raise an exception if the value is missing
    if value is None:
      msg_err = f'Missing value for environment variable {var_name}'
      logger.debug(msg_err)
      raise Exception(msg_err)
    else:
      if password is True:
        logger.debug(f'{var_name} = *******')
      else:
        logger.debug(f'{var_name} = {value}')
      setattr(self, attr_name, value)
  
  
class ClientList:
  """
  Store variables, notably client objects, and make them accessible as attributes of a class.
  
  """
  
  def add(self, attr_name, client):
    setattr(self, attr_name, client)
    
  
class GracefulKiller:
  """
  Intercept SIGINT and SIGTERM and enable the program to exit gracefully. Use the `sleep` function 
  instead of `time.sleep` to interrupt the sleep function when a signal is intercepted.
  
  """
  
  def __init__(self):
    self.kill_now = False
    self.exit = Event()
    signal.signal(signal.SIGINT, self._exit_gracefully)
    signal.signal(signal.SIGTERM, self._exit_gracefully)


  def _exit_gracefully(self, sig_num, *args):
    self.exit.set()
    self.kill_now = True
    
    
  def sleep(self, seconds):
    self.exit.wait(seconds)
