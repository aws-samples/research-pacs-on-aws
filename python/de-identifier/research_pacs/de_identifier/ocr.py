# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import logging
from io import BytesIO

import boto3

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def get_box_coordinates(orthanc, instance_id, region, dimensions):
  """
  Detect burned-in text annotations with Amazon Rekognition and return text box coordinates.
  
  Args:
    client: OrthancClient object
    instance_id (str): DICOM instance ID
    region (str): AWS Region where to use Amazon Rekognition
    dimensions (tuple): Tuple width, height
  
  """
  logger.debug('Finding burned-in text annotations with OCR')
  
  # Export the first frame as a JPEG file. It must be smaller than 5 MB in order to be passed as 
  # image bytes to Amazon Rekogniton. If the file is larger than 5 MB, we reduce the JPEG quality
  # and retry
  try:
    logger.debug('Retrieving the first frame as JPEG image')
    for quality in range(90, 40, -10):
      first_frame = orthanc.download_instance_frame(instance_id, accept='image/jpeg', quality=quality)
      if len(first_frame) < 5242880:
        break
      first_frame = None
      
  except Exception as e:
    raise Exception(f'Failed to export the first frame as a JPEG file with Orthanc - {e}')
  
  if first_frame is None:
    raise Exception('Failed to export the first frame as a JPEG file smaller than 5 MB, which is needed for Amazon Rekognition')
  
  # Detect text with Amazon Rekognition
  client = boto3.client('rekognition', region_name=region)
  response = client.detect_text(
    Image={'Bytes': first_frame},
    Filters={'WordFilter': {'MinConfidence': 90}}
  )
  
  # Calculate and return the box coordinates with a minimum confidence of 90%
  try:
    result = []
    if 'TextDetections' in response and len(response['TextDetections']) > 0:
      width, height = dimensions
      for detection in response['TextDetections']:
        if detection['Type'] == 'WORD':
          left = round(detection['Geometry']['BoundingBox']['Left'] * width)
          top = round(detection['Geometry']['BoundingBox']['Top'] * height)
          right = left + round(detection['Geometry']['BoundingBox']['Width'] * width) + 1
          bottom = top + round(detection['Geometry']['BoundingBox']['Height'] * height) + 1
          result.append([left, top, right, bottom])
    return result
    
  except Exception as e:
    raise Exception(f'Failed to detect text with Amazon Rekognition - {e}')