"""

## Tips for writing good descriptions for agents (source: https://docs.ag2.ai/blog/2023-12-29-AgentDescriptions/index#tips-for-writing-good-descriptions)

Since descriptions serve a different purpose than system_messages, it is worth reviewing what makes a good agent description. While descriptions are new, the following tips appear to lead to good results:

    Avoid using the 1st or 2nd person perspective. Descriptions should not contain “I” or “You”, unless perhaps “You” is in reference to the GroupChat / orchestrator
    Include any details that might help the orchestrator know when to call upon the agent
    Keep descriptions short (e.g., “A helpful AI assistant with strong natural language and Python coding skills.”).

The main thing to remember is that the description is for the benefit of the GroupChatManager, not for the Agent’s own use or instruction.

"""
from autogen import ConversableAgent, register_function
from get_tools import get_tools
import os
import importlib.util

from config import config

def get_agents(config_list = config.config_list):
    agents = {}
    agents_dir = os.path.join(os.path.dirname(__file__), 'agents')

    for filename in os.listdir(agents_dir):
        if filename.endswith('_agent.py') and filename != '__init__.py':
            module_name = filename[:-3]
            module_path = os.path.join(agents_dir, filename)
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            create_agent_func = getattr(module, f"create_{module_name}", None)
            if create_agent_func:
                agents[module_name] = create_agent_func(config_list)

    tools = get_tools()

    for tool_name, tool_details in tools.items():
        register_function(
            tool_details["function"],
            caller=agents[tool_details["caller"]],
            executor=agents[tool_details["executor"]],
            name=tool_details["name"],
            description=tool_details["description"]
        )

    return agents