---
name: bgl-question-answering
description: Deterministic question answering over a BGL log file. Use when the task is to measure counts, rankings, ratios, or time-based aggregates from BGL logs and return a structured answer.
metadata:
  owner: iexplain
  version: "1"
---

## Workflow

1. Use the structured BGL tool path for the exact question.
2. Treat the task as measurement, not explanation.
3. Convert the answer into the exact JSON shape requested.

## Important

- Do not answer from memory.
- Treat counts and rankings as measurable facts.
