from logparser.Drain import LogParser
from typing import List
import os
import sys

sys.path.append(os.path.abspath('../'))
from config import config

caller = "log_parser_agent"
executor = "code_executor_agent"

def parse_logs(input_dir: str, log_file: str, log_format: str, regex: List[str], output_dir: str = str(config.OUTPUT_PATH), depth: int = 4, similarity_threshold: float = 0.5) -> str:
    """
    Parse logs using the specified format and parameters.

    Args:
        input_dir (str): Directory containing the input log files.
        output_dir (str): Directory to save the parsed log results.
        log_file (str): The log file to be parsed.
        log_format (str): The format of the log file.
        regex (List[str]): List of regular expressions for preprocessing.
        depth (int, optional): Depth of the parsing tree. Defaults to 4.
        similarity_threshold (float, optional): Similarity threshold for grouping log messages. Defaults to 0.5.
    """

    # Validate the type of the input parameters
    assert isinstance(input_dir, str), "input_dir must be a string."
    assert isinstance(output_dir, str), "output_dir must be a string."
    assert isinstance(log_file, str), "log_file must be a string."
    assert isinstance(log_format, str), "log_format must be a string."
    assert isinstance(depth, int), "depth must be an integer."
    # Similarity threshold must be a float or int
    assert isinstance(similarity_threshold, (float, int)), "similarity_threshold must be a float or an integer."
    # Regex must be list of strings, but if it's a string, it will be converted to a list of strings
    if isinstance(regex, str):
        regex = [regex]
    assert isinstance(regex, list), "regex must be a list of strings."

    # Parse the logs
    parser = LogParser(
        log_format=log_format,
        indir=input_dir,
        outdir=output_dir,
        depth=depth,
        st=similarity_threshold,
        rex=regex
    )
    result = parser.parse(log_file)

    return result
