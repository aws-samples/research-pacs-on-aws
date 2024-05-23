# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from setuptools import setup


setup(
  name='research-pacs-website',
  version="1.0",
  packages=['research_pacs.website'],
  include_package_data=True,
  package_data={
    '': ['templates/*.html'],
  },
  install_requires=[
    'boto3',
    'flask=2.3.2',
    'requests',
    'waitress=2.1.2'
  ]
)