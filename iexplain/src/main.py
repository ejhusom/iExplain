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
import chromadb
import yaml

from autogen import ConversableAgent, GroupChat, GroupChatManager, AssistantAgent, UserProxyAgent
from autogen.coding import LocalCommandLineCodeExecutor
from autogen.agentchat.contrib.retrieve_user_proxy_agent import RetrieveUserProxyAgent

from config import config
from tools import parse_logs
from agents import get_agents

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
            }]
            self.max_context_length = 100000
        elif config.LLM_SERVICE == "ollama":
            self.config_list = [{
                "model": config.LLM_MODEL, 
                "api_type": "ollama",
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

    def read_logs(self) -> List[str]:
        """Read the log entries from the log directory.

        Returns:
            List[str]: A list of log entries.
        """
        logs = []
        for log_file in os.listdir(config.LOGS_PATH):
            if log_file.endswith(".json"):
                with open(config.LOGS_PATH / log_file, "r") as f:
                    logs.append(json.load(f))
            elif any(log_file.endswith(fmt) for fmt in self.plain_text_formats):
                with open(config.LOGS_PATH / log_file, "r") as f:
                    logs.append(f.read())
            else:
                print(f"Unsupported file format: {log_file}")

        return logs

    def read_metadata(self) -> List[str]:
        """Read the metadata from the metadata directory.

        Returns:
            List[str]: A list of metadata entries.
        """
        metadata = []
        for metadata_file in os.listdir(config.METADATA_PATH):
            if metadata_file.endswith(".json"):
                with open(config.METADATA_PATH / metadata_file, "r") as f:
                    metadata.append(json.load(f))
            elif any(metadata_file.endswith(fmt) for fmt in self.plain_text_formats):
                with open(config.METADATA_PATH / metadata_file, "r") as f:
                    metadata.append(f.read())
            else:
                print(f"Unsupported file format: {metadata_file}")

        return metadata

    def run_v1(self):
        """Run the iExplain framework version 1."""
        self.logs = self.read_logs()
        self.metadata = self.read_metadata()
        self.combined_logs = "\n".join(self.logs)
        self.combined_metadata = "\n".join(self.metadata)

        # Start by summarizing the metadata
        metadata_summary = self.agents["ModeratorAgent"].initiate_chats(
            [
                {
                    "recipient": self.agents["MetadataParserAgent"],
                    "message": "Please summarize the following metadata:\n\n" + self.combined_metadata,
                    "clear_history": False,
                    "max_turns": 1,
                    "summary_method": "last_msg"
                }
            ]
        )[-1].summary

        # Summarizing logs
        log_message = f"Here are some logs with the following metadata:\n\n{metadata_summary}\n\n{self.combined_logs}"
        event_log_summary = self.agents["ModeratorAgent"].initiate_chats(
            [
                {
                    "recipient": self.agents["LogAnalyzerAgent"],
                    "message": log_message,
                    "clear_history": False,
                    "max_turns": 1,
                    "summary_method": "last_msg"
                }
            ]
        )[-1].summary

        # ExplanationGeneratorAgent generates explanations based on the summaries
        explanation = self.agents["ModeratorAgent"].initiate_chats(
            [
                {
                    "recipient": self.agents["ExplanationAgent"],
                    "message": f"Please generate an explanation based on the following summaries:\n\nMetadata Summary:\n{metadata_summary}\n\nEvent Log Summary:\n{event_log_summary}",
                    "clear_history": False,
                    "max_turns": 1,
                    "summary_method": "last_msg"
                }
            ]
        )[-1].summary

    def run_v2(self):
        """Run the iExplain framework version 2."""
        groupchat = GroupChat(
            agents=[
                self.agents["UserProxyAgent"], 
                self.agents["InputAgent"],
                self.agents["AnalyzerAgent"],
                self.agents["CoderAgent"], 
                self.agents["CodeExecutorAgent"],
                self.agents["CriticAgent"],
                self.agents["ExplanationAgent"],
                self.agents["EvaluatorAgent"],
                self.agents["RetrieveUserProxyAgent"]
            ], 
            messages=[], 
            max_round=25,
            send_introductions=True
        )

        manager = GroupChatManager(
            groupchat=groupchat, 
            llm_config={"config_list": self.config_list}
        )

        task = "Analyze the files in '../data/logs' and '../data/metadata' to generate an explanation."

        self.agents["UserProxyAgent"].initiate_chat(
            manager,
            message=task
        )

    def run_v3(self):
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
        # self.agents["code_executor_agent"].initiate_chat(
            manager,
            message="Look at the logs in './logs/'. List, read, and parse them."
        )

if __name__ == '__main__':
    iexplain = iExplain()
    # iexplain.run_v1()
    iexplain.run_v3()