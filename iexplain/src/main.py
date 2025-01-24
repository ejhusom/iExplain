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

from autogen import ConversableAgent, GroupChat, GroupChatManager, AssistantAgent
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

        # Agent for receiving input and routing it to the correct agent
        # self.group_chat_manager = GroupChatManager(
        #     name="GroupChatManager",
        #     system_message="You are the group chat manager. You receive input and route it to the correct agent.",
        #     description="I receive input and route it to the correct agent.",
        #     llm_config={"config_list": self.config_list},
        #     code_execution_config=False,
        #     function_map=None,
        #     human_input_mode="ALWAYS" if DEBUG_MODE else "NEVER",
        # )

        # Agent for collecting and summarizing metadata
        self.metadata_collector = ConversableAgent(
            name="MetadataParserAgent",
            system_message="Collect and summarize metadata from the system.",
            description="I collect and summarize metadata from the system.",
            llm_config={"config_list": self.config_list},
            code_execution_config=False,
            function_map=None,
            human_input_mode="ALWAYS" if DEBUG_MODE else "NEVER",
        )

        self.log_analyzer = ConversableAgent(
            name="LogAnalyzerAgent",
            system_message="""You analyze system logs to identify patterns and relationships. Your tasks:
            1. Identify the structure and format of the logs
            2. Group related events based on available identifiers (timestamps, IDs, etc.)
            3. Detect sequences of related events
            4. Identify critical or anomalous patterns
            
            For any log format, focus on:
            - Temporal patterns (when events occur)
            - Entity relationships (which components/systems are involved)
            - Event severity and types
            - Error propagation patterns""",
            description="I analyze raw log data to extract meaningful patterns and event sequences.",
            llm_config={"config_list": self.config_list},
            human_input_mode="ALWAYS" if DEBUG_MODE else "NEVER",
        )

        self.context_provider = ConversableAgent(
            name="ContextProviderAgent",
            system_message="""You provide system and operational context for log events. Your tasks:
            1. Interpret error messages and system events
            2. Explain relationships between different system components
            3. Assess potential impacts of observed patterns
            4. Distinguish between normal operations and potential issues
            
            Consider:
            - The type of system generating the logs
            - Common patterns in such systems
            - Potential implications of different event types
            - Relationships between different components""",
            description="I provide technical and operational context for system events.",
            llm_config={"config_list": self.config_list},
            human_input_mode="ALWAYS" if DEBUG_MODE else "NEVER",
        )

        self.explanation_generator = ConversableAgent(
            name="ExplanationAgent",
            system_message="""Generate clear, structured explanations of system events at multiple levels:
            1. Technical Details: What exactly happened in the system
            2. System Impact: How these events affect system operation
            3. Operational Context: What this means for system management
            4. Recommendations: Suggested actions or monitoring needs
            
            Create explanations that:
            - Connect related events into coherent narratives
            - Highlight important patterns and their implications
            - Scale detail based on the audience (technical vs operational)
            - Provide actionable insights""",
            description="I create multi-level explanations of system events.",
            llm_config={"config_list": self.config_list},
            human_input_mode="ALWAYS" if DEBUG_MODE else "NEVER",
        )

        self.evaluator = ConversableAgent(
            name="EvaluatorAgent",
            system_message="Evaluate the quality of explanations based on relevance, correctness, and clarity. Score each explanation from 1 to 5.",
            description="I evaluate the quality of explanations based on relevance, correctness, and clarity.",
            llm_config={"config_list": self.config_list},
            code_execution_config=False,
            function_map=None,
            human_input_mode="ALWAYS" if DEBUG_MODE else "NEVER",
        )

        self.moderator = ConversableAgent(
            name="ModeratorAgent",
            system_message="You are an AI-based moderator that makes plans for the whole group. When you get a task, break it down into sub-tasks, each to be performed by one of your 'partner agents'. You will get an introduction about what each of your partner agents can do. If you speak in the middle of two tasks, remember to repeat the key information you get from the previous speaker, so that the next speaker has sufficient context. You will also serve as the interface to the human proxy.",
            description="I am an AI-based moderator that makes plans for the whole group and serves as the interface to the human proxy.",
            llm_config={"config_list": self.config_list},
            code_execution_config=False,
            function_map=None,
            human_input_mode="ALWAYS" if DEBUG_MODE else "NEVER",
        )

        self.human_proxy = ConversableAgent(
            "human_proxy",
            llm_config=False,  # no LLM used for human proxy
            human_input_mode="ALWAYS",  # always ask for human input
        )

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
        metadata_summary = self.moderator.initiate_chats(
            [
                {
                    "recipient": self.metadata_collector,
                    "message": "Please summarize the following metadata:\n\n" + self.combined_metadata,
                    "clear_history": False,
                    "max_turns": 1,
                    "summary_method": "last_msg"
                }
            ]
        )[-1].summary

        # Summarizing logs
        # log_message = self.limit_token_length(f"Here are some logs with the following metadata:\n\n{metadata_summary}\n\n{self.combined_logs}")
        log_message = f"Here are some logs with the following metadata:\n\n{metadata_summary}\n\n{self.combined_logs}"
        event_log_summary = self.moderator.initiate_chats(
            [
                {
                    "recipient": self.log_analyzer,
                    "message": log_message,
                    "clear_history": False,
                    "max_turns": 1,
                    "summary_method": "last_msg"
                }
            ]
        )[-1].summary

        # ExplanationGeneratorAgent generates explanations based on the summaries
        explanation = self.moderator.initiate_chats(
            [
                {
                    "recipient": self.explanation_generator,
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
        # Step 1: Read the content of each file
        file_contents = []
        for file_path in files:
            with open(file_path, "r") as file:
                file_contents.append(file.read())

        # Combine the contents of all files
        combined_content = "\n".join(file_contents)

        # Step 2: Route the content to the appropriate agent for analysis
        # Start by summarizing the metadata
        metadata_summary = self.moderator.initiate_chats(
            [
                {
                    "recipient": self.metadata_collector,
                    "message": "Please summarize the following metadata:\n\n" + combined_content,
                    "clear_history": False,
                    "max_turns": 1,
                    "summary_method": "last_msg"
                }
            ]
        )[-1].summary

        # Summarizing logs
        log_message = f"Here are some logs with the following metadata:\n\n{metadata_summary}\n\n{combined_content}"
        event_log_summary = self.moderator.initiate_chats(
            [
                {
                    "recipient": self.log_analyzer,
                    "message": log_message,
                    "clear_history": False,
                    "max_turns": 1,
                    "summary_method": "last_msg"
                }
            ]
        )[-1].summary

        # Step 3: Generate an explanation based on the analyzed data
        explanation = self.moderator.initiate_chats(
            [
                {
                    "recipient": self.explanation_generator,
                    "message": f"Please generate an explanation based on the following summaries:\n\nMetadata Summary:\n{metadata_summary}\n\nEvent Log Summary:\n{event_log_summary}",
                    "clear_history": False,
                    "max_turns": 1,
                    "summary_method": "last_msg"
                }
            ]
        )[-1].summary

        # Step 4: Evaluate the quality of the explanation
        evaluation = self.moderator.initiate_chats(
            [
                {
                    "recipient": self.evaluator,
                    "message": f"Please evaluate the following explanation:\n\n{explanation}",
                    "clear_history": False,
                    "max_turns": 1,
                    "summary_method": "last_msg"
                }
            ]
        )[-1].summary

        # Step 5: Provide the final explanation to the user
        final_explanation = f"Explanation:\n{explanation}\n\nEvaluation:\n{evaluation}"
        print(final_explanation)

        # Step 6: Enable the user to request further explanations or details
        self.human_proxy.initiate_chats(
            [
                {
                    "recipient": self.moderator,
                    "message": "Please provide any further explanations or details as requested by the user.",
                    "clear_history": False,
                    "max_turns": 1,
                    "summary_method": "last_msg"
                }
            ]
        )


if __name__ == '__main__':
    iexplain = iExplain()
    iexplain.run()


