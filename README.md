# iExplain - Intent Explainability Tool

iExplain is a framework for generating human-understandable explanations for intent-based management systems. It helps stakeholders understand how their high-level intents were interpreted, what actions were taken, and the outcomes achieved.

## Current Status

iExplain is currently in active development as part of the INTEND project. The tool can:
- Parse intents in TMF format (Turtle RDF)
- Analyze basic log files to determine if intents were met
- Generate structured explanations via a multi-agent system
- Present results through a web interface


## Installation

1. Clone the repository:

    ```sh
    git clone https://github.com/ejhusom/GenExplain.git
    cd iExplain/iexplain
    ```

2. Install the required packages:

    ```sh
    pip install -r requirements.txt
    ```

3. Set up your environment variables:

    ```sh
    export OPENAI_API_KEY=your_api_key_here
    ```

## Configuration

The configuration file is located in `src/config.py`. The following fields should be defined by the user:

- `LLM_SERVICE`: The language model service to use (ollama or openai).
- `LLM_MODEL`: The language model to use.
- `LLM_API_KEY`: Your OpenAI API key.

## Usage

### Generate sample data

Generate sample data for testing the framework by running the following script in the `iexplain` directory:

```sh
./setup.sh
```

### Running the web interface

The main application runs as a Flask web app:

```sh
python3 src/app.py
```

Then access the interface at: http://localhost:5000

### Development

The project uses autogen (formerly ag2) for orchestrating a multi-agent system. The main components are:

- `src/explainer.py`: Core explanation logic
- `src/app.py`: Web interface
- `src/agents/`: Specialized LLM agents for different tasks
- `src/tools/`: Utility functions used by agents

### Testing

Run the basic tests with:

```sh
python -m unittest discover tests
```