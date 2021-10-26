# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import logging
import re
from threading import Thread
from time import sleep

from flask import g

from research_pacs.shared.util import load_file
import research_pacs.shared.dicom_json as rpacs_dicom_json
import research_pacs.shared.validation as rpacs_v

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class PermissionError(Exception):
  pass


def raise_error_if_no_permission(matching_profiles):
  if len(matching_profiles) == 0:
    raise PermissionError


class PermissionsManager:
  
  def __init__(self, location, aws_region, refresh_period=10):
    """
    Create a PermissionsManager object that is used to specify and evaluate the access 
    permissions of website users.
    
    Args:
      location: Location of the permissions file, either in Amazon S3 or a local file system
      aws_region: AWS Region where the bucket resides, if the permissions file is stored in S3
      refresh_period: The permissions file is reloaded into memory every `refresh_period` seconds
    
    """
    self._location = location
    self._aws_region = aws_region
    self._refresh_period = refresh_period
    self._permissions = None
    
    # Raise an exception if the initial file load fails
    try:
      self._load_file()
    except Exception as e:
      msg_err = f'Failed to load the permissions file - {e}'
      logger.error(msg_err)
      raise Exception(msg_err)
      
    # Start a background process that runs the function `_thread_func` to reload and store the 
    # permissions file in memory every `refresh_period` seconds
    t = Thread(target=self._thread_func, daemon=True)
    t.start()
  
  
  def _thread_func(self):
    while True:
      try:
        sleep(self._refresh_period)
        self._load_file()
      except Exception as e:
        logger.warning(f'Failed to reload the permissions file - {e}')
  
  
  def _load_file(self):
    """
    Load the permissions, validate and store its content in the variable `self._permissions`. If 
    the content validation failed, a warning is logged and the variable `self._permissions` 
    remains unchanged.
    
    """
    permissions = load_file(self._location, self._aws_region, 'yaml')
    self._permissions = self._validate_and_adapt_permissions_file(permissions)
    logger.debug(f'Refreshed the permissions file')
    
    
  @staticmethod
  def _validate_and_adapt_permissions_file(permissions):
    """
    Validate the content of the permissions file:
    
    Profiles: dict                          List of profiles
      Profile1: dict                        Profile specifications
        Description: str                    Profile description
        DICOMQueryFilter: str               [Optional] You can restrict access for this profile 
                                            to a subset of DICOM instances only, by specifying a 
                                            query similar to searching or exporting DICOM 
                                            instances.
        OrthancPathPatterns: dict           You can specify a list of Orthanc path patterns for
                                            this profile that users can request directly. If you 
                                            specify a query filter in `DICOMQueryFilter`, this 
                                            parameter is ignored, because it is not possible to 
                                            restrict access to specific DICOM instances when 
                                            providing a direct access to Orthanc Explorer or APIs
          Allow: str or list                List of path patterns to allow in the form "VERB /path"
          Deny: str or list                 List of path patterns to deny in the form "VERB /path"
        
      Profile2: ...
    Permissions:
      - Users: str or list                  Users attached to the profiles in `Profiles`. There 
                                            must be at least Users or Groups defined.
        Groups: str or list                 Groups attached to the profiles in `Profiles`. There 
                                            must be at least Users or Groups defined.
        Profiles: str or list               List of profiles attached to the users or groups
      - ...
    
    """
    # Profiles
    rpacs_v.check_dict_attribute_exists_and_type(permissions, 'Profiles', dict, 'permissions')
    for profile_name, profile in rpacs_v.enumerate_dict_and_check_item_type(permissions['Profiles'], dict, f'permissions["Profiles"]'):
      profile_path = f'permissions["Profiles"]["{profile_name}"]'
      rpacs_v.check_dict_attribute_exists_and_type(profile, 'Description', str, profile_path)

      # Check that `DICOMQueryFilter` is valid, if it is specified and not empty. Translate and 
      # store the associated JSON Path query into `profile['JSONPathQuery']`
      if 'DICOMQueryFilter' in profile and profile['DICOMQueryFilter'] != '':
        assert not 'OrthancPathPatterns' in profile, f'{profile_path} cannot have both "DICOMQueryFilter" and "OrthancPathPatterns" specified'
        try:
          profile['JSONPathQuery'] = rpacs_dicom_json.translate_query_to_jsonpath(profile['DICOMQueryFilter'])
        except:
          raise Exception(f'{profile_path}["DICOMQueryFilter"] is not a valid query')
      
      if rpacs_v.check_dict_attribute_exists_and_type(profile, 'OrthancPathPatterns', dict, profile_path, optional=True):
        path_patterns = profile['OrthancPathPatterns']
        for action in ('Allow', 'Deny'):
          if action in path_patterns:
            path_patterns[action]= rpacs_v.check_or_form_list_of_str(path_patterns[action], f'{profile_path}["OrthancPathPatterns"]["{action}"]')
            for i_pattern, pattern in enumerate(path_patterns[action]):
              assert len(pattern.split(' ')) == 2, f'{profile_path}["OrthancPathPatterns"]["{action}"][{i_pattern}] must be in the form "VERB /path"'
      
    # Permissions
    rpacs_v.check_dict_attribute_exists_and_type(permissions, 'Permissions', list, 'permissions')
    for i_permission, permission in rpacs_v.enumerate_list_and_check_item_type(permissions['Permissions'], dict, f'permissions["Permissions"]'):
      permissions_path = f'permissions["Permissions"][{i_permission}]'
      assert 'Users' in permission or 'Groups' in permission, f'Missing "Users" or "Groups" in {permissions_path}'
      assert 'Profiles' in permission, f'Missing "Profiles" in {permissions_path}]'
      
      for key in ('Users', 'Groups', 'Profiles'):
        if key in permission:
          permission[key] = rpacs_v.check_or_form_list_of_str(permission[key], f'{profile_path}["{key}"]')
      
      for profile_name in permission['Profiles']:
        assert profile_name in permissions['Profiles'].keys(), f'"{profile_name}" in {permissions_path}["Profiles"] does not exist'
    
    return permissions


  def _get_matching_profiles(self):
    """
    Find the profiles in the permissions file that match the current user's name and groups

    """
    # Find the profiles in the permissions file that match the user's name or groups
    matching_profiles = []
    for permission in self._permissions['Permissions']:
      if 'Users' in permission and g.user in permission['Users']:
        matching_profiles += permission['Profiles']
      if 'Groups' in permission:
        for group in g.groups:
          if group in permission['Groups']:
            matching_profiles += permission['Profiles']
    
    # Remove duplicates
    matching_profiles = sorted(list(set(matching_profiles)))
    return matching_profiles
  
  
  @staticmethod
  def _does_orthanc_request_match_patterns(request_patterns, method, path):
    """
    Check if the request method and path matches one of the request patterns provided in the form 
    of "VERB path" (e.g. "GET /app/**). The request method can be any HTTP verb or "ANY". The 
    request path can contain a "*" (string that contains any characters expect "/") or "**" 
    (string that contains any characters)
    
    Args:
      request_patterns (list): List of request patterns in the form "VERB path"
      method: Current request mathod
      path: Current request path
      
    """
    for pattern in request_patterns:
      pattern_method, pattern_path = pattern.split(' ')
      
      # Skip this request pattern if the method does not match
      if not (method.lower() == pattern_method.lower() or pattern_method.lower() == 'any'):
        continue
        
      # Skip this request pattern if the path does not match
      re_pattern = re.escape(pattern_path)
      re_pattern = re_pattern.replace('\*\*', '.*')
      re_pattern = re_pattern.replace('\*', '[^\/]*')
      if not re.fullmatch(re_pattern.lower(), path.lower()):
        continue
    
      # Return True (match) if both the method and the path match
      return True
    
    # If none of the request patterns match, return False
    return False
  
  
  def is_orthanc_request_allowed(self, method, path):
    """
    Check whether the current user is authorized to make a request to the Orthanc server that 
    stores the de-identified DICOM instances. Returns True if the user is authorized, False 
    otherwise.
    
    Args:
      method (str): Request method
      path (str): Request path
      
    """
    matching_profiles = self._get_matching_profiles()
    raise_error_if_no_permission(matching_profiles)
    
    for profile_name in matching_profiles:
      profile = self._permissions['Profiles'][profile_name]
      if 'OrthancPathPatterns' in profile:
      
        # Check if the profile explicitly denies the request
        if 'Deny' in profile['OrthancPathPatterns']:
          request_patterns = profile['OrthancPathPatterns']['Deny']
          if self._does_orthanc_request_match_patterns(request_patterns, method, path):
            continue
    
        # Check if the profile explicitly allows the request
        if 'Allow' in profile['OrthancPathPatterns']:
          request_patterns = profile['OrthancPathPatterns']['Allow']
          if self._does_orthanc_request_match_patterns(request_patterns, method, path):
            logger.debug(f'The {method} request to {path} is explicitly allowed by the profile {profile_name}')
            return True
    
    # Deny the request if there is no explicit Allow
    logger.debug(f'The {method} request to {path} is denied')
    return False
  
  
  def has_access_to_orthanc(self):
    """
    Check whether the current user is allowed to make direct requests to Orthanc Explorer or other
    Orthanc APIs.
    
    """
    matching_profiles = self._get_matching_profiles()
    for profile_name in matching_profiles:
      profile = self._permissions['Profiles'][profile_name]
      if 'OrthancPathPatterns' in profile:
        return True
    return False
  
  
  def get_profiles_description(self):
    """
    Return a dict that contains the description of the current user's profiles. This dict 
    structure is as follow:
    
    {
      "ProfileName": {
        "Description": str,
        "DICOMQueryFilter": str (if applicable),
        "OrthancPathPatternsAllowed": list (if applicable)
        "OrthancPathPatternsDenied": list (if applicable)
      }
    }
    
    """
    result = {}
    matching_profiles = self._get_matching_profiles()
    for profile_name in matching_profiles:

      profile = self._permissions['Profiles'][profile_name]
      result[profile_name] = {
        'Description': profile['Description']
      }
      
      if 'DICOMQueryFilter' in profile and profile['DICOMQueryFilter'] != '':
        result[profile_name]['DICOMQueryFilter'] = profile['DICOMQueryFilter']
        
      if 'OrthancPathPatterns' in profile:
        if 'Allow' in profile['OrthancPathPatterns']:
          result[profile_name]['OrthancPathPatternsAllowed'] = profile['OrthancPathPatterns']['Allow']
        if 'Deny' in profile['OrthancPathPatterns']:
          result[profile_name]['OrthancPathPatternsDenied'] = profile['OrthancPathPatterns']['Deny']

    return result


  def get_jsonpath_query(self, query):
    """
    The solution makes JSONPath queries to the PostgreSQL database to find DICOM instances that 
    match specific criteria. This function translate the "human-readable" query like `Modality 
    StrEquals CT` into a JSONPath, and apply eventual profile-specific JSONPath queries that 
    restrict access to a subset of DICOM instances (attribute `DICOMQueryFilter`).
    
    Args:
      query (str): Input query
    
    """
    jsonpath_query = rpacs_dicom_json.translate_query_to_jsonpath(query)
    matching_profiles = self._get_matching_profiles()
    raise_error_if_no_permission(matching_profiles)
    
    # Return `jsonpath_query` if at least one matching profile allows access to all DICOM 
    # instances without restriction (`DICOMQueryFilter` is not specified or empty for this 
    # profile)
    for profile_name in matching_profiles:
      profile = self._permissions['Profiles'][profile_name]
      if not 'DICOMQueryFilter' in profile or profile['DICOMQueryFilter'] == '':
        return jsonpath_query
    
    # The current user can access a given DICOM instance if any of the matching profiles allows 
    # access (JSONPath queries connected by an OR operand)
    jsonpath_profiles = [self._permissions['Profiles'][profile_name]['JSONPathQuery'] for profile_name in matching_profiles]
    jsonpath_filter = '(' + ')||('.join(jsonpath_profiles) + ')'
    
    # If `query` is empty, return only the "filtering" JSONPath query issued from the matching 
    # profiles. Otherwise, the resulting JSONPath query is an AND expression between the user 
    # query `jsonpath_query` and the filter query `jsonpath_filter`
    if query == '':
      return jsonpath_filter
    else:
      return f"(({jsonpath_query})&&{jsonpath_filter})"
