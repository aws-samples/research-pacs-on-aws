# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import re


TAG_PATH_PATTERN_KEYWORD = '[A-Za-z0-9\*]+'
TAG_PATH_PATERN_NUMBER = '[0-9A-FX@]{8}'
TAG_PATH_PATTERN_PRIVATE_CREATOR = '[0-9A-FX@]{4}\{[^\}]+\}[0-9A-FX@]{2}'
TAG_PATH_PATTERN_VR = '\{[A-Z]{2}\}'

"""
A valid tag path pattern:
- Can start with an optional "+/" to search for data elements except in the top level, or "*/" to 
  search for data elements no matter where they appear. It no prefix is provided, it only looks in 
  the top level
- Is composed of tag patterns separated by ".". Each tag pattern can either be:
    - A keyword, where you can use a wilcard "*" character
    - A 8 hexadecimal-digit tag, where you can use "X" for any digit, or "@" for odd digits
    - "xxxx{Private tag creator}xx" where x can be "0-F", "X" or "@" and "Private tag creator" 
      the name of the tag private creator.
    - "{VR}", where VR is the tag VR

Examples of valid tag path patterns:
- +/*Date: Tags whose keyword ends with "Date" and not in the top level
- */XXX@XXXX: Any tags whose group is an odd number
- 0010XXXX: Tags whose group number is "0010" in the top level
- +/Sequence.Keyword: Tags whose keyword is "Keyword", that are child of a sequence data element 
  whose tag keyword is "Sequence", and this data element cannot be in the top level
- 0029{SIEMENS MEDCOM HEADER}XX: Private tags whose private creator is "SIEMENS MEDCOM HEADER",
  and whose group number is 0029
- */{DT}: Tags whose VR is DT no matter where they appear

"""


def is_tag_path_pattern(tag_path_pattern):
  """
  Return `True` if the value is a valid tag path pattern.
  
  Args:
    tag_path_pattern (str)
  
  """
  tag_patterns, prefix = _split_tag_path_pattern(tag_path_pattern)
  for tag_pattern in tag_patterns:
    if not (
      re.fullmatch(TAG_PATH_PATTERN_KEYWORD, tag_pattern) 
      or re.fullmatch(TAG_PATH_PATERN_NUMBER, tag_pattern) 
      or re.fullmatch(TAG_PATH_PATTERN_PRIVATE_CREATOR, tag_pattern)
      or re.fullmatch(TAG_PATH_PATTERN_VR, tag_pattern)
    ):
      return False
  
  return True


def enumerate_elements_match_tag_path_patterns(ds, tag_paths, except_tag_paths, sequence_prefix=[]):
  """
  Enumerator that returns all data elements of a Dataset that matches any of the tag path patterns 
  in `tag_paths` but none of the tag path patterns in `except_tag_paths`. For each data element 
  returned, it provides (the data element, the data element 8 hexa-digit tag number, the parent 
  data element).
  
  Args:
    ds: pydicom Dataset
    tag_paths (list): List of tag path patterns
    except_tag_paths (list): List of tag path patterns
    sequence_prefix: Used for the function iteration
  
  """
  for elem in ds:
    elem_sequence = sequence_prefix + [elem]
    if elem.VR == 'SQ':
      for item in elem:
        yield from enumerate_elements_match_tag_path_patterns(item, tag_paths, except_tag_paths, elem_sequence)
    else:
      
      # Check if the data element matches none of the tag path patterns in `except_tag_paths`
      match_except_tag_paths = False
      for tag_path in except_tag_paths:
        if _elem_sequence_match_tag_path_pattern(elem_sequence, tag_path):
          match_except_tag_paths = True
          break
      if match_except_tag_paths:
        continue
      
      # Check if the data element matches at least one the tag path patterns in `tag_paths`
      match_tag_paths = False
      for tag_path in tag_paths:
        if _elem_sequence_match_tag_path_pattern(elem_sequence, tag_path):
          match_tag_paths = True
          break
      if match_tag_paths:
        elem_full_tag = '.'.join([_get_elem_tag_hexa(i) for i in elem_sequence])
        yield elem, elem_full_tag, ds


def _split_tag_path_pattern(tag_path_pattern):
  """
  Returns a list of tag patterns and the prefix for a given tag path pattern.
  
  Args:
    tag_path_pattern (str)
    
  """
  if tag_path_pattern.startswith('+/') or tag_path_pattern.startswith('*/'):
    prefix = tag_path_pattern[:2]
    tag_path_pattern = tag_path_pattern[2:]
  else:
    prefix = ''
  
  return tag_path_pattern.split('.'), prefix
  
  
def _get_elem_tag_hexa(elem):
  """
  Returns a 8-hexadecimal digit corresponding to the data element tag.
  
  Args:
    elem: pydicom Data Element
    
  """
  return hex(elem.tag.group)[2:].upper().zfill(4) + hex(elem.tag.elem)[2:].upper().zfill(4)
  
  
def _elem_match_tag_pattern(elem, tag_pattern):
  """
  Return `True` if the pydicom Data Element `elem` matches the tag pattern.
  
  Args:
    elem: pydicom Data Element
    tag_pattern (str): Tag pattern
    
  """
  # Check if it matches TAG_PATH_PATTERN_KEYWORD
  if elem.keyword and re.fullmatch(TAG_PATH_PATTERN_KEYWORD, tag_pattern):
    re_pattern = re.escape(tag_pattern)
    re_pattern = re_pattern.replace('\*', '.*')
    if re.fullmatch(re_pattern, elem.keyword):
      return True

  elem_tag_hexa = _get_elem_tag_hexa(elem)

  # Check if it matches TAG_PATH_PATERN_NUMBER
  if re.fullmatch(TAG_PATH_PATERN_NUMBER, tag_pattern):
    if _tag_hexa_match_pattern(elem_tag_hexa, tag_pattern):
      return True
  
  # Check if it matches TAG_PATH_PATTERN_PRIVATE_CREATOR
  if elem.private_creator and re.fullmatch(TAG_PATH_PATTERN_PRIVATE_CREATOR, tag_pattern):
    if _tag_hexa_match_pattern(elem_tag_hexa[:4], tag_pattern[:4]) and _tag_hexa_match_pattern(elem_tag_hexa[-2:], tag_pattern[-2:]) and elem.private_creator == tag_pattern[5:-3]:
      return True
  
  # Check if it matches TAG_PATH_PATTERN_VR
  if re.fullmatch(TAG_PATH_PATTERN_VR, tag_pattern):
    if elem.VR == tag_pattern[1:-1]:
      return True
  
  return False
  

def _tag_hexa_match_pattern(tag_hexa, pattern):
  """
  Return `True` if the hexadecimal value of a tag `tag_hexa` matches the pattern. `pattern` must 
  match TAG_PATH_PATERN_NUMBER.
  
  Args:
    tag_hexa (str): 8 hexadecimal-digit tag number
    pattern (str): hexadecimal pattern
    
  """
  for i in range(len(tag_hexa)):
    if pattern[i] == 'X':
      continue
    if pattern[i] == tag_hexa[i]:
      continue
    if pattern[i] == '@' and tag_hexa[i] in ('1', '3', '5', '7', '9', 'B', 'D', 'F'):
      continue
    return False
  
  return True


def _elem_sequence_match_tag_path_pattern(elem_sequence, tag_path_pattern):
  """
  Return `True` if the list of data elements `elem_sequence` matches the tag path pattern. 
  `elem_sequence` is composed of each tag from the top level data element to the data element 
  itself. For example the tag Sequence1.Sequence2.Tag will translate to a list
  `[elem for Sequence1, elem for Sequence2, elem for Tag]`.
  
  Args:
    elem_sequence (list): List of nested data elements
    tag_path_pattern (str)
    
  """
  tag_patterns, prefix = _split_tag_path_pattern(tag_path_pattern)

  # If prefix is '', we search for data elements from the top level only. That is why the length 
  # of `elem_sequence` must be equals to the length of `tag_patterns`.
  if prefix == '' and len(elem_sequence) != len(tag_patterns):
    return False
  
  # If prefix is '+', we search for data elements except in the top level. That is why the length 
  # of `elem_sequence` must be greater than the length of `tag_patterns`.
  if prefix == '+/' and not len(elem_sequence) > len(tag_patterns):
    return False
    
  # If prefix is '*/', we search for data elements except from the top level. That is why the length  
  # of `elem_sequence` must be greater or equal than the length of `tag_patterns`.
  if prefix == '*/' and not len(elem_sequence) >= len(tag_patterns):
    return False
  
  # We start from the end and check if each data element matches the associated tag pattern. For 
  # examples:
  # - The tag is Sequence1.Sequence2.Sequence3.00100010
  # - The tag path pattern is */Sequence*.Seq*.0010XXXX
  # - We check if 00100000 matches 0010XXXX, and Sequence3 matches Seq* and Sequence2 
  #   matches Sequence*
  for i in range(1, len(tag_patterns)+1):
    tag_pattern = tag_patterns[-i]
    elem = elem_sequence[-i]
    if not _elem_match_tag_pattern(elem, tag_pattern):
      return False
    
  return True
