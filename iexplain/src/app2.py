#!/usr/bin/env python3
"""
iExplain Web Application - Simplified Version
A simple web interface using a minimal set of agents
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
import json
from pathlib import Path
import sys
from datetime import datetime

# Add the src directory to the path
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

# Import the minimal iExplain framework with agents
from mains import explainer

app = Flask(__name__)

# Configuration
DATA_DIR = Path("data")
INTENT_DIR = DATA_DIR / "intents"
LOGS_DIR = DATA_DIR / "logs" / "openstack"
OUTPUT_DIR = Path("output")

# Ensure directories exist
for dir_path in [DATA_DIR, INTENT_DIR, LOGS_DIR, OUTPUT_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Helper functions
def get_available_intents():
    """Get a list of available intent files with metadata"""
    intents = []
    mapping_file = INTENT_DIR / "intent_mapping.json"
    
    if mapping_file.exists():
        try:
            with open(mapping_file, 'r') as f:
                mapping = json.load(f)
                
            for ttl_file, metadata in mapping.items():
                intent_path = INTENT_DIR / ttl_file
                nl_path = INTENT_DIR / metadata.get('natural_language_file', '')
                
                # Skip if TTL file doesn't exist
                if not intent_path.exists():
                    continue
                
                # Get natural language content if available
                nl_content = ""
                if nl_path.exists():
                    with open(nl_path, 'r') as f:
                        nl_content = f.read()
                
                intents.append({
                    'ttl_file': ttl_file,
                    'description': metadata.get('description', 'Unknown'),
                    'created_date': metadata.get('created_date', 'Unknown'),
                    'id': metadata.get('id', 'Unknown'),
                    'natural_language': nl_content
                })
        except Exception as e:
            print(f"Error loading intent mapping: {e}")
    
    # If no mapping file or error, fall back to listing .ttl files
    if not intents:
        intents = [{'ttl_file': f, 'description': f, 'created_date': 'Unknown', 'id': 'Unknown', 'natural_language': ''}
                  for f in os.listdir(INTENT_DIR) if f.endswith('.ttl')]
    
    return intents

def get_available_logs():
    """Get a list of available log files"""
    return [f for f in os.listdir(LOGS_DIR) if f.endswith('.log')]

# Routes
@app.route('/')
def index():
    """Home page with a list of available intents and logs"""
    intents = get_available_intents()
    logs = get_available_logs()
    return render_template('index.html', intents=intents, logs=logs)

@app.route('/explain', methods=['POST'])
def explain():
    """Process the selected intent and logs to generate an explanation"""
    intent_file = request.form.get('intent')
    log_files = request.form.getlist('logs')
    
    if not intent_file or not log_files:
        return jsonify({'error': 'Please select an intent and at least one log file'}), 400
    
    try:
        # Use the minimal agent-based explainer
        explanation, output_file = explainer.explain(intent_file, log_files)
        return render_template('explanation.html', explanation=explanation, output_file=output_file)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error generating explanation: {str(e)}'}), 500

@app.route('/api/explanations', methods=['GET'])
def list_explanations():
    """API endpoint to list all saved explanations"""
    explanations = []
    for f in os.listdir(OUTPUT_DIR):
        if f.startswith('explanation_') and f.endswith('.json'):
            file_path = OUTPUT_DIR / f
            with open(file_path, 'r') as file:
                try:
                    data = json.load(file)
                    explanations.append({
                        'file': f,
                        'timestamp': data.get('timestamp', 'Unknown'),
                        'intent': data.get('intent', {}).get('description', 'Unknown intent'),
                        'outcome': data.get('outcome', 'Unknown')
                    })
                except:
                    pass
    
    return jsonify(explanations)

if __name__ == '__main__':
    # Ensure the necessary directories exist
    for dir_path in [DATA_DIR, INTENT_DIR, LOGS_DIR, OUTPUT_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # Start the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)