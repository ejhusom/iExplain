"""

## Tips for writing good descriptions for agents (source: https://docs.ag2.ai/blog/2023-12-29-AgentDescriptions/index#tips-for-writing-good-descriptions)

Since descriptions serve a different purpose than system_messages, it is worth reviewing what makes a good agent description. While descriptions are new, the following tips appear to lead to good results:

    Avoid using the 1st or 2nd person perspective. Descriptions should not contain “I” or “You”, unless perhaps “You” is in reference to the GroupChat / orchestrator
    Include any details that might help the orchestrator know when to call upon the agent
    Keep descriptions short (e.g., “A helpful AI assistant with strong natural language and Python coding skills.”).

The main thing to remember is that the description is for the benefit of the GroupChatManager, not for the Agent’s own use or instruction.

"""
from autogen import ConversableAgent, register_function
from autogen.coding import LocalCommandLineCodeExecutor, DockerCommandLineCodeExecutor

from config import config
from tools import list_files_in_directory, parse_logs

def get_agents(config_list):
    agents = {}

    agents["user_proxy_agent"] = ConversableAgent(
        name="user_proxy_agent",
        system_message="A human admin.",
        description="A proxy for human input.",
        llm_config={"config_list": config_list},
        human_input_mode="TERMINATE",
    )

    agents["input_agent"] = ConversableAgent(
        name="input_agent",
        system_message="You receive input and decide what to do with it. You may receive strings of text, numbers, or other data types. It can also be a file, a directory, or a URL. You should decide which agent should process it. If the input is a directory, instruct a code writer agent to write code to list the files in the directory. If the input is a file, instruct a code writer agent to read the file and print its contents.",
        description="Receive input and decide what to do with it, and which agent is most suitable to process it. When there is uncertainty about what to do with some input, input_agent is responsible for deciding what is the most suitable agent to process it.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )

    agents["log_parser_agent"] = ConversableAgent(
        name="log_parser_agent",
        system_message="""
        You analyze logs and determine the appropriate parameters for the LogParserAgent.
        Your tasks are:
        1. Identify the log format from provided sample logs.
        2. Suggest regular expressions for preprocessing (e.g., masking IP addresses or other patterns).
        3. Provide any additional parameters needed for parsing, such as depth or similarity thresholds.
        4. Use the tool 'parse_logs' to parse logs based on the identified format.
        
        Log format should include placeholders for fields, e.g.:
        - '<Date> <Time> <Level>:<Content>'
        - '<Timestamp> <Component> <Message>'
        For regex, consider patterns such as:
        - r'(/|)([0-9]+\.){3}[0-9]+(:[0-9]+|)(:|)' (IP addresses)
        - r'UID-[0-9]+' (User IDs)
        """,
        description="Analyze samples of log data in order to determine the format and parameters to used for log parsing.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )
    
    executor = LocalCommandLineCodeExecutor(
        timeout=10,  # Timeout for each code execution in seconds.
        work_dir=config.WORK_DIR
    )
    # # Create a Docker command line code executor.
    # executor_docker = DockerCommandLineCodeExecutor(
    #     image="python:3.12-slim",  # Execute code using the given docker image name.
    #     timeout=10,  # Timeout for each code execution in seconds.
    #     work_dir=config.WORK_DIR,  # Use the temporary directory to store the code files.
    # )

    agents["code_executor_agent"] = ConversableAgent(
        name="code_executor_agent",
        description="I execute the code provided.",
        code_execution_config={"executor": executor},
        human_input_mode="NEVER",
        llm_config=False,
    )

    agents["data_reader_agent"] = ConversableAgent(
        name="data_reader_agent",
        system_message="You are an AI assistant that writes code to read data from a file or a URL. You should print the data in a summarized form. Large output and processed data should be saved to one or several files. If you write output to a file, always print the file path(s).",
        description="Write code to read data from a file or a URL and print the data in a summarized form.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )

    agents["code_writer_agent"] = ConversableAgent(
        name="code_writer_agent",
        system_message="Write code to perform any given task. Print the results in a summarized form, and save large output to one or several files. If you write output to file, always print the file path(s).",
        description="I write code to perform any given task. I will take care of general coding tasks.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )

    register_function(
        parse_logs,
        caller=agents["log_parser_agent"],
        executor=agents["code_executor_agent"],
        # executor=executor,  
        name="parse_logs",
        description="Parse logs using the LogParser library."
    )

    register_function(
        list_files_in_directory,
        caller=agents["data_reader_agent"],
        executor=agents["code_executor_agent"],
        # executor=executor,  
        name="parse_logs",
        description="Parse logs using the LogParser library."
    )

    return agents