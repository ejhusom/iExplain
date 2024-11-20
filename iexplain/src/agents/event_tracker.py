import os

import json
from typing import Dict, List, Optional, Callable, Union
from autogen import ConversableAgent

from autogen import ConversableAgent

#agent = ConversableAgent(
#    name = "EventTrackerAgent",
#    llm_config={"config_list": [{"model": "gpt-4", "api_key": os.environ.get("OPENAI_API_KEY")}]},
#    code_execution_config=False,  # Turn off code execution, by default it is off.
#    function_map=None,  # No registered functions, by default it is None.
#    human_input_mode="NEVER",  # Never ask for human input.
#)

#class EventTrackerAgent(ConversableAgent):
#    """An agent that tracks and logs events in a conversational AI system.
#
#    The input events can be of various types, such as user interactions, system
#    responses, or AI actions. The EventTrackerAgent is responsible for logging
#    these events in a structured format, which can be used for generating
#    explanations, evaluating system performance, or analyzing user behavior.
#
#    The input events can be in many different formats, such as JSON, XML, or
#    plain text. The agent should be able to parse and extract relevant
#    information from these events, such as the event type, timestamp, and
#    details. The agent will parse the input events and store them in a
#    structured format (JSON) for further processing.
#
#    The JSON output format looks like this, where the "details" field can contain
#    additional information specific to the event type:
#
#    {
#        "event_id": "123456",
#        "event_type": "User_Input",
#        "timestamp": "2024-08-21T09:00:00Z",
#        "details": {
#            "input_text": "Hello, how are you?"
#        }
#    }
#
#    The EventTrackerAgent can be used in conjunction with other agents, such as
#    the ExplanationGeneratorAgent and EvaluatorAgent, to provide explanations
#    and evaluations for the events logged by the agent.
#
#    """
#
#    def __init__(
#        self,
#        name: str,
#        llm_config: Dict[str, Union[str, List[Dict[str, str]]]],
#        code_execution_config: Optional[bool] = False,
#        function_map: Optional[Dict[str, Callable]] = None,
#        human_input_mode: Optional[str] = "NEVER",
#    ):
#        """Initialize the EventTrackerAgent.
#
#        Args:
#            name (str): The name of the agent.
#            llm_config (Dict[str, Union[str, List[Dict[str, str]]]]): The configuration
#                for the language model used by the agent.
#            code_execution_config (Optional[bool]): Whether to allow code execution.
#                Defaults to False.
#            function_map (Optional[Dict[str, Callable]]): A map of function names to
#                function objects. Defaults to None.
#            human_input_mode (Optional[str]): The mode for human input. Can be one of
#                "NEVER", "ALWAYS", or "ASK". Defaults to "NEVER".
#
#        """
#        super().__init__(
#            name=name,
#            llm_config=llm_config,
#            code_execution_config=code_execution_config,
#            function_map=function_map,
#            human_input_mode=human_input_mode,
#        )
#
#        self.log_file = "event_tracker.log"
#
#    def process_event(self, event: dict) -> str:
#        """Process an event and log it to the event log.
#
#        Args:
#            event (dict): A dictionary representing an event to be processed.
#
#        Returns:
#            str: The event ID assigned to the event.
#
#        """
#        # Generate a unique event ID
#        event_id = self.generate_event_id()
#
#        # Add the event ID to the event dictionary
#        event["event_id"] = event_id
#
#        # Log the event to the event log
#        self.log_event(event)
#
#        return event_id
#
#    def generate_event_id(self) -> str:
#        """Generate a unique event ID.
#
#        Returns:
#            str: A unique event ID.
#
#        """
#        # In a real system, this would generate a unique ID based on a timestamp
#        # and some other unique identifier. For simplicity, we'll just use a
#        # random number here.
#        return str(random.randint(100000, 999999))
#
#    def log_event(self, event: dict):
#        """Log an event to the event log.
#
#        Args:
#            event (dict):
#
#        """
#        with open(self.log_file, "a") as f:
#            f.write(json.dumps(event) + "\n")
#
#    def get_event_log(self) -> List[dict]:
#        """Get the event log.
#
#        Returns:
#            List[dict]: A list of events in the event log.
#
#        """
#        with open(self.log_file, "r") as f:
#            return [json.loads(line) for line in f]
#
#    def clear_event_log(self):
#        """Clear the event log."""
#        with open(self.log_file, "w") as f:
#            pass
#
#
