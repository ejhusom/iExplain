# iExplain - Explainability Module

iExplain is a framework designed to generate human-understandable explanations for actions, events, or decisions made by AI agents or systems. It aims to provide clear, context-aware explanations to help users understand the reasoning behind specific sequences of events.

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

## Configuration

The configuration file is located in `src/config.py`. The following fields should be defined by the user:

- `LLM_SERVICE`: The language model service to use (ollama or openai).
- `LLM_MODEL`: The language model to use.
- `LLM_API_KEY`: Your OpenAI API key.

## Usage

### Running the Framework

Currently, the main script is set up to read and parse log files placed in `iExplain/iexplain/work_dir/logs'.
In order to run this tool, place a log file in this directory, iExplain should attempt to parse this log file automatically, independent of the format.

To run the iExplain framework, use the following command:

```sh
python3 src/main.py
```
