#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""iExplain - Explainability module.

This module provides the functionality to make sense of system logs and
metadata by generating human-understandable explanations. It uses interacting
LLM (Large Language Model) agents to analyze logs, summarize metadata, and
generate explanations based on the input data.

"""
import configparser
import os
import sys
import datetime
from typing import List, Dict, Any

import json
import ollama
import openai
import tiktoken
# import chromadb

from autogen import ConversableAgent, GroupChat, GroupChatManager, AssistantAgent, UserProxyAgent
from autogen.coding import LocalCommandLineCodeExecutor
from autogen.agentchat.contrib.retrieve_user_proxy_agent import RetrieveUserProxyAgent

from config import config
from get_agents import get_agents

DEBUG_MODE = False

class iExplain:
    """iExplain framework for generating explanations.

    iExplain generates human-understandable explanations for actions, events,
    or decisions made by AI agents or systems. It aims to provide clear,
    context-aware explanations to help users understand the reasoning behind
    specific sequences of events.

    The framework uses interacting LLM (Large Language Model) agents to
    generate explanations based on input data and context. These agents can
    leverage pre-trained language models (e.g., GPT-4) or domain-specific
    models to collaboratively produce coherent explanations.

    """

    def __init__(self):
        """Initialize the iExplain framework."""
        self.plain_text_formats = [".txt", ".csv", ".log", ".md"]

        if config.LLM_SERVICE == "openai":
            self.config_list = [{
                "model": config.LLM_MODEL, 
                "api_key": os.environ.get("OPENAI_API_KEY")
                "num_ctx": 131072,
            }]
            self.max_context_length = 100000
        elif config.LLM_SERVICE == "anthropic":
            self.config_list = [{
                "model": config.LLM_MODEL, 
                "api_key": os.environ.get("ANTHROPIC_API_KEY")
                "num_ctx": 131072,
            }]
            self.max_context_length = 100000
        elif config.LLM_SERVICE == "ollama":
            self.config_list = [{
                "model": config.LLM_MODEL, 
                "api_type": "ollama",
                "num_ctx": 131072,
            }]

            # Find context length
            modelinfo = ollama.show(config.LLM_MODEL).modelinfo
            # Find an item in modelinfo with a key that contains the string "context_length"
            context_length_key = next(item for item in modelinfo if "context_length" in item)
            self.max_context_length = modelinfo[context_length_key]
        else:
            raise ValueError("Invalid LLM service specified in config.")

        self.agents = get_agents(self.config_list)

    def limit_token_length(self, text: str) -> str:
        """Limit the token length to avoid exceeding the LLM token limit.

        Args:
            text (str): The input text to be limited.

        Returns:
            str: The text limited to the maximum token length.
        """
        indicator = " [truncated]"

        encoding = tiktoken.encoding_for_model(config.LLM_MODEL)
        encoded_text = encoding.encode(text)
        encoded_indicator = encoding.encode(indicator)
        if len(encoded_text) > self.max_context_length:
            encoded_text = encoded_text[:self.max_context_length - len(encoded_indicator)]
            encoded_text += encoded_indicator
        text = encoding.decode(encoded_text)
        return text


    def run(self):
        """Run the iExplain framework version 3."""

        groupchat = GroupChat(
            agents=[
                self.agents["user_proxy_agent"],
                self.agents["input_agent"],
                self.agents["code_executor_agent"],
                self.agents["code_writer_agent"],
                self.agents["data_reader_agent"],
                self.agents["log_parser_agent"],
            ],
            messages=[],
            max_round=60,
            send_introductions=True
        )

        manager = GroupChatManager(
            groupchat=groupchat, 
            llm_config={"config_list": self.config_list}
        )

        self.agents["user_proxy_agent"].initiate_chat(
            manager,
            message="Look at the log files in './logs/'. List, read, and parse the log files."
        )

    def run_demo(self, intent=None, log_files=None):
        """Run the iExplain framework.

        Args:
            intent (str, optional): Intent in natural language or TMF format.
                                   If None, will look for intents in the data directory.
            log_files (list, optional): List of log files to analyze.
                                       If None, will use all logs in the logs directory.
        """
        # Initialize agents if not already initialized
        if not hasattr(self, 'agents'):
            self.agents = get_agents(self.config_list)

        # Set up the group chat with the new agents
        groupchat = GroupChat(
            agents=[
                self.agents["user_proxy_agent"],
                self.agents["intent_parser_agent"],     # New
                self.agents["input_agent"],
                self.agents["log_parser_agent"],
                self.agents["log_analysis_agent"],      # New
                self.agents["causal_inference_agent"],  # New
                self.agents["explanation_generator_agent"], # New
                self.agents["code_writer_agent"],
                self.agents["code_executor_agent"],
                self.agents["data_reader_agent"],
            ],
            messages=[],
            max_round=60,
            send_introductions=True
        )

        manager = GroupChatManager(
            groupchat=groupchat,
            llm_config={"config_list": self.config_list}
        )

        # Formulate the initial message based on provided intent and log files
        initial_message = "I need to explain how the system has addressed a user intent."

        if intent:
            initial_message += f"\n\nThe intent is: {intent}"
        else:
            initial_message += "\n\nPlease look for intent files in the './data/metadata/' directory."

        if log_files:
            initial_message += f"\n\nAnalyze the following log files: {', '.join(log_files)}"
        else:
            initial_message += "\n\nAnalyze all log files in the './data/logs/' directory."

        initial_message += """

        Follow this workflow:
        1. Parse and interpret the intent
        2. Identify relevant log entries
        3. Analyze logs to find actions related to the intent
        4. Determine causality between actions and outcomes
        5. Generate a clear explanation
        6. Create an HTML dashboard with the explanation

        The final output should be an explanation of how the system interpreted and acted upon the intent.
        """

        # Start the conversation
        self.agents["user_proxy_agent"].initiate_chat(
            manager,
            message=initial_message
        )

        # Return the path to the generated dashboard
        # This would need to be captured from the agent conversation results
        return "Path to explanation dashboard"  # Placeholder

if __name__ == '__main__':
    iexplain = iExplain()
    iexplain.run_demo()
