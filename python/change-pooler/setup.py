# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from setuptools import setup

setup(
  name='research-pacs-change-pooler',
  version="1.0",
  packages=['research_pacs.change_pooler'],
  install_requires=[
    'boto3',
    'setuptools'
  ]
)