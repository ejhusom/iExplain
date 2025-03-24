#!/usr/bin/env python3
"""Global parameters for project.

Example:

    >>> from config import config
    >>> some_path = config.DATA_PATH
    >>> file = config.DATA_PATH / "filename.txt"

Author:   Erik Johannes Husom

"""
import os
from pathlib import Path

class Config:
    def __init__(self):
        # PARAMETERS
        #
        # Example:
        # self.PARAMETER = "value"

        # PATHS
        self.DATA_PATH = Path("./data")
        self.LOGS_PATH = self.DATA_PATH / "logs"
        self.INTENTS_PATH = self.DATA_PATH / "intents"
        self.METADATA_PATH = self.DATA_PATH / "metadata"
        self.OUTPUT_PATH = Path("./output")
        self.WORK_DIR = Path("./work_dir")

        # User-defined parameters:
        self.LLM_SERVICE = "openai"
        self.LLM_MODEL = "gpt-4o-mini"
        # self.LLM_SERVICE = "ollama"
        # self.LLM_MODEL = "llama3.2:1b"
        # self.LLM_MODEL = "deepseek-r1:1.5b"
        # self.LLM_MODEL = "qwen2.5:0.5b"
        # self.LLM_MODEL = "gemma2:2b-instruct-q3_K_S"
        self.LLM_API_KEY = os.environ.get("OPENAI_API_KEY")

        self.config_list = [{
            "model": self.LLM_MODEL,
            "api_key": self.LLM_API_KEY,
            "api_type": self.LLM_SERVICE,
        }]

        self._init_paths()

    def _init_paths(self):
        """Create directories if they don't exist."""
        directories = [
            self.DATA_PATH,
            self.LOGS_PATH,
            self.INTENTS_PATH,
            self.METADATA_PATH,
            self.OUTPUT_PATH
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

config = Config()
