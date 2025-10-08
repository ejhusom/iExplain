#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nested workflow for agent interaction.

This workflow uses nested chats for complex log analysis:
- Outer: Sequential flow (Intent Parser -> Coordinator -> Explanation Generator)
- Inner: Nested log analysis (triggered after intent parsing)
"""

from typing import Dict, Any, List, Tuple
from workflows.base_workflow import BaseWorkflow


class NestedWorkflow(BaseWorkflow):
    """Nested workflow with complex log analysis.

    The coordinator triggers a nested conversation for log analysis,
    which can involve multiple specialized agents working together.
    """

    def get_required_agents(self) -> List[str]:
        """Return required agents for nested workflow."""
        return [
            "coordinator_agent",
            "intent_parser_agent",
            "log_analysis_agent",
            "explanation_generator_agent"
        ]

    def execute(
        self,
        agents: Dict[str, Any],
        config_list: List[Dict],
        intent_data: Dict[str, Any],
        log_files: List[str],
        expected_fields: List[str]
    ) -> Tuple[Any, List]:
        """Execute the nested workflow.

        Args:
            agents: Dictionary of available agents
            config_list: LLM configuration list
            intent_data: Intent information
            log_files: List of log file paths
            expected_fields: Expected explanation fields

        Returns:
            Tuple of (result, conversation_log)
        """
        self.validate_agents(agents)

        coordinator = agents["coordinator_agent"]

        # Build prompts
        intent_prompt = self._build_intent_prompt(intent_data)

        # Define nested chat for log analysis
        # This will be triggered automatically after intent parsing
        nested_log_analysis = [
            {
                "recipient": agents["log_analysis_agent"],
                "message": self._build_log_analysis_message(log_files),
                "summary_method": "reflection_with_llm",
                "summary_args": {
                    "summary_prompt": "Summarize the key findings from log analysis, including measured outcomes and evidence."
                },
                "max_turns": 2
            }
        ]

        # Register nested chats on the coordinator
        # These will be triggered when the intent_parser_agent responds
        coordinator.register_nested_chats(
            nested_log_analysis,
            trigger=agents["intent_parser_agent"]
        )

        print("Stage 1: Parsing intent...")
        print("Stage 2: Nested log analysis will be triggered automatically...")

        # Sequential outer flow
        result = coordinator.initiate_chats([
            {
                "recipient": agents["intent_parser_agent"],
                "message": intent_prompt,
                "max_turns": 1,
                "summary_method": "last_msg"
            },
            {
                "recipient": agents["explanation_generator_agent"],
                "message": self._build_explanation_prompt(expected_fields),
                "max_turns": 1,
                "summary_method": "last_msg"
            }
        ])

        # Extract conversation log
        conversation_log = result.chat_history if hasattr(result, 'chat_history') else []

        return result, conversation_log

    def _build_intent_prompt(self, intent_data: Dict[str, Any]) -> str:
        """Build the prompt for intent parsing stage."""
        nl_section = ""
        if intent_data.get('nl_intent'):
            nl_section = f"\n\nNatural language version:\n{intent_data['nl_intent']}"

        return f"""Analyze this TMF intent and extract structured information.

Intent (TMF format):
```
{intent_data['structured_intent']}
```
{nl_section}

Extract and provide:
1. Primary Objective: What does the user want to achieve?
2. Key Metrics and Thresholds: What specific measurements and targets are defined?
3. Context: Geographic regions, time constraints, or other contextual information
4. Success Criteria: How do we determine if the intent is fulfilled?

Provide a clear, structured summary of these components."""

    def _build_log_analysis_message(self, log_files: List[str]) -> str:
        """Build the message for nested log analysis."""
        return f"""Analyze these log files: {', '.join(log_files)}

Based on the intent summary provided, determine:
1. What actions were taken by the system?
2. What were the measured outcomes for the specified metrics?
3. Did the system meet the success criteria?
4. What factors influenced the outcome?

Provide evidence from the logs to support your analysis."""

    def _build_explanation_prompt(self, expected_fields: List[str]) -> str:
        """Build the prompt for explanation generation stage."""
        field_list = "\n".join(expected_fields)

        return f"""Generate a structured explanation based on the intent analysis and log findings.

Create a JSON object with these fields:
{field_list}

Guidelines:
- Classify outcome as "Success", "Partial Success", or "Failure"
- Provide clear explanations supported by evidence
- Be concise but complete
- Use language appropriate for non-technical stakeholders

Output ONLY the JSON object, wrapped in ```json``` markers."""
