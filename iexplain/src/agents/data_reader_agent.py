
from autogen import ConversableAgent

def create_data_reader_agent(config_list):
    return ConversableAgent(
        name="data_reader_agent",
        system_message="You are an AI assistant that writes code to read data from a file or a URL. You should print the data in a summarized form. Large output and processed data should be saved to one or several files. If you write output to a file, always print the file path(s).",
        description="Write code to read data from a file or a URL and print the data in a summarized form.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )
