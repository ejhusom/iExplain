# src/tools/parse_tmf_intent.py
import re
from typing import Dict, Any, List

caller = "intent_parser_agent"
executor = "code_executor_agent"

def parse_tmf_intent(turtle_string: str) -> Dict[str, Any]:
    """
    High-level parser for TMF-formatted intents that extracts all descriptions
    and their associated types.
    
    Args:
        turtle_string (str): The TMF intent as a Turtle RDF string
        
    Returns:
        Dict[str, Any]: A representation of the intent with all descriptions
    """
    # Check for empty input
    if not turtle_string or turtle_string.strip() == "":
        return {
            "error": "Failed to parse intent: Empty input",
            "raw_intent": ""
        }
    
    try:
        # Initialize the result structure
        intent = {
            "descriptions": [],
            "raw_intent": turtle_string
        }
        
        # Split into lines for line-by-line processing
        lines = turtle_string.strip().split('\n')
        
        # Track current subject and its type
        current_subject = None
        subject_types = {}
        
        # Process each line
        for line in lines:
            line = line.strip()
            if not line or line.startswith('@prefix') or line.startswith('#'):
                continue
                
            # Check for subject type declarations
            type_match = re.search(r'(\w+:[^\s]+)\s+a\s+(\w+:[^\s]+)', line)
            if type_match:
                subject = type_match.group(1)
                type_name = type_match.group(2)
                subject_types[subject] = type_name
                current_subject = subject
                
            # Check for description predicates
            desc_match = re.search(r'dct:description\s+"([^"]+)"@en', line)
            if desc_match and current_subject:
                description = desc_match.group(1)
                
                # Get type for this subject
                subject_type = subject_types.get(current_subject, "Unknown")
                
                # Extract simple type name
                type_parts = subject_type.split(':')
                simple_type = type_parts[-1] if len(type_parts) > 1 else subject_type
                
                # Add to descriptions list
                intent["descriptions"].append({
                    "subject": current_subject,
                    "type": simple_type,
                    "description": description
                })
                
            # Check if we need to reset the current subject (end of triples for this subject)
            if line.endswith('.'):
                current_subject = None
        
        # Create a simple summary
        if intent["descriptions"]:
            # Try to find Intent or DeliveryExpectation description first
            main_desc = None
            for desc in intent["descriptions"]:
                if desc["type"] in ["Intent", "DeliveryExpectation"]:
                    main_desc = desc
                    break
            
            # If not found, use the first description
            if not main_desc and intent["descriptions"]:
                main_desc = intent["descriptions"][0]
                
            if main_desc:
                intent["summary"] = f"{main_desc['type']}: {main_desc['description']}"
            else:
                intent["summary"] = "Intent with no descriptions found"
        else:
            intent["summary"] = "Intent with no descriptions found"
        
        return intent
    
    except Exception as e:
        return {
            "error": f"Failed to parse intent: {str(e)}",
            "raw_intent": turtle_string
        }