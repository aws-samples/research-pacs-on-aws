# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import datetime
import logging
import json
import random
import string

import numpy as np
import pydicom

import research_pacs.de_identifier.dicom_tag_path as dicom_tp
import research_pacs.de_identifier.dicom_tag_path_pattern as dicom_tpp
import research_pacs.shared.dicom_util as rpacs_dicom_util
import research_pacs.shared.dicom_json as rpacs_dicom_json
import research_pacs.shared.validation as rpacs_v

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class DicomDeidentifier:
  """
  Class to de-identify a DICOM file. You should call the functions in the following order:
  - `__init__` to create a DicomDeidentifier object and initialize the config file
  - `load_dicom` to load the DICOM file, get matching labels and transformations to apply
  - `is_transcoding_needed` to determine if a transcoded version of the file must be provided
    in order to alter pixel data (start again from `load_dicom` in that case)
  - `is_ocr_needed` to determine if a OCR engine must be used to find burned-in text annotations
  - `add_box_coordinates` to add the coordinates of boxes to mask after OCR
  - `apply_transformations` to apply the transformations
  - `export_dicom` to export the de-identified DICOM file
  
  """
  
  def __init__(self, config, db, db_mapping):
    """
    Creates a DicomDeidentifier object and validate the config file.
    
    Args:
      config (dict): Config file
      db: DB object
      db_mapping: DBDicomMapping object
    
    """
    self._config = config
    self._db = db
    self._db_mapping = db_mapping
    self.dicom = None
    try:
      logger.debug('Validating the content of the config file')
      self._validate_and_adapt_config_file()
    except Exception as e:
      raise Exception(f'The config file is invalid - {e}')
  
  
  def load_dicom(self, dicom_bytes, src_transfer_syntax=None, initial_load=True):
    """
    Load a DICOM file with pydicom from the file bytes, find the labels that match the DICOM file, 
    determine whether the DICOM file should be de-identified and forwarded to the destination 
    Orthanc server, and, in this case, find all transformations that should be apply to the DICOM 
    file.
    
    The function returns the list of matching labels, and whether the DICOM file should be skipped 
    or forwarded.
    
    Args:
      dicom_bytes (bytes): DICOM file
      src_transfer_syntax (str): You can pass the initial transfer syntax before the DICOM file 
        was transcoded
      initial_load (bool): Set to `False` to reload the pydicom dataset from a new bytes object,
        without calculating the matching labels, and transformations to apply
    
    """
    logger.debug('Loading a new DICOM file in the DicomDeidentifier object')
    self.dicom = rpacs_dicom_util.load_dicom_from_bytes(dicom_bytes)
    self._src_transfer_syntax = src_transfer_syntax if src_transfer_syntax != None else self.dicom.file_meta.TransferSyntaxUID
    
    if initial_load is True:
      self._matching_labels = self._find_matching_labels()
      skipped = not self._do_labels_match_scope_rules(self._matching_labels, self._config['ScopeToForward'])
      if skipped is False:
        self._transformations, self._remove_burned_in_annotations, self._use_ocr = self._find_transformations_to_apply()
      return self._matching_labels, skipped

    else:
      return self._matching_labels, False
  
  
  def _validate_and_adapt_config_file(self):
    """
    Validate the content of the config file, and prepare it for the following computation like 
    translating DICOM query filters to JSONPath queries.
    
    Labels: list                          List of labels
      - Name: str                         Label name
        DICOMQueryFilter: str             [Optional] DICOM query filter similar to searching or 
                                          exporting DICOM instances. If you don't provide a query 
                                          or if the query is empty, the label matches all DICOM 
                                          instances
    Categories: list                      List of categories. A category is a set of labels
      - Name: str                         Category name
        Labels: list                      List of labels associated with this category
    ScopeToForward: dict                  List of labels or categories that should be forwarded to 
                                          the target Orthanc server
      Labels: str or list
      ExceptLabels: str or list
      Categories: str or list
      ExceptCategories: str or list
    Transformations: list                 List of transformations to apply
      - Scope: dict                       Scope to which the transformation specified in this item 
                                          should apply. Similar to "ScopeToForward"
        [See below]                       See inline comments for the possible types of 
                                          transformations
        
    """
    VALID_REUSE_VALUE = ('Always', 'SamePatient', 'SameStudy', 'SameSeries', 'SameInstance')
    
    def label_exists(label_name):
      for label in self._config['Labels']:
        if label['Name'] == label_name:
          return True
      return False
      
    def category_exists(category_name):
      if not 'Categories' in self._config:
        return False
      for category in self._config['Categories']:
        if category['Name'] == category_name:
          return True
      return False
      
    def check_scope_rules(rules, path):
      """
      Args:
        rules (dict): Dict that can contain `Labels`, `ExceptLabels`, `Categories`, 
          `ExceptCategories` attributes
        path (str): Path to this dict in the config file
      
      """
      for rule_type in ('Labels', 'ExceptLabels', 'Categories', 'ExceptCategories'):
        if rule_type in rules:
          if isinstance(rules[rule_type], str):
            rules[rule_type] = [rules[rule_type]]
          assert isinstance(rules[rule_type], list), f'{path}["{rule_type}"] is not a string or a list of strings'
          rpacs_v.check_list_item_type(rules[rule_type], str, f'{path}["{rule_type}"]')
          for item in rules[rule_type]:
            if rule_type in ('Labels', 'ExceptLabels'):
              assert item == 'ALL' or label_exists(item), f'"{item}" is not a valid label. Make sure it exists in config["Labels"]'
            else:
              assert category_exists(item), f'"{item}" is not a valid category. Make sure it exists in config["Categories"]'      

    def check_tag_patterns_exist(element, path):
      """
      Check if the element contains an attribute "TagPatterns" that is a path pattern or a list of 
      path patterns, and an optional "ExceptTagPatterns".
      
      Args:
        element (dict)
        path (str)
      
      """
      assert 'TagPatterns' in element, f'{path}["TagPatterns"] is missing'
      element['TagPatterns'] = rpacs_v.check_or_form_list_of_str(element['TagPatterns'], f'{path}["TagPatterns"]')
      for i_tag_pattern, tag_pattern in enumerate(element['TagPatterns']):
        assert dicom_tpp.is_tag_path_pattern(tag_pattern), f'{path}["TagPatterns"][{i_tag_pattern}] is not a valid tag pattern'
      
      if 'ExceptTagPatterns' in element:
        element['ExceptTagPatterns'] = rpacs_v.check_or_form_list_of_str(element['ExceptTagPatterns'], f'{path}["ExceptTagPatterns"]')
        for i_tag_pattern, tag_pattern in enumerate(element['ExceptTagPatterns']):
          assert dicom_tpp.is_tag_path_pattern(tag_pattern), f'{path}["ExceptTagPatterns"][{i_tag_pattern}] is not a valid tag pattern'
      else:
        element['ExceptTagPatterns'] = []

    # Labels
    rpacs_v.check_dict_attribute_exists_and_type(self._config, 'Labels', list, 'config')
    for i_label, label in rpacs_v.enumerate_list_and_check_item_type(self._config['Labels'], dict, 'config["Labels"]'):
      rpacs_v.check_dict_attribute_exists_and_type(label, 'Name', str, f'config["Labels"][{i_label}]')

      # Check that `DICOMQueryFilter` is valid, if it is specified and not empty. Translate and 
      # store the associated JSON Path query into `label['JSONPathQuery']`
      if 'DICOMQueryFilter' in label and label['DICOMQueryFilter'] != '':
        try:
          label['JSONPathQuery'] = rpacs_dicom_json.translate_query_to_jsonpath(label['DICOMQueryFilter'])
        except:
          raise Exception(f'label["Labels"][{i_label}]["DICOMQueryFilter"] is not a valid query')
    
    # Categories
    if rpacs_v.check_dict_attribute_exists_and_type(self._config, 'Categories', list, 'config', optional=True) is True:
      for i_category, category in rpacs_v.enumerate_list_and_check_item_type(self._config['Categories'], dict, 'config["Categories"]'):
        rpacs_v.check_dict_attribute_exists_and_type(category, 'Name', str, f'config["Categories"][{i_category}]')
        rpacs_v.check_dict_attribute_exists_and_type(category, 'Labels', list, f'config["Categories"][{i_category}]')
        rpacs_v.check_list_item_type(category['Labels'], str, f'config["Categories"][{i_category}]["Labels"]')

    # Scope to forward
    rpacs_v.check_dict_attribute_exists_and_type(self._config, 'ScopeToForward', dict, 'config')
    check_scope_rules(self._config['ScopeToForward'], 'config["ScopeToForward"]')

    # Transformations
    rpacs_v.check_dict_attribute_exists_and_type(self._config, 'Transformations', list, 'config')
    for i_t, t in rpacs_v.enumerate_list_and_check_item_type(self._config['Transformations'], dict, 'config["Transformations"]'):
      t_path = f'config["Transformations"][{i_t}]'
      rpacs_v.check_dict_attribute_exists_and_type(t, 'Scope', dict, t_path)
      check_scope_rules(t['Scope'], f'{t_path}["Scope"]')

      # ShiftDateTime
      #   - TagPatterns: str or list              List of UID tag patterns to shift
      #     ExceptTagPatterns: str or list        Except this list of tag patterns
      #     ShiftBy: int                          Will shift by a random number of days (if Date) 
      #                                           or seconds (if DateTime or Time) between
      #                                           `-ShiftBy` and `+ShiftBy`
      #     ReuseMapping: str                     [Optional] Scope of the mapping
      if rpacs_v.check_dict_attribute_exists_and_type(t, 'ShiftDateTime', list, t_path, optional=True) is True:
        for i_element, element in rpacs_v.enumerate_list_and_check_item_type(t['ShiftDateTime'], dict, f'{t_path}["ShiftDateTime"]'):
          check_tag_patterns_exist(element, f'{t_path}["ShiftDateTime"][{i_element}]')
          rpacs_v.check_dict_attribute_exists_and_type(element, 'ShiftBy', int, f'{t_path}["ShiftDateTime"]')
          if rpacs_v.check_dict_attribute_exists_and_type(element, 'ReuseMapping', str, f'{t_path}["ShiftDateTime"]', optional=True) is True:
            assert element['ReuseMapping'] in VALID_REUSE_VALUE, f'{t_path}["ShiftDateTime"][{i_element}]["ReuseMapping"] is invalid'

      # RandomizeText
      #   - TagPatterns: str or list              List of UID tag patterns to shift
      #     ExceptTagPatterns: str or list        Except this list of tag patterns
      #     Split: str                            Split the element value on `Split` and randomize
      #                                           each item obtained separately
      #     IgnoreCase: bool                      Specified whether the original value must be 
      #                                           lowercased before being randomized. Default is
      #                                           `False`.
      #     ReuseMapping: str                     [Optional] Scope of the mapping
      if rpacs_v.check_dict_attribute_exists_and_type(t, 'RandomizeText', list, t_path, optional=True) is True:
        for i_element, element in rpacs_v.enumerate_list_and_check_item_type(t['RandomizeText'], dict, f'{t_path}["RandomizeText"]'):
          check_tag_patterns_exist(element, f'{t_path}["RandomizeText"][{i_element}]')
          if rpacs_v.check_dict_attribute_exists_and_type(element, 'Split', str, f'{t_path}["RandomizeText"]', optional=True) is False:
            element['Split'] = None
          if rpacs_v.check_dict_attribute_exists_and_type(element, 'IgnoreCase', bool, f'{t_path}["RandomizeText"]', optional=True) is False:
            element['IgnoreCase'] = False
          if rpacs_v.check_dict_attribute_exists_and_type(element, 'ReuseMapping', str, f'{t_path}["RandomizeText"]', optional=True) is True:
            assert element['ReuseMapping'] in VALID_REUSE_VALUE, f'{t_path}["RandomizeText"][{i_element}]["ReuseMapping"] is invalid'

      # RandomizeUID:
      #   - TagPatterns: str or list              List of UID tag patterns to randomize
      #     ExceptTagPatterns: str or list        Except this list of tag patterns
      #     PrefixUID: str                        [Optional] UID prefix to use when creating the 
      #                                           UID. Default is the pydicom root UID
      if rpacs_v.check_dict_attribute_exists_and_type(t, 'RandomizeUID', list, t_path, optional=True) is True:
        for i_element, element in rpacs_v.enumerate_list_and_check_item_type(t['RandomizeUID'], dict, f'{t_path}["RandomizeUID"]'):
          check_tag_patterns_exist(element, f'{t_path}["RandomizeUID"][{i_element}]')
          rpacs_v.check_dict_attribute_exists_and_type(element, 'Prefix', str, f'{t_path}["RandomizeUID"]', optional=True)
      
      # AddTags
      #   - Tag: str                              Tag path
      #     VR: str                               Value Representation of the tag
      #     Value: str                            Value of the tag to create
      #     OverwriteIfExists                     If the tag already exists, set `True` to 
      #                                           overwrite its value. Default is `False`
      if rpacs_v.check_dict_attribute_exists_and_type(t, 'AddTags', list, t_path, optional=True) is True:
        for i_element, element in rpacs_v.enumerate_list_and_check_item_type(t['AddTags'], dict, f'{t_path}["AddTags"]'):
          rpacs_v.check_dict_attribute_exists_and_type(element, 'Tag', str, f'{t_path}["AddTags"]')
          assert dicom_tp.is_tag_path(element['Tag']), f'{t_path}["AddTags"][{i_element}]["Tag"] is not a valid tag path'
          rpacs_v.check_dict_attribute_exists_and_type(element, 'VR', str, f'{t_path}["AddTags"]')
          rpacs_v.check_dict_attribute_exists_and_type(element, 'Value', str, f'{t_path}["AddTags"]')
          if rpacs_v.check_dict_attribute_exists_and_type(element, 'OverwriteIfExists', bool, f'{t_path}["AddTags"]', optional=True) is False:
            element['OverwriteIfExists'] = False
      
      # RemoveBurnedInAnnotations:
      #   - Type: str                     OCR or Manual
      #     BoxCoordinates: list          [Conditional] Provide a list of box coordinates. Each 
      #                                   box coordinate is a 4-element list with integer (left, 
      #                                   top, right, bottom)
      if rpacs_v.check_dict_attribute_exists_and_type(t, 'RemoveBurnedInAnnotations', list, t_path, optional=True) is True:
        for i_element, element in rpacs_v.enumerate_list_and_check_item_type(t['RemoveBurnedInAnnotations'], dict, f'{t_path}["RemoveBurnedInAnnotations"]'):
          rpacs_v.check_dict_attribute_exists_and_type(element, 'Type', str, f'{t_path}["RemoveBurnedInAnnotations"][{i_element}]')
          assert element['Type'] in ('OCR', 'Manual'), f'{t_path}["RemoveBurnedInAnnotations"][{i_element}]["Type"] must be equal to "OCR" or "Manual"'
          
          if element['Type'] == 'Manual':
            rpacs_v.check_dict_attribute_exists_and_type(element, 'BoxCoordinates', list, f'{t_path}["RemoveBurnedInAnnotations"][{i_element}]')
            for i_box, box in rpacs_v.enumerate_list_and_check_item_type(element['BoxCoordinates'], list, f'{t_path}["RemoveBurnedInAnnotations"][{i_element}]["BoxCoordinates"]'):
              rpacs_v.check_list_item_type(box, int, f'{t_path}["RemoveBurnedInAnnotations"][{i_element}]["BoxCoordinates"][{i_box}]')
              assert len(box) == 4, f'{t_path}["RemoveBurnedInAnnotations"][{i_element}]["BoxCoordinates"][{i_box}] is not a 4-element list'
              assert box[0] < box[2] and box[1] < box[3], f'{t_path}["RemoveBurnedInAnnotations"][{i_element}]["BoxCoordinates"][{i_box}] contains invalid coordinates'

      # DeleteTags:
      #   - TagPatterns: str or list                      List of tag patterns to remove
      #     ExceptTagPatterns: str or list                List of tag patterns to retain
      #     Action: str                                   Remove or Empty
      if rpacs_v.check_dict_attribute_exists_and_type(t, 'DeleteTags', list, t_path, optional=True) is True:
        for i_element, element in rpacs_v.enumerate_list_and_check_item_type(t['DeleteTags'], dict, f'{t_path}["DeleteTags"]'):
          check_tag_patterns_exist(element, f'{t_path}["DeleteTags"][{i_element}]')
          rpacs_v.check_dict_attribute_exists_and_type(element, 'Action', str, f'{t_path}["DeleteTags"][{i_element}]')
          assert element['Action'] in ('Remove', 'Empty'), f'{t_path}["DeleteTags"][{i_element}]["Action"] must be equal to "Remove" or "Empty"'

      # Transcode: str                    Transfer syntax UID to which the de-identified DICOM
      #                                   file should be transcoded. If not provided, the 
      #                                   de-identified DICOM file will use the same transfer
      #                                   syntax than the original DICOM file.
      rpacs_v.check_dict_attribute_exists_and_type(t, 'Transcode', str, t_path, optional=True)


  def _find_transformations_to_apply(self):
    """
    Generate a list of transformations to apply based on the DICOM file's matching labels. 
    It also determines if access to pixel data is needed to remove burned-in annotations, 
    and if OCR is requested.
    
    """
    transformations = {}
    remove_burned_in_annotations = False
    use_ocr = False
    for t in self._config['Transformations']:
      
      # Check if the transformation should be apply based on the matching labels
      if self._do_labels_match_scope_rules(self._matching_labels, t['Scope']) is True:
        
        for key in t.keys():
          if key == 'Transcode':
            transformations[key] = t[key]
          else:
            transformations.setdefault(key, [])
            transformations[key] += t[key]
            
        # Check if access to pixel data and OCR are needed
        if 'RemoveBurnedInAnnotations' in t.keys():
          remove_burned_in_annotations = True
          for element in t['RemoveBurnedInAnnotations']:
            if element['Type'] == 'OCR':
              use_ocr = True
        
    return transformations, remove_burned_in_annotations, use_ocr


  def apply_transformations(self, logs):
    """
    Apply the transformations in `self._transformations` to the DICOM file. The transformations 
    are applied in the following order:
    - ShiftDateTime
    - RandomizeText
    - RandomizeUID
    - AddTags
    - RemoveBurnedInAnnotations
    - DeleteTags
    - Transcode. This does not alter the DICOM file but returns a transfer syntax UID to which 
      the de-identified DICOM file will be transcoded with Orthanc.
    
    Args:
      logs (dict): Dict where logs should be added
    
    """
    
    def _log_t(transformation, value):
      """
      Add a transformation applied to the log dict.
      
      """
      logs.setdefault('TransformationsApplied', {})
      logs['TransformationsApplied'].setdefault(transformation, [])
      logs['TransformationsApplied'][transformation].append(value)
      
    def _process_each_elem_item(f, elem, *args):
      """
      If the element contains multiple items, process each item with the function `f`. Otherwise,
      process its single item value with `f`. `f` returns the new value of the element item.
      
      """
      if isinstance(elem.value, pydicom.multival.MultiValue):
        for i in range(len(elem.value)):
          elem.value[i] = f(elem, elem.value[i], *args)
      else:
        elem.value = f(elem, elem.value, *args)
    
    def _get_new_value_from_mapping(t, value_type, old_value, new_value):
      """
      If `ReuseMapping` is specified in `t`, check if a mapping already exists in the database, 
      and return the existing value in that case. Otherwise, create a new mapping in the database 
      between `old_value` and `new_value` if `ReuseMapping` is specified, and return the new 
      value.
      
      Args:
        t: dict that may contain a `ReuseMapping` attribute
        value_type (str): The type of data (`TEXT` or `DATETIME`)
        old_value (str): The original value of the DICOM data element
        new_value (str): The value of the DICOM data element after de-identification
        
      """
      if 'ReuseMapping' in t:
        if t['ReuseMapping'] == 'Always':
          scope_type = 'always'
          scope_value = 'always'
        elif t['ReuseMapping'] == 'SamePatient':
          scope_type = 'patient'
          scope_value = _old_patient_id if _old_patient_id != None else self.dicom.PatientID
        elif t['ReuseMapping'] == 'SameStudy':
          scope_type = 'study'
          scope_value = self.dicom.StudyInstanceUID
        elif t['ReuseMapping'] == 'SameSeries':
          scope_type = 'series'
          scope_value = self.dicom.SeriesInstanceUID
        else:
          scope_type = 'study'
          scope_value = self.dicom.SOPInstanceUID
        if scope_value == '':
          raise Exception('The scope value for ReuseMapping must not be empty')
        return self._db_mapping.add_or_get_mapping(value_type, old_value, new_value, scope_type, scope_value)
      else:
        return new_value
      
    dst_transfer_syntax = self._src_transfer_syntax
    _last_action = ''  # This is used for debugging if an exception is raised
    _old_patient_id = None  # Keep track of the initial PatientID value if it is changed
    try:
      
      ### ShiftDateTime
      if 'ShiftDateTime' in self._transformations:
        _last_action = f'ShiftDateTime'
        
        def shift_date_time(elem, item_value, elem_full_tag, t):
          """
          Converts the string value to a datetime object and shift by `ShiftBy` days if it is a 
          DA, or `ShiftBy` seconds if it a DT or TM.
          
          Args:
            elem: pydicom DataElement
            elem_value (str): Value of the element item to process
            elem_full_tag (str): Full path to the element
            t: dict for the current transformation
            
          """
          old_value = str(item_value)
          shift_value = random.randint(-t['ShiftBy'], +t['ShiftBy'])
          
          # If VR is DA, shift the date by `shift_value` days
          if elem.VR == 'DA':
            old_date = datetime.datetime.strptime(old_value, '%Y%m%d')
            new_date = old_date + datetime.timedelta(days=shift_value)
            new_value = new_date.strftime('%Y%m%d')
            
          # If VR is TM, shift the date by `shift_value` seconds
          elif elem.VR == 'TM':
            old_date = datetime.datetime.strptime(old_value[:6], '%H%M%S')
            new_date = old_date + datetime.timedelta(seconds=shift_value)
            new_value = new_date.strftime('%H%M%S')
            
          # If VR is DT, shift the date by `shift_valxue` seconds
          else:
            old_date = datetime.datetime.strptime(old_value[:14], '%Y%m%d%H%M%S')
            new_date = old_date + datetime.timedelta(seconds=shift_value)
            new_value = new_date.strftime('%Y%m%d%H%M%S')
          
          final_value = _get_new_value_from_mapping(t, 'DATETIME', old_value, new_value)
          _log_t('ShiftDateTime', f"Tag={elem_full_tag} OldValue={old_value} NewValue={final_value}")
          return final_value
          
        for t in self._transformations['ShiftDateTime']:
          for elem, elem_full_tag, parent_elem in dicom_tpp.enumerate_elements_match_tag_path_patterns(self.dicom, t['TagPatterns'], t['ExceptTagPatterns']):
            _last_action = f'ShiftDateTime Tag={elem_full_tag}'
            if elem.VR in ('DA', 'DT', 'TM') and not elem.is_empty:
              _process_each_elem_item(shift_date_time, elem, elem_full_tag, t)
      
      ### RandomizeText
      if 'RandomizeText' in self._transformations:
        _last_action = f'RandomizeText'
        
        def randomize_text(elem, item_value, elem_full_tag, t):
          """
          Split the original item value if specified by `Split`, replace each part by a random 
          8-character string, and rejoin the parts if needed.
          
          Args:
            elem: pydicom DataElement
            elem_i (int): If elem contains multiple values, `elem_i` is the index of the value to 
              process. If there is a single value, `elem_i ` equals `None`
            elem_full_tag (str): Full path to the element
            t: dict for the current transformation
            
          """
          old_value_before_split = str(item_value)
          old_value_after_split = old_value_before_split.split(t['Split']) if t['Split'] is True else [str(old_value_before_split)]
          new_value_before_join = []
          
          for old_value in old_value_after_split:
            if old_value == '':
              new_value = ''
            else:
              old_value = old_value.lower() if t['IgnoreCase'] is True else old_value
              random_value = ''.join(random.choice(string.ascii_letters + string.digits) for i in range(8))
              new_value = _get_new_value_from_mapping(t, 'DATETIME', old_value, random_value)
            new_value_before_join.append(new_value)
          
          final_value = t['Split'].join(new_value_before_join) if t['Split'] is True else new_value_before_join[0]
          _log_t('RandomizeText', f"Tag={elem_full_tag} OldValue={old_value_before_split} NewValue={final_value}")
          return final_value
        
        for t in self._transformations['RandomizeText']:
          for elem, elem_full_tag, parent_elem in dicom_tpp.enumerate_elements_match_tag_path_patterns(self.dicom, t['TagPatterns'], t['ExceptTagPatterns']):
            _last_action = f'RandomizeText Tag={elem_full_tag}'
            if not elem.is_empty:
              if elem_full_tag == '00100020':
                _old_patient_id = elem.value
              _process_each_elem_item(randomize_text, elem, elem_full_tag, t)
      
      ### RandomizeUID
      if 'RandomizeUID' in self._transformations:
        _last_action = f'RandomizeUID'
        
        def randomize_uid(elem, item_value, elem_full_tag, t):
          """
          Replaces the old UID by a new UID. If the old UID already exists in the mapping 
          table of the database, it is always replaced by the same UID.
          
          Args:
            elem: pydicom DataElement
            elem_i (int): If elem contains multiple values, `elem_i` is the index of the value to 
              process. If there is a single value, `elem_i ` equals `None`
            elem_full_tag (str): Full path to the element
            t: dict for the current transformation
            
          """
          old_uid = str(item_value)
          random_uid = pydicom.uid.generate_uid(prefix=t['Prefix']) if 'Prefix' in t else pydicom.uid.generate_uid()
          new_uid = self._db_mapping.add_or_get_mapping('UID', old_uid, random_uid, 'always', 'always')
          # Update the tag value, and the meta header tag MediaStorageSOPInstanceUID if the 
          # current element is SOPInstanceUID
          if elem_full_tag == '00080018':
            self.dicom.file_meta.MediaStorageSOPInstanceUID = new_uid
          _log_t('RandomizeUID', f"Tag={elem_full_tag} OldValue={old_uid} NewValue={new_uid}")
          return new_uid
        
        for t in self._transformations['RandomizeUID']:
          for elem, elem_full_tag, parent_elem in dicom_tpp.enumerate_elements_match_tag_path_patterns(self.dicom, t['TagPatterns'], t['ExceptTagPatterns']):
            _last_action = f'RandomizeUID Tag={elem_full_tag}'
            # Ignore the element if its VR is not UI
            if elem.VR == 'UI' and not elem.is_empty:
              _process_each_elem_item(randomize_uid, elem, elem_full_tag, t)
      
      ### AddTags
      if 'AddTags' in self._transformations:
        _last_action = f'AddTags'
        for t in self._transformations['AddTags']:
          _last_action = f"AddTags Tag={t['Tag']}"
          for parent_elem, tag_int in dicom_tp.enumerate_parent_elements(self.dicom, t['Tag']):
            if tag_int in parent_elem and t['OverwriteIfExists'] is False:
              continue
            new_elem = pydicom.dataelem.DataElement(tag_int, t['VR'], t['Value'])
            parent_elem.add(new_elem)
          _log_t('AddTags', f"Tag={t['Tag']}")

      ## RemoveBurnedInAnnotations
      if 'RemoveBurnedInAnnotations' in self._transformations:
        _last_action = f'RemoveBurnedInAnnotations'
        pixels = self.dicom.pixel_array
        width, height = rpacs_dicom_util.get_dimensions(self.dicom)
        samples_per_pixel = rpacs_dicom_util.get_samples_per_pixel(self.dicom)
        _last_action = f'RemoveBurnedInAnnotations Step=CreateMask PixelArrayShape={pixels.shape} Width={width} Height={height} SamplesPerPixel={samples_per_pixel}'
        
        # Generate a mask that will be used to replace boxes to mask with black pixels. The mask 
        # contains only "1" values first, and will be set to "0" later for pixels to obscur
        if pixels.ndim == 4:
          # (frames, Y, X, channel)
          mask = np.ones((1, height, width, 1), dtype=np.uint8)
        elif pixels.ndim == 3 and pixels.shape[2] == samples_per_pixel:
          # (Y, X, channel)
          mask = np.ones((height, width, 1), dtype=np.uint8)
        elif pixels.ndim == 3:
          # (frames, Y, X)
          mask = np.ones((1, height, width), dtype=np.uint8)
        else:
          # (Y, X)
          mask = np.ones((height, width), dtype=np.uint8)
        
        for t in self._transformations['RemoveBurnedInAnnotations']:
          if 'BoxCoordinates' in t:
            for box in t['BoxCoordinates']:
              box_left, box_top, box_right, box_bottom = box
              _last_action = f'RemoveBurnedInAnnotations Step=EditMask PixelArrayShape={pixels.shape} MaskShape={mask.shape} Box=({box_left}, {box_top}, {box_right}, {box_bottom})'
              box_left = max(0, min(width-1, box_left))
              box_right = max(0, min(width-1, box_right))
              box_top = max(0, min(height-1, box_top))
              box_bottom = max(0, min(height-1, box_bottom))
              # Put zeros in the mask where pixels must be obscured
              if pixels.ndim == 4:
                mask[0, box_top:box_bottom, box_left:box_right, 0] = 0
              elif pixels.ndim == 3 and pixels.shape[2] == samples_per_pixel:
                mask[box_top:box_bottom, box_left:box_right, 0] = 0
              elif pixels.ndim == 3:
                mask[0, box_top:box_bottom, box_left:box_right] = 0
              else:
                mask[box_top:box_bottom, box_left:box_right] = 0
              _log_t('RemoveBurnedInAnnotations', f"Type={t['Type']} Box=({box_left}, {box_top}, {box_right}, {box_bottom})")
        
        # Apply the mask and updated the DICOM image tags accordingly
        _last_action = f'RemoveBurnedInAnnotations Step=ApplyMask PixelArrayShape={pixels.shape} MaskShape={mask.shape}'
        new_pixels = mask * pixels
        self.dicom.PixelData = new_pixels.tobytes()
        self.dicom.BitsAllocated = pixels.itemsize*8
        self.dicom.BitsStored = pixels.itemsize*8
        self.dicom.HighBit = pixels.itemsize*8-1
        if samples_per_pixel > 1:
          self.dicom.PlanarConfiguration = 0
      
      ### DeleteTags
      if 'DeleteTags' in self._transformations:
        _last_action = 'DeleteTags'
        for t in self._transformations['DeleteTags']:
          for elem, elem_full_tag, parent_elem in dicom_tpp.enumerate_elements_match_tag_path_patterns(self.dicom, t['TagPatterns'], t['ExceptTagPatterns']):
            _last_action = f'DeleteTags Tag={elem_full_tag}'
            if t['Action'] == 'Remove':
              del parent_elem[elem.tag]
            else:
              elem.clear()
            _log_t('DeleteTags', f"Tag={elem_full_tag} Action={t['Action']}")
      
      ### Transcode
      if 'Transcode' in self._transformations:
        dst_transfer_syntax = self._transformations['Transcode']
        _log_t('Transcode', f"{dst_transfer_syntax}")
  
    except Exception as e:
      raise Exception(f'Last action attempted: {_last_action} - {e}')
  
    # Check if the current DICOM file in `self.dicom` should be transcoded to a new transfer 
    # syntax and return the new transfer syntax and the list of changes applied
    return None if self.dicom.file_meta.TransferSyntaxUID == dst_transfer_syntax else dst_transfer_syntax


  def get_transformations_to_apply(self):
    """
    Return the transformations to apply.
    
    """
    return self._transformations
    

  def is_transcoding_needed(self):
    """
    The DICOM file must be transcoded to a deflated and little endian transfer syntax in order 
    to manipulate pixel data.
    
    """
    if self._remove_burned_in_annotations is True and (self.dicom.file_meta.TransferSyntaxUID != '1.2.840.10008.1.2.1'):
      return True, self.dicom.file_meta.TransferSyntaxUID
    else:
      return False, None


  def is_ocr_needed(self):
    """
    Return `True` if there is at least one transformation "RemoveBurnedInAnnotations" that uses 
    OCR to find burned-in text annotations.
    
    """
    return self._use_ocr


  def add_box_coordinates(self, boxes):
    """
    Add the coordinates of boxes that contain burned-in text annotations after using a OCR engine.
    
    Args:
      boxes (list): List of box coordinates (left, top, right, bottom)
      
    """
    self._transformations['RemoveBurnedInAnnotations'].append({
      'Type': 'FromOCR',
      'BoxCoordinates': boxes
    })


  def _find_matching_labels(self):
    """
    Generate the list of labels that match the current DICOM instance.
    
    """
    matching_labels = ['ALL']
    dicom_json = rpacs_dicom_json.convert_dicom_to_json(self.dicom)
    for label in self._config['Labels']:
      logger.debug(f"Checking whether the DICOM file matches the label \"{label['Name']}\"")
      try:
        
        # The label automatically matches if there is no filtering query
        if not 'JSONPathQuery' in label:
          matching_labels.append(label['Name'])
          
        # If a filtering query is specified, query the PostgreSQL database to check if the DICOM 
        # instance match the resulting JSONPath query
        else:
          arg_dicom = json.dumps(dicom_json)
          arg_query = f"$ ? ({label['JSONPathQuery']})"
          self._db.execute(f"SELECT jsonb %s @? %s;", (arg_dicom, arg_query))
          if self._db.fetchone()[0] == True:
            matching_labels.append(label['Name'])
            
      except Exception as e:
        raise Exception(f"Failed to check if the DICOM file matches the label \"{label['Name']}\" - {e}")
    return matching_labels


  def _do_labels_match_scope_rules(self, labels, rules):
    """
    Evaluate whether one of the labels in `labels` match the included labels defined by the rules 
    in `rules`, and not with the excluded labels.
    
    Args:
      labels (list): List of labels
      rules (dict): Dict that can contain `Labels`, `ExceptLabels`, `Categories`, `ExceptCategories` 
        attributes
    
    """
    included_labels = []
    excluded_labels = []
    
    if 'Labels' in rules:
      included_labels += rules['Labels']
    if 'Categories' in rules:
      for category in rules['Categories']:
        included_labels += self._get_labels_for_category(category)
    if 'ExceptLabels' in rules:
      excluded_labels += rules['ExceptLabels']
    if 'ExceptCategories' in rules:
      for category in rules['ExceptCategories']:
        excluded_labels += self._get_labels_for_category(category)

    for label in labels:
      if label in excluded_labels:
        return False
    for label in labels:
      if label in included_labels:
        return True
    return False


  def _get_labels_for_category(self, category_name):
    """
    Return the list of labels associated with a given category, as defined in the "Categories" 
    attribute of the config file.
    
    """
    for category in self._config['Categories']:
      if category['Name'] == category_name:
        return category['Labels']
