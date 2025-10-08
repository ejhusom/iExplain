from autogen import ConversableAgent

def create_intent_parser_agent(config_list):
    return ConversableAgent(
        name="intent_parser_agent",
        system_message="""You are an expert at parsing TMF Intent Ontology (v3.6.0) expressed in Turtle RDF format.

Your ONLY task is to extract structured information from the intent. DO NOT analyze logs. DO NOT generate explanations.

For Turtle RDF format intents (TM Forum Intent Ontology v3.6.0), extract:
- Intent ID (e.g., iexp:I1)
- Intent description and primary objective
- Delivery Expectations with specific conditions and thresholds
- Reporting Expectations
- Context information (geographic regions, time constraints, resource constraints)
- Condition parameters with specific values (latency thresholds, bandwidth requirements, etc.)

For natural language intents (if provided), identify:
- Primary objective (what the user wants to achieve)
- Key metrics with targets (e.g., "latency < 100ms", "bandwidth > 1Gbps")
- Geographic or temporal context
- Any constraints or special requirements

Output a structured summary in this format:
- Primary Objective: [clear statement of what the user wants]
- Key Metrics: [list each metric with its threshold or target value]
- Context: [regions, time constraints, or other relevant context]
- Success Criteria: [specific conditions that indicate the intent is fulfilled]

Be precise and extract actual values from the intent. Only state what is explicitly defined in the intent.""",
        description="Parses TMF Intent Ontology (Turtle RDF) and natural language intents into structured requirements with specific metrics and thresholds.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )