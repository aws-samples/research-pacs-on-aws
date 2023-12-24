# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

ARG ORTHANC_VERSION=latest

FROM osimis/orthanc:$ORTHANC_VERSION as orthanc_build
ARG S3_PLUGIN_BRANCH=default
ARG REPO_URL
ARG REPO_BRANCH
RUN apt-get -y update
RUN apt-get install -y git mercurial build-essential unzip cmake wget
WORKDIR /tmp
RUN hg clone https://hg.orthanc-server.com/orthanc-object-storage/
WORKDIR /tmp/orthanc-object-storage
RUN hg up -c "$S3_PLUGIN_BRANCH"

# Switch to a specific version of OpenSSL
WORKDIR /tmp/build
RUN wget https://www.openssl.org/source/openssl-1.1.1l.tar.gz
RUN tar -xzvf openssl-1.1.1l.tar.gz
WORKDIR /tmp/build/openssl-1.1.1l

# Build OpenSSL
RUN ./config && make && make install

WORKDIR /tmp/build
RUN cmake -DSTATIC_BUILD=ON -DCMAKE_BUILD_TYPE=Release -DUSE_VCPKG_PACKAGES=OFF -DUSE_SYSTEM_GOOGLE_TEST=OFF ../orthanc-object-storage/Aws
RUN CORES=`grep -c ^processor /proc/cpuinfo` && make -j$CORES
RUN wget $REPO_URL/raw/$REPO_BRANCH/dockerfile/orthanc_s3.py

FROM osimis/orthanc:$ORTHANC_VERSION
RUN pip3 install boto3
COPY --from=orthanc_build /tmp/build/libOrthancAwsS3Storage.so /usr/share/orthanc/plugins-available/
COPY --from=orthanc_build /tmp/build/orthanc_s3.py /
RUN chmod +x orthanc_s3.py
ENV BEFORE_ORTHANC_STARTUP_SCRIPT=/orthanc_s3.py
