# iExplain Framework Documentation

## Overview

iExplain is an explainability framework designed to make intent-based management systems transparent to stakeholders. The framework analyzes how high-level intents are interpreted and implemented by systems, then generates human-readable explanations of outcomes, actions taken, and influencing factors.

## Architecture

### Core Components

The iExplain framework consists of the following components:

1. **Multi-agent System**: Orchestrated network of specialized LLM agents
2. **Data Processing Tools**: Tools and functions for processing intents, logs, and other inputs
3. **Web Interface**: Dashboard for viewing explanations and results

### Agent Types

iExplain uses a collection of specialized agents working together:

- **Intent Parser Agent**: Analyzes and structures TMF-formatted intents and natural language expressions
- **Log Analysis Agent**: Examines log data to identify events related to intents
- **Causal Inference Agent**: Determines relationships between system actions and outcomes
- **Explanation Generator Agent**: Constructs clear, evidence-based explanations
- **Input Agent**: Routes inputs to appropriate processing agents
- **Code Writer/Executor Agents**: Generate and execute code for analysis tasks

The framework can easily be extended with other agents.

### Data Flow

1. **Input**: 
    - Intent definitions (TMF format and/or natural language)
    - System logs
2. **Processing**: 
    - Multi-step analysis through specialized agents
3. **Output**: 
    - Web interface displaying:
        - Original intent request (TMF format and/or natural language)
        - Intent outcome (was the intent fulfilled or not) with explanation for why or why not
        - Analysis results based on the system logs
        - Influencing factors
        - Recommendations
        - The full interaction log of the multi-agent framework

## Installation & Setup

### Prerequisites

- Python 3.8+
- OpenAI API key or local LLMs served by Ollama
- Required Python packages (see requirements.txt)

### Installation Steps

1. Clone the repository: `git clone https://github.com/ejhusom/iExplain`
2. Install dependencies: `pip install -r requirements.txt`
3. Configure LLM access (see below)

For running a simple demo case, run the included setup-script: `./setup.sh`

## Configuration

The `config.py` file controls framework behavior, with the following parameters being most important to define:

| Setting      | Description                      | Default        |
| ------------ | -------------------------------- | -------------- |
| LLM_SERVICE  | Service provider (openai/ollama) | openai         |
| LLM_MODEL    | Model to use                     | gpt-4o-mini    |
| LLM_API_KEY  | API key for service              | (from env)     |


Additionally, it's possible to customize where input and output data is stored:


| Setting      | Description                      | Default        |
| ------------ | -------------------------------- | -------------- |
| DATA_PATH    | Path to data directory           | ./data         |
| LOGS_PATH    | Path to log files                | ./data/logs    |
| INTENTS_PATH | Path to intent definitions       | ./data/intents |
| OUTPUT_PATH  | Path for output files            | ./output       |

### Output and Dashboard Configuration

The explanation dashboard is dynamically generated and can be fully customized through these configuration parameters:

| Setting                   | Description                                          | Example Values                |
| ------------------------- | ---------------------------------------------------- | ---------------------------- |
| EXPLANATION_CONFIG        | Field display settings for the dashboard             | Dictionary of field configs  |
| HIDDEN_EXPLANATION_FIELDS | Fields that are hidden by default but can be toggled | ["analysis"]                 |
| EXCLUDED_EXPLANATION_FIELDS | Fields completely excluded from the dashboard      | ["timestamp"]                |
| EXPLANATION_SINGLE_COLUMN | Toggle between one and two-column layout             | True/False                   |


#### Explanation Output Configuration

`EXPLANATION_CONFIG` controls how the multi-agent framework will structure its output.
Each field can be configured with the following options:

```python
"field_name": {
    "title": "Display Title",
    "display_type": "text",  # text, list, key_value, status, etc.
    "description": "Field description (used in the system prompt of the multi-agent framework)",
    "display_priority": 10,  # Lower numbers appear first
    "item_type": "simple"    # For lists: simple, recommendation, factor
}
```

This configuration approach allows for:

- Adding new fields without modifying the display template
- Changing the order of displayed fields
- Hiding or excluding specific fields
- Customizing how each field is displayed
- Switching between single and two-column layouts

#### Explanation Output

The default explanation output includes:

- Original intent request (TMF format and/or natural language)
- Intent outcome (was the intent fulfilled or not) with explanation for why or why not
- Analysis results based on the system logs
- Influencing factors
- Recommendations
- The full interaction log of the multi-agent framework

All of these components are configurable through the dashboard settings.

## Usage

### Starting the Application

Run the Flask application:

```bash
python src/app.py
```

Access the web interface at: [http://localhost:5000](http://localhost:5000).

### Defining Intents

iExplain accepts intents in two formats:

1. **Natural Language**: Placed in a .txt file in the intents directory
2. **TMF Format (Turtle RDF)**: Placed in a .ttl file in the intents directory

The naming convention for intent files is:

- `intent_name.txt` for natural language
- `intent_name.ttl` for TMF format

Place these files under `data/intents/`.

Below follows an example of a TMF Intent.

#### TMF Intent Structure

```turtle
@prefix icm:  <http://tio.models.tmforum.org/tio/v3.6.0/IntentCommonModel/> .
@prefix dct:  <http://purl.org/dc/terms/> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix log:  <http://www.w3.org/2000/10/swap/log#> .
@prefix set:  <http://www.w3.org/2000/10/swap/set#> .
@prefix quan: <http://www.w3.org/2000/10/swap/quantities#> .
@prefix iexp: <http://intendproject.eu/iexplain#> .

iexp:I1 a icm:Intent ;
    dct:description "Intent description"@en ;
    log:allOf ( iexp:DE1 iexp:RE1 ) ;
.

iexp:DE1 a icm:DeliveryExpectation ;
    icm:target iexp:target-service ;
    dct:description "Delivery expectation description"@en ;
    log:allOf ( iexp:C1 ) ;
.

iexp:C1 a icm:Condition ;
    dct:description "Condition description"@en ;
    set:forAll (
    _:X
    [ icm:valuesOfTargetProperty ( iexp:MetricName ) ]
    quan:smaller ( _:X [ rdf:value "threshold_value"^^xsd:decimal ; quan:unit "unit" ] )
    ) ;
.

iexp:RE1 a icm:ReportingExpectation ;
    icm:target iexp:monitoring-system ;
    dct:description "Reporting expectation description"@en ;
.
```

### Providing Log Data

Place log files in the `data/logs` directory. iExplain supports various log formats and will attempt to automatically identify and parse them. 

### Generating Explanations

1. Navigate to the web interface
2. Select an intent from the list
3. Choose relevant log files
4. Click "Generate Explanation"
    - This process may take seconds or minutes depending on the size of the input data and the speed of the LLM service used for the agents.
5. View the resulting explanation dashboard

### Explanation Output

The default explanation output includes:

- Original intent request (TMF format and/or natural language)
- Intent outcome (was the intent fulfilled or not) with explanation for why or why not
- Analysis results based on the system logs
- Influencing factors
- Recommendations
- The full interaction log of the multi-agent framework

## Extending iExplain

### Adding New Agent Types

6. Create a new agent file in `src/agents/`
7. Implement a creation function
8. Register the agent in `get_agents.py`

Example agent structure:

```python
# src/agents/my_new_agent.py
from autogen import ConversableAgent

def create_my_new_agent(config_list):
    return ConversableAgent(
        name="my_new_agent",
        system_message="""
        Your detailed instructions...
        """,
        description="Brief description of agent's purpose",
        llm_config={"config_list": config_list},
        human_input_mode="NEVER",
    )
```

### Adding New Tools

**IMPORTANT**: *As of 2025-03-30, the tool functionality needs fixing to function properly. Because of this it is disabled in the current commit of iExplain.*

Add tool functions to `src/tools/` with this structure:

```python
# src/tools/my_new_tool.py
from typing import Dict, Any

caller = "agent_that_calls_tool"
executor = "agent_that_executes_tool"

def my_new_tool(param1: str, param2: int) -> Dict[str, Any]:
    """
    Tool description.
    
    Args:
        param1: Description of param1
        param2: Description of param2
        
    Returns:
        Dictionary with results
    """
    # Tool implementation
    result = {}
    
    # Process inputs
    
    return result
```

## API Reference

### explainer.py

The core module that orchestrates the explanation process.

#### Methods

- `explain(intent_folder, log_files)`: Generate an explanation for the given intent using specified log files
- `_extract_explanation_from_result(result, nl_intent, structured_intent, intent_id, intent_description)`: Parse the agent conversation into a structured explanation
- `_save_explanation_to_file(explanation)`: Save the explanation to a JSON file

### app.py

Web application controller.

#### Routes

- `GET /`: Home page showing available intents and logs
- `POST /explain`: Generate an explanation for selected intent and logs
- `GET /api/explanations`: List all saved explanations

### Tools

#### parse_tmf_intent.py

Parses TMF-formatted intents.

```python
parse_tmf_intent(turtle_string: str) -> Dict[str, Any]
```

#### parse_logs.py

Parses log files using the Drain algorithm.

```python
parse_logs(input_dir: str, log_file: str, log_format: str, regex: List[str], 
           output_dir: str, depth: int, similarity_threshold: float) -> str
```

#### generate_explanation_dashboard.py

Creates HTML dashboards for explanations.

```python
generate_explanation_dashboard(intent_summary: str, system_interpretation: str,                               key_actions: List[Dict[str, str]], outcome: str,                              influencing_factors: List[str], output_file: str) -> str
```

## Troubleshooting

### Common Issues

1. **Missing API Key**: Ensure OPENAI_API_KEY is set correctly, either in `config.py` or by running `export OPENAI_API_KEY=[your_key]`.

## Future Development

- Integrate log analysis into the multi-agent interaction
- Improved multi-agent interaction
- Support for large log files
