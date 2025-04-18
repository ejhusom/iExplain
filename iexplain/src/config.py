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

        self.EXPLANATION_CONFIG = {
            "timestamp": {
                "title": "Timestamp",
                "display_type": "text",
                "description": "Time when the explanation was generated",
                "display_priority": 5,
            },
            "intent": {
                "title": "Intent",
                "display_type": "object",
                "description": "The intent object containing id and description",
                "display_priority": 8,
            },
            "outcome": {
                "title": "Outcome",
                "display_type": "status",  # Special handling for success/failure states
                "description": "Whether the intent was fulfilled, either 'Success', 'Partial Success', or 'Failure'",
                "display_priority": 10,  # Lower numbers appear first
            },
            "outcome_explanation": {
                "title": "Outcome Explanation",
                "display_type": "text",
                "description": "Explanation of the outcome",
                "display_priority": 20,
            },
            "system_interpretation": {
                "title": "System Interpretation",
                "display_type": "text",
                "description": "How the system interpreted the intent",
                "display_priority": 30,
            },
            "key_actions": {
                "title": "Key Actions",
                "display_type": "list",
                "description": "Actions taken by the system",
                "display_priority": 40,
                "item_type": "simple"
            },
            "analysis": {
                "title": "Analysis Results",
                "display_type": "key_value",  # Will display as key-value pairs
                "description": "Detailed metrics from logs",
                "display_priority": 50,
            },
            "recommendations": {
                "title": "Recommendations",
                "display_type": "list",
                "description": "Suggested improvements, as a list of action/reason pairs",
                "display_priority": 60,
                "item_type": "recommendation"  # Special format for recommendations with action/reason pairs
            },
            "influencing_factors": {
                "title": "Influencing Factors",
                "display_type": "list",
                "description": "Factors affecting the outcome",
                "display_priority": 70,
                "item_type": "factor"
            },
        }

        # Fields that should be hidden/collapsed by default
        self.HIDDEN_EXPLANATION_FIELDS = []
        # Fields that are excluded from having a separate field in the dashboard
        self.EXCLUDED_EXPLANATION_FIELDS = ["timestamp", "intent"]

        self.EXPLANATION_SINGLE_COLUMN = False

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
