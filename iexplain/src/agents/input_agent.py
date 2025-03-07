
from autogen import ConversableAgent

def create_input_agent(config_list):
    return ConversableAgent(
        name="input_agent",
        system_message="You receive input and decide what to do with it. You may receive strings of text, numbers, or other data types. It can also be a file, a directory, or a URL. You should decide which agent should process it. If the input is a directory, instruct a code writer agent to write code to list the files in the directory. If the input is a file, instruct a code writer agent to read the file and print its contents.",
        description="Receive input and decide what to do with it, and which agent is most suitable to process it. When there is uncertainty about what to do with some input, input_agent is responsible for deciding what is the most suitable agent to process it.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )
