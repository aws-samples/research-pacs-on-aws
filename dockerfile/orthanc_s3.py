#!/usr/bin/python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import json
import os
import shutil

import boto3


# Configure the S3 plugin

bucket = os.getenv('RPACS_S3_DICOM_BUCKET_NAME')
region = os.getenv('RPACS_S3_DICOM_AWS_REGION')
prefix = os.getenv('RPACS_S3_DICOM_KEY_PREFIX')

if bucket != None and region != None:

  if prefix is None:
    prefix = ''

  with open('/tmp/orthanc.json', 'r') as f_read:
    data = json.load(f_read)

  data['AwsS3Storage'] = {
  'BucketName': bucket,
  'Region': region,
  'RootPath': prefix
  }

  with open('/tmp/orthanc.json', 'w') as f_write:
    json.dump(data, f_write)

  shutil.copy2('/usr/share/orthanc/plugins-available/libOrthancAwsS3Storage.so', '/usr/share/orthanc/plugins')
  print('Enabled cloud object storage (S3) plugin: %s' %json.dumps(data['AwsS3Storage']))

else:
  print('Disabled cloud object storage (S3) plugin')


# Copy configuration files from S3

bucket = os.getenv('RPACS_S3_CONFIG_BUCKET_NAME')
region = os.getenv('RPACS_S3_CONFIG_AWS_REGION')
prefix = os.getenv('RPACS_S3_CONFIG_KEY_PREFIX')
local_dir='/s3-files/'

if bucket != None and region != None:
  
  if prefix is None:
    prefix = ''

  s3_resource = boto3.resource('s3', region_name=region)
  bucket_resource = s3_resource.Bucket(bucket)
  
  for obj in bucket_resource.objects.filter(Prefix=prefix):
    
    if not obj.key.endswith('/'):
      local_path = local_dir + obj.key[len(prefix):]
      
      if not os.path.exists(os.path.dirname(local_path)):
        os.makedirs(os.path.dirname(local_path))
        
      bucket_resource.download_file(obj.key, local_path)
      print('Copied file s3://%s/%s to %s' %(bucket, obj.key, local_path))
