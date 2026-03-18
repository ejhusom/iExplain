# iExplain Integration Reference

This file describes the current integration surface in this repo.

## Main entry points

Preferred API base:

- `GET /api/v1/health`
- `GET /api/v1/catalog`
- `POST /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/sessions`
- `POST /api/v1/sessions/{session_id}/tasks`

CLI fallback:

- `iexplain run ...`
- `iexplain intent-summary ...`
- `iexplain serve --config config/app.toml`

## Discovery first

Use `GET /api/v1/catalog` before submitting work when possible.

Why:

- profile names come from server config
- available skills and tools may vary by deployment
- prompt overrides and execution modes are server-side concerns

## Direct job example

Use this shape for one-off log explanation:

```json
{
  "run": {
    "task": "Explain what happened in session.log",
    "profile": "default",
    "artifacts": [
      {
        "name": "session.log",
        "content": "2026-03-18T10:15:00Z INFO started\n2026-03-18T10:15:08Z ERROR timeout while writing block"
      }
    ],
    "metadata": {
      "source_tool": "external-agent"
    }
  }
}
```

Completion response fields to read:

- `status`
- `result.content`
- `result.metadata.trace`

## Intent summary example

Use the `intent_demo` profile when the iExplain server is configured for GraphDB access:

```json
{
  "run": {
    "task": "Target intent id: If9587ca040be457d908d54e7aecc2ef6\nSummarize what happened for this intent. Explain the state transitions, the main evidence from intent reports and observations, and mention any missing information.",
    "profile": "intent_demo",
    "metadata": {
      "source_tool": "external-agent",
      "request_type": "intent-summary"
    }
  }
}
```

## Session example

Create a session when you expect repeated tasks with the same profile:

```json
{
  "name": "intent-demo-session",
  "profile": "intent_demo",
  "metadata": {
    "source_tool": "external-agent"
  },
  "overrides": {
    "max_turns": 4
  }
}
```

Then submit tasks to that session:

```json
{
  "task": "Summarize what happened for intent If9587ca040be457d908d54e7aecc2ef6",
  "metadata": {
    "ticket": "INC-42"
  }
}
```

## Current repo profiles

These come from the current [config/app.toml](../../../config/app.toml) and may differ in another deployment.

- `default`: agent mode with general file-reading and search tools
- `controlled`: fixed two-stage log explanation pipeline
- `autonomous`: planner mode with bounded delegation
- `hdfs_eval`: HDFS pipeline
- `hdfs_eval_zero_shot`: HDFS pipeline with zero-shot prompt variants
- `bgl_eval`: legacy BGL question answering
- `bgl_v2_eval`: BGL v2 question answering
- `intent_demo`: intent summary pipeline using `fetch_intent_bundle`

## Data contract notes

- `artifacts[].content` is the safest API input for external callers.
- `artifacts[].source_path` is resolved on the API server itself, not uploaded from the client.
- `metadata` is opaque caller data preserved with the run and included in traces.
- `overrides` can replace tools, skills, prompt variants, and model settings, but most callers should start with profile defaults.

## Suggested integration policy

- Prefer `default` or another named profile over inventing your own prompt.
- Use `intent_demo` for intent lifecycle summaries instead of querying GraphDB directly from the external agent.
- Use sessions for repeated work from the same upstream system.
- Treat `result.content` as the user-facing answer.
- Treat `result.metadata.trace` as audit or debugging detail.

## Packaging recommendation

This skill is intentionally stored as a plain folder so it can be copied into another agent's skill directory unchanged.

Practical options:

- keep this folder in the repo and copy or vendor it into another agent
- publish this folder as a zip or release asset later
- move the same folder into a separate skill repo later if distribution becomes important
