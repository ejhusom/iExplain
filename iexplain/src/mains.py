#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""iExplain - Minimal Viable Service

A simplified version of the iExplain framework that focuses on the core functionality
using a minimal set of agents.
"""
import os
import json
from pathlib import Path
import re
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

# Import from your existing code
import sys
sys.path.append(str(Path(__file__).parent))
from tools.parse_tmf_intent import parse_tmf_intent

class MinimalExplainer:
    """
    A minimal implementation of the iExplain framework using basic parsing
    and analysis without the full agent system.
    """
    
    def __init__(self):
        """Initialize the minimal explainer."""
        self.data_dir = Path("data")
        self.logs_dir = self.data_dir / "logs"
        self.intents_dir = self.data_dir / "intents"
        self.output_dir = Path("output")
        
        # Create necessary directories
        for directory in [self.data_dir, self.logs_dir, self.intents_dir, self.output_dir]:
            directory.mkdir(exist_ok=True, parents=True)
    
    def analyze_intent(self, intent_file: str) -> Dict[str, Any]:
        """
        Analyze a TMF intent file.
        
        Args:
            intent_file (str): Path to the intent file
            
        Returns:
            Dict[str, Any]: Parsed intent information
        """
        # Read and parse the intent
        intent_path = self.intents_dir / intent_file
        with open(intent_path, 'r') as f:
            intent_content = f.read()
        
        # Parse the intent using the existing tool
        parsed_intent = parse_tmf_intent(intent_content)
        
        # Get natural language intent if available
        nl_intent = self._get_natural_language_intent(intent_file)
        
        # Extract key information from the parsed intent
        intent_info = {
            'id': parsed_intent.get('summary', 'Unknown intent'),
            'description': '',
            'threshold': 0,
            'threshold_unit': 'ms',
            'target': '',
            'natural_language': nl_intent
        }
        
        # Extract more detailed information from the parsed intent
        for desc in parsed_intent.get('descriptions', []):
            if desc['type'] == 'DeliveryExpectation':
                intent_info['description'] = desc['description']
            
            # Look for condition with threshold
            if desc['type'] == 'Condition' and 'description' in desc:
                # Check for API response time condition
                if 'API response time' in desc['description']:
                    # Try to extract threshold value from turtle format using regex
                    threshold_match = re.search(r'rdf:value "(\d+)"', intent_content)
                    if threshold_match:
                        intent_info['threshold'] = int(threshold_match.group(1))
                        intent_info['threshold_unit'] = 'ms'
                
                # Check for VM startup time condition
                elif 'VM startup time' in desc['description']:
                    # Try to extract threshold value from turtle format using regex
                    threshold_match = re.search(r'rdf:value "(\d+)"', intent_content)
                    if threshold_match:
                        intent_info['threshold'] = int(threshold_match.group(1))
                        intent_info['threshold_unit'] = 's'
        
        return intent_info
    
    def _get_natural_language_intent(self, intent_file: str) -> str:
        """Get the natural language version of the intent if available."""
        mapping_file = self.intents_dir / "intent_mapping.json"
        if mapping_file.exists():
            try:
                with open(mapping_file, 'r') as f:
                    mapping = json.load(f)
                
                if intent_file in mapping:
                    nl_path = self.intents_dir / mapping[intent_file].get('natural_language_file', '')
                    if nl_path.exists():
                        with open(nl_path, 'r') as f:
                            return f.read()
            except Exception as e:
                print(f"Error loading natural language intent: {e}")
        
        return ""
    
    def analyze_logs(self, log_files: List[str], intent_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze log files based on the intent information.
        
        Args:
            log_files (List[str]): List of log file paths
            intent_info (Dict[str, Any]): Intent information
            
        Returns:
            Dict[str, Any]: Analysis results
        """
        # Initialize results
        log_results = {
            'total_entries': 0,
            'api_calls': 0,
            'avg_latency': 0,
            'max_latency': 0,
            'calls_over_threshold': 0,
            'vm_startups': 0,
            'avg_startup_time': 0
        }
        
        # Process each log file
        for log_file in log_files:
            log_path = self.logs_dir / "openstack" / log_file
            
            if not log_path.exists():
                print(f"Log file not found: {log_path}")
                continue
                
            with open(log_path, 'r') as f:
                log_lines = f.readlines()
            
            # Count entries and extract relevant info
            for line in log_lines:
                log_results['total_entries'] += 1
                
                # Check if it's a Nova API call for servers/detail
                if "nova.osapi_compute.wsgi.server" in line and "GET /v2/" in line and "/servers/detail" in line:
                    log_results['api_calls'] += 1
                    
                    # Extract latency
                    try:
                        latency_part = line.split("time:")[-1].strip()
                        latency = float(latency_part) * 1000  # Convert to ms
                        
                        # Update latency stats
                        if log_results['api_calls'] == 1:
                            log_results['avg_latency'] = latency
                        else:
                            log_results['avg_latency'] = (log_results['avg_latency'] * (log_results['api_calls'] - 1) + latency) / log_results['api_calls']
                        
                        if latency > log_results['max_latency']:
                            log_results['max_latency'] = latency
                            
                        # Check if over threshold
                        if intent_info['threshold'] > 0 and latency > intent_info['threshold']:
                            log_results['calls_over_threshold'] += 1
                    except Exception as e:
                        print(f"Error extracting latency: {e}")
                        
                # Check for VM startup times
                if "nova.compute.manager" in line and "Instance spawned in" in line:
                    log_results['vm_startups'] += 1
                    
                    # Extract startup time
                    try:
                        time_part = line.split("spawned in")[1].split("seconds")[0].strip()
                        startup_time = float(time_part)  # Already in seconds
                        
                        # Update startup time stats
                        if log_results['vm_startups'] == 1:
                            log_results['avg_startup_time'] = startup_time
                        else:
                            log_results['avg_startup_time'] = (log_results['avg_startup_time'] * (log_results['vm_startups'] - 1) + startup_time) / log_results['vm_startups']
                    except Exception as e:
                        print(f"Error extracting startup time: {e}")
        
        # Round averages
        log_results['avg_latency'] = round(log_results['avg_latency'], 2)
        log_results['max_latency'] = round(log_results['max_latency'], 2)
        log_results['avg_startup_time'] = round(log_results['avg_startup_time'], 2)
        
        return log_results
    
    def generate_recommendations(self, intent_info: Dict[str, Any], log_results: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate recommendations based on the intent and log analysis."""
        recommendations = []
        
        # Check if it's an API latency intent
        if intent_info['threshold_unit'] == 'ms':
            # API latency recommendations
            if log_results['avg_latency'] > intent_info['threshold']:
                recommendations.append({
                    'action': 'Increase API server resources',
                    'reason': 'Higher resource allocation can reduce processing time'
                })
                recommendations.append({
                    'action': 'Optimize database queries',
                    'reason': 'Many list operations are slowed by inefficient queries'
                })
                recommendations.append({
                    'action': 'Implement request caching',
                    'reason': 'Frequently accessed server details can be cached'
                })
            else:
                recommendations.append({
                    'action': 'Monitor during peak hours',
                    'reason': 'Current performance is good, but should be monitored during high load'
                })
        
        # Check if it's a VM startup time intent
        elif intent_info['threshold_unit'] == 's':
            # VM startup time recommendations
            if log_results['avg_startup_time'] > intent_info['threshold']:
                recommendations.append({
                    'action': 'Optimize image caching',
                    'reason': 'Pre-cached images reduce VM startup time'
                })
                recommendations.append({
                    'action': 'Upgrade storage infrastructure',
                    'reason': 'Faster storage I/O speeds up VM provisioning'
                })
                recommendations.append({
                    'action': 'Use lightweight VM images',
                    'reason': 'Smaller images load faster during VM creation'
                })
            else:
                recommendations.append({
                    'action': 'Document current configuration',
                    'reason': 'Current setup is performing well and should be documented as a baseline'
                })
        
        return recommendations
    
    def determine_outcome(self, intent_info: Dict[str, Any], log_results: Dict[str, Any]) -> str:
        """Determine the outcome of the intent based on the analysis."""
        # Check if it's an API latency intent
        if intent_info['threshold_unit'] == 'ms':
            if log_results['calls_over_threshold'] == 0:
                return 'Success'
            elif log_results['calls_over_threshold'] / log_results['api_calls'] < 0.2:
                return 'Partial Success'
            else:
                return 'Failure'
        
        # Check if it's a VM startup time intent
        elif intent_info['threshold_unit'] == 's':
            if log_results['avg_startup_time'] <= intent_info['threshold']:
                return 'Success'
            elif log_results['avg_startup_time'] <= intent_info['threshold'] * 1.1:
                return 'Partial Success'
            else:
                return 'Failure'
        
        return 'Unknown'
    
    def get_influencing_factors(self, intent_info: Dict[str, Any]) -> List[str]:
        """Get the influencing factors for the intent."""
        if intent_info['threshold_unit'] == 'ms':
            # API latency influencing factors
            return [
                'Server resource utilization',
                'Database query efficiency',
                'Network conditions',
                'Request volume'
            ]
        elif intent_info['threshold_unit'] == 's':
            # VM startup time influencing factors
            return [
                'Image size and complexity',
                'Storage I/O performance',
                'Hypervisor scheduling efficiency',
                'Available compute resources'
            ]
        
        return []
    
    def explain(self, intent_file: str, log_files: List[str]) -> Tuple[Dict[str, Any], str]:
        """
        Generate an explanation for an intent based on log files.
        
        Args:
            intent_file (str): Path to the intent file
            log_files (List[str]): List of log file paths
            
        Returns:
            Tuple[Dict[str, Any], str]: Explanation results and output file path
        """
        # Parse the intent
        intent_info = self.analyze_intent(intent_file)
        
        # Analyze logs
        log_results = self.analyze_logs(log_files, intent_info)
        
        # Generate recommendations
        recommendations = self.generate_recommendations(intent_info, log_results)
        
        # Determine outcome
        outcome = self.determine_outcome(intent_info, log_results)
        
        # Get influencing factors
        influencing_factors = self.get_influencing_factors(intent_info)
        
        # Generate a timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create the explanation structure
        explanation = {
            'timestamp': timestamp,
            'natural_language_intent': intent_info['natural_language'],
            'intent': {
                'id': intent_info['id'],
                'description': intent_info['description'],
                'threshold': intent_info['threshold']
            },
            'analysis': {
                'total_logs_analyzed': log_results['total_entries']
            },
            'recommendations': recommendations,
            'outcome': outcome,
            'influencing_factors': influencing_factors
        }
        
        # Add type-specific metrics
        if intent_info['threshold_unit'] == 'ms':
            # API latency metrics
            explanation['analysis'].update({
                'relevant_api_calls': log_results['api_calls'],
                'avg_response_time': log_results['avg_latency'],
                'max_response_time': log_results['max_latency'],
                'calls_exceeding_threshold': log_results['calls_over_threshold'],
                'threshold_violation_rate': round((log_results['calls_over_threshold'] / log_results['api_calls'] * 100 
                                               if log_results['api_calls'] > 0 else 0), 2)
            })
        elif intent_info['threshold_unit'] == 's':
            # VM startup time metrics
            explanation['analysis'].update({
                'vm_startups_analyzed': log_results['vm_startups'],
                'avg_startup_time': log_results['avg_startup_time'],
                'threshold_violation_rate': round((log_results['vm_startups'] if log_results['avg_startup_time'] > intent_info['threshold'] else 0) / 
                                               (log_results['vm_startups'] if log_results['vm_startups'] > 0 else 1) * 100, 2)
            })
        
        # Save explanation to a file
        output_file = self.output_dir / f"explanation_{timestamp.replace(' ', '_').replace(':', '-')}.json"
        with open(output_file, 'w') as f:
            json.dump(explanation, f, indent=4)
        
        return explanation, str(output_file)


# Create a singleton instance for use by app.py
explainer = MinimalExplainer()