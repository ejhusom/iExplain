#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""iExplain - Minimal Viable Service using a few key agents

A simplified version of the iExplain framework using just a few core agents.
"""
import os
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any

from autogen import GroupChat, GroupChatManager

# Import from existing code
sys.path.append(str(Path(__file__).parent))
from config import config
from get_agents import get_agents
from utils import parse_escaped_json, extract_intent_metadata_from_file

class iExplain:
    """
    A minimal implementation of the iExplain framework using just a few agents.
    """
    
    def __init__(self):
        """Initialize the minimal explainer with agents."""
        
        # Initialize agents - for the MVS, we just use 3 key agents
        self.config_list = config.config_list
        self.agents = get_agents(self.config_list)
        
    def explain(self, intent_folder: str, log_files: List[str]) -> Tuple[Dict[str, Any], str]:
        """
        Generate an explanation for an intent based on log files using agents.
        
        Args:
            intent_folder (str): Name of the intent folder
            log_files (List[str]): List of log file paths
            
        Returns:
            Tuple[Dict[str, Any], str]: Explanation results and output file path
        """
        # Construct paths to the intent files
        intent_dir = config.INTENTS_PATH / intent_folder
        ttl_file = intent_dir / f"{intent_folder}.ttl"
        nl_file = intent_dir / f"{intent_folder}.txt"
        metadata_file = intent_dir / "metadata.json"
        
        # Check if files exist
        if not ttl_file.exists():
            raise FileNotFoundError(f"TTL file not found: {ttl_file}")
        
        # Read the TTL intent file
        with open(ttl_file, 'r') as f:
            structured_intent = f.read()
        
        # Read natural language intent if available
        nl_intent = ""
        if nl_file.exists():
            try:
                with open(nl_file, 'r') as f:
                    nl_intent = f.read()
            except Exception as e:
                print(f"Error reading natural language intent: {e}")

         # Extract metadata from TTL file
        metadata = extract_intent_metadata_from_file(ttl_file)
        intent_description = metadata['description']
        intent_id = metadata['id']
        
        # Create the full log file paths
        log_file_paths = [str(config.LOGS_PATH / log_file) for log_file in log_files]
        
        # Create the groupchat with agents
        groupchat = GroupChat(
            agents=[
                self.agents["user_proxy_agent"],
                self.agents["intent_parser_agent"],
                self.agents["log_analysis_agent"],
                self.agents["explanation_generator_agent"]
            ],
            messages=[],
            max_round=2,  # Keep it simple with fewer rounds
            send_introductions=True
        )
        
        manager = GroupChatManager(
            groupchat=groupchat,
            llm_config={"config_list": self.config_list}
        )

        # Use the config to create the fields list for the prompt
        expected_fields = []
        for field_name, field_config in config.EXPLANATION_CONFIG.items():
            expected_fields.append(f"- {field_name}: {field_config['description']}")

        # Build the prompt with expected fields
        field_list = "\n".join(expected_fields)
        
        # Create a prompt for the agents
        prompt = f"""
I need to explain how a system has addressed a user's intent.

The intent is specified in TMF format (file format: {metadata['format']}):
```
{structured_intent}
```

{f"The original natural language intent was: '{nl_intent}'" if nl_intent else ""}

I need to analyze the following log files to determine if the intent was fulfilled:
{', '.join(log_file_paths)}

Please follow this simple process:
1. Parse the intent to understand what the user wants
2. Analyze the logs to see if the intent was met
3. Generate a structured explanation with:
{field_list}

Structure the explanation as a JSON with all these fields.

Keep the analysis focused on determining if the intent was fulfilled based on the logs.
"""
        
        # Start the conversation
        result = self.agents["user_proxy_agent"].initiate_chat(
            manager,
            message=prompt
        )

        # Extract the full conversation history
        conversation_log = result.chat_history
        
        # Extract the explanation from the conversation
        explanation = self._extract_explanation_from_result(result, nl_intent, structured_intent, intent_id, intent_description)

        # Add session metadata before agent_conversation
        explanation['session_metadata'] = self._get_session_metadata()
        explanation['agent_conversation'] = conversation_log
        
        # Save the explanation to a file
        output_file = self._save_explanation_to_file(explanation)
        
        return explanation, output_file

    def _get_session_metadata(self):
        # Get LLM config (service/model)
        llm_cfg = self.config_list[0]
        llm_config = {
            "service": llm_cfg.get("api_type", ""),
            "model": llm_cfg.get("model", "")
        }

        # Get agent details (name/system_message)
        agents_info = []
        for name, agent in self.agents.items():
            # Try to get system_message, fallback to None
            sys_msg = getattr(agent, "system_message", None)
            agents_info.append({
                "name": name,
                "system_message": sys_msg
            })

        return {
            "llm_config": llm_config,
            "agents": agents_info
        }
    
    def _extract_explanation_from_result(self, result, nl_intent: str, structured_intent: str, intent_id: str, intent_description: str) -> Dict[str, Any]:
        """
        Extract the structured explanation from the agent conversation result.
        
        This function looks for JSON content in the conversation and parses it.
        If no valid JSON is found, it creates a basic explanation structure.
        """
        
        # Look for JSON in the conversation (between ```json and ```)
        json_pattern = r'```json\s*([\s\S]*?)\s*```'
        json_matches = re.findall(json_pattern, str(result))
        
        if json_matches:
            print("Found JSON content in the result")
            # Try to parse the JSON
            try:
                explanation = parse_escaped_json(json_matches[0])
                # Add natural language intent if available
                explanation['natural_language_intent'] = nl_intent
                explanation['structured_intent'] = structured_intent
                
                # Add or update basic intent info
                explanation.setdefault('intent', {})
                if explanation['intent'].get('id') != intent_id:
                    print(f"Warning: Agent-generated intent ID '{explanation['intent'].get('id')}' does not match expected ID '{intent_id}'")
                explanation['intent']['id'] = intent_id
                
                if explanation['intent'].get('description') != intent_description:
                    print(f"Warning: Agent-generated intent description '{explanation['intent'].get('description')}' does not match expected description '{intent_description}'")
                explanation['intent']['description'] = intent_description
                
                # Set the timestamp to the current time and date
                explanation['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                return explanation
            except json.JSONDecodeError:
                print(f"Error decoding JSON from result: {json_matches[0]}")
        
        # If no valid JSON found, look for explanation content in a more flexible way
        messages = result.chat_history[::-1]
        
        # Default explanation structure
        explanation = {
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'natural_language_intent': nl_intent,
            'structured_intent': structured_intent,
            'intent': {
                'id': intent_id,
                'description': intent_description
            },
            'analysis': {
                'total_logs_analyzed': 0
            },
            'recommendations': [
                {
                    'action': 'Improve system monitoring',
                    'reason': 'Could not determine specific recommendations from logs'
                }
            ],
            'outcome': 'Unknown',
            'outcome_explanation': 'Could not determine outcome from logs',
            'influencing_factors': ['Log analysis incomplete']
        }
        
        # Find explanation content in messages from explanation_generator_agent
        for msg in messages:
            if msg.get('role') == 'assistant' and 'explanation_generator_agent' in msg.get('name', ''):
                content = msg.get('content', '')
                
                # Try to extract intent description
                intent_desc_match = re.search(r'Intent Summary[:\s]+(.*?)(?:\n|$)', content, re.IGNORECASE)
                if intent_desc_match:
                    explanation['intent']['description'] = intent_desc_match.group(1).strip()
                
                # Try to extract outcome
                outcome_match = re.search(r'Outcome[:\s]+(Success|Partial Success|Failure)', content, re.IGNORECASE)
                if outcome_match:
                    explanation['outcome'] = outcome_match.group(1).strip()

                # Try to extract outcome explanation
                outcome_explanation_match = re.search(r'Outcome Explanation[:\s]+(.*?)(?:\n\n|$)', content, re.DOTALL)
                if outcome_explanation_match:
                    explanation['outcome_explanation'] = outcome_explanation_match.group(1).strip()
                
                # Try to extract recommendations
                recommendations = []
                rec_matches = re.findall(r'- (.+?)(?::|:)\s+(.+?)(?:\n|$)', content)
                for action, reason in rec_matches:
                    recommendations.append({
                        'action': action.strip(),
                        'reason': reason.strip()
                    })
                
                if recommendations:
                    explanation['recommendations'] = recommendations
                
                # Try to extract influencing factors
                factors = []
                factor_section = re.search(r'(?:Factors|Influencing Factors)[:\s]+(.*?)(?:\n\n|$)', content, re.DOTALL)
                if factor_section:
                    factor_list = re.findall(r'- (.+?)(?:\n|$)', factor_section.group(1))
                    factors = [factor.strip() for factor in factor_list if factor.strip()]
                
                if factors:
                    explanation['influencing_factors'] = factors
        
        return explanation
    
    def _save_explanation_to_file(self, explanation: Dict[str, Any]) -> str:
        """Save the explanation to a JSON file and return the file path."""

        # Use timestamp from explanation or generate a new one
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        timestamp_str = timestamp.replace(' ', '_').replace(':', '-')
        
        # Create the output file path
        output_file = config.OUTPUT_PATH / f"explanation_{timestamp_str}.json"
        
        # Save the explanation to the file
        with open(output_file, 'w') as f:
            json.dump(explanation, f, indent=4)
        
        return str(output_file)

# Create a singleton instance for use by app.py
explainer = iExplain()

# For testing the explainer directly
if __name__ == "__main__":
    # Test with sample data
    intent_folder = "nova_api_latency_intent"
    log_files = ["openstack/nova-api.log"]
    
    explanation, output_file = explainer.explain(intent_folder, log_files)
    print(f"Explanation generated and saved to {output_file}")
    print(json.dumps(explanation, indent=2))
