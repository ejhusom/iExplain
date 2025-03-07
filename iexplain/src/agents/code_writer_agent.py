from autogen import ConversableAgent

def create_code_writer_agent(config_list):
    return ConversableAgent(
        name="code_writer_agent",
        system_message="Write code to perform any given task. Print the results in a summarized form, and save large output to one or several files. If you write output to file, always print the file path(s).",
        description="I write code to perform any given task. I will take care of general coding tasks.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )
