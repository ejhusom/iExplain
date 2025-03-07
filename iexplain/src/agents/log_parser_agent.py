
from autogen import ConversableAgent

def create_log_parser_agent(config_list):
    return ConversableAgent(
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
