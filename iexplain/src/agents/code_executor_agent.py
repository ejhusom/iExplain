
from autogen import ConversableAgent
from autogen.coding import LocalCommandLineCodeExecutor
from config import config

def create_code_executor_agent(config_list):
    executor = LocalCommandLineCodeExecutor(
        timeout=10,  # Timeout for each code execution in seconds.
        work_dir=config.WORK_DIR
    )

    return ConversableAgent(
        name="code_executor_agent",
        description="I execute the code provided.",
        code_execution_config={"executor": executor},
        human_input_mode="NEVER",
        llm_config=False,
    )
