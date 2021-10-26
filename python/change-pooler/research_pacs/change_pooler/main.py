# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import logging
import sys

import boto3

from research_pacs.change_pooler.env import get_env
from research_pacs.shared.database import DB, DBKeyJsonValue
from research_pacs.shared.orthanc import OrthancClient
from research_pacs.shared.util import ClientList, GracefulKiller

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
env = None
client = None


def main():
  logger.info('Starting change pooler')

  try:
    global env
    env = get_env()
    
    # Create the clients
    global client
    client = ClientList()
    client.add('db', DB(env.pg_host, env.pg_port, env.pg_user, env.pg_pwd, env.pg_db))
    client.add('db_last_state', DBKeyJsonValue(client.db, table_name="rpacs_change_pooler_last_state"))
    client.add('orthanc', OrthancClient(env.orthanc_host, env.orthanc_user, env.orthanc_pwd))
    client.add('sqs', boto3.client('sqs', region_name=env.region))

    # Retrieve the last Orthanc change ID (Seq) already processed from the database
    last_state = client.db_last_state.get(key=env.orthanc_host, init_value={"last_seq": 0})
    current_last_seq = last_state['last_seq']
    logger.info(f'Last Orthanc change ID (Seq) already processed = {current_last_seq}')
    
    # This variable will be set to True if we fail to update the last change ID (Seq) that 
    # was processed in the database
    db_update_orthanc_failed = False
  
  # Exit if any of the previous initialization steps failed
  except Exception as e:
    logger.fatal(f'Failed to initialize the program - {e}')
    sys.exit(1)

  # Loop until the program is interrupted by SIGINT or SIGTERM
  killer = GracefulKiller()
  while not killer.kill_now:
    
    # Retrieve and process the changes that occured in Orthanc whose change ID (Seq) is larger 
    # than `current_last_seq`
    try:
      changes, last_seq = client.orthanc.get_changes(from_seq=current_last_seq)
      new_last_seq = current_last_seq
      
      # If you run Orthanc with no persistent storage, the Orthanc change ID is zeroed if you lose 
      # the Orthanc database content. In that case, we reset the change ID to zero.
      if last_seq < current_last_seq:
        logger.warning(f'Orthanc may have been reinitialized. Setting the last Orthanc change ID (Seq) to 0')
        new_last_seq = 0

      else:
        for change in changes:
          logger.debug(f'New Orthanc change: {json.dumps(change)}')
          
          if change['ChangeType'] == 'NewInstance':
            logger.info(f"New DICOM instance in Orthanc - ID={change['ID']}")
            
            # Send a SQS message to notify of the new DICOM instance. If the message could not be 
            # sent, we interrupt the loop iteration and retry later
            if send_sqs_message({'EventType': 'NewDICOM', 'Source': f"orthanc://{change['ID']}"}) is False:
              break
          
          # Increment the last Orthanc change ID already processed
          new_last_seq = change['Seq']
        
      # Update the last Orthanc change ID in the database, if its value changed or if the previous 
      # update failed
      if new_last_seq != current_last_seq or db_update_orthanc_failed is True:
        current_last_seq = new_last_seq
        try:
          client.db_last_state.update(key=env.orthanc_host, new_value_dict={"last_seq": current_last_seq})
          db_update_orthanc_failed = False
        except Exception as e:
          logger.warning(f'Failed to update the last Orthanc change ID - {e}')
          db_update_orthanc_failed = True
          
    except Exception as e:
      logger.error(f'Failed to get and process Orthanc changes - {e}')

    # Close the DB connection after each iteration
    client.db.close()

    # Wait 5 seconds before the next iteration
    logger.debug(f"Waiting 5 seconds")
    killer.sleep(5)

  # Before the program exits
  logger.info('Stopping change pooler')


def send_sqs_message(message_dict):
  """
  Sends a SQS message. Returns True if succeeded, False otherwise.
  
  """
  try:
    logger.debug('Sending a SQS message')
    client.sqs.send_message(
      QueueUrl=env.queue_url,
      MessageBody=json.dumps(message_dict)
    )
    return True
  except Exception as e:
    logger.error(f'Failed to send a message to SQS - {e}')
    return False
