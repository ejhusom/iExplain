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
# current_dir = Path(__file__).parent
# sys.path.append(str(current_dir))

# Import the minimal iExplain framework with agents
from config import config
from explainer import explainer

app = Flask(__name__)

# Helper functions
def get_available_intents():
    """Get a list of available intent folders with metadata"""
    intents = []
    
    # Get metadata if available
    metadata = {}
    metadata_file = config.INTENTS_PATH / "intent_metadata.json"
    if metadata_file.exists():
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
        except Exception as e:
            print(f"Error loading intent metadata: {e}")
    
    # List all subdirectories in the intents directory
    for item in os.listdir(config.INTENTS_PATH):
        # Skip regular files and the metadata file
        if item == "intent_metadata.json" or not os.path.isdir(config.INTENTS_PATH / item):
            continue
        
        intent_dir = config.INTENTS_PATH / item
        ttl_file = intent_dir / f"{item}.ttl"
        nl_file = intent_dir / f"{item}.txt"
        
        # Skip if TTL file doesn't exist
        if not ttl_file.exists():
            continue
        
        # Get natural language content if available
        nl_intent = ""
        if nl_file.exists():
            try:
                with open(nl_file, 'r') as f:
                    nl_intent = f.read()
            except Exception as e:
                print(f"Error reading natural language intent: {e}")

        if ttl_file.exists():
            try:
                with open(ttl_file, 'r') as f:
                    structured_intent = f.read()
            except Exception as e:
                print(f"Error reading TTL file: {e}")
        
        # Get metadata for this intent if available
        description = item
        created_date = "Unknown"
        intent_id = "Unknown"
        
        if item in metadata:
            description = metadata[item].get('description', description)
            created_date = metadata[item].get('created_date', created_date)
            intent_id = metadata[item].get('id', intent_id)
        
        intents.append({
            'folder': item,
            'description': description,
            'created_date': created_date,
            'id': intent_id,
            'natural_language': nl_intent,
            'structured': structured_intent
        })
    
    return intents

def get_available_logs():
    """Get a list of available log files, including those in subdirectories"""
    log_files = []
    for root, _, files in os.walk(config.LOGS_PATH):
        for f in files:
            if f.endswith('.log'):
                log_files.append(os.path.relpath(os.path.join(root, f), config.LOGS_PATH))
    return log_files

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
    intent_folder = request.form.get('intent')
    log_files = request.form.getlist('logs')
    
    if not intent_folder or not log_files:
        return jsonify({'error': 'Please select an intent and at least one log file'}), 400
    
    try:
        # Use the minimal agent-based explainer
        explanation, output_file = explainer.explain(intent_folder, log_files)
        return render_template('explanation.html', explanation=explanation, output_file=output_file)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Error generating explanation: {str(e)}'}), 500

@app.route('/api/explanations', methods=['GET'])
def list_explanations():
    """API endpoint to list all saved explanations"""
    explanations = []
    for f in os.listdir(config.OUTPUT_PATH):
        if f.startswith('explanation_') and f.endswith('.json'):
            file_path = config.OUTPUT_PATH / f
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
    for dir_path in [config.DATA_PATH, config.INTENTS_PATH, config.LOGS_PATH, config.OUTPUT_PATH]:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # Start the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)