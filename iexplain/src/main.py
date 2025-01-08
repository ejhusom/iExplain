#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""iExplain - Explainability module.

This module provides the functionality to generate explanations for system
adaptations based on log entries. It is intended to be used as a part of the
inGen system, which is a conversational AI system that can adapt to user
feedback.

"""
import configparser
import os
import sys
import datetime

import json

from autogen import ConversableAgent, GroupChat, GroupChatManager, AssistantAgent
from autogen.agentchat.contrib.retrieve_user_proxy_agent import RetrieveUserProxyAgent

from config import config

class iExplain:
    """Generate explanations for actions and adaptations made by AI agents.

    iExplain is a Python framework designed to generate human-understandable
    explanations for a series of actions, events, or decisions. These actions
    could originate from AI agents, machine learning models, or even sequences
    in a complex system. The goal is to provide clear, context-aware
    explanations that help users understand why a specific sequence of events
    occurred.

    The framework is centered around the concept of **Intent-based Computing**,
    where actions are driven by high-level intents or objectives. By tracing
    the reasoning behind each action, iExplain aims to reveal the complex
    decision-making processes and enhance transparency in AI systems.

    iExplain employs a set of interacting LLM (Large Language Model) agents
    to generate explanations based on input data and contextual information.
    These agents can leverage pre-trained language models (e.g., GPT-4) or
    domain-specific models to collaboratively generate explanations tailored to
    different audiences or applications. The interaction between multiple LLM
    agents allows the framework to reason about diverse factors and arrive at
    coherent, multi-layered explanations.

    """

    def __init__(self):
        """Initialize the iExplain framework."""

        if config.LLM_SERVICE == "openai":
            self.config_list = [{
                "model": config.LLM_MODEL, 
                "api_key": os.environ.get("OPENAI_API_KEY")
            }]
        elif config.LLM_SERVICE == "ollama":
            self.config_list = [{
                "model": config.LLM_MODEL, 
                "api_type": "ollama",
            }]

        self.event_collector = ConversableAgent(
            name="EventCollectorAgent",
            system_message="Collect and summarize events from the system.",
            description="I collect and summarize events from the system.",
            llm_config={"config_list": self.config_list},
            code_execution_config=False,
            function_map=None,
            human_input_mode="NEVER",
        )
    
        # Agent for collecting and summarizing metadata
        self.metadata_collector = ConversableAgent(
            name="MetadataCollectorAgent",
            system_message="Collect and summarize metadata from the system.",
            description="I collect and summarize metadata from the system.",
            llm_config={"config_list": self.config_list},
            code_execution_config=False,
            function_map=None,
            human_input_mode="NEVER",
        )

        self.explanation_generator = ConversableAgent(
            name="ExplanationGeneratorAgent",
            system_message="""
Generate a concise explanation of event sequences based on the provided summaries. Focus on causality and relationships between events.
""",
            description="I generate concise explanations of event sequences based on input data.",
            llm_config={"config_list": self.config_list},
            code_execution_config=False,
            function_map=None,
            human_input_mode="NEVER",
            is_termination_msg=lambda msg: "TERMINATE" in msg["content"],
        )

        self.evaluator = ConversableAgent(
            name="EvaluatorAgent",
            system_message="Evaluate the quality of explanations based on relevance, correctness, and clarity. Score each explanation from 1 to 5.",
            description="I evaluate the quality of explanations based on relevance, correctness, and clarity.",
            llm_config={"config_list": self.config_list},
            code_execution_config=False,
            function_map=None,
            human_input_mode="NEVER",
        )

        self.initiator = ConversableAgent(
            name="InitiatorAgent",
            system_message="Initiate the conversation by asking the EventCollectorAgent and MetadataCollectorAgent to provide their summaries.",
            description="I initiate the conversation by asking for event and metadata summaries.",
            llm_config=False,
            code_execution_config=False,
            function_map=None,
            human_input_mode="NEVER",
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
            elif log_file.endswith(".txt"):
                with open(config.LOGS_PATH / log_file, "r") as f:
                    logs.append(f.read())
            elif log_file.endswith(".csv"):
                with open(config.LOGS_PATH / log_file, "r") as f:
                    logs.append(f.read())
            else:
                print(f"Unsupported file format: {log_file}")

        return logs

    def read_metadata(self):
        """Read the metadata from the metadata directory."""

        metadata = []
        plain_text_formats = [".txt", ".csv", ".log", ".md"]
        for metadata_file in os.listdir(config.METADATA_PATH):
            if metadata_file.endswith(".json"):
                with open(config.METADATA_PATH / metadata_file, "r") as f:
                    metadata.append(json.load(f))
            elif any(metadata_file.endswith(fmt) for fmt in plain_text_formats):
                with open(config.METADATA_PATH / metadata_file, "r") as f:
                    metadata.append(f.read())
            else:
                print(f"Unsupported file format: {metadata_file}")

        return metadata

    def run(self):
        """Run the iExplain framework."""
        logs = self.read_logs()
        metadata = self.read_metadata()
        group_chat_manager = self.setup_group_chat_manager()
        self.initiate_conversation(group_chat_manager, logs, metadata)
        self.save_conversation(group_chat_manager)

    def setup_group_chat_manager(self):
        """Set up the group chat manager with agents and transitions."""
        allowed_transitions = {
            self.initiator: [self.event_collector, self.metadata_collector, self.explanation_generator, self.evaluator],
            self.event_collector: [self.explanation_generator, self.metadata_collector, self.initiator],
            self.metadata_collector: [self.explanation_generator, self.event_collector, self.initiator],
            self.explanation_generator: [self.evaluator, self.event_collector, self.metadata_collector, self.initiator],
            self.evaluator: [self.explanation_generator],
        }

        group_chat = GroupChat(
            agents=[self.initiator, self.event_collector, self.metadata_collector, self.explanation_generator, self.evaluator],
            allowed_or_disallowed_speaker_transitions=allowed_transitions,
            speaker_transitions_type="allowed",
            messages=[],
            max_round=6,
            send_introductions=True,
            speaker_selection_method="auto",
        )

        return GroupChatManager(
            groupchat=group_chat,
            llm_config={"config_list": self.config_list},
        )

    def initiate_conversation(self, group_chat_manager, logs, metadata):
        """Initiate the conversation by asking for event and metadata summaries."""
        combined_logs = "\n".join(logs)
        combined_metadata = "\n".join(metadata)

        # Start by summarizing the metadata
        metadata_summary = self.initiator.initiate_chats(
            [
                {
                    "recipient": self.metadata_collector,
                    "message": "MetadataCollectorAgent, please summarize the following metadata:\n\n" + combined_metadata,
                    "clear_history": False,
                    "max_turns": 1,
                    "summary_method": "last_msg"
                }
            ]
        )[-1].summary

        # Metadata summary is provided to the EventCollectorAgent, which will summarize the logs
        event_log_summary = self.initiator.initiate_chats(
            [
                {
                    "recipient": self.event_collector,
                    "message": f"EventCollectorAgent, here are some logs with the following metadata:\n\n{metadata_summary}\n\nPlease summarize the following logs:\n\n{combined_logs}",
                    "clear_history": False,
                    "max_turns": 1,
                    "summary_method": "last_msg"
                }
            ]
        )[-1].summary

        # ExplanationGeneratorAgent generates explanations based on the summaries
        explanation = self.initiator.initiate_chats(
            [
                {
                    "recipient": self.explanation_generator,
                    "message": f"ExplanationGeneratorAgent, please generate an explanation based on the following summaries:\n\nMetadata Summary:\n{metadata_summary}\n\nEvent Log Summary:\n{event_log_summary}",
                    "clear_history": False,
                    "max_turns": 1,
                    "summary_method": "last_msg"
                }
            ]
        )[-1].summary

        # chat_results = self.initiator.initiate_chats(
        #     [
        #         {
        #             "recipient": group_chat_manager,
        #             "message": f"Here are the summaries of the logs and metadata:\n\nMetadata Summary:\n{metadata_summary}\n\nEvent Log Summary:\n{event_log_summary}\n\nPlease give a summary of the logs and metadata.",
        #         },
        #     ]
        # )

        # # Present summaries to the user and allow them to ask questions
        # self.human_proxy.initiate_chats(
        #     [
        #         {
        #             "recipient": group_chat_manager,
        #             "message": f"Here are the summaries of the logs and metadata:\n\nMetadata Summary:\n{metadata_summary}\n\nEvent Log Summary:\n{event_log_summary}\n\nPlease ask any questions you have, and I will pass them on to the most suitable agent."
        #         }
        #     ]
        # )

    def save_conversation(self, group_chat_manager):
        """Save the conversation logs to the output folder with a timestamp."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = config.OUTPUT_PATH / f"conversation_{timestamp}.txt"
        
        with open(output_file, "w") as f:
            for message in group_chat_manager.groupchat.messages:
                role = message.get('role', 'Unknown role')
                name = message.get('name', 'Unknown name')
                content = message.get('content', '')
                f.write(f"{role}, {name}: {content}\n")

if __name__ == '__main__':
    iexplain = iExplain()
    iexplain.run()


