import unittest
import sys
import os
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from tools.parse_tmf_intent import parse_tmf_intent
from tools.parse_logs import parse_logs

class TestExplanationFlow(unittest.TestCase):
    def setUp(self):
        self.intent_file = Path("data/intents/nova_api_latency_intent/nova_api_latency_intent.ttl")
        self.log_file = Path("data/logs/openstack/nova-api.log")
        
    def test_intent_parsing(self):
        with open(self.intent_file, "r") as f:
            intent_str = f.read()
        
        parsed_intent = parse_tmf_intent(intent_str)
        
        # Basic validation of parsed intent
        self.assertNotIn("error", parsed_intent)
        self.assertIn("descriptions", parsed_intent)
        
        # Check for expected content
        found_condition = False
        for desc in parsed_intent["descriptions"]:
            if desc["type"] == "Condition" and "API response time" in desc["description"]:
                found_condition = True
                break
        
        self.assertTrue(found_condition, "Expected condition not found in parsed intent")
        
if __name__ == "__main__":
    unittest.main()
