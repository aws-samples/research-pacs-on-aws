# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import re

import pydicom


TAG_PATH_KEYWORD = '([A-Za-z0-9]+)(?:\[(\d+|%)\])?'
TAG_PATH_NUMBER = '([0-9A-F]{8})(?:\[(\d+|%)\])?'

"""
A valid tag path is composed of tag separated by ".". Each tag can either be a keyword, or a 
8 hexadecimal-digit. It can optionally ends with an item-number `[x]` (x is a number of `@`
for the item-number wildcard) if the data element is a sequence.

Examples of valid tag path:
- PatientName
- Sequence[0].Tag1: Data element whose tag is `Tag1` in the first value of the top-level data 
  element `Sequence`
- Sequence[%].Tag1: Data element whose tag is `Tag1` in the all values of the top-level data 
  element `Sequence`

"""


def is_tag_path(tag_path):
  """
  Return `True` if the value is a valid tag path (either the tag number or the keyword).
  
  Args:
    tag (str)
  
  """
  for tag in tag_path.split('.'):
    if not (re.fullmatch(TAG_PATH_KEYWORD, tag) or re.fullmatch(TAG_PATH_NUMBER, tag)):
      return False
  return True


def enumerate_parent_elements(ds, tag_path):
  """
  Enumerator that returns all data elements that are the parent of the tag to add, and the tag 
  number.
  
  Args:
    ds: pydicom Dataset
    tag_path (str)
    
  """
  tag_path_split = tag_path.split('.')
  tag = tag_path_split[0]
  tag_int, value_index = _parse_tag(tag)
  
  # If this is the last element of the tag path
  if len(tag_path_split) == 1:
    yield ds, tag_int
    
  else:
    if not tag_int in ds:
      raise Exception(f'The tag "{tag}" does not exist in the tag path')
    
    # The intermediate data elements must be a Sequence
    elem = ds[tag_int]
    if elem.VR != 'SQ':
      raise Exception('The tag "{tag}" must be a sequence')

    # Iterate on each sequence item, according to what the item-number defined in the tag path
    items_range = range(len(elem.value)) if (value_index == '%' or value_index is None) else [int(value_index)]
    for i in items_range:
      yield from enumerate_parent_elements(elem.value[i], '.'.join(tag_path_split[1:]))

    
def _parse_tag(tag):
  """
  Returns the tag hexadecimal number and the item-number index if it is provided, or `None` if not.
  
  """
  match = re.fullmatch(TAG_PATH_NUMBER, tag)
  if match:
    tag_int = int(match.group(1), 16)
    return tag_int, match.group(2)
    
  match = re.fullmatch(TAG_PATH_KEYWORD, tag)
  if match:
    tag_int = pydicom.datadict.tag_for_keyword(match.group(1))
    if tag_int:
      return tag_int, match.group(2)
  
  raise Exception(f'The tag "{tag}" does not correspond to a valid tag')
