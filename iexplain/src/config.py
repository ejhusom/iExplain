#!/usr/bin/env python3
"""Global parameters for project.

Example:

    >>> from config import config
    >>> some_path = config.DATA_PATH
    >>> file = config.DATA_PATH / "filename.txt"

Author:   Erik Johannes Husom

"""
from pathlib import Path

class Config:
    def __init__(self):
        # PARAMETERS
        #
        # Example:
        # self.PARAMETER = "value"

        # PATHS
        self.CONFIG_PATH = Path("./config")
        self.CONFIG_FILE_PATH = self.CONFIG_PATH / "config.ini"
        self.DATA_PATH = Path("./data")
        self.OUTPUT_PATH = Path("./output")
        self.LOG_FILE_PATH = self.DATA_PATH / "system_adaptations.log"

        self._init_paths()

    def _init_paths(self):
        """Create directories if they don't exist."""
        directories = [
            self.CONFIG_PATH,
            self.DATA_PATH,
            self.OUTPUT_PATH
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

# Instantiate a single configuration object to use throughout your application
config = Config()
