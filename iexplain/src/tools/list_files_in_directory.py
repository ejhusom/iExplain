import os
from typing import List

caller = "data_reader_agent"
executor = "code_executor_agent"

def list_files_in_directory(directory: str) -> List[str]:
    """
    List all files in a directory.

    Args:
        directory (str): The directory to list files from.

    Returns:
        List[str]: A list of file names in the directory.
    """
    files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    return files
