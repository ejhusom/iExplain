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

import json

from autogen import ConversableAgent, GroupChat, GroupChatManager

from config import config
#from agents.event_tracker import EventTrackerAgent
#from agents.explanation_generator import ExplanationGeneratorAgent
#from agents.evaluator import EvaluatorAgent

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

    def __init__(self, config_file: str = "config.ini"):
        """Initialize the iExplain framework.

        Args:
            config_file (str): The path to the configuration file.

        """
        self.config = configparser.ConfigParser()
        self.config.read(config_file)

        self.event_collector = ConversableAgent(
            name="EventCollectorAgent",
            system_message="You are responsible for collecting events from the system.",
            llm_config={"config_list": [{"model": "gpt-4o-mini", "api_key": os.environ.get("OPENAI_API_KEY")}]},
            code_execution_config=False,
            function_map=None,
            human_input_mode="NEVER",
        )

        self.event_tracker = ConversableAgent(
            name="EventTrackerAgent",
            system_message="You are responsible for recording and tracking events, and outputting them in a structured JSON format, looking like this: {\"event_id\": \"123456\", \"event_type\": \"User_Input\", \"timestamp\": \"2024-08-21T09:00:00Z\", \"details\": {\"input_text\": \"Hello, how are you?\"}}. The output cannot under any circumstances be in any other format, and should not include anything else than the JSON. You are allowed to add additional fields under the \"details\" field. You need to provide the full log of events based on the information you receive.",
            llm_config={"config_list": [{"model": "gpt-4o-mini", "api_key": os.environ.get("OPENAI_API_KEY")}]},
            code_execution_config=False,
            function_map=None,
            human_input_mode="NEVER",
        )

        self.explanation_generator = ConversableAgent(
            name="ExplanationGeneratorAgent",
            system_message="""
You are the ExplanationGeneratorAgent, responsible for generating comprehensive explanations of event sequences based on the input data provided by the EventTrackerAgent. Your primary tasks include:

1. Analyzing a series of events, intents, and actions taken within the system.
2. Constructing coherent narratives that elucidate the causality and relationships between events.
3. Utilizing information from various knowledge sources, including logs and knowledge graphs, to enhance the quality and accuracy of your explanations.
4. Interpreting feedback from the EvaluatorAgent to refine your outputs, ensuring they are clear and accurate.
5. Maintaining a focus on generating user-friendly natural language explanations that can be easily understood by IT administrators and stakeholders.

Your goal is to provide insightful and actionable explanations that help users understand system behavior and decision-making processes.
""",
            llm_config={"config_list": [{"model": "gpt-4o-mini", "api_key": os.environ.get("OPENAI_API_KEY")}]},
            code_execution_config=False,
            function_map=None,
            human_input_mode="NEVER",
            is_termination_msg=lambda msg: "TERMINATE" in msg["content"],
        )

        self.evaluator = ConversableAgent(
            name="EvaluatorAgent",
            system_message="You are responsible for evaluating the quality of explanatiions generated by the ExplanationGeneratorAgent. The main criteria for evaluation are relevance, correctness, and clarity. Give a score between 1 and 5 for each explanation, where 1 is the lowest and 5 is the highest. If the score is lower than 4 for correctness, ask for a correction. If the score is 4 or higher for correctness, end your message with 'TERMINATE'.",
            llm_config={"config_list": [{"model": "gpt-4o-mini", "api_key": os.environ.get("OPENAI_API_KEY")}]},
            code_execution_config=False,
            function_map=None,
            human_input_mode="NEVER",
        )

    def run(self, logs_json: str):
        """Run the iExplain framework.

        Args:
            logs_json (str): The path to the log entries in JSON format.

        """

        allowed_transitions = {
            self.event_collector: [self.event_tracker],
            self.event_tracker: [self.explanation_generator],
            self.explanation_generator: [self.evaluator],
            self.evaluator: [self.explanation_generator],
        }

        group_chat = GroupChat(
            agents=[self.event_collector, self.event_tracker, self.explanation_generator, self.evaluator],
            allowed_or_disallowed_speaker_transitions=allowed_transitions,
            speaker_transitions_type="allowed",
            messages=[],
            max_round=6,
            send_introductions=True,
            # speaker_selection_method="manual",
        )

        group_chat_manager = GroupChatManager(
            groupchat=group_chat,
            llm_config={"config_list": [{"model": "gpt-4o-mini", "api_key": os.environ["OPENAI_API_KEY"]}]},
        )

        chat_results = self.event_collector.initiate_chats(
            [
                {
                    "recipient": group_chat_manager,
                    "message": "Here are my collected events: " + logs_json,
                },
            ]
        )

        #chat_results = self.event_collector.initiate_chats(
        #    [
        #        {
        #            "recipient": self.event_tracker,
        #            "message": logs_json,
        #        },
        #        {
        #            "recipient": self.explanation_generator,
        #            "message": "Here are the recorded events.",
        #        },
        #        {
        #            "recipient": self.evaluator,
        #            "message": "Here are the generated explanations.",
        #        },
        #    ]
        #)



if __name__ == '__main__':

    iexplain = iExplain()

    # Read the log entries from files located in the directory passed as an
    # argument. If no directory is passed, read the log entries from the
    # default directory.
    log_dir = sys.argv[1] if len(sys.argv) > 1 else config.DATA_PATH
    # Read JSON log entries into a single text string
    logs_json = {}
    for log_file in log_dir.glob("*.json"):
        with open(log_file, "r") as file:
            logs_json[log_file.stem] = json.load(file)

    print(logs_json)
    #breakpoint()

    # Run the iExplain framework with the log entries.
    iexplain.run(str(logs_json))


