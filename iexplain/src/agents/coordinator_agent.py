from autogen import ConversableAgent

def create_coordinator_agent(config_list):
    """Create a coordinator agent for orchestrating workflows.

    The coordinator agent doesn't use an LLM - it just routes messages
    between agents in sequential and nested chat patterns.
    """
    return ConversableAgent(
        name="coordinator",
        system_message="You coordinate communication between specialized agents.",
        description="Orchestrates multi-agent workflows without requiring LLM inference.",
        llm_config=False,  # No LLM needed for coordination
        human_input_mode="NEVER",
    )
