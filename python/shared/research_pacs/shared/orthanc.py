# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import logging

import requests

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class OrthancClient:
  """
  Class used to interact with an Orthanc server.
  
  """
  
  def __init__(self, host, username, password):
    self._host = host
    self._username = username
    self._password = password
  
  
  def _request(self, method, full_path, raise_error=True, **kwargs):
    """
    Make a HTTP request to the Orthanc server.
    
    Args:
      method (str): HTTP method (GET, POST...)
      full_path (str): URL path that must not start with a /
      raise_error: Raise an exception if the response code is 4xx or 5xx
      **kwargs: Other keyword arguments passed to the `requests.request` function
      
    """
    url = '%s/%s' %(self._host, full_path)
    try:
      logger.debug(f'Sending a {method} request to {url}')
      response = requests.request(
        method = method,
        url = url,
        auth = requests.auth.HTTPBasicAuth(self._username, self._password),
        timeout = (5, 30),  # 5 seconds to connect, 30 seconds to read the first byte
        **kwargs
      )
      # Raise an exception if the HTTP request failed (4xx or 5xx status code)
      if raise_error is True:
        response.raise_for_status()
      return response
    except requests.exceptions.HTTPError as e:
      try:
        orthanc_error = response.json()['OrthancError']
      except:
        orthanc_error = ''
      err_msg = f'Failed to make a {method} request to {url} - ErrorCode={e.response.status_code} Error="{e}" OrthancError="{orthanc_error}"'
      logger.debug(err_msg)
      raise Exception(err_msg)
    except Exception as e:
      err_msg = f'Failed to make {method} request to {url} - Error={e}'
      logger.debug(err_msg)
      raise Exception(err_msg)


  def get_changes(self, from_seq=0, limit=100):
    """
    Return the list of changes that ocurred in Orthanc (GET /changes).
    
    Args:
      from_seq: Find changes whose change ID (Seq) are larger than `from_seq`
      limit: Maximum number of changes to return
    
    """
    params = {
      'limit': limit,
      'since': from_seq
    }
    logger.debug(f'Getting {limit} changes since Seq={from_seq}')
    response = self._request('GET', 'changes', params=params)
    response_json = response.json()
    changes = response_json['Changes']
    new_last_seq = response_json['Last']
    logger.debug(f'Returned {len(changes)} changes and LastSeq={new_last_seq}')
    return changes, new_last_seq


  def upload_instance(self, dicom_file):
    """
    Upload a DICOM file to Orthanc.
    
    Args:
      dicom_file (bytes): Content of the DICOM file to upload
    
    """
    logger.debug(f'Uploading a DICOM file')
    response = self._request('POST', 'instances', data = dicom_file)
    status = response.json()['Status']
    instance_id = response.json()['ID']
    logger.debug(f'Uploaded a DICOM file Status={status} ID={instance_id}')
    return instance_id


  def download_instance_dicom(self, instance_id, transcode=None):
    """
    Download and return a DICOM file from the Orthanc server.
    
    Args:
      instance_id (str): Orthanc instance ID
      transcode (str): You can provide a Transfer Syntax UID to download a transcoded DICOM 
        file from Orthanc
    
    """
    if transcode != None:
      parameters = {
        'Keep': ['StudyInstanceUID', 'SeriesInstanceUID', 'SOPInstanceUID'],
        'Transcode': transcode,
        "Force": True
      }
      logger.debug(f'Downloading the instance ID={instance_id} Transfer_Syntax={transcode}')
      response = self._request('POST', f'instances/{instance_id}/modify', json=parameters)
    
    else:
      logger.debug(f'Downloading the instance ID={instance_id}')
      response = self._request('GET', f'instances/{instance_id}/file')
    
    return response.content


  def count_instance_frames(self, instance_id):
    """
    Return the number of frames contained in a given instance.
    
    """
    logger.debug(f'Counting frames for instance ID={instance_id}')
    response = self._request('GET', f'instances/{instance_id}/frames')
    return len(response.json())


  def download_instance_frame(self, instance_id, accept='image/png', quality=90, frame=0):
    """
    Download one frame of the given DICOM instance as a PNG or JPEG image.
    
    Args:
      instance_id (str): Orthanc instance ID
      accept (str): Format to export ('image/png' or 'image/jpeg')
      quality (int): Quality for JPEG image between 1 and 100. Default is 90
      frame (int): Frame number
    
    """
    logger.debug(f'Downloading a frame of instance ID={instance_id} Frame={frame} Format={accept}')
    url = f'instances/{instance_id}/frames/{frame}/preview'
    if accept == 'image/jpeg':
      url += f'?quality={quality}'
    response = self._request('GET', url, headers={'Accept': accept})
    return response.content


  def delete_instance(self, instance_id):
    """
    Delete an instance from Orthanc.
    
    Args:
      instance_id (str): Orthanc instance ID
    
    """
    logger.debug(f'Deleting the instance ID={instance_id}')
    self._request('DELETE', f'instances/{instance_id}')


  def list_instance_ids(self):
    """
    Return the list of IDs of all instances stored in the Orthanc server
    
    """
    logger.debug(f'Listing the instance IDs')
    response = self._request('GET', 'instances')
    return response.json()


  def get_series_information(self, instance_id):
    """
    Return the series ID and the index in series for a given instance.
    
    Args:
      instance_id (str): Orthanc instance ID
    
    """
    logger.debug(f'Getting series information for instance ID={instance_id}')
    response = self._request('GET', f'instances/{instance_id}?full')
    response_json = response.json()
    series_id = response_json['ParentSeries']
    index_in_series = response_json['IndexInSeries'] if 'IndexInSeries' in response_json else 0
    return series_id, index_in_series


  def download_series_zip(self, series_id):
    """
    Download an entire series as a ZIP file.
    
    Args:
      series_id (str): Series ID
      
    """
    logger.debug(f'Downloading a ZIP file of the series ID={series_id}')
    response = self._request('GET', f'series/{series_id}/archive')
    return response.content
