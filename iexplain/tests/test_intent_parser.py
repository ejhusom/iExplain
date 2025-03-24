import unittest
import json
import os
import sys
from pathlib import Path

# Add the src directory to the Python path to import the module
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from tools.parse_tmf_intent import parse_tmf_intent

class TestSimplifiedIntentParser(unittest.TestCase):
    def setUp(self):
        # Create test data directory if it doesn't exist
        self.test_data_dir = Path(__file__).parent / "test_data"
        self.test_data_dir.mkdir(exist_ok=True)
        
        # Create output directory for parsed results
        self.output_dir = Path(__file__).parent / "test_output"
        self.output_dir.mkdir(exist_ok=True)
        
        # Sample intent in Turtle format for testing
        self.sample_intent1 = """
@prefix icm:  <http://tio.models.tmforum.org/tio/v3.6.0/IntentCommonModel/> .
@prefix dct:  <http://purl.org/dc/terms/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix geo:  <http://www.opengis.net/ont/geosparql#> .
@prefix intendproject: <http://intendproject.eu/> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .
@prefix set: <http://www.w3.org/2000/10/swap/set#> .
@prefix quan: <http://www.w3.org/2000/10/swap/quantities#> .

intendproject:I1 a icm:Intent ;
    dct:description "Improve latency for AR application in shopping mall"@en ;
    log:allOf ( intendproject:DE1 intendproject:RE1) ;
.

intendproject:DE1 a icm:DeliveryExpectation ;
    icm:target intendproject:inSwitch ;
    dct:description "Ensure low latency and sufficient bandwidth for AR application in K1 Shopping Mall"@en ;
    log:allOf ( intendproject:C1 intendproject:C2 intendproject:C3 intendproject:CX1 )
.

intendproject:C1 a icm:Condition ;
    dct:description "Network latency must be below threshold"@en ;
    set:forAll ( _:X
        [ icm:valuesOfTargetProperty ( intendproject:Telenor5GLatency ) ]
        quan:smaller ( _:X [ rdf:value "20.0"^^xsd:decimal ;
        quan:unit "ms"
        ] )
    )
.

intendproject:C2 a icm:Condition ;
    dct:description "Network bandwidth must be above threshold"@en ;
    set:forAll ( _:X
        [ icm:valuesOfTargetProperty ( intendproject:Telenor5GBandwidth ) ]
        quan:larger ( _:X [ rdf:value "300.0"^^xsd:decimal ;
        quan:unit "mbit/s"
        ] )
    )
.

intendproject:C3 a icm:Condition ;
    dct:description "Edge compute latency must be below threshold"@en ;
    set:forAll ( _:X
        [ icm:valuesOfTargetProperty ( intendproject:TelenorEdgeComputeLatency ) ]
        quan:smaller ( _:X [ rdf:value "10.0"^^xsd:decimal ;
        quan:unit "ms"
        ] )
    )
.

intendproject:CX1 a icm:Context ;
    dct:description "Applied to K1 Shopping Mall in Tromsø"@en ;
    intendproject:appliesToRegion intendproject:K1ShoppingMallRegion ;
.

intendproject:K1ShoppingMallRegion a geo:Feature ;
    dct:description "K1 Shopping Mall in Tromsø"@en ;
    geo:hasGeometry [
    a geo:Polygon ;
    geo:asWKT "POLYGON((69.673545 18.921344, 69.673448 18.924026, 69.672195 18.923903, 69.672356 18.921052))"^^geo:wktLiteral ;
    ] ;
.

intendproject:RE1 a icm:ReportingExpectation ;
    icm:target intendproject:inSwitch ;
    dct:description "Report if expectation is met with reports including metrics related to expectations"@en ;
.
        """
        
        # Save test intent to a file
        with open(self.test_data_dir / "sample_intent1.ttl", "w") as f:
            f.write(self.sample_intent1)
        
        # Invalid intent with syntax errors
        self.invalid_intent = """
@prefix icm:  <http://tio.models.tmforum.org/tio/v3.6.0/IntentCommonModel/> .
@prefix dct:  <http://purl.org/dc/terms/> .

# Missing closing tag
intendproject:I1 a icm:Intent 
    log:allOf ( intendproject:DE1 intendproject:RE1) ;
.
        """
        
        with open(self.test_data_dir / "invalid_intent.ttl", "w") as f:
            f.write(self.invalid_intent)

    def save_parsed_result(self, parsed_intent, filename):
        """Save the parsed intent to a JSON file for inspection."""
        output_path = self.output_dir / filename
        
        # Create a copy that's safe to serialize to JSON
        # (some objects might not be JSON serializable)
        safe_output = {}
        for key, value in parsed_intent.items():
            if key == "raw_intent" and isinstance(value, str) and len(value) > 100:
                # Truncate long raw intent strings to keep output files manageable
                safe_output[key] = value[:100] + "... [truncated]"
            else:
                safe_output[key] = value
        
        with open(output_path, 'w') as f:
            json.dump(safe_output, f, indent=2)
            
        print(f"Saved parsed result to {output_path}")
        return output_path

    def test_parse_valid_intent(self):
        """Test parsing a valid intent and extracting descriptions."""
        parsed_intent = parse_tmf_intent(self.sample_intent1)
        
        # Save the parsed result for inspection
        self.save_parsed_result(parsed_intent, "valid_intent_result.json")
        
        # Check if parsing was successful (no error key)
        self.assertNotIn("error", parsed_intent)
        
        # Check that descriptions were extracted
        self.assertIn("descriptions", parsed_intent)
        self.assertGreater(len(parsed_intent["descriptions"]), 0)
        
        # Check for expected types in the descriptions
        types = [desc["type"] for desc in parsed_intent["descriptions"]]
        self.assertIn("Intent", types)
        self.assertIn("DeliveryExpectation", types)
        self.assertIn("Condition", types)
        self.assertIn("ReportingExpectation", types)
        
        # Check if we can find specific descriptions
        intent_desc = None
        for desc in parsed_intent["descriptions"]:
            if desc["type"] == "Intent":
                intent_desc = desc
                break
        
        self.assertIsNotNone(intent_desc)
        self.assertIn("Improve latency", intent_desc["description"])
        
        # Check for summary
        self.assertIn("summary", parsed_intent)
        self.assertNotEqual(parsed_intent["summary"], "")

    def test_parse_from_file(self):
        """Test parsing an intent from a file."""
        file_path = self.test_data_dir / "sample_intent1.ttl"
        with open(file_path, "r") as f:
            intent_str = f.read()
        
        parsed_intent = parse_tmf_intent(intent_str)
        
        # Save the parsed result
        self.save_parsed_result(parsed_intent, "file_intent_result.json")
        
        # Verify basic structure
        self.assertNotIn("error", parsed_intent)
        self.assertIn("descriptions", parsed_intent)
        self.assertGreater(len(parsed_intent["descriptions"]), 0)

    def test_parse_empty_string(self):
        """Test parsing an empty string."""
        parsed_intent = parse_tmf_intent("")
        
        # Save the parsed result
        self.save_parsed_result(parsed_intent, "empty_intent_result.json")
        
        # Should contain an error
        self.assertIn("error", parsed_intent)
        self.assertEqual(parsed_intent["error"], "Failed to parse intent: Empty input")

    def test_descriptions_content(self):
        """Test the content of extracted descriptions."""
        parsed_intent = parse_tmf_intent(self.sample_intent1)
        
        # Save the parsed result
        self.save_parsed_result(parsed_intent, "descriptions_content_result.json")
        
        # Find specific description types and check content
        condition_descriptions = [
            desc for desc in parsed_intent["descriptions"] 
            if desc["type"] == "Condition"
        ]
        
        # Should have found 3 conditions
        self.assertEqual(len(condition_descriptions), 3)
        
        # Check content of descriptions
        latency_condition = None
        for desc in condition_descriptions:
            if "Network latency" in desc["description"]:
                latency_condition = desc
                break
        
        self.assertIsNotNone(latency_condition)
        self.assertEqual(latency_condition["type"], "Condition")
        self.assertIn("below threshold", latency_condition["description"])

    def test_invalid_intent(self):
        """Test parsing an invalid intent with syntax errors."""
        parsed_intent = parse_tmf_intent(self.invalid_intent)
        
        # Save the parsed result
        self.save_parsed_result(parsed_intent, "invalid_intent_result.json")
        
        # Should have attempted to parse and returned a result, possibly with warnings
        self.assertIn("descriptions", parsed_intent)

if __name__ == "__main__":
    unittest.main()