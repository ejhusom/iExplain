#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GroupChat workflow for agent interaction.

This workflow uses AG2's GroupChat pattern for free-form multi-agent collaboration.
Improved version with better configuration and prompting.
"""

from typing import Dict, Any, List, Tuple
from autogen import GroupChat, GroupChatManager
from workflows.base_workflow import BaseWorkflow


class GroupchatWorkflow(BaseWorkflow):
    """GroupChat workflow for multi-agent collaboration.

    Agents collaborate in a group chat format, with the GroupChatManager
    selecting speakers based on context.
    """

    def get_required_agents(self) -> List[str]:
        """Return required agents for groupchat workflow."""
        return [
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
        """Execute the groupchat workflow.

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

        # Get workflow config from config_list if available
        # Import here to avoid circular dependency
        from config import config as cfg
        workflow_config = cfg.WORKFLOW_CONFIG.get("groupchat", {})
        max_rounds = workflow_config.get("max_rounds", 10)
        send_introductions = workflow_config.get("send_introductions", True)

        # Create a user proxy agent for initiating the conversation
        from autogen import ConversableAgent
        user_proxy = ConversableAgent(
            name="user_proxy",
            system_message="You initiate tasks and provide context.",
            llm_config=False,
            human_input_mode="NEVER",
        )

        # Create the groupchat with agents
        groupchat = GroupChat(
            agents=[
                user_proxy,
                agents["intent_parser_agent"],
                agents["log_analysis_agent"],
                agents["explanation_generator_agent"]
            ],
            messages=[],
            max_round=max_rounds,
            send_introductions=send_introductions
        )

        # Create the manager
        manager = GroupChatManager(
            groupchat=groupchat,
            llm_config={"config_list": config_list} if config_list else False
        )

        # Build the initial prompt
        prompt = self._build_initial_prompt(intent_data, log_files, expected_fields)

        print(f"Starting GroupChat with max {max_rounds} rounds...")

        # Start the conversation
        result = user_proxy.initiate_chat(
            manager,
            message=prompt
        )

        # Extract conversation log
        conversation_log = result.chat_history if hasattr(result, 'chat_history') else []

        return result, conversation_log

    def _build_initial_prompt(
        self,
        intent_data: Dict[str, Any],
        log_files: List[str],
        expected_fields: List[str]
    ) -> str:
        """Build the initial prompt for the groupchat."""
        nl_section = ""
        if intent_data.get('nl_intent'):
            nl_section = f"\n\nNatural language version:\n{intent_data['nl_intent']}"

        field_list = "\n".join(expected_fields)

        return f"""I need to explain how a system addressed a user's intent.

INTENT (TMF format):
```
{intent_data['structured_intent']}
```
{nl_section}

LOG FILES to analyze: {', '.join(log_files)}

TASK:
Work together to:
1. Parse and understand the intent (intent_parser_agent)
2. Analyze the logs to determine if the intent was met (log_analysis_agent)
3. Generate a structured explanation (explanation_generator_agent)

REQUIRED OUTPUT:
The final explanation must be a JSON object with these fields:
{field_list}

The explanation should:
- Classify outcome as "Success", "Partial Success", or "Failure"
- Be evidence-based (cite log entries where appropriate)
- Be clear and concise for non-technical stakeholders
- Include actionable recommendations

Please collaborate to produce this explanation."""
