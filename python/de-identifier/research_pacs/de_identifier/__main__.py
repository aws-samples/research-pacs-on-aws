# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from research_pacs.shared.log import get_logger
import research_pacs.de_identifier.main as main


if __name__ == '__main__':
  logger = get_logger()
  main.main()
