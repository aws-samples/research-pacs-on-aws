# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from setuptools import setup


setup(
  name='research-pacs-de-identifier',
  version="1.0",
  packages=['research_pacs.de_identifier'],
  install_requires=[
    'boto3',
    'numpy',
    'pydicom'
  ]
)