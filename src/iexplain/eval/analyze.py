from __future__ import annotations

import json
import os
from collections import defaultdict
from html import escape
from pathlib import Path
from typing import Any


def collect_summaries(runs_dir: str | Path) -> list[dict[str, Any]]:
    root = Path(runs_dir).resolve()
    summaries = []
    for summary_file in sorted(root.glob("*/summary.json")):
        summaries.append(json.loads(summary_file.read_text(encoding="utf-8")))
    return summaries


def build_comparison_rows(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    factor_names: set[str] = set()
    for summary in summaries:
        metrics = summary.get("metrics", {})
        performance = summary.get("performance", {})
        resolved_runtime = summary.get("resolved_runtime", {})
        resolved_model = resolved_runtime.get("model", {})
        metric_name, metric_value, metric_numeric = _primary_metric(summary.get("suite", ""), metrics)
        matrix_context = summary.get("matrix_context", {})
        matrix_factors = {
            str(name): str(value)
            for name, value in sorted((matrix_context.get("combination") or {}).items())
        }
        factor_names.update(matrix_factors)
        rows.append(
            {
                "run_id": str(summary.get("run_id", "-")),
                "name": str(summary.get("name", "-")),
                "suite": str(summary.get("suite", "-")),
                "dataset": _dataset_label(summary),
                "model": str(
                    resolved_model.get("model")
                    or summary.get("runtime", {}).get("overrides", {}).get("model")
                    or "-"
                ),
                "provider": str(
                    resolved_model.get("provider")
                    or summary.get("runtime", {}).get("overrides", {}).get("provider")
                    or "-"
                ),
                "profile": str(resolved_runtime.get("profile") or summary.get("runtime", {}).get("profile") or "-"),
                "mode": str(resolved_runtime.get("mode") or "-"),
                "pipeline": str(resolved_runtime.get("pipeline") or "-"),
                "score": f"{metric_name}={metric_value}",
                "primary_metric_name": metric_name,
                "primary_metric_value": str(metric_value),
                "primary_metric_numeric": metric_numeric,
                "tokens_per_case": _format_number(performance.get("avg_total_tokens_per_case")),
                "tokens_per_case_numeric": _float_or_none(performance.get("avg_total_tokens_per_case")),
                "avg_latency_ms": _format_number(performance.get("avg_latency_ms")),
                "avg_latency_ms_numeric": _float_or_none(performance.get("avg_latency_ms")),
                "prompt_variants": _prompt_variant_label(summary),
                "tools": _list_label(resolved_runtime.get("tools")),
                "skills": _list_label(resolved_runtime.get("skills")),
                "max_turns": str(resolved_runtime.get("max_turns", "-")),
                "max_delegations": str(resolved_runtime.get("max_delegations", "-")),
                "assistant_turns": _format_number(performance.get("assistant_turns"), digits=0),
                "tool_calls": _format_number(performance.get("tool_calls"), digits=0),
                "total_tokens": _format_number(performance.get("total_tokens"), digits=0),
                "total_latency_ms": _format_number(performance.get("total_latency_ms")),
                "matrix_name": str(matrix_context.get("name") or "-"),
                "matrix_factors": matrix_factors,
                "matrix_label": _matrix_label(matrix_context),
            }
        )

    rows = sorted(rows, key=lambda row: (row["suite"], row["name"], row["run_id"]))
    for row in rows:
        for factor_name in sorted(factor_names):
            row[f"matrix_{factor_name}"] = row["matrix_factors"].get(factor_name, "-")
    return rows


def write_report(
    runs_dir: str | Path,
    *,
    markdown_output: str | Path | None = None,
    json_output: str | Path | None = None,
    plots_dir: str | Path | None = None,
) -> dict[str, Any]:
    summaries = collect_summaries(runs_dir)
    rows = build_comparison_rows(summaries)
    factor_names = _matrix_factor_names(rows)
    plots_root = Path(plots_dir).resolve() if plots_dir else (Path(runs_dir).resolve() / "plots")
    plots = _write_plots(rows, plots_root)
    report = {
        "runs": summaries,
        "comparison_rows": rows,
        "matrix_factor_names": factor_names,
        "plots": plots,
    }
    if markdown_output:
        markdown_path = Path(markdown_output).resolve()
        markdown_path.write_text(build_markdown_report(report, markdown_path=markdown_path), encoding="utf-8")
    if json_output:
        Path(json_output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def build_markdown_report(report: dict[str, Any], *, markdown_path: Path | None = None) -> str:
    comparison_rows = report.get("comparison_rows", [])
    factor_names = report.get("matrix_factor_names", [])
    plots = report.get("plots", [])
    lines = ["# iExplain Evaluation Report", ""]
    if not comparison_rows:
        lines.append("No runs found.")
        return "\n".join(lines)

    if plots:
        lines.extend(["## Plots", ""])
        for plot in plots:
            title = str(plot.get("title", "Plot"))
            plot_path = Path(str(plot.get("path", "")))
            image_path = str(plot_path)
            if markdown_path is not None:
                image_path = os.path.relpath(plot_path, markdown_path.parent)
            lines.extend([f"### {title}", "", f"![{title}]({image_path})", ""])

    lines.extend(
        [
            "## Overview",
            "",
            "| Run | Suite | Dataset | Model | Profile | Mode | Pipeline | Score | Matrix | Tokens/Case | Avg Latency (ms) |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in comparison_rows:
        lines.append(
            "| {run_id} | {suite} | {dataset} | {model} | {profile} | {mode} | {pipeline} | {score} | {matrix_label} | {tokens_per_case} | {avg_latency_ms} |".format(
                **row
            )
        )

    if factor_names:
        header = "| Run | Matrix | " + " | ".join(name for name in factor_names) + " |"
        divider = "| --- | --- | " + " | ".join("---" for _ in factor_names) + " |"
        lines.extend(["", "## Matrix Factors", "", header, divider])
        for row in comparison_rows:
            values = " | ".join(str(row.get(f"matrix_{name}", "-")) for name in factor_names)
            lines.append(f"| {row['run_id']} | {row['matrix_name']} | {values} |")

    lines.extend(
        [
            "",
            "## Runtime Config",
            "",
            "| Run | Prompt Variants | Tools | Skills | Max Turns | Max Delegations |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in comparison_rows:
        lines.append(
            "| {run_id} | {prompt_variants} | {tools} | {skills} | {max_turns} | {max_delegations} |".format(
                **row
            )
        )

    lines.extend(
        [
            "",
            "## Performance",
            "",
            "| Run | Assistant Turns | Tool Calls | Total Tokens | Total Latency (ms) |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in comparison_rows:
        lines.append(
            "| {run_id} | {assistant_turns} | {tool_calls} | {total_tokens} | {total_latency_ms} |".format(
                **row
            )
        )
    return "\n".join(lines)


def _write_plots(rows: list[dict[str, Any]], plots_root: Path) -> list[dict[str, Any]]:
    if not rows:
        return []
    plots_root.mkdir(parents=True, exist_ok=True)
    plots: list[dict[str, Any]] = []
    suites = sorted({row["suite"] for row in rows})
    for suite in suites:
        suite_rows = [row for row in rows if row["suite"] == suite and row["primary_metric_numeric"] is not None]
        if not suite_rows:
            continue
        axis_max = _metric_axis_max(suite_rows)
        score_plot_path = plots_root / f"{suite}_score_by_run.svg"
        _write_horizontal_bar_chart(
            score_plot_path,
            title=f"{suite}: score by run",
            x_label=_metric_axis_label(suite_rows),
            items=[(_run_label(row), float(row["primary_metric_numeric"])) for row in suite_rows],
            x_max=axis_max,
        )
        plots.append({"suite": suite, "kind": "score_by_run", "title": f"{suite}: score by run", "path": str(score_plot_path)})

        scatter_rows = [
            row
            for row in suite_rows
            if row["tokens_per_case_numeric"] is not None and row["avg_latency_ms_numeric"] is not None
        ]
        if len(scatter_rows) >= 2:
            token_plot_path = plots_root / f"{suite}_tokens_vs_score.svg"
            _write_scatter_plot(
                token_plot_path,
                title=f"{suite}: tokens per case vs score",
                x_label="Avg total tokens per case",
                y_label=_metric_axis_label(suite_rows),
                points=[
                    {
                        "label": _run_label(row),
                        "x": float(row["tokens_per_case_numeric"]),
                        "y": float(row["primary_metric_numeric"]),
                    }
                    for row in scatter_rows
                ],
                y_max=axis_max,
            )
            plots.append(
                {
                    "suite": suite,
                    "kind": "tokens_vs_score",
                    "title": f"{suite}: tokens per case vs score",
                    "path": str(token_plot_path),
                }
            )

            latency_plot_path = plots_root / f"{suite}_latency_vs_score.svg"
            _write_scatter_plot(
                latency_plot_path,
                title=f"{suite}: latency vs score",
                x_label="Avg latency (ms)",
                y_label=_metric_axis_label(suite_rows),
                points=[
                    {
                        "label": _run_label(row),
                        "x": float(row["avg_latency_ms_numeric"]),
                        "y": float(row["primary_metric_numeric"]),
                    }
                    for row in scatter_rows
                ],
                y_max=axis_max,
            )
            plots.append(
                {
                    "suite": suite,
                    "kind": "latency_vs_score",
                    "title": f"{suite}: latency vs score",
                    "path": str(latency_plot_path),
                }
            )

        for factor_name in _suite_factor_names(suite_rows):
            grouped: dict[str, list[float]] = defaultdict(list)
            for row in suite_rows:
                factor_value = row["matrix_factors"].get(factor_name)
                if factor_value:
                    grouped[factor_value].append(float(row["primary_metric_numeric"]))
            if len(grouped) < 2:
                continue
            factor_plot_path = plots_root / f"{suite}_score_by_{_slug(factor_name)}.svg"
            _write_horizontal_bar_chart(
                factor_plot_path,
                title=f"{suite}: average score by {factor_name}",
                x_label=_metric_axis_label(suite_rows),
                items=[
                    (label, sum(values) / len(values))
                    for label, values in sorted(grouped.items())
                ],
                x_max=axis_max,
            )
            plots.append(
                {
                    "suite": suite,
                    "kind": "score_by_factor",
                    "title": f"{suite}: average score by {factor_name}",
                    "path": str(factor_plot_path),
                    "factor": factor_name,
                }
            )
    return plots


def _write_horizontal_bar_chart(
    path: Path,
    *,
    title: str,
    x_label: str,
    items: list[tuple[str, float]],
    x_max: float,
) -> None:
    width = 960
    left = 300
    right = 60
    top = 70
    bottom = 60
    bar_height = 22
    gap = 14
    plot_width = width - left - right
    height = top + bottom + len(items) * (bar_height + gap)
    x_max = max(1.0, x_max)
    ticks = 5

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="white" />',
        f'<text x="{left}" y="30" font-size="20" font-family="monospace" fill="#111">{escape(title)}</text>',
        f'<line x1="{left}" y1="{top - 10}" x2="{left}" y2="{height - bottom}" stroke="#333" stroke-width="1" />',
        f'<line x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}" stroke="#333" stroke-width="1" />',
    ]
    for tick in range(ticks + 1):
        value = (x_max / ticks) * tick
        x = left + (plot_width * tick / ticks)
        lines.append(f'<line x1="{x:.2f}" y1="{top - 10}" x2="{x:.2f}" y2="{height - bottom}" stroke="#e5e7eb" stroke-width="1" />')
        lines.append(
            f'<text x="{x:.2f}" y="{height - bottom + 20}" text-anchor="middle" font-size="12" font-family="monospace" fill="#555">{_format_metric(value)}</text>'
        )
    lines.append(
        f'<text x="{left + plot_width / 2:.2f}" y="{height - 15}" text-anchor="middle" font-size="12" font-family="monospace" fill="#555">{escape(x_label)}</text>'
    )

    for index, (label, value) in enumerate(items):
        y = top + index * (bar_height + gap)
        bar_width = 0.0 if x_max == 0 else (value / x_max) * plot_width
        lines.append(
            f'<text x="{left - 10}" y="{y + 15}" text-anchor="end" font-size="12" font-family="monospace" fill="#111">{escape(label)}</text>'
        )
        lines.append(
            f'<rect x="{left}" y="{y}" width="{bar_width:.2f}" height="{bar_height}" fill="#2563eb" />'
        )
        lines.append(
            f'<text x="{left + bar_width + 8:.2f}" y="{y + 15}" font-size="12" font-family="monospace" fill="#111">{_format_metric(value)}</text>'
        )

    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_scatter_plot(
    path: Path,
    *,
    title: str,
    x_label: str,
    y_label: str,
    points: list[dict[str, float | str]],
    y_max: float,
) -> None:
    width = 960
    height = 640
    left = 90
    right = 40
    top = 70
    bottom = 70
    plot_width = width - left - right
    plot_height = height - top - bottom
    x_max = max(float(point["x"]) for point in points) if points else 1.0
    x_max = max(1.0, x_max * 1.1)
    y_max = max(1.0, y_max)
    ticks = 5

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="white" />',
        f'<text x="{left}" y="30" font-size="20" font-family="monospace" fill="#111">{escape(title)}</text>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height - bottom}" stroke="#333" stroke-width="1" />',
        f'<line x1="{left}" y1="{height - bottom}" x2="{width - right}" y2="{height - bottom}" stroke="#333" stroke-width="1" />',
    ]
    for tick in range(ticks + 1):
        x_value = (x_max / ticks) * tick
        x = left + (plot_width * tick / ticks)
        y_value = (y_max / ticks) * tick
        y = height - bottom - (plot_height * tick / ticks)
        lines.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{height - bottom}" stroke="#e5e7eb" stroke-width="1" />')
        lines.append(f'<line x1="{left}" y1="{y:.2f}" x2="{width - right}" y2="{y:.2f}" stroke="#e5e7eb" stroke-width="1" />')
        lines.append(
            f'<text x="{x:.2f}" y="{height - bottom + 20}" text-anchor="middle" font-size="12" font-family="monospace" fill="#555">{_format_metric(x_value)}</text>'
        )
        lines.append(
            f'<text x="{left - 10}" y="{y + 4:.2f}" text-anchor="end" font-size="12" font-family="monospace" fill="#555">{_format_metric(y_value)}</text>'
        )
    lines.append(
        f'<text x="{left + plot_width / 2:.2f}" y="{height - 15}" text-anchor="middle" font-size="12" font-family="monospace" fill="#555">{escape(x_label)}</text>'
    )
    lines.append(
        f'<text x="20" y="{top + plot_height / 2:.2f}" transform="rotate(-90 20 {top + plot_height / 2:.2f})" text-anchor="middle" font-size="12" font-family="monospace" fill="#555">{escape(y_label)}</text>'
    )

    show_labels = len(points) <= 10
    for point in points:
        x = left + (float(point["x"]) / x_max) * plot_width
        y = height - bottom - (float(point["y"]) / y_max) * plot_height
        label = str(point["label"])
        lines.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="#dc2626"><title>{escape(label)}</title></circle>')
        if show_labels:
            lines.append(
                f'<text x="{x + 8:.2f}" y="{y - 8:.2f}" font-size="11" font-family="monospace" fill="#111">{escape(label)}</text>'
            )

    lines.append("</svg>")
    path.write_text("\n".join(lines), encoding="utf-8")


def _primary_metric(suite: str, metrics: dict[str, Any]) -> tuple[str, str, float | None]:
    if suite == "hdfs":
        value = metrics.get("f1")
        return "f1", _format_metric(value), _float_or_none(value)
    value = metrics.get("pass_rate")
    return "pass_rate", _format_metric(value), _float_or_none(value)


def _dataset_label(summary: dict[str, Any]) -> str:
    settings = summary.get("suite_settings", {})
    suite = summary.get("suite")
    if suite in {"bgl", "bgl_v2"}:
        return str(settings.get("tier", "default"))
    if suite == "hdfs":
        sample_limit = settings.get("sample_limit")
        if sample_limit in {None, 0}:
            return "all"
        return f"limit={sample_limit}"
    return "-"


def _prompt_variant_label(summary: dict[str, Any]) -> str:
    prompt_variants = summary.get("prompt_variants_seen", {})
    if prompt_variants:
        pairs = []
        for role, variants in sorted(prompt_variants.items()):
            pairs.append(f"{role}={','.join(variants)}")
        return "; ".join(pairs)
    resolved_overrides = summary.get("resolved_runtime", {}).get("prompt_overrides", {})
    if resolved_overrides:
        return "; ".join(f"{role}={variant}" for role, variant in sorted(resolved_overrides.items()))
    return "-"


def _matrix_label(matrix_context: dict[str, Any]) -> str:
    name = str(matrix_context.get("name") or "-")
    factors = matrix_context.get("combination") or {}
    if not factors:
        return name
    values = ", ".join(f"{key}={value}" for key, value in sorted(factors.items()))
    return f"{name}: {values}"


def _matrix_factor_names(rows: list[dict[str, Any]]) -> list[str]:
    factor_names = set()
    for row in rows:
        factor_names.update(row.get("matrix_factors", {}))
    return sorted(factor_names)


def _suite_factor_names(rows: list[dict[str, Any]]) -> list[str]:
    factor_names = set()
    for row in rows:
        factor_names.update(row.get("matrix_factors", {}))
    return sorted(factor_names)


def _run_label(row: dict[str, Any]) -> str:
    return str(row.get("name") or row.get("run_id") or "-")


def _metric_axis_label(rows: list[dict[str, Any]]) -> str:
    metric_name = rows[0].get("primary_metric_name", "score")
    return "Pass rate" if metric_name == "pass_rate" else metric_name.upper()


def _metric_axis_max(rows: list[dict[str, Any]]) -> float:
    metric_name = rows[0].get("primary_metric_name", "score")
    if metric_name == "pass_rate":
        return 100.0
    values = [float(row["primary_metric_numeric"]) for row in rows if row["primary_metric_numeric"] is not None]
    if not values:
        return 1.0
    return max(1.0, max(values) * 1.1)


def _slug(text: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in text.lower()).strip("-") or "plot"


def _list_label(values: Any) -> str:
    if not values:
        return "-"
    return ", ".join(str(value) for value in values)


def _format_metric(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def _format_number(value: Any, *, digits: int = 1) -> str:
    if value is None:
        return "-"
    if digits == 0:
        return str(int(round(float(value))))
    return f"{float(value):.{digits}f}"


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
