
from autogen import ConversableAgent

def create_user_proxy_agent(config_list):
    return ConversableAgent(
        name="user_proxy_agent",
        system_message="A human admin.",
        description="A proxy for human input.",
        llm_config={"config_list": config_list},
        human_input_mode="TERMINATE",
    )
