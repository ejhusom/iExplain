from logparser.Drain import LogParser
from typing import List

def parse_logs(input_dir: str, output_dir: str, log_file: str, log_format: str, regex: List[str], depth: int = 4, similarity_threshold: float = 0.5) -> str:
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
    parser = LogParser(
        log_format=log_format,
        indir=input_dir,
        outdir=output_dir,
        depth=depth,
        st=similarity_threshold,
        rex=regex
    )
    result = parser.parse(log_file)
    print(result)

    return result