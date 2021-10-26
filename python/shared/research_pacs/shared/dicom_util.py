# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import logging
from io import BytesIO

import pydicom

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


def load_dicom_from_bytes(dicom_bytes):
  """
  Open and return a pydicom Dataset from bytes.
  
  Args:
    dicom_bytes (bytes): Content of the DICOM file
  
  """
  try:
    logger.debug('Opening DICOM file with pydicom')
    return pydicom.dcmread(pydicom.filebase.DicomBytesIO(dicom_bytes))
  except Exception as e:
    err_msg = f'Failed to open the DICOM file - {e}'
    logger.debug(err_msg)
    raise Exception(err_msg)
    
    
def get_dimensions(dicom):
  """
  Return the frame dimensions (width, height).
  
  Args:
    dicom: pydicom Dataset
  
  """
  try:
    width = dicom.Columns
    height = dicom.Rows
    return width, height
  except:
    raise Exception('Missing "Rows" or "Columns" DICOM tag')
    

def get_samples_per_pixel(dicom):
  """
  Return the number of pixels per sample.
  
  Args:
    dicom: pydicom Dataset
  
  """
  try:
    return dicom.SamplesPerPixel
  except:
    raise Exception('Missing "SamplesPerPixel" DICOM tag')


def get_transfer_syntax_uid(dicom):
  """
  Return the Transfer Syntax UID.
  
  Args:
    dicom: pydicom Dataset
  
  """
  return dicom.file_meta.TransferSyntaxUID
    
    
def get_sop_instance_uid(dicom):
  """
  Return the SOP Instance UID.
  
  Args:
    dicom: pydicom Dataset
  
  """
  return dicom.SOPInstanceUID
  

def set_sop_instance_uid(dicom, sop_instance_uid=None):
  """
  Replace the SOP Instance UID by `sop_instance_uid`, or by a random UID  if no 
  `sop_instance_uid` is provided.
  
  Args:
    dicom: pydicom Dataset
    sop_instance_uid (str, Optional): New SOP Instance UID. Will generate a random UID if 
      equals to `None`
      
  """
  if sop_instance_uid:
    new_uid = sop_instance_uid
  else:
    new_uid = pydicom.uid.generate_uid()
  dicom.SOPInstanceUID = new_uid
  dicom.file_meta.MediaStorageSOPInstanceUID = new_uid


def export_dicom(dicom):
  """
  Export a pydicom Dataset as bytes.
  
  Args:
    dicom: pydicom Dataset
  
  """
  out = BytesIO()
  dicom.save_as(out)
  return out.getvalue()
