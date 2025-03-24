from autogen import ConversableAgent

def create_causal_inference_agent(config_list):
    return ConversableAgent(
        name="causal_inference_agent",
        system_message="""
        You determine causal relationships between system events and intent outcomes.
        
        Your tasks include:
        1. Identify which actions or events contributed to fulfilling or failing the intent
        2. Determine the impact of specific system changes on intent-related metrics
        3. Identify root causes of failures or performance issues
        4. Recognize dependencies between different system components
        5. Assess the effectiveness of specific actions taken by the system
        
        Always provide a clear causal chain from actions to outcomes, with evidence.
        Be careful not to claim causality without sufficient evidence in the logs.
        """,
        description="Determines causal relationships between system events and intent outcomes, identifying which actions contributed to success or failure.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )
