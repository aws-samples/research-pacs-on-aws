# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from setuptools import setup


setup(
  name='research-pacs-shared',
  version="1.0",
  packages=['research_pacs.shared'],
  install_requires=[
    'boto3',
    'psycopg2-binary',
    'pydicom',
    'requests',
    'pyyaml'
  ]
)