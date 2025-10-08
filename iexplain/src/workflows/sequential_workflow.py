#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sequential workflow for agent interaction.

This workflow uses a three-stage sequential pattern:
1. Intent Parser analyzes the TMF intent
2. Log Analyzer examines logs against intent requirements
3. Explanation Generator creates final structured output
"""

from typing import Dict, Any, List, Tuple
from workflows.base_workflow import BaseWorkflow


class SequentialWorkflow(BaseWorkflow):
    """Three-stage sequential workflow for intent explanation.

    Each stage builds on the previous one, with summaries carried forward.
    This pattern is deterministic and easy to debug.
    """

    def get_required_agents(self) -> List[str]:
        """Return required agents for sequential workflow."""
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
        """Execute the three-stage sequential workflow.

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

        # Build prompts for each stage
        intent_prompt = self._build_intent_prompt(intent_data)

        # Stage 1: Parse intent
        print("Stage 1: Parsing intent...")
        intent_result = coordinator.initiate_chats([
            {
                "recipient": agents["intent_parser_agent"],
                "message": intent_prompt,
                "max_turns": 1,
                "summary_method": "last_msg"
            }
        ])

        # The function `initiate_chats` returns a list of ChatResult objects
        # corresponding to the finished chats in the chat_queue. We only have
        # one chat here, so we default to the latest result.
        intent_result = intent_result[-1]

        # Extract intent summary from result
        intent_summary = self._extract_summary(intent_result)

        # Stage 2: Analyze logs
        print("Stage 2: Analyzing logs...")
        log_prompt = self._build_log_analysis_prompt(intent_summary, log_files)
        log_result = coordinator.initiate_chats([
            {
                "recipient": agents["log_analysis_agent"],
                "message": log_prompt,
                "max_turns": 2,
                "summary_method": "reflection_with_llm",
                "summary_args": {
                    "summary_prompt": "Summarize the key findings from the log analysis, including measured outcomes and evidence."
                }
            }
        ])

        # The function `initiate_chats` returns a list of ChatResult objects
        # corresponding to the finished chats in the chat_queue. We only have
        # one chat here, so we default to the latest result.
        log_result = log_result[-1]

        # Extract log analysis summary
        log_summary = self._extract_summary(log_result)

        # Stage 3: Generate explanation
        print("Stage 3: Generating explanation...")
        explanation_prompt = self._build_explanation_prompt(
            intent_summary,
            log_summary,
            expected_fields
        )
        explanation_result = coordinator.initiate_chats([
            {
                "recipient": agents["explanation_generator_agent"],
                "message": explanation_prompt,
                "max_turns": 1,
                "summary_method": "last_msg"
            }
        ])

        # The function `initiate_chats` returns a list of ChatResult objects
        # corresponding to the finished chats in the chat_queue. We only have
        # one chat here, so we default to the latest result.
        explanation_result = explanation_result[-1]

        # Combine all conversations into a single log
        full_conversation = []
        full_conversation.extend(intent_result.chat_history)
        full_conversation.extend(log_result.chat_history)
        full_conversation.extend(explanation_result.chat_history)

        return explanation_result, full_conversation

    def _extract_summary(self, result: Any) -> str:
        """Extract summary from chat result.

        Args:
            result: Result object from initiate_chats

        Returns:
            Summary string
        """
        if hasattr(result, 'summary'):
            return result.summary
        elif hasattr(result, 'chat_history') and result.chat_history:
            # Get last message content
            last_msg = result.chat_history[-1]
            if isinstance(last_msg, dict) and 'content' in last_msg:
                return last_msg['content']
        return ""

    def _build_intent_prompt(self, intent_data: Dict[str, Any]) -> str:
        """Build the prompt for intent parsing stage.

        Args:
            intent_data: Intent information dictionary

        Returns:
            Formatted prompt string
        """
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
2. Key Metrics and Thresholds: What specific measurements and targets are defined? (e.g., "latency < 100ms", "bandwidth > 1Gbps")
3. Context: Geographic regions, time constraints, or other contextual information
4. Success Criteria: How do we determine if the intent is fulfilled?

Provide a clear, structured summary of these components."""

    def _build_log_analysis_prompt(
        self,
        intent_summary: str,
        log_files: List[str]
    ) -> str:
        """Build the prompt for log analysis stage.

        Args:
            intent_summary: Summary from intent parsing stage
            log_files: List of log file paths

        Returns:
            Formatted prompt string
        """
        return f"""Based on this intent summary:

```
{intent_summary}
```

Analyze these log files: {', '.join(log_files)}

Your task:
1. Identify what actions were taken by the system (cite specific log entries with timestamps)
2. Measure actual outcomes for the metrics specified in the intent
3. Compare measured values against the intent's thresholds
4. Determine if the system met the success criteria
5. Identify factors that influenced the outcome (positive or negative)

Provide evidence from the logs to support your analysis. Structure your response clearly with sections for Actions, Outcomes, Comparison, and Factors."""

    def _build_explanation_prompt(
        self,
        intent_summary: str,
        log_summary: str,
        expected_fields: List[str]
    ) -> str:
        """Build the prompt for explanation generation stage.

        Args:
            intent_summary: Summary from intent parsing
            log_summary: Summary from log analysis
            expected_fields: List of expected explanation fields

        Returns:
            Formatted prompt string
        """
        field_list = "\n".join(expected_fields)

        return f"""Generate a structured explanation based on the following analysis:

INTENT SUMMARY:
```
{intent_summary}
```

LOG ANALYSIS:
```
{log_summary}
```

Create a JSON object with these fields:

{field_list}

Guidelines:
- Classify outcome as "Success", "Partial Success", or "Failure"
- Provide clear explanations supported by evidence
- Be concise but complete
- Use language appropriate for non-technical stakeholders

Output ONLY the JSON object, wrapped in ```json``` markers."""
