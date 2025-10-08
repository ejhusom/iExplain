#!/usr/bin/env python3
"""
iExplain Web Application
A web interface for selecting intents and logs to generate explanations.
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
import json
from pathlib import Path
import sys
from datetime import datetime

from config import config
from explainer import explainer
from utils import extract_intent_metadata_from_file, load_config_for_display

app = Flask(__name__)

# Helper functions
def get_available_intents():
    """Get a list of available intent folders with metadata"""
    intents = []
    
    # List all subdirectories in the intents directory
    for item in os.listdir(config.INTENTS_PATH):
        
        intent_dir = config.INTENTS_PATH / item
        ttl_file = intent_dir / f"{item}.ttl"
        nl_file = intent_dir / f"{item}.txt"
        metadata_file = intent_dir / "metadata.json"
        
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
        
        # Extract metadata directly from the TTL file
        metadata = extract_intent_metadata_from_file(ttl_file)
        
        intents.append({
            'folder': item,
            'description': metadata['description'],
            'created_date': metadata['created_date'],
            'id': metadata['id'],
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
        explanation, output_file = explainer.explain(intent_folder, log_files)
        sections = load_config_for_display()
        return render_template(
                'explanation.html', 
                explanation=explanation, 
                output_file=output_file,
                all_sections=sections,
                config=config,
        )
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

@app.route('/explanations')
def explanations_list():
    """Show a list of all generated explanations"""
    explanations = []
    
    # Get all explanation files
    for f in os.listdir(config.OUTPUT_PATH):
        if f.startswith('explanation_') and f.endswith('.json'):
            file_path = config.OUTPUT_PATH / f
            try:
                with open(file_path, 'r') as file:
                    data = json.load(file)
                    explanations.append({
                        'id': f.replace('explanation_', '').replace('.json', ''),
                        'file': f,
                        'timestamp': data.get('timestamp', 'Unknown'),
                        'intent': data.get('intent', {}).get('description', 'Unknown intent'),
                        'outcome': data.get('outcome', 'Unknown')
                    })
            except Exception as e:
                print(f"Error reading explanation file {f}: {e}")
    
    # Sort by timestamp descending (newest first)
    explanations.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return render_template('explanations_list.html', explanations=explanations)

@app.route('/explanations/<explanation_id>')
def view_explanation(explanation_id):
    """View a specific explanation by ID"""
    file_path = config.OUTPUT_PATH / f"explanation_{explanation_id}.json"
    
    if not file_path.exists():
        return jsonify({'error': 'Explanation not found'}), 404
    
    try:
        with open(file_path, 'r') as file:
            explanation = json.load(file)

            sections = load_config_for_display()

            return render_template('explanation.html', 
                                  explanation=explanation, 
                                  output_file=str(file_path),
                                  conversation_log=explanation.get('agent_conversation', []),
                                  all_sections=sections,
                                  config=config,
            )

    except Exception as e:
        return jsonify({'error': f'Error reading explanation: {str(e)}'}), 500

if __name__ == '__main__':
    # Ensure the necessary directories exist
    for dir_path in [config.DATA_PATH, config.INTENTS_PATH, config.LOGS_PATH, config.OUTPUT_PATH]:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # Start the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)
