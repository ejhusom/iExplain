from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import uvicorn

from iexplain.api.app import create_app
from iexplain.config import AppConfig
from iexplain.eval.analyze import write_report
from iexplain.eval.runner import run_experiment, run_matrix_experiment
from iexplain.runtime.models import ArtifactInput, RunRequest, RunOverrides
from iexplain.runtime.service import IExplainService


def main() -> None:
    parser = argparse.ArgumentParser(prog="iexplain")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run a single iExplain task.")
    run_parser.add_argument("task")
    run_parser.add_argument("--config", default="config/app.toml")
    run_parser.add_argument("--profile", default="default")
    run_parser.add_argument("--artifact", action="append", default=[])

    intent_parser = subparsers.add_parser("intent-summary", help="Summarize one intent from GraphDB.")
    intent_parser.add_argument("intent_id")
    intent_parser.add_argument("--config", default="config/app.toml")
    intent_parser.add_argument("--profile", default="intent_demo")
    intent_parser.add_argument("--graphdb-url")
    intent_parser.add_argument("--repository")
    intent_parser.add_argument("--resource-prefix")

    serve_parser = subparsers.add_parser("serve", help="Start the API server.")
    serve_parser.add_argument("--config", default="config/app.toml")

    eval_parser = subparsers.add_parser("eval-run", help="Run an evaluation experiment.")
    eval_parser.add_argument("experiment")
    eval_parser.add_argument("--config", default="config/app.toml")
    eval_parser.add_argument("--dry-run", action="store_true")

    matrix_parser = subparsers.add_parser("eval-matrix", help="Run an evaluation matrix.")
    matrix_parser.add_argument("matrix")
    matrix_parser.add_argument("--config", default="config/app.toml")
    matrix_parser.add_argument("--dry-run", action="store_true")

    analyze_parser = subparsers.add_parser("eval-analyze", help="Analyze evaluation runs.")
    analyze_parser.add_argument("runs_dir", default="runs")
    analyze_parser.add_argument("--markdown-output")
    analyze_parser.add_argument("--json-output")
    analyze_parser.add_argument("--plots-dir")

    args = parser.parse_args()

    if args.command == "run":
        config = AppConfig.from_file(args.config)
        service = IExplainService(config)
        artifacts = [
            ArtifactInput(name=Path(path).name, source_path=path)
            for path in args.artifact
        ]
        result = service.run(
            RunRequest(
                task=args.task,
                profile=args.profile,
                artifacts=artifacts,
                overrides=RunOverrides(),
            )
        )
        print(result.content)
        return

    if args.command == "intent-summary":
        if args.graphdb_url:
            os.environ["IEXPLAIN_INTENT_GRAPHDB_URL"] = args.graphdb_url
        if args.repository:
            os.environ["IEXPLAIN_INTENT_GRAPHDB_REPOSITORY"] = args.repository
        if args.resource_prefix:
            os.environ["IEXPLAIN_INTENT_GRAPHDB_RESOURCE_PREFIX"] = args.resource_prefix

        config = AppConfig.from_file(args.config)
        service = IExplainService(config)
        task = (
            f"Target intent id: {args.intent_id}\n"
            "Summarize what happened for this intent. Explain the state transitions, the main evidence from intent reports "
            "and observations, and mention any missing information."
        )
        result = service.run(
            RunRequest(
                task=task,
                profile=args.profile,
                overrides=RunOverrides(),
            )
        )
        print(result.content)
        return

    if args.command == "serve":
        config = AppConfig.from_file(args.config)
        app = create_app(args.config)
        uvicorn.run(app, host=config.api.host, port=config.api.port)
        return

    if args.command == "eval-run":
        run_dir = run_experiment(
            args.experiment,
            config_path=args.config,
            dry_run=args.dry_run,
            show_progress=True,
        )
        print(run_dir)
        return

    if args.command == "eval-matrix":
        run_dirs = run_matrix_experiment(
            args.matrix,
            config_path=args.config,
            dry_run=args.dry_run,
            show_progress=True,
        )
        print(json.dumps([str(path) for path in run_dirs], indent=2))
        return

    if args.command == "eval-analyze":
        report = write_report(
            args.runs_dir,
            markdown_output=args.markdown_output,
            json_output=args.json_output,
            plots_dir=args.plots_dir,
        )
        print(json.dumps(report, indent=2))
