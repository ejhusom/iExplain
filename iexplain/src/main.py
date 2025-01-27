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

        self.agents = self.load_agents_from_config()

    def load_agents_from_config(self):
        """Load agents from the YAML configuration file."""
        with open("src/agents.yaml", "r") as file:
            agents_config = yaml.safe_load(file)

        agents = {}
        for agent_name, agent_config in agents_config.items():
            llm_config = {"config_list": self.config_list} if agent_config["llm_config"] == "default" else agent_config["llm_config"]
            agent = ConversableAgent(
                name=agent_name,
                system_message=agent_config["system_message"],
                description=agent_config["description"],
                llm_config=llm_config,
                code_execution_config=False,
                function_map=None,
                human_input_mode=agent_config["human_input_mode"],
            )
            agents[agent_name] = agent

        return agents

    def limit_token_length(self, text):
        """Limit the token length to avoid exceeding the LLM token limit."""
        indicator = " [truncated]"

        encoding = tiktoken.encoding_for_model(config.LLM_MODEL)
        encoded_text = encoding.encode(text)
        encoded_indicator = encoding.encode(indicator)
        if len(encoded_text) > self.max_context_length:
            encoded_text = encoded_text[:self.max_context_length - len(encoded_indicator)]
            encoded_text += encoded_indicator
        text = encoding.decode(encoded_text)
        return text

    def read_logs(self):
        """Read the log entries from the log directory."""

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

    def read_metadata(self):
        """Read the metadata from the metadata directory."""

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

    def run(self):
        """Run the iExplain framework."""
        self.logs = self.read_logs()
        self.metadata = self.read_metadata()
        self.combined_logs = "\n".join(self.logs)
        self.combined_metadata = "\n".join(self.metadata)

        self.initiate_conversation()

    def initiate_conversation(self):
        """Initiate the conversation by asking for event and metadata summaries."""

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


    def explain(self, files):
        """Initiate the explanation process based on the provided files.

        The explanation process involves the following steps:
        1. For each file, read the content and decide which agent should process it.
        2. Route the content to the appropriate agent for analysis.
        3. Generate an explanation based on the analyzed data.
        4. Evaluate the quality of the explanation.
        5. Provide the final explanation to the user.
        6. Enable the user to request further explanations or details.

        Args:
            files (list): List of file paths to be explained.

        """

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


if __name__ == '__main__':
    iexplain = iExplain()
    # iexplain.run()
    iexplain.explain(["logs", "metadata"])