from autogen import ConversableAgent

def create_log_analysis_agent(config_list):
    return ConversableAgent(
        name="log_analysis_agent",
        system_message="""
        You analyze parsed log data to identify patterns, anomalies, and events relevant to a user's intent.
        
        Your tasks include:
        1. Identify log entries related to the intent's objectives and metrics
        2. Detect patterns or sequences of events that indicate intent fulfillment or failure
        3. Identify system state changes that might affect the intent
        4. Recognize relationships between different log entries
        5. Summarize the key findings from the logs that relate to the intent
        
        Always provide evidence from the logs to support your analysis.
        """,
        description="Analyzes parsed log data to identify events, patterns, and anomalies relevant to user intents.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )
