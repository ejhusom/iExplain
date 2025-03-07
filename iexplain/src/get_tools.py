from typing import List, Dict, Callable, Any
import os
import importlib.util

def get_tools() -> Dict[str, Dict[str, Any]]:
    """
    Dynamically import all tool functions from scripts in the tools directory.

    Returns:
        Dict[str, Dict[str, Any]]: A dictionary of tool function names and their corresponding details.
    """
    tools = {}
    tools_dir = os.path.join(os.path.dirname(__file__), 'tools')

    for filename in os.listdir(tools_dir):
        if filename.endswith('.py') and filename != '__init__.py':
            module_name = filename[:-3]
            module_path = os.path.join(tools_dir, filename)
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for attr in dir(module):
                func = getattr(module, attr)
                if callable(func) and not attr.startswith("__") and func.__module__ == module_name:
                    tools[attr] = {
                        "function": func,
                        "caller": getattr(module, "caller", None),
                        "executor": getattr(module, "executor", None),
                        "name": attr,
                        "description": func.__doc__
                    }

    return tools