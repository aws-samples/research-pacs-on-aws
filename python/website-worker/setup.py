# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from setuptools import setup


setup(
  name='research-pacs-website-worker',
  version="1.0",
  packages=['research_pacs.website_worker'],
  install_requires=[
    'boto3'
  ]
)