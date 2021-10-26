# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import logging
import sys
from datetime import datetime
from threading import Thread

import boto3

import research_pacs.shared.dicom_json as rpacs_dicom_json
import research_pacs.shared.dicom_util as rpacs_dicom_util
import research_pacs.shared.util as rpacs_util
from research_pacs.shared.database import DB, DBDicomJson, DBExportTasks
from research_pacs.shared.orthanc import OrthancClient
from research_pacs.website_worker.env import get_env

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
env = None
client = None


def main():
  logger.info('Starting website worker')

  try:
    global env
    env = get_env()

    # Create the clients
    global client
    client = rpacs_util.ClientList()
    client.add('orthanc', OrthancClient(env.orthanc_host, env.orthanc_user, env.orthanc_pwd))
    client.add('sqs', boto3.client('sqs', region_name=env.region))
    
    # This will store the last time when `clean_database` was called
    last_time_clean_database = None

  # Exit if any of the previous steps failed
  except Exception as e:
    logger.fatal(f'Failed to initialize the program - {e}')
    sys.exit(1)

  # Loop until the program is interrupted
  killer = rpacs_util.GracefulKiller()
  while not killer.kill_now:
    
    # Retrieve up to 10 messages from the SQS queue
    try:
      messages_returned = False
      logger.debug(f'Retrieving messages from the SQS queue')
      sqs_response = client.sqs.receive_message(
        QueueUrl=env.queue_url,
        AttributeNames=['ApproximateReceiveCount'],
        MaxNumberOfMessages=10,
        MessageAttributeNames=['All'],
        VisibilityTimeout=env.queue_timeout,
        WaitTimeSeconds=1
      )
      
      # Process each message and delete it from the queue if it succeeded
      messages = sqs_response['Messages'] if 'Messages' in sqs_response else []
      logger.debug(f'SQS returned {len(messages)} messages to process')
      if len(messages) > 0:
        messages_returned = True
      
      for message in messages:
        try:
          
          # Delete the message if it was served more than `queue_max_attemps`
          nb_attempts = int(message['Attributes']['ApproximateReceiveCount'])
          if nb_attempts > env.queue_max_attemps:
            client.sqs.delete_message(QueueUrl=env.queue_url, ReceiptHandle=message['ReceiptHandle'])
            continue
          
          process_message(message)
          
        except Exception as e:
          logger.error(f'Failed to process the message ({nb_attempts} attempts) - {e}')

    except Exception as e:
      logger.error(f'Failed to poll messages from SQS - {e}')

    # Clean the database every 60 seconds
    if last_time_clean_database is None or (datetime.now() - last_time_clean_database).seconds > 60:
      clean_database()
      last_time_clean_database = datetime.now()

    # Wait 5 seconds if the previous request returned no SQS message
    if messages_returned is False:
      logger.debug(f"Waiting 5 seconds")
      killer.sleep(5)

  # Before the program exits
  logger.info('Stopping website worker')


def process_message(msg):
  """
  Pass the message to another function depending on the event type (e.g. NewDICOM)
  
  Args:
    msg (dict): SQS message

  """
  msg_body = msg['Body']
  try:
    msg_content = json.loads(msg_body)
    logger.debug(f"New message: {json.dumps(msg_content)}")
    event_type = msg_content['EventType']
  except:
    logger.error(f'Skipping malformed message: {msg_body}')
    return

  """
  Message received when a new de-identified DICOM file must be indexed into the PostgreSQL database
  
  Format : {
    "EventType":      "NewDICOM"
    "Source":         Location of the DICOM file (orthanc://instance-id)
  }
  
  """
  if event_type == 'NewDICOM':
    process_new_dicom(msg_content)
    client.sqs.delete_message(QueueUrl=env.queue_url, ReceiptHandle=msg['ReceiptHandle'])
  
  """
  Message received when an export task is created
  
  Format : {
    "EventType":      "NewExport"
    "TaskId":         Export task ID in the database
    "AccessKey":      AWS Access Key
    "SecretKey":      AWS Secret Key
    "SessionToken":   AWS Session Token
  }
  
  """
  if event_type == 'NewExport':
    t = Thread(target=process_new_export, daemon=True, args=(msg, msg_content))
    t.start()


def process_new_dicom(msg):
  """
  Export new de-identified DICOM images in the PostgreSQL to make it faster to query DICOM images 
  from the database instead of from Orthanc.
  
  Args:
    msg (dict): Content of the SQS message
  
  """
  try:
    dicom_source = msg['Source']
    logger.info(f"New DICOM file: Source={dicom_source}")
  except:
    logger.error(f'Attribute "Source" is missing in the message')
    return
  
  assert dicom_source.startswith('orthanc://'), 'msg["Source"] must start with "orthanc://"'
  instance_id = dicom_source.replace('orthanc://', '')
  
  # Load the DICOM file and convert it to a formatted JSON document
  dicom_bytes = client.orthanc.download_instance_dicom(instance_id)
  dicom = rpacs_dicom_util.load_dicom_from_bytes(dicom_bytes)
  dicom_json = rpacs_dicom_json.convert_dicom_to_json(dicom)
  
  # Get the series ID and the index in series for this instance
  series_id, index_in_series = client.orthanc.get_series_information(instance_id)
  
  # Insert the JSON document into the PostgreSQL database
  db = DB(env.pg_host, env.pg_port, env.pg_user, env.pg_pwd, env.pg_db)
  db_dicom_json = DBDicomJson(db)
  db_dicom_json.upsert_instance(instance_id, series_id, index_in_series, dicom_json)
  db.close()
  
  
def process_new_export(msg, msg_content):
  """
  Function that runs in a thread to process an export task.
  
  Args:
    msg (dict): SQS message
    msg_content (dict): Content of the SQS message
  
  """
  def extend_message_timeout():
    """
    Make the message unavailable to other SQS consumers until the export task is running.
    
    """
    logger.debug(f'Export #{task_id} - Extanding the message visibility timeout')
    client.sqs.change_message_visibility(
      QueueUrl=env.queue_url,
      ReceiptHandle=msg['ReceiptHandle'],
      VisibilityTimeout=15
    )
  
  try:
    # Initialize thread variables
    db = None
    nb_exported = 0
    nb_failed = 0
    error_messages = {}
    
    assert 'TaskId' in msg_content, 'Missing "TaskId" attribute in the message'
    assert 'AccessKey' in msg_content, 'Missing "AccessKey" attribute in the message'
    assert 'SecretKey' in msg_content, 'Missing "SecretKey" attribute in the message'
    assert 'SessionToken' in msg_content, 'Missing "SessionToken" attribute in the message'
    
    task_id = msg_content['TaskId']
    logger.info(f'Export #{task_id} - Starting the export task')
    
    extend_message_timeout()
    last_timeout_extension = datetime.now()
    
    try:
      db = DB(env.pg_host, env.pg_port, env.pg_user, env.pg_pwd, env.pg_db)
      
      # Retrieve the export task parameters
      db_exports = DBExportTasks(db)
      parameters = db_exports.get_task(task_id)
      
      # Retrieve the DICOM instances that match the query
      db_dicom_json = DBDicomJson(db)
      instances = db_dicom_json.search_instances(parameters['JSONPathQuery'])
      logger.debug(f'Export #{task_id} - Exporting {len(instances)} instances to Amazon S3')
      
    except Exception as e:
      logger.error(f'Export #{task_id} - Failed to list the Orthanc instances to export - {e}')
      raise Exception('Failed to list the Orthanc instances to export')
    
    # Prepare S3 credentials
    credentials = {
      'aws_access_key_id': msg_content['AccessKey'],
      'aws_secret_access_key': msg_content['SecretKey']
    }
    if msg_content['SessionToken'] != '':
      credentials['aws_session_token'] = msg_content['SessionToken']
    
    # For each instance to export
    for instance in instances:
      instance_id = instance[0]
      instance_json = instance[1]
      s3_prefix = f"s3://{parameters['S3Bucket']}/{parameters['S3Prefix']}{instance_id}"
      
      # Extand the message visibility timeout every 5 seconds to prevent the SQS message from
      # being visible by other queue consumers
      if (datetime.now() - last_timeout_extension).seconds > 5:
        extend_message_timeout()
        last_timeout_extension = datetime.now()
    
      try:
        logger.debug(f'Export #{task_id} - Exporting the instance {instance_id}')
        
        # If the export format is DICOM, download the file from Orthanc and upload it to the S3 
        # bucket
        if parameters['Format'] == 'dicom':
          
          try:
            transcode = parameters['Transcode'] if parameters['Transcode'] != '' else None
            file_bytes = client.orthanc.download_instance_dicom(instance_id, transcode)
          except Exception as e:
            logger.warning(f'Export #{task_id} - Failed to download the Orthanc instance - {e}')
            raise Exception('Failed to download the DICOM file from Orthanc, the Transfer Syntax UID may be incorrect or incompatible')
            
          try:
            s3_key = s3_prefix+'.dcm'
            rpacs_util.write_file(file_bytes, s3_key, env.region, 'bytes', credentials)
          except Exception as e:
            logger.warning(f'Export #{task_id} - Failed to write the file to S3 - {e}')
            raise Exception('Failed to write the file to the S3 bucket, please check the S3 path and credentials')
        
        # If the export format is PNG or JPEG, count the number of frames and export each frame
        else:

          try:
            nb_frames = client.orthanc.count_instance_frames(instance_id)
          except Exception as e:
            logger.warning(f'Export #{task_id} - Failed to count the frames in a DICOM file - {e}')
            raise Exception('Orthanc failed to count the number of frames in the DICOM image')
          
          for frame in range(nb_frames):
            
            try:
              accept = 'image/png' if parameters['Format'] == 'png' else 'image/jpeg'
              file_bytes = client.orthanc.download_instance_frame(instance_id, accept, frame)
            except Exception as e:
              logger.warning(f'Export #{task_id} - Failed to download a frame of a DICOM file - {e}')
              raise Exception(f'Failed to export frames as "{accept}" format')
              
            try:
              s3_key = f"{s3_prefix}_{frame}.{parameters['Format']}" if nb_frames > 1 else f"{s3_prefix}.{parameters['Format']}"
              rpacs_util.write_file(file_bytes, s3_key, env.region, 'bytes', credentials)
            except Exception as e:
              logger.warning(f'Export #{task_id} - Failed to write the file to S3 - {e}')
              raise Exception('Failed to write the file to the S3 bucket, please check the S3 path and credentials')
          
        # If the DICOM attributes must be exported to a JSON document
        if parameters['ExportJSON']:
          
          try:
            s3_key = s3_prefix+'.json'
            instance_json_keywords = rpacs_dicom_json.add_keywords_to_dicom_json(instance_json)
            rpacs_util.write_file(instance_json_keywords, s3_key, env.region, 'json', credentials)
          except Exception as e:
            logger.warning(f'Export #{task_id} - Failed to write the JSON file to S3 - {e}')
            raise Exception('Failed to write the JSON file to the S3 bucket, please check the S3 path and credentials')
        
        nb_exported += 1
        
      # Count the number of occurences for each error message
      except Exception as e:
        nb_failed += 1
        err_msg = str(e)
        if not err_msg in error_messages.keys():
          error_messages[err_msg] = 1
        else:
          error_messages[err_msg] += 1
    
    # Update the export task results
    try:
      results = {
        'NbExported': nb_exported,
        'NbFailed': nb_failed,
      }
      if len(error_messages) > 0:
        results['Errors'] = '. '.join([f'{v} times: {k}' for k,v in error_messages.items()])
      db_exports.update_task(task_id, 'completed', results)
      logger.info(f'Export #{task_id} - Export task has completed - Exported={nb_exported} Failed={nb_failed}')
      
    except Exception as e:
      raise Exception("Failed to update the export task results")
    
  except Exception as e:
    db_exports.update_task(task_id, 'failed', results={'Errors': str(e)})
  
  finally:
    client.sqs.delete_message(QueueUrl=env.queue_url, ReceiptHandle=msg['ReceiptHandle'])
    if db != None:
      db.close()

    
def clean_database():
  """
  If an instance is removed from the Orthanc server that contains de-identified DICOM images, it 
  must also be removed from the database. This function compared the list of instance IDs in the 
  database with those in Orthanc.
  
  """
  try:
    logger.debug('Cleaning the database')
    db = DB(env.pg_host, env.pg_port, env.pg_user, env.pg_pwd, env.pg_db)
    db_dicom_json = DBDicomJson(db)
    ids_in_db = db_dicom_json.list_instance_ids()
    ids_in_orthanc = client.orthanc.list_instance_ids()
    ids_to_delete = [i for i in ids_in_db if not i in ids_in_orthanc]
    for instance_id in ids_to_delete:
      db_dicom_json.delete_instance(instance_id)
    
  except Exception as e:
    logger.error(f'Failed to clean database - {e}')
    
    
