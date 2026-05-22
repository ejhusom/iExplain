from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineStage:
    name: str
    role: str
    task_template: str
    tools: list[str]


PIPELINES: dict[str, list[PipelineStage]] = {
    "log_explanation": [
        PipelineStage(
            name="analysis",
            role="general_analyst",
            tools=["list_files", "read_file", "search_text", "fetch_url"],
            task_template=(
                "Original task:\n{task}\n\n"
                "Workspace artifacts:\n{artifacts}\n\n"
                "Inspect the available artifacts and produce grounded analysis notes.\n"
                "Return markdown with these headings:\n"
                "- Findings\n- Evidence\n- Open questions"
            ),
        ),
        PipelineStage(
            name="report",
            role="log_explainer",
            tools=[],
            task_template=(
                "Original task:\n{task}\n\n"
                "Prior stage outputs:\n{history}\n\n"
                "Produce the final answer.\n"
                "Stay grounded in the prior stage outputs and do not invent evidence."
            ),
        ),
    ],
    "hdfs_anomaly": [
        PipelineStage(
            name="preprocess",
            role="log_preprocessor",
            tools=["read_file"],
            task_template=(
                "Read the HDFS session from `session.log` and normalize it into a concise event list.\n"
                "Original task:\n{task}\n\n"
                "Return only the normalized session."
            ),
        ),
        PipelineStage(
            name="detect",
            role="log_anomaly_detector",
            tools=[],
            task_template=(
                "Original task:\n{task}\n\n"
                "Normalized HDFS session:\n{previous_output}\n\n"
                "Classify the session as normal (0) or anomalous (1).\n"
                "Return JSON with keys `label` and `signals`."
            ),
        ),
        PipelineStage(
            name="explain",
            role="log_explainer",
            tools=[],
            task_template=(
                "Original task:\n{task}\n\n"
                "Prior stage outputs:\n{history}\n\n"
                "Keep the detector label unchanged.\n"
                "Use the detector signals as the basis for the final answer.\n"
                "Return only JSON with keys `label`, `summary`, and `signals`.\n"
                "The `label` must exactly match the detector label.\n"
                "The `summary` must be 1-2 grounded sentences.\n"
                "The `signals` list must contain concise grounded evidence phrases only.\n"
                "Do not return markdown headings, prose sections, or code fences."
            ),
        ),
    ],
    "hdfs_single_pass": [
        PipelineStage(
            name="classify",
            role="log_anomaly_detector",
            tools=["read_file"],
            task_template=(
                "Read the HDFS session from `session.log` and classify it directly.\n"
                "Original task:\n{task}\n\n"
                "Return JSON with keys `label` and `signals`."
            ),
        ),
    ],
    "bgl_question_answering": [
        PipelineStage(
            name="answer",
            role="bgl_qa",
            tools=["bgl_answer_question"],
            task_template=(
                "Use `bgl_answer_question` with the workspace artifact `bgl.log` to answer the question below.\n"
                "Question:\n{task}\n\n"
                "Return only JSON with the shape {{\"answer\": ...}}."
            ),
        ),
    ],
    "bgl_v2_question_answering": [
        PipelineStage(
            name="answer",
            role="bgl_qa",
            tools=["bgl_query", "read_file"],
            task_template=(
                "Use the workspace artifacts to answer the question below.\n"
                "Available artifacts:\n{artifacts}\n\n"
                "Question:\n{task}\n\n"
                "Use `bgl_query` for measurements over `bgl.log`.\n"
                "Use `read_file` only for small supporting artifacts such as `.json`, `.md`, or `.txt`, not for reading `bgl.log`."
            ),
        ),
    ],
    "bgl_v2_raw_text_question_answering": [
        PipelineStage(
            name="answer",
            role="bgl_qa",
            tools=["read_file", "search_text"],
            task_template=(
                "Use the workspace artifacts to answer the question below.\n"
                "Available artifacts:\n{artifacts}\n\n"
                "Question:\n{task}\n\n"
                "You do not have access to structured BGL tools in this configuration.\n"
                "Use `search_text` to locate candidate evidence in `bgl.log` and `read_file` for bounded inspection.\n"
                "Keep tool use disciplined and avoid reading large raw chunks unnecessarily."
            ),
        ),
    ],
    "bgl_v2_summary_question_answering": [
        PipelineStage(
            name="answer",
            role="bgl_qa",
            tools=["bgl_file_stats", "bgl_query", "read_file"],
            task_template=(
                "Use the workspace artifacts to answer the question below.\n"
                "Available artifacts:\n{artifacts}\n\n"
                "Question:\n{task}\n\n"
                "Use `bgl_file_stats` first for broad whole-file aggregates when relevant.\n"
                "Use `bgl_query` for filtered measurements and subset comparisons over `bgl.log`.\n"
                "Use `read_file` only for small supporting artifacts such as `.json`, `.md`, or `.txt`."
            ),
        ),
    ],
    "intent_summary": [
        PipelineStage(
            name="summarize",
            role="log_explainer",
            tools=["fetch_intent_bundle"],
            task_template=(
                "Target task:\n{task}\n\n"
                "Use `fetch_intent_bundle` exactly once with the target intent identifier from the task.\n"
                "Then return markdown with these headings:\n"
                "- Intent\n- Current Status\n- Timeline\n- Evidence\n- Open Questions\n\n"
                "Stay grounded in the fetched bundle. If the data is incomplete, say so explicitly."
            ),
        ),
    ],
    "ingraph_fill_summary": [
        PipelineStage(
            name="summarize",
            role="log_explainer",
            tools=["fetch_fill_entity_bundle"],
            task_template=(
                "Target task:\n{task}\n\n"
                "Use `fetch_fill_entity_bundle` exactly once with the target FILL entity identifier from the task.\n"
                "Then return markdown with these headings:\n"
                "- Entity\n- Direct Relationships\n- Interpretation\n- Open Questions\n\n"
                "Explain what the entity is, what it is directly connected to, and any limitations in the visible neighborhood.\n"
                "Stay grounded in the fetched bundle."
            ),
        ),
    ],
}


def get_pipeline(name: str) -> list[PipelineStage]:
    try:
        return PIPELINES[name]
    except KeyError as exc:
        raise KeyError(f"Unknown pipeline: {name}") from exc
