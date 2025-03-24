from autogen import ConversableAgent

def create_intent_parser_agent(config_list):
    return ConversableAgent(
        name="intent_parser_agent",
        system_message="""
        You parse and analyze user intents in both Turtle RDF format and natural language.
        
        For Turtle RDF format intents (TM Forum Intent Ontology v3.6.0), extract:
        - Intent ID (e.g., intendproject:I1)
        - Delivery Expectations (descriptions, targets, conditions)
        - Reporting Expectations
        - Context information (including geographic regions)
        - Condition parameters (latency, bandwidth, etc.)
        
        For natural language intents, identify:
        - Primary objective (what the user wants to achieve)
        - Key metrics (latency, bandwidth, compute latency)
        - Geographic/contextual information
        - Constraints (time, resources, etc.)
        
        Convert all intents into a standardized structured format for other agents to use.
        Always list the key components of the intent in your response.
        """,
        description="Analyzes and structures user intents, parsing Turtle RDF format intents (TM Forum Intent Ontology) or natural language into a structured representation.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )