# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import logging
import re

import pydicom

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

    
def convert_dicom_to_json(dicom):
  """
  Convert a pydicom Dataset to a JSON document. The dict returned has the following structure, 
  and is used to index DICOM data elements into the PostgreSQL database, or to evaluate a DICOM 
  query on a given DICOM file:
  
  {
    "HexaNumber": str or list of str
    "SequenceHexaNumber": dict or list of dict
  }
  
  Example:
  
  {
    "00080008": ["DERIVED, "PRIMARY"],
    "00100010": "Patient Name",
    "00082112": {
      "00081150": "value"
    }
  }
  
  Args:
    dicom: pydicom Dataset
    
  """
  logger.debug('Converting a DICOM file to a JSON document')
  # Function that modifies recursively the content of the JSON document returned by the pydicom 
  # `to_json_dict()` function to make it easier to index and search DICOM data elements in the 
  # PostgreSQL database
  def process_level(level_dict):
    new_level_dict = {}
    for tag, element in level_dict.items():
      # `element` may not contain an attribute `Value` if the tag is empty, or if it contains a 
      # binary value like PixelData
      if not 'Value' in element:
        new_level_dict[tag] = ''
      else:
        # `element['Value']` should be a list, whatever the tag VM (Value Multiplicity)
        if isinstance(element['Value'], list):
          # Parse the content of `element['Value']` differently if the VR is SQ, PN or something 
          # else. Numbers are converted to strings.
          if element['vr'] == 'SQ':
            new_level_dict[tag] = [process_level(i) for i in element['Value']]
          elif element['vr'] == 'PN':
            new_level_dict[tag] = [i['Alphabetic'] if 'Alphabetic' in i else str(i) for i in element['Value']]
          else:
            new_level_dict[tag] = [str(i) for i in element['Value']]
          # If there is a single item in the list, remove the list and keep only the item value
          if len(new_level_dict[tag]) == 1:
            new_level_dict[tag] = new_level_dict[tag][0]
    return new_level_dict
  
  # Generate and return a JSON document that contains both dataset and meta header information
  try:
    j = process_level(dicom.to_json_dict())
    j.update(process_level(dicom.file_meta.to_json_dict()))
    return j
  except Exception as e:
    err_msg = f'Failed to convert the DICOM file to a JSON document - {e}'
    logger.debug(err_msg)
    raise Exception(err_msg)


def get_top_level_elem_value_from_dict(dicom_json, tag):
  """
  Returns a string value for a specific data element who tag is `tag`. The data element must be 
  at the top level of the JSON document.
  
  Args:
    dicom_json (dict)
    tag (str): Hexadecimal tag (e.g. 00080060) or keyword (e.g. Modality)
  
  """
  try:
    logger.debug(f'Retrieving the value of the top-level tag "{tag}"')
    tag_int = pydicom.datadict.tag_for_keyword(tag)
    if tag_int != None:
      tag_key = hex(tag_int)[2:].upper().zfill(8)
    else:
      tag_key = tag
    if not tag_key in dicom_json:
      return ''
    elif isinstance(dicom_json[tag_key], list):
      return ', '.join(dicom_json[tag_key])
    elif isinstance(dicom_json[tag_key], dict):
      return json.dumps(dicom_json[tag_key])
    else:
      return str(dicom_json[tag_key])
      
  except Exception as e:
    err_msg = f'Failed to retrieve the value of the top-level tag "{tag}" - {e}'
    logger.debug(err_msg)
    raise Exception(err_msg)
  
  
def add_keywords_to_dicom_json(dicom_json):
  """
  Replace in the JSON document returned by the function `convert_dicom_to_json`the hexadecimal 
  tags by "xxxx,xxxx [keyword]" if a standard keyword exists for this tag (e.g. "00080060" is 
  replaced by "0008,0060 Modality") or by "xxxx,xxxx" if there is no keyword (e.g. "00090010" is
  replaced by "0009,0010").
  
  Args:
    dicom_json (dict): Input JSON document with hexadecimal tags
    
  """
  logger.debug(f'Adding keywords to a JSON document')
  
  def process_level(level_dict):
    new_level_dict = {}
    for tag_hexa, value in level_dict.items():
      # Check if the tag hexadecimal value matches a known standard keyword in the pydicom 
      # dictionary. We don't use private dictionaries here
      tag_int = int(tag_hexa, 16)
      tag_hexa_formatted = f'{tag_hexa[0:4]},{tag_hexa[4:8]}'
      tag_keyword = pydicom.datadict.keyword_for_tag(tag_int)
      if tag_keyword != '':
        tag_key = f'{tag_hexa_formatted} {tag_keyword}'
      else:
        tag_key = tag_hexa_formatted
      # Iterate recursively
      if isinstance(value, list):
        new_level_dict[tag_key] = [process_level(i) if isinstance(i, dict) else i for i in value]
      elif isinstance(value, dict):
        new_level_dict[tag_key] = process_level(value)
      else:
        new_level_dict[tag_key] = value
    return new_level_dict
    
  try:
    return process_level(dicom_json)
  except Exception as e:
    err_msg = f'Failed to replace DICOM tags by keywords - {e}'
    logger.debug(err_msg)
    raise Exception(err_msg)


def translate_query_to_jsonpath(query):
  """
  Transform a DICOM query to a PostgreSQL JSONPath query. For example: `Modality Equals CT 
  AND (Manufacturer Equals GE* OR Manufacturer Equals Philips*)` returns `@.00080060 like_regex 
  "CT" flag "i" && (@.00080070 like_regex "GE.*" flag "i" || @.00080070 like_regex "Philips.*" 
  flag "i")`
  
  Args:
    query (str): Input query
    
  """
  logger.debug(f'Translating the query "{query}" to a JSON Path query')
  try:
    
    # If the query is empty, return an empty JSONPath query
    if query.strip() == '':
      return ''
  
    # RegEx pattern of one query condition (e.g. Tag StrEquals Value)
    pattern = (
      '([a-zA-Z0-9\.]+) +' # Tag
      '(?:' # One of the following
      '((?i:(?:Exists|NotExists|Empty|NotEmpty)))|' # Exists|NotExist|Empty|NotEmpty 
      '((?i:(?:NbEquals|NbNotEquals|NbGreater|NbLess))) +([0-9]+(?:\.[0-9]+)?)|' # NbEquals|NbNotEquals|NbGreater|NbLess number
      '((?i:(?:StrEquals|StrNotEquals))) +(?:([^"() ]+)|"([^"]*)")' # StrEquals|StrNotEquals string
      ')'
    )
    
    pg_query = ''
    previous_left = 0
    str_between_conditions = ''
    
    # Parse string between query conditions. Example: In `PatientName StrEquals A OR PatientName 
    # StrEquals B`, ` OR ` is a string between two conditions.
    def parse_between_conditions(string):
      new_string = string.lower().replace(' ', '').replace('and', ' && ').replace('or', ' || ')
      for char in new_string:
        assert char in '()&| '
      return new_string
    
    # For each condition found in the query string
    conditions = re.finditer(pattern, query)
    for condition in conditions:
      cur_left, cur_right = condition.span()
      
      # Parse the string at the left of this condition
      if previous_left < cur_left:
        tmp = parse_between_conditions(query[previous_left:cur_left])
        pg_query += tmp
        str_between_conditions += tmp
      previous_left = cur_right
      
      # Get the tag of the element corresponding to the keyword(s `condition.group(1)` contains the 
      # condition tag. For example, `RequestedProcedureCodeSequence.CodeMeaning` gives
      # `00321064.00080104`
      tag_hexa_split = []
      tag_keywords = condition.group(1)
      for tag_keyword in tag_keywords.split('.'):
        tag_int = pydicom.datadict.tag_for_keyword(tag_keyword)
        if tag_int != None:
          hexa = hex(tag_int)[2:].upper().zfill(8)
          tag_hexa_split.append(hexa)
        else:
          tag_hexa_split.append(tag_keyword)
      tag_hexa = '.'.join(tag_hexa_split)
      
      # If the operator is Exists, NotExists, Empty or NotEmpty
      # `condition.group(2)` contains the operator
      operator = condition.group(2)
      if operator != None:
        if operator.lower() == 'exists':
          pg_query += f'exists(@.{tag_hexa})'
        elif operator.lower() == 'notexists':
          pg_query += f'!(exists(@.{tag_hexa}))'
        elif operator.lower() == 'empty':
          pg_query += f'@.{tag_hexa} == ""'
        elif operator.lower() == 'notempty':
          pg_query += f'!(@.{tag_hexa} == "")'
      
      # If the operator is NbEquals, NbNotEquals, Greater or Less
      # `condition.group(3)` contains the operator that manipulates numbers
      # `condition.group(4)` contains the value
      operator = condition.group(3)
      if operator != None:
        nb_value = condition.group(4)
        if operator.lower() == 'nbequals':
          pg_query += f'@.{tag_hexa}.double() == {nb_value}'
        elif operator.lower() == 'nbnotequals':
          pg_query += f'!(@.{tag_hexa}.double() == {nb_value})'
        elif operator.lower() == 'nbgreater':
          pg_query += f'@.{tag_hexa}.double() > {nb_value}'
        elif operator.lower() == 'nbless':
          pg_query += f'@.{tag_hexa}.double() < {nb_value}'
      
      # If the operator is StrEquals or StrNotEquals
      # `condition.group(5)` contains the operator that manipulates strings
      # `condition.group(6)` or `condition.group(7)` contains the value
      operator = condition.group(5)
      if operator != None:
        str_value = condition.group(7) if condition.group(6) is None else condition.group(6)
        # The value must be contain ' or " characters
        assert not ("'" in str_value or '"' in str_value), "The condition value cannot contain \" or '"
        escape_str_value = re.escape(str_value).replace('\*', '.*')
        reg_value = f'^{escape_str_value}$'
        if operator.lower() == 'strequals':
          pg_query += f'@.{tag_hexa} like_regex "{reg_value}" flag "i"'
        elif operator.lower() == 'strnotequals':
          pg_query += f'!(@.{tag_hexa} like_regex "{reg_value}" flag "i"'
  
    # Parse the string at the right of the last condtion
    if previous_left < len(query):
      tmp = parse_between_conditions(query[previous_left:])
      pg_query += tmp
      str_between_conditions += tmp

    # Check if there is the small number of opening and closing parathesis and if there is no 
    # empty parenthesis block
    assert str_between_conditions.count('(') == str_between_conditions.count(')')
    assert str_between_conditions.count('()') == 0
    
    return pg_query

  except Exception as e:
    err_msg = f'Failed to translate the query "{query}" to a JSONPath query - {e}'
    logger.debug(err_msg)
    raise ValueError(err_msg)
