# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

FROM public.ecr.aws/amazonlinux/amazonlinux:latest
ARG REPO_URL
ARG REPO_BRANCH
RUN yum install python3 python3-pip git setuptools -q -y
RUN pip3 install --no-cache-dir git+$REPO_URL.git@$REPO_BRANCH#subdirectory=python/shared
RUN pip3 install --no-cache-dir git+$REPO_URL.git@$REPO_BRANCH#subdirectory=python/change-pooler
CMD [ "python3", "-m", "research_pacs.change_pooler" ]