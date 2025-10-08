#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Base workflow class for agent interaction patterns."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple


class BaseWorkflow(ABC):
    """Base class for agent interaction workflows.

    All workflow implementations should inherit from this class and implement
    the required methods.
    """

    @abstractmethod
    def execute(
        self,
        agents: Dict[str, Any],
        config_list: List[Dict],
        intent_data: Dict[str, Any],
        log_files: List[str],
        expected_fields: List[str]
    ) -> Tuple[Any, List]:
        """Execute the workflow and return results.

        Args:
            agents: Dictionary of available agents
            config_list: LLM configuration list
            intent_data: Dictionary containing intent information:
                - structured_intent: TMF format intent
                - nl_intent: Natural language intent (optional)
                - metadata: Intent metadata (id, description, etc.)
            log_files: List of log file paths to analyze
            expected_fields: List of expected explanation fields

        Returns:
            Tuple of (result_object, conversation_log)
            - result_object: The final result from the workflow
            - conversation_log: List of all conversation messages
        """
        pass

    @abstractmethod
    def get_required_agents(self) -> List[str]:
        """Return list of required agent names for this workflow.

        Returns:
            List of agent names that must be available
        """
        pass

    def validate_agents(self, agents: Dict[str, Any]) -> None:
        """Validate that all required agents are available.

        Args:
            agents: Dictionary of available agents

        Raises:
            ValueError: If required agents are missing
        """
        required = self.get_required_agents()
        missing = [name for name in required if name not in agents]

        if missing:
            raise ValueError(
                f"{self.__class__.__name__} requires agents: {required}. "
                f"Missing: {missing}"
            )
