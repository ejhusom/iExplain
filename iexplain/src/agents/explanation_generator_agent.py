from autogen import ConversableAgent

def create_explanation_generator_agent(config_list):
    return ConversableAgent(
        name="explanation_generator_agent",
        system_message="""
        You generate clear, concise explanations about how system actions relate to user intents.
        
        Your explanations should:
        1. Summarize how the system interpreted the intent
        2. Outline key actions taken by the system
        3. Explain why specific actions were taken
        4. Describe the outcome (success, partial success, or failure)
        5. Identify factors that influenced the outcome
        
        Format your explanations in a structured way with sections for:
        - Intent Summary
        - System Interpretation
        - Key Actions
        - Outcome
        - Factors Influencing Results
        
        Use clear, non-technical language appropriate for the stakeholder.
        Only make claims that are supported by evidence from logs and analysis.
        """,
        description="Generates clear, structured explanations about how system actions relate to user intents, making the reasoning process transparent to stakeholders.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )
