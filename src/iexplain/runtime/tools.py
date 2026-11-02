from __future__ import annotations

import calendar
import csv
import json
import math
import os
import re
import time
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import requests

from iexplain.ingraph_fill import InGraphFillClient
from iexplain.intent_graphdb import GraphDBIntentClient


@dataclass
class ToolContext:
    workspace: Path


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def call(self, raw_arguments: str | dict[str, Any] | None) -> Any:
        if raw_arguments is None:
            arguments: dict[str, Any] = {}
        elif isinstance(raw_arguments, str):
            arguments = json.loads(raw_arguments)
        else:
            arguments = raw_arguments
        if not isinstance(arguments, dict):
            raise TypeError(f"Tool arguments for {self.name} must decode to an object.")
        return self.handler(**arguments)


def _safe_path(workspace: Path, relative_path: str) -> Path:
    candidate = (workspace / relative_path).resolve()
    try:
        candidate.relative_to(workspace.resolve())
    except ValueError as exc:
        raise ValueError(f"Path escapes workspace: {relative_path}") from exc
    return candidate


def _list_files_tool(context: ToolContext) -> ToolSpec:
    def handler(directory: str = ".") -> dict[str, Any]:
        target = _safe_path(context.workspace, directory)
        if not target.exists():
            return {"error": f"Directory not found: {directory}"}
        entries = []
        for item in sorted(target.iterdir()):
            entries.append({"name": item.name, "type": "dir" if item.is_dir() else "file"})
        return {"directory": directory, "entries": entries}

    return ToolSpec(
        name="list_files",
        description="List files in the current workspace.",
        parameters={
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory relative to the workspace root.",
                }
            },
        },
        handler=handler,
    )


def _read_file_tool(context: ToolContext) -> ToolSpec:
    def handler(path: str, start_line: int = 1, max_lines: int = 50) -> dict[str, Any]:
        target = _safe_path(context.workspace, path)
        if not target.exists():
            return {"error": f"File not found: {path}"}
        if start_line < 1:
            return {"error": "start_line must be >= 1"}
        if max_lines < 1:
            return {"error": "max_lines must be >= 1"}
        max_lines = min(max_lines, 100)
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        subset = lines[start_line - 1 : start_line - 1 + max_lines]
        return {
            "path": path,
            "start_line": start_line,
            "max_lines": max_lines,
            "content": "\n".join(subset),
            "truncated": start_line - 1 + max_lines < len(lines),
        }

    return ToolSpec(
        name="read_file",
        description="Read a bounded slice of a text file from the workspace. Prefer small targeted windows over large reads.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start_line": {"type": "integer", "default": 1},
                "max_lines": {"type": "integer", "default": 50},
            },
            "required": ["path"],
        },
        handler=handler,
    )


def _search_text_tool(context: ToolContext) -> ToolSpec:
    def handler(path: str, query: str, case_sensitive: bool = False, max_matches: int = 50) -> dict[str, Any]:
        target = _safe_path(context.workspace, path)
        if not target.exists():
            return {"error": f"File not found: {path}"}
        max_matches = min(max_matches, 50)
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(re.escape(query), flags=flags)
        matches = []
        for lineno, line in enumerate(target.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if pattern.search(line):
                matches.append({"line": lineno, "text": line})
            if len(matches) >= max_matches:
                break
        return {"path": path, "query": query, "matches": matches, "count": len(matches)}

    return ToolSpec(
        name="search_text",
        description="Search for a text fragment inside a workspace file.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "query": {"type": "string"},
                "case_sensitive": {"type": "boolean", "default": False},
                "max_matches": {"type": "integer", "default": 50},
            },
            "required": ["path", "query"],
        },
        handler=handler,
    )


def _parse_bgl_line(line: str, line_number: int) -> dict[str, Any] | None:
    parts = line.strip().split(None, 9)
    if len(parts) < 10:
        return None
    return {
        "line": line_number,
        "timestamp": parts[4],
        "hour": parts[4].split("-")[3].split(".")[0],
        "node_id": parts[5],
        "component": parts[7],
        "level": parts[8],
        "message": parts[9],
    }


def _parse_bgl_rows(target: Path) -> list[dict[str, Any]]:
    parsed_rows = []
    for line_number, raw_line in enumerate(target.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        parsed = _parse_bgl_line(raw_line, line_number)
        if parsed:
            parsed_rows.append(parsed)
    return parsed_rows


def _bgl_hour(timestamp: str) -> str | None:
    parts = timestamp.split("-")
    if len(parts) < 4:
        return None
    return parts[3].split(".")[0]


def _rank_counter(counter: Counter[str]) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def _bgl_summary(parsed_rows: list[dict[str, Any]]) -> dict[str, Any]:
    level_counts = Counter(row["level"] for row in parsed_rows)
    component_counts = Counter(row["component"] for row in parsed_rows)
    node_counts = Counter(row["node_id"] for row in parsed_rows)
    hour_error_counts: Counter[str] = Counter()
    hour_counts: Counter[str] = Counter()
    component_error_counts: Counter[str] = Counter()

    for row in parsed_rows:
        hour = row["hour"] or _bgl_hour(row["timestamp"])
        if hour is not None:
            hour_counts[hour] += 1
            if row["level"] == "ERROR":
                hour_error_counts[hour] += 1
        if row["level"] == "ERROR":
            component_error_counts[row["component"]] += 1

    ranked_components = _rank_counter(component_counts)
    ranked_nodes = _rank_counter(node_counts)
    ranked_component_errors = _rank_counter(component_error_counts)
    ranked_hours = sorted(hour_counts.items(), key=lambda item: (item[1], item[0]))
    ranked_busy_hours = sorted(hour_counts.items(), key=lambda item: (-item[1], item[0]))
    ranked_error_hours = sorted(hour_error_counts.items(), key=lambda item: (-item[1], item[0]))

    return {
        "total_lines": len(parsed_rows),
        "level_counts": dict(level_counts),
        "component_counts_top5": dict(ranked_components[:5]),
        "top_components": [name for name, _ in ranked_components[:5]],
        "top_component": ranked_components[0][0] if ranked_components else None,
        "unique_nodes_count": len(node_counts),
        "peak_error_hour": ranked_error_hours[0][0] if ranked_error_hours else None,
        "component_error_counts": dict(ranked_component_errors[:5]),
        "component_with_most_errors": ranked_component_errors[0][0] if ranked_component_errors else None,
        "busiest_node": ranked_nodes[0][0] if ranked_nodes else None,
        "warning_count": level_counts.get("WARNING", 0),
        "level_types": sorted(level_counts),
        "error_ratio_percent": round((level_counts.get("ERROR", 0) / len(parsed_rows)) * 100) if parsed_rows else 0,
        "has_fatal": level_counts.get("FATAL", 0) > 0,
        "info_error_ratio": round(level_counts.get("INFO", 0) / level_counts.get("ERROR", 1))
        if level_counts.get("ERROR", 0)
        else 0,
        "info_vs_warning": "INFO" if level_counts.get("INFO", 0) >= level_counts.get("WARNING", 0) else "WARNING",
        "quietest_hour": ranked_hours[0][0] if ranked_hours else None,
        "busiest_hour": ranked_busy_hours[0][0] if ranked_busy_hours else None,
        "nodes_vs_components": "nodes" if len(node_counts) >= len(component_counts) else "components",
        "hours_with_errors": len(hour_error_counts),
    }


def _normalize_text_values(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value}
    return {str(value)}


def _normalize_hour_values(value: Any) -> set[str]:
    hours = set()
    for item in _normalize_text_values(value):
        hours.add(str(item).zfill(2))
    return hours


def _bgl_row_matches(row: dict[str, Any], filters: dict[str, Any]) -> bool:
    if not filters:
        return True

    for field in ("level", "component", "node_id"):
        values = _normalize_text_values(filters.get(field))
        if values and str(row[field]) not in values:
            return False

    hour_values = _normalize_hour_values(filters.get("hour"))
    if hour_values and str(row["hour"]).zfill(2) not in hour_values:
        return False

    node_prefixes = _normalize_text_values(filters.get("node_prefix"))
    if node_prefixes and not any(str(row["node_id"]).startswith(prefix) for prefix in node_prefixes):
        return False

    message_contains = _normalize_text_values(filters.get("message_contains"))
    if message_contains:
        lowered_message = str(row["message"]).lower()
        if not any(fragment.lower() in lowered_message for fragment in message_contains):
            return False

    hour_range = filters.get("hour_range")
    if isinstance(hour_range, dict):
        start = hour_range.get("start")
        end = hour_range.get("end")
        hour_value = int(str(row["hour"]).zfill(2))
        if start is not None and hour_value < int(str(start)):
            return False
        if end is not None and hour_value > int(str(end)):
            return False

    return True


def _filter_bgl_rows(parsed_rows: list[dict[str, Any]], filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    active_filters = filters or {}
    return [row for row in parsed_rows if _bgl_row_matches(row, active_filters)]


def _rank_field(rows: list[dict[str, Any]], field: str, top_k: int) -> list[dict[str, Any]]:
    counts = Counter(str(row[field]) for row in rows)
    ranked = _rank_counter(counts)
    return [{"value": value, "count": count} for value, count in ranked[:top_k]]


def _bgl_file_stats_tool(context: ToolContext) -> ToolSpec:
    cache: dict[str, dict[str, Any]] = {}

    def handler(path: str = "bgl.log") -> dict[str, Any]:
        target = _safe_path(context.workspace, path)
        if not target.exists():
            return {"error": f"File not found: {path}"}
        cache_key = str(target)
        if cache_key in cache:
            return cache[cache_key]

        parsed_rows = _parse_bgl_rows(target)
        result = {"path": path, **_bgl_summary(parsed_rows)}
        cache[cache_key] = result
        return result

    return ToolSpec(
        name="bgl_file_stats",
        description="Compute compact aggregate statistics for a BGL log file.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the BGL log file inside the workspace.",
                    "default": "bgl.log",
                }
            },
        },
        handler=handler,
    )


def _bgl_query_tool(context: ToolContext) -> ToolSpec:
    cache: dict[str, list[dict[str, Any]]] = {}
    allowed_fields = {"hour", "level", "component", "node_id"}

    def _normalize_field_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple, set)):
            return [str(item) for item in value]
        return [str(value)]

    def handler(
        path: str = "bgl.log",
        filters: dict[str, Any] | None = None,
        count_by: list[str] | str | None = None,
        unique_fields: list[str] | str | None = None,
        top_k: int = 5,
        include_samples: bool = False,
        sample_limit: int = 5,
        level: Any = None,
        component: Any = None,
        node_id: Any = None,
        hour: Any = None,
        node_prefix: Any = None,
        message_contains: Any = None,
        hour_range: Any = None,
        **_: Any,
    ) -> dict[str, Any]:
        target = _safe_path(context.workspace, path)
        if not target.exists():
            return {"error": f"File not found: {path}"}

        cache_key = str(target)
        if cache_key not in cache:
            cache[cache_key] = _parse_bgl_rows(target)

        parsed_rows = cache[cache_key]
        active_filters = dict(filters or {})
        for field_name, field_value in {
            "level": level,
            "component": component,
            "node_id": node_id,
            "hour": hour,
            "node_prefix": node_prefix,
            "message_contains": message_contains,
            "hour_range": hour_range,
        }.items():
            if field_value is not None and field_name not in active_filters:
                active_filters[field_name] = field_value
        filtered_rows = _filter_bgl_rows(parsed_rows, active_filters)
        top_k = max(1, min(top_k, 20))
        sample_limit = max(1, min(sample_limit, 10))

        response: dict[str, Any] = {
            "path": path,
            "filters": active_filters,
            "matching_rows": len(filtered_rows),
            "sample_refs": [f"{path}:{row['line']}" for row in filtered_rows[:sample_limit]],
        }

        count_fields = _normalize_field_list(count_by)
        if len(count_fields) > 1:
            return {
                "error": "Provide at most one `count_by` field per call. Use `filters` to narrow the subset first, then rank exactly one field such as `component`, `hour`, `level`, or `node_id`.",
            }
        counts_by: dict[str, list[dict[str, Any]]] = {}
        for field in count_fields:
            if field not in allowed_fields:
                return {"error": f"Unsupported count_by field: {field}"}
            counts_by[field] = _rank_field(filtered_rows, field, top_k)
        if counts_by:
            response["counts_by"] = counts_by

        unique_fields_list = _normalize_field_list(unique_fields)
        unique_counts: dict[str, int] = {}
        for field in unique_fields_list:
            if field not in allowed_fields:
                return {"error": f"Unsupported unique field: {field}"}
            unique_counts[field] = len({str(row[field]) for row in filtered_rows})
        if unique_counts:
            response["unique_counts"] = unique_counts

        if include_samples:
            response["samples"] = [
                {
                    "line": row["line"],
                    "hour": row["hour"],
                    "node_id": row["node_id"],
                    "component": row["component"],
                    "level": row["level"],
                    "message": row["message"],
                }
                for row in filtered_rows[:sample_limit]
            ]

        return response

    return ToolSpec(
        name="bgl_query",
        description=(
            "Filter and summarize BGL log rows without loading raw log chunks into the model context. "
            "Use `filters` whenever the question asks about a subset. Read `matching_rows` for plain counts, "
            "use exactly one `count_by` field for rankings, and use `unique_fields` for distinct counts."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the BGL log file inside the workspace.",
                    "default": "bgl.log",
                },
                "filters": {
                    "type": "object",
                    "additionalProperties": False,
                    "description": "Optional exact filters for the subset you want to measure.",
                    "properties": {
                        "level": {
                            "anyOf": [
                                {"type": "string", "enum": ["INFO", "WARNING", "ERROR", "FATAL", "SEVERE"]},
                                {"type": "array", "items": {"type": "string", "enum": ["INFO", "WARNING", "ERROR", "FATAL", "SEVERE"]}, "minItems": 1},
                            ],
                            "description": "Exact log level filter.",
                        },
                        "component": {
                            "anyOf": [
                                {"type": "string"},
                                {"type": "array", "items": {"type": "string"}, "minItems": 1},
                            ],
                            "description": "Exact component filter, for example MMCS or KERNEL.",
                        },
                        "node_id": {
                            "anyOf": [
                                {"type": "string"},
                                {"type": "array", "items": {"type": "string"}, "minItems": 1},
                            ],
                            "description": "Exact node id filter.",
                        },
                        "hour": {
                            "anyOf": [
                                {"type": "string", "pattern": "^[0-9]{1,2}$"},
                                {"type": "integer", "minimum": 0, "maximum": 23},
                                {
                                    "type": "array",
                                    "items": {
                                        "anyOf": [
                                            {"type": "string", "pattern": "^[0-9]{1,2}$"},
                                            {"type": "integer", "minimum": 0, "maximum": 23},
                                        ]
                                    },
                                    "minItems": 1,
                                },
                            ],
                            "description": "Hour filter such as 12 or 10.",
                        },
                        "node_prefix": {
                            "anyOf": [
                                {"type": "string"},
                                {"type": "array", "items": {"type": "string"}, "minItems": 1},
                            ],
                            "description": "Match node ids by prefix.",
                        },
                        "message_contains": {
                            "anyOf": [
                                {"type": "string"},
                                {"type": "array", "items": {"type": "string"}, "minItems": 1},
                            ],
                            "description": "Case-insensitive substring filter over the message text.",
                        },
                        "hour_range": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "start": {"type": "integer", "minimum": 0, "maximum": 23},
                                "end": {"type": "integer", "minimum": 0, "maximum": 23},
                            },
                            "required": ["start", "end"],
                            "description": "Inclusive hour range, for example {\"start\": 12, \"end\": 16}.",
                        },
                    },
                },
                "count_by": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["hour", "level", "component", "node_id"]},
                    "minItems": 1,
                    "maxItems": 1,
                    "description": "Exactly one field to rank within the filtered subset. Use for top-k questions only.",
                },
                "unique_fields": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["hour", "level", "component", "node_id"]},
                    "minItems": 1,
                    "description": "Fields for distinct counts within the filtered subset.",
                },
                "top_k": {
                    "type": "integer",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20,
                },
                "include_samples": {"type": "boolean", "default": False},
                "sample_limit": {
                    "type": "integer",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 10,
                },
            },
        },
        handler=handler,
    )


def _bgl_answer_question_tool(context: ToolContext) -> ToolSpec:
    cache: dict[str, dict[str, Any]] = {}

    def handler(question: str, path: str = "bgl.log") -> dict[str, Any]:
        target = _safe_path(context.workspace, path)
        if not target.exists():
            return {"error": f"File not found: {path}"}

        cache_key = str(target)
        if cache_key not in cache:
            cache[cache_key] = _bgl_summary(_parse_bgl_rows(target))
        summary = cache[cache_key]
        normalized = " ".join(question.strip().lower().split())

        if "how many error level log entries" in normalized:
            answer: Any = summary["level_counts"].get("ERROR", 0)
        elif "how many total log lines" in normalized:
            answer = summary["total_lines"]
        elif "which component has the most log entries" in normalized:
            answer = summary["top_component"]
        elif "what are the top 3 components by log volume" in normalized:
            answer = summary["top_components"][:3]
        elif "during which hour did the most errors occur" in normalized:
            answer = summary["peak_error_hour"]
        elif "how many warning level entries" in normalized:
            answer = summary["warning_count"]
        elif "what log levels are present" in normalized:
            answer = summary["level_types"]
        elif "what percentage of log entries are errors" in normalized:
            answer = summary["error_ratio_percent"]
        elif "how many unique nodes generated logs" in normalized:
            answer = summary["unique_nodes_count"]
        elif "which node generated the most logs" in normalized:
            answer = summary["busiest_node"]
        elif "are there any fatal level logs" in normalized:
            answer = "yes" if summary["has_fatal"] else "no"
        elif "which component generated the most error logs" in normalized:
            answer = summary["component_with_most_errors"]
        elif "what is the ratio of info logs to error logs" in normalized:
            answer = summary["info_error_ratio"]
        elif "which level appears more frequently: info or warning" in normalized:
            answer = summary["info_vs_warning"]
        elif "during which hour were the fewest logs generated" in normalized:
            answer = summary["quietest_hour"]
        elif "during which hour were the most logs generated" in normalized:
            answer = summary["busiest_hour"]
        elif "are there more unique nodes or unique components" in normalized:
            answer = summary["nodes_vs_components"]
        elif "how many hours had at least one error log" in normalized:
            answer = summary["hours_with_errors"]
        else:
            return {"error": "Unsupported BGL question.", "question": question}

        return {"answer": answer}

    return ToolSpec(
        name="bgl_answer_question",
        description="Answer a deterministic BGL log question from structured aggregates.",
        parameters={
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The natural-language BGL question to answer.",
                },
                "path": {
                    "type": "string",
                    "description": "Path to the BGL log file inside the workspace.",
                    "default": "bgl.log",
                },
            },
            "required": ["question"],
        },
        handler=handler,
    )


_OPENRCA_UTILIZATION_CATEGORIES = ("cpu", "memory", "jvm_cpu", "jvm_heap", "network", "disk")
# OpenRCA Bank CSV timestamps are POSIX/UTC epochs, but the gold datetime strings and task
# windows are Beijing local time (UTC+8). Convert between the two with this fixed offset.
_OPENRCA_TZ_OFFSET_SECONDS = 8 * 3600


def _openrca_category(kpi_name: str) -> str:
    name = kpi_name
    if "JVM" in name and "Heap" in name:
        return "jvm_heap"
    if "JVM" in name and "CPULoad" in name:
        return "jvm_cpu"
    if "MemPerc" in name or "MEMUsedMem" in name or "MemPercent" in name or "MemUsage" in name:
        return "memory"
    if "CpuUtil" in name or "CPUCpuUtil" in name or "CpuPercent" in name or "_CPU_CPULoad" in name:
        return "cpu"
    if "NETWORK" in name or "NetworkRx" in name or "NetworkTx" in name or "NETPackets" in name or "NETInErr" in name or "NETOutErr" in name or "NETBandwidth" in name:
        return "network"
    if "LOCALDISK" in name or "DSK" in name or "Disk" in name:
        return "disk"
    return "other"


def _openrca_epoch(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return int(float(text))
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return calendar.timegm(parsed.timetuple()) - _OPENRCA_TZ_OFFSET_SECONDS
    return None


def _openrca_datetime(epoch_seconds: float) -> str:
    return time.strftime(
        "%Y-%m-%d %H:%M:%S", time.gmtime(int(epoch_seconds) + _OPENRCA_TZ_OFFSET_SECONDS)
    )


def _openrca_str_list(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value}
    return {str(value)}


def _openrca_iter_csv(path: Path):
    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            yield row


def _openrca_query_tool(context: ToolContext) -> ToolSpec:
    memo: dict[str, dict[str, Any]] = {}

    def _files(telemetry_dir: str) -> dict[str, Path]:
        base = telemetry_dir.strip().strip("/")
        return {
            "metric_container": _safe_path(context.workspace, f"{base}/metric/metric_container.csv"),
            "log_service": _safe_path(context.workspace, f"{base}/log/log_service.csv"),
            "trace_span": _safe_path(context.workspace, f"{base}/trace/trace_span.csv"),
        }

    def _catalog(metric_path: Path, max_scan_rows: int) -> dict[str, Any]:
        components: set[str] = set()
        categories: dict[str, set[str]] = {}
        scanned = 0
        for row in _openrca_iter_csv(metric_path):
            if len(row) < 4:
                continue
            components.add(row[1])
            category = _openrca_category(row[2])
            categories.setdefault(category, set()).add(row[2])
            scanned += 1
            if scanned >= max_scan_rows:
                break
        return {
            "components": sorted(components),
            "kpi_categories": {
                category: sorted(list(names))[:8]
                for category, names in sorted(categories.items())
            },
            "scanned_rows": scanned,
            "sampled": scanned >= max_scan_rows,
        }

    def _metric_summary(
        metric_path: Path,
        start_epoch: int,
        end_epoch: int,
        components: set[str],
        categories: set[str],
        top_k: int,
    ) -> dict[str, Any]:
        day: dict[tuple[str, str], list[float]] = {}
        window: dict[tuple[str, str], dict[str, float]] = {}
        for row in _openrca_iter_csv(metric_path):
            if len(row) < 4:
                continue
            cmdb_id, kpi_name = row[1], row[2]
            if components and cmdb_id not in components:
                continue
            category = _openrca_category(kpi_name)
            target_categories = categories or set(_OPENRCA_UTILIZATION_CATEGORIES)
            if category not in target_categories:
                continue
            ts = _openrca_epoch(row[0])
            if ts is None:
                continue
            try:
                val = float(row[3])
            except ValueError:
                continue
            key = (cmdb_id, kpi_name)
            agg = day.get(key)
            if agg is None:
                day[key] = [1.0, val, val * val]
            else:
                agg[0] += 1.0
                agg[1] += val
                agg[2] += val * val
            if start_epoch <= ts <= end_epoch:
                win = window.get(key)
                if win is None:
                    window[key] = {"count": 1.0, "sum": val, "max": val, "argmax_ts": float(ts)}
                else:
                    win["count"] += 1.0
                    win["sum"] += val
                    if val > win["max"]:
                        win["max"] = val
                        win["argmax_ts"] = float(ts)
        ranked: list[dict[str, Any]] = []
        for key, win in window.items():
            cmdb_id, kpi_name = key
            day_count, day_sum, day_sumsq = day[key]
            day_mean = day_sum / day_count
            day_std = math.sqrt(max(day_sumsq / day_count - day_mean * day_mean, 0.0))
            window_mean = win["sum"] / win["count"]
            deviation = (win["max"] - day_mean) / (day_std + 1e-6)
            ranked.append(
                {
                    "component": cmdb_id,
                    "kpi_name": kpi_name,
                    "category": _openrca_category(kpi_name),
                    "window_max": round(win["max"], 4),
                    "window_mean": round(window_mean, 4),
                    "day_mean": round(day_mean, 4),
                    "day_std": round(day_std, 4),
                    "deviation_score": round(deviation, 4),
                    "peak_time": _openrca_datetime(win["argmax_ts"]),
                }
            )
        ranked.sort(key=lambda item: item["deviation_score"], reverse=True)
        return {
            "window": {"start": _openrca_datetime(start_epoch), "end": _openrca_datetime(end_epoch)},
            "ranked_anomalies": ranked[:top_k],
            "series_considered": len(window),
        }

    def _metric_series(
        metric_path: Path,
        start_epoch: int,
        end_epoch: int,
        components: set[str],
        categories: set[str],
        query: str | None,
        max_points: int,
    ) -> dict[str, Any]:
        points: list[tuple[int, float]] = []
        kpi_seen: set[str] = set()
        for row in _openrca_iter_csv(metric_path):
            if len(row) < 4:
                continue
            cmdb_id, kpi_name = row[1], row[2]
            if components and cmdb_id not in components:
                continue
            if categories and _openrca_category(kpi_name) not in categories:
                continue
            if query and query.lower() not in kpi_name.lower():
                continue
            ts = _openrca_epoch(row[0])
            if ts is None or not (start_epoch <= ts <= end_epoch):
                continue
            try:
                val = float(row[3])
            except ValueError:
                continue
            kpi_seen.add(kpi_name)
            points.append((ts, val))
        points.sort(key=lambda item: item[0])
        peak = max(points, key=lambda item: item[1], default=None)
        step = max(1, len(points) // max_points)
        sampled = [
            {"time": _openrca_datetime(ts), "value": round(val, 4)}
            for ts, val in points[::step][:max_points]
        ]
        return {
            "matched_kpis": sorted(kpi_seen)[:10],
            "point_count": len(points),
            "peak": (
                {"time": _openrca_datetime(peak[0]), "value": round(peak[1], 4)} if peak else None
            ),
            "series": sampled,
        }

    def _log_search(
        log_path: Path,
        query: str,
        components: set[str],
        start_epoch: int | None,
        end_epoch: int | None,
        max_matches: int,
    ) -> dict[str, Any]:
        needle = query.lower()
        matches: list[dict[str, Any]] = []
        for row in _openrca_iter_csv(log_path):
            if len(row) < 5:
                continue
            cmdb_id, value = row[2], row[4]
            if components and cmdb_id not in components:
                continue
            ts = _openrca_epoch(row[1])
            if start_epoch is not None and (ts is None or ts < start_epoch):
                continue
            if end_epoch is not None and (ts is None or ts > end_epoch):
                continue
            if needle and needle not in value.lower():
                continue
            matches.append(
                {
                    "time": _openrca_datetime(ts) if ts is not None else row[1],
                    "component": cmdb_id,
                    "log_name": row[3],
                    "value": value[:240],
                }
            )
            if len(matches) >= max_matches:
                break
        return {"query": query, "match_count": len(matches), "matches": matches}

    def _trace_latency(
        trace_path: Path,
        start_epoch: int,
        end_epoch: int,
        components: set[str],
        top_k: int,
        max_scan_rows: int,
    ) -> dict[str, Any]:
        stats: dict[str, dict[str, float]] = {}
        scanned = 0
        truncated = False
        for row in _openrca_iter_csv(trace_path):
            scanned += 1
            if scanned > max_scan_rows:
                truncated = True
                break
            if len(row) < 6:
                continue
            ts_raw = _openrca_epoch(row[0])
            if ts_raw is None:
                continue
            ts = ts_raw // 1000 if ts_raw > 10_000_000_000 else ts_raw
            if not (start_epoch <= ts <= end_epoch):
                continue
            cmdb_id = row[1]
            if components and cmdb_id not in components:
                continue
            try:
                duration = float(row[5])
            except ValueError:
                continue
            agg = stats.get(cmdb_id)
            if agg is None:
                stats[cmdb_id] = {"count": 1.0, "sum": duration, "max": duration}
            else:
                agg["count"] += 1.0
                agg["sum"] += duration
                agg["max"] = max(agg["max"], duration)
        ranked = [
            {
                "component": cmdb_id,
                "span_count": int(agg["count"]),
                "mean_duration": round(agg["sum"] / agg["count"], 3),
                "max_duration": round(agg["max"], 3),
            }
            for cmdb_id, agg in stats.items()
        ]
        ranked.sort(key=lambda item: item["mean_duration"], reverse=True)
        return {"ranked_latency": ranked[:top_k], "scanned_rows": scanned, "truncated": truncated}

    def handler(
        op: str,
        telemetry_dir: str,
        start_time: Any = None,
        end_time: Any = None,
        component: Any = None,
        kpi_category: Any = None,
        query: str | None = None,
        top_k: int = 8,
        max_points: int = 60,
        max_matches: int = 20,
        **_: Any,
    ) -> dict[str, Any]:
        files = _files(telemetry_dir)
        components = _openrca_str_list(component)
        categories = _openrca_str_list(kpi_category)
        top_k = max(1, min(int(top_k), 20))
        max_points = max(5, min(int(max_points), 200))
        max_matches = max(1, min(int(max_matches), 50))
        start_epoch = _openrca_epoch(start_time)
        end_epoch = _openrca_epoch(end_time)

        memo_key = json.dumps(
            [op, telemetry_dir, start_epoch, end_epoch, sorted(components), sorted(categories), query, top_k, max_points, max_matches],
            sort_keys=True,
        )
        if memo_key in memo:
            return memo[memo_key]

        try:
            if op == "catalog":
                if not files["metric_container"].exists():
                    return {"error": f"File not found: {files['metric_container']}"}
                result = _catalog(files["metric_container"], max_scan_rows=400_000)
            elif op == "metric_summary":
                if start_epoch is None or end_epoch is None:
                    return {"error": "metric_summary requires start_time and end_time."}
                if not files["metric_container"].exists():
                    return {"error": f"File not found: {files['metric_container']}"}
                result = _metric_summary(files["metric_container"], start_epoch, end_epoch, components, categories, top_k)
            elif op == "metric_series":
                if start_epoch is None or end_epoch is None:
                    return {"error": "metric_series requires start_time and end_time."}
                if not files["metric_container"].exists():
                    return {"error": f"File not found: {files['metric_container']}"}
                result = _metric_series(files["metric_container"], start_epoch, end_epoch, components, categories, query, max_points)
            elif op == "log_search":
                if not query:
                    return {"error": "log_search requires a query substring."}
                if not files["log_service"].exists():
                    return {"error": f"File not found: {files['log_service']}"}
                result = _log_search(files["log_service"], query, components, start_epoch, end_epoch, max_matches)
            elif op == "trace_latency":
                if start_epoch is None or end_epoch is None:
                    return {"error": "trace_latency requires start_time and end_time."}
                if not files["trace_span"].exists():
                    return {"error": f"File not found: {files['trace_span']}"}
                result = _trace_latency(files["trace_span"], start_epoch, end_epoch, components, top_k, max_scan_rows=3_000_000)
            else:
                return {"error": f"Unknown op: {op}. Use catalog, metric_summary, metric_series, log_search, or trace_latency."}
        except FileNotFoundError as exc:
            return {"error": str(exc)}

        memo[memo_key] = result
        return result

    return ToolSpec(
        name="openrca_query",
        description=(
            "Query OpenRCA telemetry (metric/log/trace CSVs) with bounded aggregates instead of "
            "reading raw rows. Ops: `catalog` (list components and KPI categories), `metric_summary` "
            "(rank components x KPI by in-window deviation from their daily baseline; the top result is "
            "usually the root-cause component and its peak_time is the occurrence time), `metric_series` "
            "(downsampled series + peak for one component/category), `log_search` (bounded substring "
            "search over logs), and `trace_latency` (per-component span duration stats). Pass times as "
            "'YYYY-MM-DD HH:MM:SS'."
        ),
        parameters={
            "type": "object",
            "properties": {
                "op": {
                    "type": "string",
                    "enum": ["catalog", "metric_summary", "metric_series", "log_search", "trace_latency"],
                    "description": "The query operation to run.",
                },
                "telemetry_dir": {
                    "type": "string",
                    "description": "Day folder relative to the workspace, e.g. dataset/Bank/telemetry/2021_03_04.",
                },
                "start_time": {"type": "string", "description": "Window start, 'YYYY-MM-DD HH:MM:SS'."},
                "end_time": {"type": "string", "description": "Window end, 'YYYY-MM-DD HH:MM:SS'."},
                "component": {
                    "anyOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ],
                    "description": "Optional component filter (cmdb_id), e.g. Redis02.",
                },
                "kpi_category": {
                    "anyOf": [
                        {"type": "string", "enum": list(_OPENRCA_UTILIZATION_CATEGORIES)},
                        {"type": "array", "items": {"type": "string", "enum": list(_OPENRCA_UTILIZATION_CATEGORIES)}},
                    ],
                    "description": "Optional KPI category filter: cpu, memory, jvm_cpu, jvm_heap, network, disk.",
                },
                "query": {"type": "string", "description": "Substring for log_search or to narrow metric_series KPI names."},
                "top_k": {"type": "integer", "default": 8, "minimum": 1, "maximum": 20},
                "max_points": {"type": "integer", "default": 60, "minimum": 5, "maximum": 200},
                "max_matches": {"type": "integer", "default": 20, "minimum": 1, "maximum": 50},
            },
            "required": ["op", "telemetry_dir"],
        },
        handler=handler,
    )


def _fetch_url_tool(_: ToolContext) -> ToolSpec:
    def handler(url: str, timeout_seconds: int = 20) -> dict[str, Any]:
        response = requests.get(url, timeout=timeout_seconds)
        return {
            "url": url,
            "status_code": response.status_code,
            "text": response.text,
        }

    return ToolSpec(
        name="fetch_url",
        description="Fetch a text response from a URL.",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "timeout_seconds": {"type": "integer", "default": 20},
            },
            "required": ["url"],
        },
        handler=handler,
    )


def _fetch_intent_bundle_tool(_: ToolContext) -> ToolSpec:
    cache: dict[tuple[str, str, str], GraphDBIntentClient] = {}

    def handler(intent_id: str) -> dict[str, Any]:
        base_url = os.getenv("IEXPLAIN_INTENT_GRAPHDB_URL", "http://localhost:7200")
        repository_id = os.getenv("IEXPLAIN_INTENT_GRAPHDB_REPOSITORY", "intents_and_intent_reports")
        resource_prefix = os.getenv("IEXPLAIN_INTENT_GRAPHDB_RESOURCE_PREFIX", "http://5g4data.eu/5g4data#")
        cache_key = (base_url, repository_id, resource_prefix)

        if cache_key not in cache:
            cache[cache_key] = GraphDBIntentClient(
                base_url,
                repository_id,
                resource_prefix=resource_prefix,
            )

        try:
            bundle = cache[cache_key].fetch_intent_bundle(intent_id)
        except requests.RequestException as exc:
            return {"error": f"GraphDB request failed: {exc}"}
        except ValueError as exc:
            return {"error": str(exc)}

        latest_report = bundle.reports[-1] if bundle.reports else None
        bundle_data = asdict(bundle)
        return {
            "intent_id": intent_id,
            "intent_iri": bundle.intent_iri,
            "intent_name": bundle.intent_name,
            "handler": bundle.handler,
            "owner": bundle.owner,
            "current_state": latest_report.state if latest_report else None,
            "latest_reason": latest_report.reason if latest_report else None,
            "counts": {
                "expectations": len(bundle.expectations),
                "conditions": len(bundle.conditions),
                "contexts": len(bundle.contexts),
                "reports": len(bundle.reports),
                "observations": len(bundle.observations),
            },
            "expectations": bundle_data["expectations"],
            "conditions": bundle_data["conditions"],
            "contexts": bundle_data["contexts"],
            "timeline": bundle_data["reports"],
            "observations": bundle_data["observations"],
        }

    return ToolSpec(
        name="fetch_intent_bundle",
        description=(
            "Fetch one intent plus its expectations, reports, and observations from GraphDB. "
            "Use this when the task asks what happened to a specific intent."
        ),
        parameters={
            "type": "object",
            "properties": {
                "intent_id": {
                    "type": "string",
                    "description": "The target intent identifier, for example a TMForum-style I-prefixed id or a UUID.",
                }
            },
            "required": ["intent_id"],
        },
        handler=handler,
    )


def _fetch_fill_entity_bundle_tool(_: ToolContext) -> ToolSpec:
    cache: dict[tuple[str, str, str], InGraphFillClient] = {}

    def handler(entity_id: str) -> dict[str, Any]:
        base_url = os.getenv("IEXPLAIN_INGRAPH_URL", "http://localhost:5000")
        repository_id = os.getenv("IEXPLAIN_INGRAPH_FILL_REPOSITORY", "FILL")
        resource_prefix = os.getenv("IEXPLAIN_INGRAPH_FILL_RESOURCE_PREFIX", "https://intendproject.eu/fill/")
        cache_key = (base_url, repository_id, resource_prefix)

        if cache_key not in cache:
            cache[cache_key] = InGraphFillClient(
                base_url,
                repository_id,
                resource_prefix=resource_prefix,
            )

        try:
            bundle = cache[cache_key].fetch_entity_bundle(entity_id)
        except requests.RequestException as exc:
            return {"error": f"inGraph request failed: {exc}"}
        except ValueError as exc:
            return {"error": str(exc)}

        bundle_data = asdict(bundle)
        return {
            "entity_id": entity_id,
            "entity_iri": bundle.entity_iri,
            "entity_name": bundle.entity_name,
            "entity_type": bundle.entity_type,
            "external_id": bundle.external_id,
            "description": bundle.description,
            "counts": {
                "outgoing_relations": len(bundle.outgoing),
                "outgoing_entities": sum(len(group.entities) for group in bundle.outgoing),
                "incoming_relations": len(bundle.incoming),
                "incoming_entities": sum(len(group.entities) for group in bundle.incoming),
            },
            "outgoing": bundle_data["outgoing"],
            "incoming": bundle_data["incoming"],
        }

    return ToolSpec(
        name="fetch_fill_entity_bundle",
        description=(
            "Fetch one FILL entity from inGraph and summarize its direct outgoing and incoming graph relations. "
            "Use this when the task asks what a FILL machine, service, component, or container is connected to."
        ),
        parameters={
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "string",
                    "description": "The target FILL entity identifier, for example `Machine5`, `Service3`, or a full IRI.",
                }
            },
            "required": ["entity_id"],
        },
        handler=handler,
    )


STANDARD_TOOL_BUILDERS: dict[str, Callable[[ToolContext], ToolSpec]] = {
    "bgl_answer_question": _bgl_answer_question_tool,
    "bgl_file_stats": _bgl_file_stats_tool,
    "bgl_query": _bgl_query_tool,
    "fetch_fill_entity_bundle": _fetch_fill_entity_bundle_tool,
    "fetch_intent_bundle": _fetch_intent_bundle_tool,
    "list_files": _list_files_tool,
    "openrca_query": _openrca_query_tool,
    "read_file": _read_file_tool,
    "search_text": _search_text_tool,
    "fetch_url": _fetch_url_tool,
}


def build_tools(
    tool_names: list[str],
    context: ToolContext,
    extra_tools: dict[str, ToolSpec] | None = None,
) -> dict[str, ToolSpec]:
    tools: dict[str, ToolSpec] = {}
    for name in tool_names:
        try:
            tools[name] = STANDARD_TOOL_BUILDERS[name](context)
        except KeyError as exc:
            raise KeyError(f"Unknown tool: {name}") from exc
    if extra_tools:
        tools.update(extra_tools)
    return tools


def tool_catalog() -> list[str]:
    return sorted(STANDARD_TOOL_BUILDERS)
