import json
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

from config import config

def load_config_for_display():
    """Load config for displaying in dashboard."""

    # Prepare all sections for display, sorted by priority
    sections = []

    # Sort fields by priority
    for field_name, field_config in sorted(
        config.EXPLANATION_CONFIG.items(),
        key=lambda x: x[1]['display_priority']
    ):
        section = {
            'key': field_name,
            'title': field_config['title'],
            'type': field_config['display_type'],
            'item_type': field_config.get('item_type', 'simple')
        }
        sections.append(section)

    return sections

def parse_escaped_json(text):
    # Unescape the string (convert \\n to \n, etc.)
    unescaped = text.encode().decode('unicode_escape')
    
    # Remove surrounding quotes if present
    if unescaped.startswith("'") and unescaped.endswith("'"):
        unescaped = unescaped[1:-1]
    
    # Parse the JSON
    return json.loads(unescaped)

def extract_intent_metadata_from_file(intent_file_path: Path) -> Dict[str, str]:
    """
    Extract intent metadata (ID, description) from a structured intent file.
    Currently supports Turtle (.ttl) format, with extensibility for other formats.
    
    Args:
        intent_file_path: Path to the intent file
        
    Returns:
        Dict containing 'id', 'description', and 'format' of the intent
    """
    metadata = {
        'id': 'Unknown',
        'description': 'Unknown intent',
        'created_date': 'Unknown',
        'format': 'unknown'
    }
    
    # Return empty metadata if file doesn't exist
    if not intent_file_path.exists():
        return metadata
    
    file_format = intent_file_path.suffix.lower()
    
    try:
        with open(intent_file_path, 'r') as f:
            content = f.read()
            
        if file_format == '.ttl':
            metadata['format'] = 'turtle'
            metadata.update(_extract_metadata_from_turtle(content))
        # Future formats can be added here with elif statements
        # elif file_format == '.json':
        #     metadata['format'] = 'json'
        #     metadata.update(_extract_metadata_from_json(content))
    except Exception as e:
        print(f"Error extracting metadata from {intent_file_path}: {e}")
    
    return metadata

def _extract_metadata_from_turtle(content: str) -> Dict[str, str]:
    """Extract metadata from Turtle format content"""
    metadata = {}
    
    # Extract the ID - match any prefix
    # Look for any prefix followed by a colon, then the ID, then "a icm:Intent"
    id_match = re.search(r'(\w+):([A-Za-z0-9_-]+)\s+a\s+icm:Intent\b', content)
    if id_match:
        prefix = id_match.group(1)  # The prefix (like "iexp")
        id_value = id_match.group(2)  # The actual ID value (like "I2")
        metadata['id'] = id_value
        metadata['prefix'] = prefix  # Store prefix for potential future use
    
    # Extract the description - match the same entity that was identified as Intent
    # This looks for the description that follows the Intent declaration
    if id_match:
        full_id = f"{prefix}:{id_value}"
        desc_pattern = rf'{re.escape(full_id)}\s+a\s+icm:Intent[^;]*;\s+dct:description\s+"([^"]+)"@en'
        desc_match = re.search(desc_pattern, content)
        if desc_match:
            metadata['description'] = desc_match.group(1)
    
    return metadata
