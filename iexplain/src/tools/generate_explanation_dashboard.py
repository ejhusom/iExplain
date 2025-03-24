import os
from typing import Dict, Any, List, Optional

caller = "explanation_generator_agent"
executor = "code_executor_agent"

def generate_explanation_dashboard(
    intent_summary: str,
    system_interpretation: str,
    key_actions: List[Dict[str, str]],
    outcome: str,
    influencing_factors: List[str],
    output_file: str = "explanation_dashboard.html"
) -> str:
    """
    Generate an HTML dashboard with explanations about an intent.
    
    Args:
        intent_summary (str): Summary of the user's intent
        system_interpretation (str): How the system interpreted the intent
        key_actions (List[Dict[str, str]]): List of actions taken, each with "action" and "reason" keys
        outcome (str): Description of the outcome (success, failure, partial)
        influencing_factors (List[str]): Factors that influenced the outcome
        output_file (str, optional): Path to save the HTML file. Defaults to "explanation_dashboard.html".
        
    Returns:
        str: Path to the generated HTML file
    """
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Intent Explanation Dashboard</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; line-height: 1.6; }}
        .container {{ max-width: 1000px; margin: 0 auto; }}
        .card {{ background: #f9f9f9; border: 1px solid #ddd; border-radius: 5px; padding: 20px; margin-bottom: 20px; }}
        h1, h2, h3 {{ color: #333; }}
        .actions {{ display: flex; flex-direction: column; gap: 10px; }}
        .action-card {{ background: #fff; border: 1px solid #eee; border-radius: 5px; padding: 15px; }}
        .action-title {{ font-weight: bold; margin-bottom: 5px; }}
        .factors {{ display: flex; flex-direction: column; gap: 5px; }}
        .factor {{ background: #f0f0f0; padding: 10px; border-radius: 5px; }}
        .outcome {{ padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .success {{ background: #d4edda; }}
        .partial {{ background: #fff3cd; }}
        .failure {{ background: #f8d7da; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Intent Explanation Dashboard</h1>
        
        <div class="card">
            <h2>Intent Summary</h2>
            <p>{intent_summary}</p>
        </div>
        
        <div class="card">
            <h2>System Interpretation</h2>
            <p>{system_interpretation}</p>
        </div>
        
        <div class="card">
            <h2>Key Actions</h2>
            <div class="actions">
"""
    
    for action in key_actions:
        html_content += f"""
                <div class="action-card">
                    <div class="action-title">{action.get('action', '')}</div>
                    <div class="action-reason">{action.get('reason', '')}</div>
                </div>
"""
    
    outcome_class = "success"
    if "fail" in outcome.lower():
        outcome_class = "failure"
    elif "partial" in outcome.lower():
        outcome_class = "partial"
    
    html_content += f"""
            </div>
        </div>
        
        <div class="card">
            <h2>Outcome</h2>
            <div class="outcome {outcome_class}">
                {outcome}
            </div>
        </div>
        
        <div class="card">
            <h2>Influencing Factors</h2>
            <div class="factors">
"""
    
    for factor in influencing_factors:
        html_content += f"""
                <div class="factor">{factor}</div>
"""
    
    html_content += """
            </div>
        </div>
    </div>
</body>
</html>
"""
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    
    # Write HTML to file
    with open(output_file, "w") as f:
        f.write(html_content)
    
    return os.path.abspath(output_file)
