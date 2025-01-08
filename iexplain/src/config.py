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
        self.METADATA_PATH = self.DATA_PATH / "metadata"
        self.OUTPUT_PATH = Path("./output")

        # User-defined parameters:
        self.LLM_SERVICE = "openai"
        self.LLM_MODEL = "gpt-4o-mini"
        # self.LLM_SERVICE = "ollama"
        # self.LLM_MODEL = "gemma2:2b-instruct-q3_K_S"
        self.LLM_API_KEY = os.environ.get("OPENAI_API_KEY")
        self.use_case_context = "A company is using an edge-cloud computing infrastructure to process data from IoT devices spread across multiple locations. The primary intent is to optimize energy consumption across the infrastructure while ensuring data is processed efficiently and sustainably."
        self.system_prompt =	"""
You are a helpful assistant that describes and explains adaptations made in the edge-cloud computing infrastructure based on the available information.
You will be provided with a list of intents, and a list of adaptations.
List the intents, and list the adaptations under each of the intents.
Under each adaptation, explain why the adaptation was made.
"""

        self._init_paths()

    def _init_paths(self):
        """Create directories if they don't exist."""
        directories = [
            self.DATA_PATH,
            self.LOGS_PATH,
            self.METADATA_PATH,
            self.OUTPUT_PATH
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

config = Config()
