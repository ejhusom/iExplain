import json

def parse_escaped_json(text):
    # Unescape the string (convert \\n to \n, etc.)
    unescaped = text.encode().decode('unicode_escape')
    
    # Remove surrounding quotes if present
    if unescaped.startswith("'") and unescaped.endswith("'"):
        unescaped = unescaped[1:-1]
    
    # Parse the JSON
    return json.loads(unescaped)