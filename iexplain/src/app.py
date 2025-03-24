#!/usr/bin/env python3
"""
iExplain Web Application
A simple web interface for demonstrating iExplain functionality
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
import json
from pathlib import Path
import sys
from datetime import datetime

# Add the src directory to the path
current_dir = Path(__file__).parent
sys.path.append(str(current_dir / "src"))

# Import iExplain modules
from config import config
from tools.parse_tmf_intent import parse_tmf_intent

app = Flask(__name__)

# Configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Sample data paths
DATA_DIR = Path("data")
INTENT_DIR = DATA_DIR / "intents"
LOGS_DIR = DATA_DIR / "logs" / "openstack"
OUTPUT_DIR = Path("output")

# Ensure directories exist
for dir_path in [DATA_DIR, INTENT_DIR, LOGS_DIR, OUTPUT_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Helper functions
def get_available_intents():
    """Get a list of available intent files"""
    return [f for f in os.listdir(INTENT_DIR) if f.endswith('.ttl')]

def get_available_logs():
    """Get a list of available log files"""
    return [f for f in os.listdir(LOGS_DIR) if f.endswith('.log')]

def generate_explanation(intent_file, log_files):
    """
    Mock function to generate an explanation
    In a real implementation, this would call the iExplain processing pipeline
    """
    # Read the intent file
    with open(INTENT_DIR / intent_file, 'r') as f:
        intent_content = f.read()
    
    # Parse the intent
    parsed_intent = parse_tmf_intent(intent_content)
    
    # Mock log analysis results
    log_results = {
        'total_entries': 0,
        'api_calls': 0,
        'avg_latency': 0,
        'max_latency': 0,
        'calls_over_threshold': 0
    }
    
    # Process each log file
    for log_file in log_files:
        with open(LOGS_DIR / log_file, 'r') as f:
            log_lines = f.readlines()
            
        # Count entries and extract latency info
        api_calls = 0
        total_latency = 0
        max_latency = 0
        over_threshold = 0
        
        for line in log_lines:
            log_results['total_entries'] += 1
            
            # Check if it's a Nova API call for servers/detail
            if "nova.osapi_compute.wsgi.server" in line and "GET /v2/" in line and "/servers/detail" in line:
                api_calls += 1
                
                # Extract latency
                try:
                    latency_part = line.split("time:")[-1].strip()
                    latency = float(latency_part) * 1000  # Convert to ms
                    total_latency += latency
                    
                    if latency > max_latency:
                        max_latency = latency
                        
                    # Check if over threshold (250ms)
                    if latency > 250:
                        over_threshold += 1
                except Exception:
                    pass
        
        # Update log results
        log_results['api_calls'] += api_calls
        
        if api_calls > 0:
            log_results['avg_latency'] = round(total_latency / api_calls, 2)
        
        log_results['max_latency'] = max(log_results['max_latency'], max_latency)
        log_results['calls_over_threshold'] += over_threshold
    
    # Generate a timestamp for the report
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create an explanation
    explanation = {
        'timestamp': timestamp,
        'intent': {
            'id': parsed_intent.get('summary', 'Unknown intent'),
            'description': next((d['description'] for d in parsed_intent.get('descriptions', []) 
                               if d['type'] == 'Intent'), 'No description found'),
            'threshold': 250  # ms
        },
        'analysis': {
            'total_logs_analyzed': log_results['total_entries'],
            'relevant_api_calls': log_results['api_calls'],
            'avg_response_time': log_results['avg_latency'],
            'max_response_time': log_results['max_latency'],
            'calls_exceeding_threshold': log_results['calls_over_threshold'],
            'threshold_violation_rate': round((log_results['calls_over_threshold'] / log_results['api_calls'] * 100 
                                             if log_results['api_calls'] > 0 else 0), 2)
        },
        'recommendations': [
            {
                'action': 'Increase API server resources',
                'reason': 'Higher resource allocation can reduce processing time'
            },
            {
                'action': 'Optimize database queries',
                'reason': 'Many list operations are slowed by inefficient queries'
            },
            {
                'action': 'Implement request caching',
                'reason': 'Frequently accessed server details can be cached'
            }
        ],
        'outcome': 'Partial Success' if log_results['calls_over_threshold'] > 0 else 'Success',
        'influencing_factors': [
            'Server resource utilization',
            'Database query efficiency',
            'Network conditions',
            'Request volume'
        ]
    }
    
    # Save explanation to a file
    output_file = OUTPUT_DIR / f"explanation_{timestamp.replace(' ', '_').replace(':', '-')}.json"
    with open(output_file, 'w') as f:
        json.dump(explanation, f, indent=4)
    
    return explanation, str(output_file)

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
        explanation, output_file = generate_explanation(intent_file, log_files)
        return render_template('explanation.html', explanation=explanation, output_file=output_file)
    except Exception as e:
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