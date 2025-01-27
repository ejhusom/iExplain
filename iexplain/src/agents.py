from autogen import ConversableAgent, register_function
from autogen.coding import LocalCommandLineCodeExecutor, DockerCommandLineCodeExecutor

from config import config
from tools import parse_logs

def get_agents(config_list):
    agents = {}

    agents["user_proxy_agent"] = ConversableAgent(
        name="user_proxy_agent",
        system_message="A human admin.",
        description="I act as a proxy for human input.",
        llm_config={"config_list": config_list},
        human_input_mode="TERMINATE",
    )

    agents["input_agent"] = ConversableAgent(
        name="input_agent",
        system_message="You receive input and decide what to do with it. You may receive strings of text, numbers, or other data types. It can also be a file, a directory, or a URL. You should decide which agent should process it. If the input is a directory, instruct a code writer agent to write code to list the files in the directory. If the input is a file, instruct a code writer agent to read the file and print its contents.",
        description="I receive input and decide what to do with it, and which agent is most suitable to process it. When unsure about what to do with some input, I am responsible for deciding which agent should process it.",
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
        description="I analyze samples of log data in order to determine the format and parameters to used for log parsing.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )
    # agents["log_parser"].register_for_llm(name="parse_logs", description="Parse logs using the LogParser library.")(parse_logs)
    
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
        description="I write code to read data from a file or a URL and print the data in a summarized form.",
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

    # V1 and V2 agents
    agents["MetadataParserAgent"] = ConversableAgent(
        name="MetadataParserAgent",
        system_message="Collect and summarize metadata from the system.",
        description="I collect and summarize metadata from the system.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )

    agents["LogAnalyzerAgent"] = ConversableAgent(
        name="LogAnalyzerAgent",
        system_message="""
        You analyze system logs to identify patterns and relationships. Your tasks:
        1. Identify the structure and format of the logs
        2. Group related events based on available identifiers (timestamps, IDs, etc.)
        3. Detect sequences of related events
        4. Identify critical or anomalous patterns
        
        For any log format, focus on:
        - Temporal patterns (when events occur)
        - Entity relationships (which components/systems are involved)
        - Event severity and types
        - Error propagation patterns
        """,
        description="I analyze raw log data to extract meaningful patterns and event sequences.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )

    agents["ContextProviderAgent"] = ConversableAgent(
        name="ContextProviderAgent",
        system_message="""
        You provide system and operational context for log events. Your tasks:
        1. Interpret error messages and system events
        2. Explain relationships between different system components
        3. Assess potential impacts of observed patterns
        4. Distinguish between normal operations and potential issues
        
        Consider:
        - The type of system generating the logs
        - Common patterns in such systems
        - Potential implications of different event types
        - Relationships between different components
        """,
        description="I provide technical and operational context for system events.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )

    agents["ExplanationAgent"] = ConversableAgent(
        name="ExplanationAgent",
        system_message="""
        Generate clear, structured explanations of system events at multiple levels:
        1. Technical Details: What exactly happened in the system
        2. System Impact: How these events affect system operation
        3. Operational Context: What this means for system management
        4. Recommendations: Suggested actions or monitoring needs
        
        Create explanations that:
        - Connect related events into coherent narratives
        - Highlight important patterns and their implications
        - Scale detail based on the audience (technical vs operational)
        - Provide actionable insights
        """,
        description="I create multi-level explanations of system events.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )

    agents["EvaluatorAgent"] = ConversableAgent(
        name="EvaluatorAgent",
        system_message="Evaluate the quality of explanations based on relevance, correctness, and clarity. Score each explanation from 1 to 5.",
        description="I evaluate the quality of explanations based on relevance, correctness, and clarity.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )

    agents["ModeratorAgent"] = ConversableAgent(
        name="ModeratorAgent",
        system_message="""
        You are an AI-based moderator that makes plans for the whole group. When you get a task, break it down into sub-tasks, each to be performed by one of your 'partner agents'. You will get an introduction about what each of your partner agents can do. If you speak in the middle of two tasks, remember to repeat the key information you get from the previous speaker, so that the next speaker has sufficient context. You will also serve as the interface to the human proxy.
        """,
        description="I am an AI-based moderator that makes plans for the whole group and serves as the interface to the human proxy.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )

    agents["HumanProxyAgent"] = ConversableAgent(
        name="HumanProxyAgent",
        system_message="You are responsible for facilitating user interaction by presenting summaries and passing user questions to the most suitable agent.",
        description="I facilitate user interaction by presenting summaries and passing user questions to the most suitable agent.",
        llm_config={"config_list": config_list},
        human_input_mode="ALWAYS",
    )

    agents["UserProxyAgent"] = ConversableAgent(
        name="UserProxyAgent",
        system_message="A human admin.",
        description="I act as a proxy for human input.",
        llm_config={"config_list": config_list},
        human_input_mode="TERMINATE",
    )

    agents["InputAgent"] = ConversableAgent(
        name="InputAgent",
        system_message="You receive input and decide what to do with it.",
        description="I receive input and decide which agent should process it.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )

    agents["AnalyzerAgent"] = ConversableAgent(
        name="AnalyzerAgent",
        system_message="Write code to analyze input data. Print the results in a summarized form, using the print statement.",
        description="I write code to analyze and summarize the input data.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )

    agents["CoderAgent"] = ConversableAgent(
        name="CoderAgent",
        system_message="Write code to perform any given task, and print the results in a summarized form.",
        description="I write code to analyze input data.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )

    agents["CodeExecutorAgent"] = ConversableAgent(
        name="CodeExecutorAgent",
        system_message="Execute the code provided.",
        description="I execute the code provided.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )

    agents["CriticAgent"] = ConversableAgent(
        name="CriticAgent",
        system_message="""
        Critic. You are a helpful assistant highly skilled in evaluating the quality of a given visualization code by providing a score from 1 (bad) - 10 (good) while providing clear rationale. YOU MUST CONSIDER VISUALIZATION BEST PRACTICES for each evaluation. Specifically, you can carefully evaluate the code across the following dimensions
        - bugs (bugs):  are there bugs, logic errors, syntax error or typos? Are there any reasons why the code may fail to compile? How should it be fixed? If ANY bug exists, the bug score MUST be less than 5.
        - Data transformation (transformation): Is the data transformed appropriately for the visualization type? E.g., is the dataset appropriated filtered, aggregated, or grouped  if needed? If a date field is used, is the date field first converted to a date object etc?
        - Goal compliance (compliance): how well the code meets the specified visualization goals?
        - Visualization type (type): CONSIDERING BEST PRACTICES, is the visualization type appropriate for the data and intent? Is there a visualization type that would be more effective in conveying insights? If a different visualization type is more appropriate, the score MUST BE LESS THAN 5.
        - Data encoding (encoding): Is the data encoded appropriately for the visualization type?
        - aesthetics (aesthetics): Are the aesthetics of the visualization appropriate for the visualization type and the data?

        YOU MUST PROVIDE A SCORE for each of the above dimensions.
        {bugs: 0, transformation: 0, compliance: 0, type: 0, encoding: 0, aesthetics: 0}
        Do not suggest code.
        Finally, based on the critique above, suggest a concrete list of actions that the coder should take to improve the code.
        """,
        description="I evaluate the quality of the code and provide a score and rationale.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )

    agents["RetrieveUserProxyAgent"] = ConversableAgent(
        name="RetrieveUserProxyAgent",
        system_message="Retrieve user input and act as a proxy.",
        description="I retrieve user input and act as a proxy.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )

    return agents

