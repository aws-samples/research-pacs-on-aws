# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import logging
import sys

import boto3

import research_pacs.shared.dicom_util as rpacs_dicom_util
import research_pacs.shared.util as rpacs_util
from research_pacs.de_identifier.dicom import DicomDeidentifier
from research_pacs.de_identifier.env import get_env
from research_pacs.de_identifier.ocr import get_box_coordinates
from research_pacs.shared.database import DB, DBKeyJsonValue, DBDicomMapping
from research_pacs.shared.orthanc import OrthancClient

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
env = None
client = None


def main():
  logger.info('Starting de-identifier')

  try:
    global env
    env = get_env()

    # Create the clients
    global client
    client = rpacs_util.ClientList()
    client.add('db', DB(env.pg_host, env.pg_port, env.pg_user, env.pg_pwd, env.pg_db))
    client.add('db_msg', DBKeyJsonValue(db_client=client.db, table_name="rpacs_related_msg"))
    client.add('db_mapping', DBDicomMapping(db_client=client.db))
    client.add('src_orthanc', OrthancClient(env.src_orthanc_host, env.src_orthanc_user, env.src_orthanc_pwd))
    #client.add('dst_orthanc', OrthancClient(env.dst_orthanc_host, env.dst_orthanc_user, env.dst_orthanc_pwd))
    client.add('sqs', boto3.client('sqs', region_name=env.region))
    
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
          
          process_message(message['Body'])
          client.sqs.delete_message(QueueUrl=env.queue_url, ReceiptHandle=message['ReceiptHandle'])

        except Exception as e:
          logger.error(f'Failed to process the message ({nb_attempts} attempts) - {e}')

    except Exception as e:
      logger.error(f'Failed to poll messages from SQS - {e}')
      
    # Close the DB connection after each iteration
    client.db.close()

    # Wait 5 seconds if the previous request returned no SQS message
    if messages_returned is False:
      logger.debug(f"Waiting 5 seconds")
      killer.sleep(5)

  # Before the program exits
  logger.info('Stopping de-identifier')


def process_message(msg_str):
  """
  Pass the message to another function depending on the event type (e.g. NewDICOM)
  
  Args:
    msg_str (str): Content of the SQS message
  
  """
  try:
    msg = json.loads(msg_str)
    logger.debug(f"New message: {json.dumps(msg)}")
    event_type = msg['EventType']
  except:
    logger.error(f'Skipping malformed message: {msg_str}')
    return

  """
  Message received when a new DICOM file must be de-identified and sent to the destination 
  Orthanc server.
  
  Format : {
    "EventType":      "NewDICOM"
    "Source":         Location of the DICOM file, either from Orthanc (orthanc://instance-id),
                      from Amazon S3 (s3://bucket/key), or from a local file system
    "ConfigFile":     [Optional] Location of a custom config file to use to de-identify this
                      DICOM file. Use the default config file is no value is provided
    "Destination":    [Optional] Location where the de-identified DICOM file should be sent: 
                      s3://bucket/key for Amazon S3, or /folder/file.ext for a local file. If 
                      no value is provided, the file is sent to the destination Orthanc server
    "LogFile":        [Optional] If the destination is S3 or a local file, set this to `True` to 
                      write a file with detailed de-identification steps, or the error message 
                      if the de-identification process failed
    "Skip":           [Optional] Skip this file is `True`. Default is `False`
    "Retry":          [Optional] Set to `False` to not retry if the message processing failed
  }
  
  """
  if event_type == 'NewDICOM':
    try:
      process_new_dicom(msg)
    except Exception as e:
      if not ('Retry' in msg and msg['Retry'] == False):
        raise e
    
    

def process_new_dicom(msg):
  """
  Process incoming DICOM files as follows:
  
  If the new DICOM file is stored in Amazon S3 or a file system that is locally mounted to this 
  server, we send it to Orthanc so that we can leverage Orthanc native API for some of the 
  de-identification parts. A new SQS message will be trigger the de-identification for the 
  Orthanc instance.
  
  If the new DICOM file is stored in the source Orthanc server, check if the Orthanc instance is 
  associated with previous "instructions" (see below) and overwrite the current message if needed. 
  Then, process the new Orthanc DICOM instance with the function `process_new_dicom_orthanc` and 
  delete the instance from the source Orthanc server if the processing succeeded.
  
  Args:
    msg (dict): Content of the SQS message
  
  """
  try:
    dicom_source = msg['Source']
    logger.info(f"New DICOM file: Source={dicom_source}")
  except:
    logger.error(f'Attribute "Source" is missing in the message')
    return
  
  # If the DICOM instance is stored in a local file system or S3, upload it to Orthanc and store 
  # the original message in the database. The change pooler will detect that new Orthanc instance 
  # and send another message. That new message will be replaced by the "instructions" contained in 
  # the previous message, such as using a custom config file
  if not dicom_source.startswith('orthanc://'):
    try:
      dicom_file = rpacs_util.load_file(dicom_source, env.region, 'bytes')
      location = f's3://pacs-bucket-wvdeqzoc1jc3/dicom/{dicom_source.replace("orthanc://", "")}'
      instance_id = rpacs_util.s3_write_file(dicom_file, location, env.region, 'bytes')
      # instance_id = client.src_orthanc.upload_instance(dicom_file)
      client.db_msg.upsert(instance_id, msg)
      logger.info(f"Uploaded the local DICOM file to Orthanc - Instance ID={instance_id}")
    except Exception as e:
      raise Exception(f'Failed to upload the local DICOM file to Orthanc - {e}')
    
  # If the DICOM file is stored in the source Orthanc server
  else:
    instance_id = dicom_source.replace('orthanc://', '')
    
    # Check if a message was previously stored in the database, with "instructions" on how to 
    # process this Orthanc instance
    try:
      previous_msg = client.db_msg.get(instance_id)
      if previous_msg != None:
        if 'Source' in previous_msg:
          previous_msg['OriginalSource'] = previous_msg['Source']
        previous_msg['Source'] = dicom_source
        msg = previous_msg
        logger.debug(f"Modified the message: {json.dumps(previous_msg)}")
    except Exception as e:
      raise Exception(f'Failed to check if a related message was previously stored in the database - {e}')
    
    # Skip the message if it has an attribute `Skip=True` and delete the associated Orthanc 
    # instance, because it was uploaded by the de-identifier
    if 'Skip' in msg and msg['Skip'] == True:
      logger.info(f'Skipping the Orthanc instance (Skip=True)')
      client.src_orthanc.delete_instance(instance_id)
      
    # Otherwise, process the message and delete the original DICOM file in Orthanc unless 
    # we need to preserve them
    else:
      process_new_dicom_orthanc(instance_id, msg)
      if env.preserve_files.lower() == 'no':
        client.src_orthanc.delete_instance(instance_id)

      
def process_new_dicom_orthanc(src_instance_id, msg):
  """
  Process new DICOM instances stored in the source Orthanc server as follows:
  - Download the configuration file how original DICOM files are processed
  - De-identify the DICOM file uing the function `deidentify_dicom_orthanc`
  - Write the de-identified DICOM file to the destination (destination Orthanc server, S3 or local)
  - Write detailed logs to S3 or file, if needed
  
  Args:
    src_instance_id (str): Instance ID in the source Orthanc server
    msg (dict): Content of the SQS message
    
  """
  err = None
  logs = {'Message': msg}
  try:
  
    # Load the config file, either from the custom location passed in the message or from the 
    # default location, and create a DicomDeidentifier object
    try:
      if 'ConfigFile' in msg:
        config_location = msg['ConfigFile']
        logger.info(f'Using a custom config file "{config_location}"')
      else:
        config_location = env.config_file
      logger.debug(f'Loading the config file at "{config_location}"')
      logs['ConfigFile'] = config_location
      config = rpacs_util.load_file(config_location, env.region, 'yaml')
    except Exception as e:
      raise Exception(f'Failed to download the config file - {e}')
    
    # Download the original DICOM file
    try:
      logger.debug('Loading the original DICOM file from Orthanc')
      src_dicom = client.src_orthanc.download_instance_dicom(src_instance_id)
    except Exception as e:
      raise Exception(f'Failed to download the original DICOM file from Orthanc - {e}')
    
    # De-identify the DICOM file
    logger.debug('De-identifying the original DICOM file from Orthanc')
    dst_dicom = deidentify_dicom_orthanc(src_instance_id, src_dicom, config, logs)
    
    # Send the de-identified DICOM file to the destination, if the call is `deidentify_dicom` 
    # returned a DICOM file (the file might be skipped based on its labels)
    try:
      if dst_dicom != None:
        if 'Destination' in msg:
          rpacs_util.write_file(dst_dicom, msg['Destination'], env.region, 'bytes')
          logger.info(f"Uploaded the de-identified DICOM file to \"{msg['Destination']}\"")
        else:
          dst_instance_id = rpacs_util.s3_write_file(dicom_file, location, env.region, 'bytes')
          # dst_instance_id = client.dst_orthanc.upload_instance(dst_dicom)
          rpacs_util.write_file(dicom_file, location, env.region, 'bytes')
          logger.info(f"Uploaded the de-identified DICOM file to Orthanc - ID={dst_instance_id}")
    except Exception as e:
      raise Exception(f'Failed the write the de-identified DICOM file - {e}')
    
  except Exception as e:
    logger.error(f'Failed to process the DICOM file - {e}')
    logs.update({'Error': str(e)})
    err = e
  
  # Print the result logs to the screen
  for key, value in logs.items():
    if key == 'Message':
      continue
    elif key == 'TransformationsApplied':
      for t_key, t_value in value.items():
        logger.info(f'Result: {key} {t_key}={json.dumps(t_value)}')
    else:  
      logger.info(f'Result: {key}={json.dumps(value)}')
  
  # Upload the detailed logs
  if 'LogFile' in msg:
    try:
      rpacs_util.write_file(logs, msg['LogFile'], env.region, 'json')
      logger.info(f"Uploaded the detailed logs to \"{msg['LogFile']}\"")
    except Exception as e:
      logger.error(f'Failed to upload the log file - {e}')

  # Raise the exception err if it was catched earlier
  if err != None:
    raise err


def deidentify_dicom_orthanc(instance_id, src_dicom, config, logs):
  """
  De-identify a DICOM instance from in the source Orthanc server as follows:
  - Retrieve the labels matching this Orthanc instance (`Labels` section of the configuration 
    file) and whether the DICOM should be de-identified and sent to the destination, or skipped 
    (`ScopeToForward` section of the config file)
  - If the Orthanc instance is not skipped:
      - Download from Orthanc a transcoded version of the DICOM file to "Explicit VR Little 
        Endian" if pixel data must be edited to mask burned-in annotations
      - If OCR must be used to detect burned-in annotations, retrieve the pixel coordinates of 
        boxes that need to be masked
      - Apply the transformation rules (`Transformations` section of the config file) and 
        retrieve the de-identified DICOM file
      - Transcode the DICOM file if the target transfer syntax is not "Explicit VR Little Endian"
      - Return the de-identified DICOM file
  
  Args:
    instance_id (str): Orthanc instance ID
    src_dicom (bytes): Content of the DICOM file downloaded from Orthanc
    config (dict): Configuration file
    logs (dict): Dict where logs should be added
  
  """
  # Create a DicomDeidentifier object and load the DICOM file
  try:
    deidentifier = DicomDeidentifier(config, client.db, client.db_mapping)
  except Exception as e:
    raise Exception(f'Failed to initialize the DicomDeidentifier - {e}')
  
  # The function `load_dicom` returns a list of matching labels for this DICOM file, and whether 
  # the DICOM file should be discarded based on these tags
  try:
    labels, skipped = deidentifier.load_dicom(src_dicom)
    logs.update({
      'OriginalDICOMFile': {
        'SOPInstanceUID': rpacs_dicom_util.get_sop_instance_uid(deidentifier.dicom),
        'TransferSyntaxUID': rpacs_dicom_util.get_transfer_syntax_uid(deidentifier.dicom)
      },
      'MatchingLabels': labels,
      'Skipped': skipped
    })
  except Exception as e:
    raise Exception(f'Failed to load the original DICOM file in the DicomDeidentifier - {e}')
  
  if skipped is True:
    return None
  
  # Log transformations to apply
  transformations = deidentifier.get_transformations_to_apply()
  logs.update({'TransformationsToApply': transformations})

  # If burned-in annotations must be removed from the pixel data, the DICOM file must be in 
  # uncompressed and in Little Endian format. If needed, we use Orthanc to download a transcoded 
  # version of the DICOM file
  need_transcode, src_transfer_syntax = deidentifier.is_transcoding_needed()
  if need_transcode is True:
    try:
      src_dicom = client.src_orthanc.download_instance_dicom(instance_id, transcode='1.2.840.10008.1.2.1')
      deidentifier.load_dicom(src_dicom, src_transfer_syntax, initial_load=False)
    except Exception as e:
      raise Exception(f'Failed to transcode the original DICOM file to "Explicit VR Little Endian" with Orthanc in order to alter pixel data - {e}')

  # If OCR must be used to detect burned-in annotations in pixel data
  if deidentifier.is_ocr_needed():
    
    # Find box coordinates with burned-in annotations and update the transformations rules
    try:
      dimensions = rpacs_dicom_util.get_dimensions(deidentifier.dicom)
      boxes = get_box_coordinates(client.src_orthanc, instance_id, env.rekognition_region, dimensions)
      deidentifier.add_box_coordinates(boxes)
    except Exception as e:
      raise Exception(f'Failed to find burned-in annotations in the original DICOM file with OCR - {e}')

  # Apply the transformation rules
  try:
    dst_transfer_syntax = deidentifier.apply_transformations(logs)
  except Exception as e:
    raise Exception(f'Failed to apply the transformation rules to the original DICOM file - {e}')
  
  # `apply_transformations` returns a transfer syntax if the de-identified DICOM file must be 
  # transcoded, or `None` if it should be sent as-is to the destination Orthanc server. If it must 
  # be transcoded, we upload the de-identified DICOM file to the source Orthanc server, and we 
  # download and return a transcoded version
  dst_dicom = rpacs_dicom_util.export_dicom(deidentifier.dicom)
  if dst_transfer_syntax != None:
    try:
      
      # Temporarily change the SOP Instance ID before uploading the de-identified DICOM file to 
      # Orthanc in order to prevent the original DICOM file
      src_sop_instance_uid = rpacs_dicom_util.get_sop_instance_uid(deidentifier.dicom)
      rpacs_dicom_util.set_sop_instance_uid(deidentifier.dicom)
      dst_dicom = rpacs_dicom_util.export_dicom(deidentifier.dicom)
      
      # Upload the de-identified DICOM file to Orthanc. This new DICOM file should be ignored by the 
      # de-identifier
      # tmp_instance_id = client.src_orthanc.upload_instance(dst_dicom)
      tmp_instance_id = rpacs_util.s3_write_file(dicom_file, location, env.region, 'bytes')
      client.db_msg.upsert(tmp_instance_id, {'Skip': True})
      
      # Download a transcoded version of the de-identified DICOM file, and we restore the SOP 
      # Instance ID to its original value
      dst_dicom = client.src_orthanc.download_instance_dicom(tmp_instance_id, transcode=dst_transfer_syntax)
      deidentifier.load_dicom(dst_dicom, initial_load=False)
      rpacs_dicom_util.set_sop_instance_uid(deidentifier.dicom, src_sop_instance_uid)
      dst_dicom = rpacs_dicom_util.export_dicom(deidentifier.dicom)
      
    except Exception as e:
      raise Exception(f'Failed to transcode the de-identified DICOM file to "{dst_transfer_syntax}" - {e}')

  return dst_dicom
