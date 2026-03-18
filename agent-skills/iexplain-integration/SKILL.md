---
name: iexplain-integration
description: Delegate explanation work to a running iExplain service or local iexplain CLI. Use when another agent or agentic system needs grounded intent summaries, log explanations, or benchmark-specific analysis without re-implementing iExplain profiles, pipelines, or adapters.
compatibility: Requires access to a running iExplain API or a local environment with the iexplain CLI installed.
metadata:
  owner: iexplain-next
  version: "1"
---

# Purpose

Use this skill when another agent should hand off explanation work to iExplain instead of doing the explanation itself.

Good fits:

- summarize what happened for one intent id
- explain a provided log artifact
- run HDFS anomaly explanation through the existing profile
- answer structured BGL questions through the existing profile

## Preferred path

1. Prefer the HTTP API when available.
2. Discover available profiles first with `GET /api/v1/catalog`.
3. Submit a job with the smallest useful task and artifact set.
4. Poll until completion.
5. Return `result.content` to the caller, and use `result.metadata.trace` only when trace detail is needed.

## Current profile mapping

Treat these as defaults from the current repo config, not as a permanent contract. Prefer discovery from `/api/v1/catalog`.

- `intent_demo`: summarize one TM Forum style intent through GraphDB
- `default`: open-ended artifact inspection and explanation
- `controlled`: two-stage log explanation pipeline
- `autonomous`: planner mode with bounded delegation
- `hdfs_eval`: HDFS anomaly classification and explanation
- `bgl_v2_eval`: structured BGL v2 question answering

## Job pattern

Use a direct job for one-off work.

Send:

- `run.task`: the explanation request
- `run.profile`: chosen profile
- `run.artifacts`: optional inline text artifacts
- `run.metadata`: optional caller metadata

Then poll `GET /api/v1/jobs/{job_id}` until `status` is `completed` or `failed`.

## Session pattern

Use sessions when multiple tasks share the same profile, overrides, or metadata.

Flow:

1. `POST /api/v1/sessions`
2. `POST /api/v1/sessions/{session_id}/tasks`
3. poll the returned `job_id`

## CLI fallback

Use the CLI only when the agent runs on the same machine as iExplain.

Examples:

```bash
iexplain run "Explain what happened in session.log" --profile default --artifact /path/to/session.log

iexplain intent-summary If9587ca040be457d908d54e7aecc2ef6 --profile intent_demo
```

## Important constraints

- Do not hardcode profile names if the API is reachable. Discover them.
- Do not use `source_path` over the API unless the file path exists on the API server.
- Prefer small grounded artifacts over huge raw dumps.
- If the service exposes a benchmark-specific profile, prefer that over a generic profile.

See [the API reference](references/API.md) for request shapes and examples.
