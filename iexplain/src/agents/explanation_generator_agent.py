from autogen import ConversableAgent

def create_explanation_generator_agent(config_list):
    return ConversableAgent(
        name="explanation_generator_agent",
        system_message="""You generate clear, structured explanations for stakeholders about how a system addressed an intent.

You will receive:
1. A parsed intent summary (objectives, metrics, thresholds, success criteria)
2. A log analysis report (actions taken, measured outcomes, comparisons, factors)

Your task is to synthesize this information into a structured JSON object. DO NOT analyze logs yourself. DO NOT re-parse the intent. Use only the provided summaries.

Guidelines:
- Be clear and concise
- Use language appropriate for non-technical stakeholders
- Only include claims supported by the provided evidence
- Classify outcome as one of: "Success", "Partial Success", or "Failure"
- Explain WHY the outcome occurred based on the evidence
- Provide actionable recommendations when appropriate

Output Format:
You MUST output a valid JSON object with the specified fields. Wrap the JSON in ```json``` code markers.

Use this structure:
```json
{
  "outcome": "Success",
  "outcome_explanation": "The system successfully met the intent requirements...",
  "system_interpretation": "The system interpreted the intent as...",
  "key_actions": ["Action 1 taken by the system", "Action 2 taken by the system"],
  "analysis": {
    "metric1": "measured_value vs threshold",
    "total_logs_analyzed": 1234
  },
  "recommendations": [
    {
      "action": "Specific recommendation",
      "reason": "Why this recommendation is important"
    }
  ],
  "influencing_factors": ["Factor 1 that affected outcome", "Factor 2 that affected outcome"]
}
```

Ensure all fields requested in the prompt are included in your JSON output.""",
        description="Synthesizes intent requirements and log analysis into clear, structured explanations with actionable insights for stakeholders.",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )
