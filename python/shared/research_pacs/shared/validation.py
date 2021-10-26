# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

def check_dict_attribute_exists_and_type(parent_dict, attribute, expected_type, path, optional=False):
  """
  Check if the attribute `attribute` exists in the dict `parent_dict` and check that the type of 
  `parent_dict[attribute]` is of `expected_type`.
  
  Args:
    parent_dict (dict)
    attribute (str)
    expected_type (type)
    path (str): Full path of `parent_dict` for logging purposes
    optional (bool): If set to `True`, the function returns `False` if the attribute does not 
      exist in the parent dict, but will not raise an exception.
  
  """
  if optional is True and not attribute in parent_dict:
    return False
  assert attribute in parent_dict, f'{path}["{attribute}"] is missing'
  assert isinstance(parent_dict[attribute], expected_type), f'{path}["{attribute}"] is not a {expected_type.__name__}'
  return True
  
  
def check_list_item_type(parent_list, expected_type, path):
  """
  Check that all items of the list `parent_list` are of type `expected_type`
  
  Args:
    parent_list (list)
    expected_type (type)
    path (str): Full path of `parentlist` for logging purposes
    
  """
  for i_item, item in enumerate(parent_list):
    assert isinstance(item, expected_type), f'{path}[{i_item}] is not a {expected_type.__name__}'
  
  
def enumerate_list_and_check_item_type(parent_list, expected_type, path):
  """
  Enumerator that goes through each item of `parent_list` and check that it is of type
  `expected_type`.
  
  Args:
    parent_list (list)
    expected_type (type)
    path (str): Full path of `parent_list` for logging purposes
    
  """
  for i_item, item in enumerate(parent_list):
    assert isinstance(item, expected_type), f'{path}[{i_item}] is not a {expected_type.__name__}'
    yield i_item, item
    
    
def check_dict_item_type(parent_dict, expected_type, path):
  """
  Check that all attributes of the dict `parent_dict` are of type `expected_type`
  
  Args:
    parent_dict (dict)
    expected_type (type)
    path (str): Full path of `parent_dict` for logging purposes
    
  """
  for key, value in parent_dict.items():
    assert isinstance(value, expected_type), f'{path}["{key}"] is not a {expected_type.__name__}'
    
    
def enumerate_dict_and_check_item_type(parent_dict, expected_type, path):
  """
  Enumerator that goes through each attribute of `parent_dict` and check that it is of type
  `expected_type`.
  
  Args:
    parent_dict (dict)
    expected_type (type)
    path (str): Full path of `parent_dict` for logging purposes
    
  """
  for key, value in parent_dict.items():
    assert isinstance(value, expected_type), f'{path}["{key}"] is not a {expected_type.__name__}'
    yield key, value
    
    
def check_or_form_list_of_str(item, path):
  """
  Check that `item` is a string or a list of strings. If `item` is a string, the function returns 
  a list that contains a single item (the string).
  
  Args:
    item (should be a str or a list)
    path (str): Full path of `item` for logging purposes
  
  """
  if isinstance(item, str):
    item = [item]
  assert isinstance(item, list), f'{path} is not a string or a list of a strings'
  for i_value, value in enumerate(item):
    assert isinstance(value, str), f'{path} is not a string or a list of a strings'
  return item