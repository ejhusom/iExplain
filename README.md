# iExplain

iExplain is a framework for generating human-understandable explanations for intent-based management systems. It helps stakeholders understand how their high-level intents were interpreted, what actions were taken, and the outcomes achieved.

## Project Layout

```text
config/        App config and named runtime profiles
docs/          Architecture and evaluation documentation
experiments/   JSON experiment definitions
lab/           Local integration harnesses and sandbox services
prompts/       Prompt roles and variants
skills/        Markdown skill files
src/iexplain/  Runtime, API, CLI, and evaluation code
tests/         Small regression suite
```

## Quick Start

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Run one task
iexplain run "Explain what happened in the provided logs" --artifact /path/to/log.txt

# Start the API
iexplain serve --config config/app.toml

# Open the lightweight inspector
# then visit http://localhost:8000/inspector
iexplain serve --config config/app.toml

# Run an HDFS experiment
iexplain eval-run experiments/hdfs_smoke.json

# Run the current BGL v2 challenge benchmark
iexplain eval-run experiments/bgl_v2_challenge.json

# Run a matrix of BGL v2 ablations
iexplain eval-matrix experiments/bgl_v2_model_matrix.json

# Analyze all runs
iexplain eval-analyze runs --markdown-output runs/report.md --json-output runs/report.json
```

## Local Intent GraphDB Lab

`lab/intent_graphdb` is a sandbox for experimenting against a local GraphDB. It is intentionally separate from the core app.

API and inspector-submitted demo jobs are persisted separately from evaluation runs under `runs/jobs/`. Evaluation artifacts remain under `runs/<run-id>/`.

Start GraphDB:

```bash
docker compose -f lab/intent_graphdb/compose.yaml up -d
```

Seed the local repository with sample intents and reports:

```bash
uv run python3 lab/intent_graphdb/seed_graphdb.py --reset
```

<!-- If the sibling repo `../5G4Data-private/TM-Forum-Intent-Toolkit/` exists, the seed script will automatically load the TM Forum ontology bundle first. If not, it will still load the sample intents and reports. -->
The TM Forum ontology bundle can be automatically loaded first, for those who have access to it.

To skip ontology loading explicitly:

```bash
uv run python3 lab/intent_graphdb/seed_graphdb.py --reset --ontology-path skip
```

This lab is for manual integration testing and future intent-focused experiments. It is not part of the runtime or evaluation core.

### Sample Data Provenance

The sample files in [lab/intent_graphdb/sample_data](lab/intent_graphdb/sample_data) were created as a small synthetic lab dataset, but they are based on the public 5G4Data examples and vocabulary:

- `sample_intents.ttl` was assembled from the public 5G4Data TM Forum intent examples for:
  - network intent
  - deployment intent
  - combined network and deployment intent
- The structure and prefixes were aligned with:
  - [graphdb-talk-to-graph/system_prompt.txt](https://github.com/INTEND-Project/5G4Data-public/blob/main/graphdb-talk-to-graph/system_prompt.txt)
  - [CreateIntent/README.md](https://github.com/INTEND-Project/5G4Data-public/blob/main/Lifecycle-Management/src/CreateIntent/README.md)
- `sample_reports.ttl` was written manually to create a small but useful lifecycle narrative:
  - one stable compliant network intent
  - one deployment intent that degrades and then recovers
  - one combined intent that degrades and then recovers
- The report and observation structure follows the TM Forum ontology classes and properties already used in the 5G4Data material:
  - `icm:IntentReport`
  - `icm:about`
  - `icm:reportNumber`
  - `icm:reportGenerated`
  - `icm:intentHandlingState`
  - `met:Observation`

The purpose of these files is not benchmark realism yet. They are just a controlled local dataset for integration work on intent-level explanation.

### Things To Try

Once the lab is running and seeded, these commands are useful:

List repositories:

```bash
curl http://localhost:7200/rest/repositories
```

Count intents:

```bash
uv run python3 - <<'PY'
from urllib.request import Request, urlopen
query = """
PREFIX icm: <http://tio.models.tmforum.org/tio/v3.6.0/IntentCommonModel/>
SELECT ?intent WHERE { ?intent a icm:Intent . }
"""
req = Request(
    "http://localhost:7200/repositories/intents_and_intent_reports",
    data=f"query={query}".encode(),
    headers={
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded",
    },
)
print(urlopen(req).read().decode())
PY
```

Show the report timeline for one intent:

```bash
uv run python3 - <<'PY'
from urllib.request import Request, urlopen
query = """
PREFIX icm: <http://tio.models.tmforum.org/tio/v3.6.0/IntentCommonModel/>
PREFIX data5g: <http://5g4data.eu/5g4data#>
SELECT ?reportNumber ?generated ?state ?reason
WHERE {
  ?report a icm:IntentReport ;
          icm:about data5g:If9587ca040be457d908d54e7aecc2ef6 ;
          icm:reportNumber ?reportNumber ;
          icm:reportGenerated ?generated ;
          icm:intentHandlingState ?state ;
          icm:reason ?reason .
}
ORDER BY ?reportNumber
"""
req = Request(
    "http://localhost:7200/repositories/intents_and_intent_reports",
    data=f"query={query}".encode(),
    headers={
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/x-www-form-urlencoded",
    },
)
print(urlopen(req).read().decode())
PY
```

Reset and reseed the local lab:

```bash
uv run python3 lab/intent_graphdb/seed_graphdb.py --reset --ontology-path skip
```

Run an intent summary from the CLI:

```bash
OPENAI_API_KEY=[insert your key]
IEXPLAIN_INTENT_GRAPHDB_URL="http://localhost:7200" \
IEXPLAIN_INTENT_GRAPHDB_REPOSITORY="intents_and_intent_reports" \
uv run python3 -m iexplain intent-summary If9587ca040be457d908d54e7aecc2ef6
```

Or use the inspector UI:

```bash
OPENAI_API_KEY=[insert your key]
IEXPLAIN_INTENT_GRAPHDB_URL="http://localhost:7200" \
IEXPLAIN_INTENT_GRAPHDB_REPOSITORY="intents_and_intent_reports" \
uv run python3 -m iexplain serve --config config/app.toml
```

Then open `http://localhost:8000/inspector`, submit an `intent_demo` job, and inspect the resulting trace, tool calls, and intent timeline.

Completed demo jobs remain available after API restart because their job records are stored in `runs/jobs/`.

## Main Concepts

- Profiles live in [config/app.toml](config/app.toml).
- Runtime code lives under [src/iexplain/runtime](src/iexplain/runtime).
- Evaluation code lives under [src/iexplain/eval](src/iexplain/eval).

The runtime and evaluation are intentionally separate. Evaluation calls the runtime through the same `IExplainService` interface as the API and CLI.

## API Usage

The API has two submission styles:

- direct jobs for simple callers
- sessions plus tasks for tools that want to keep profile, overrides, and metadata across multiple requests

The fastest way to understand the API surface is to use the generated docs:

- interactive Swagger UI: `http://localhost:8000/docs`
- alternative ReDoc view: `http://localhost:8000/redoc`
- raw OpenAPI schema for tooling and code generation: `http://localhost:8000/openapi.json`

Start the server:

```bash
OPENAI_API_KEY=[insert your key]
uv run python3 -m iexplain serve --config config/app.toml
```

Core endpoints:

```text
GET    /api/v1/health
GET    /api/v1/catalog
GET    /api/v1/jobs
POST   /api/v1/jobs
GET    /api/v1/jobs/{job_id}
GET    /api/v1/sessions
POST   /api/v1/sessions
GET    /api/v1/sessions/{session_id}
PATCH  /api/v1/sessions/{session_id}
DELETE /api/v1/sessions/{session_id}
GET    /api/v1/sessions/{session_id}/jobs
POST   /api/v1/sessions/{session_id}/tasks
```

Inspector endpoints used by the lightweight UI:

```bash
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/catalog
curl http://localhost:8000/api/v1/inspector/context
curl http://localhost:8000/api/v1/inspector/runs
```

### Direct Job Submission

Submit one job directly:

```bash
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "run": {
      "task": "Explain what happened in session.log",
      "profile": "hdfs_eval",
      "artifacts": [
        {
          "name": "session.log",
          "content": "081111 061856 34 INFO dfs.FSNamesystem: BLOCK* NameSystem.allocateBlock: /tmp/x blk_1"
        }
      ]
    }
  }'
```

The API returns `202 Accepted` with a lightweight job record:

```json
{
  "job_id": "job_123456789abc",
  "status": "pending",
  "session_id": null
}
```

Poll the job:

```bash
curl http://localhost:8000/api/v1/jobs/job_XXXXXXXXXXXX
```

Completed jobs include the final `result`:

```json
{
  "job_id": "job_123456789abc",
  "status": "completed",
  "session_id": null,
  "created_at": "2026-03-18T08:15:00Z",
  "started_at": "2026-03-18T08:15:01Z",
  "completed_at": "2026-03-18T08:15:04Z",
  "error": null,
  "result": {
    "content": "done: Explain what happened in session.log",
    "mode": "agent",
    "profile": "hdfs_eval",
    "prompt_variants": {},
    "tool_calls": [],
    "events": [],
    "metadata": {}
  }
}
```

List recent jobs:

```bash
curl http://localhost:8000/api/v1/jobs
```

### Session And Task Flow

Create a session:

```bash
curl -X POST http://localhost:8000/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "name": "freno-demo",
    "profile": "intent_demo",
    "metadata": {
      "source_tool": "freno-ui",
      "customer": "demo"
    },
    "overrides": {
      "max_turns": 4
    }
  }'
```

This returns a `session_id`. Use it to submit tasks:

```bash
curl -X POST http://localhost:8000/api/v1/sessions/session_XXXXXXXXXXXX/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task": "Summarize what happened for intent Id392bc9f3ccb49f5989af6df730f940f",
    "metadata": {
      "ticket": "INC-42"
    }
  }'
```

Task submission returns the same `202 Accepted` shape as direct job submission, with the owning `session_id` included.

Check the session:

```bash
curl http://localhost:8000/api/v1/sessions/session_XXXXXXXXXXXX
curl http://localhost:8000/api/v1/sessions/session_XXXXXXXXXXXX/jobs
```

Update the default session profile or overrides:

```bash
curl -X PATCH http://localhost:8000/api/v1/sessions/session_XXXXXXXXXXXX \
  -H "Content-Type: application/json" \
  -d '{
    "profile": "hdfs_eval_zero_shot",
    "overrides": {
      "max_turns": 6
    }
  }'
```

Delete the session:

```bash
curl -X DELETE http://localhost:8000/api/v1/sessions/session_XXXXXXXXXXXX
```

### Practical Notes

- Sessions are stored under `runs/sessions/`.
- API-submitted jobs are stored under `runs/jobs/`.
- Evaluation runs stay under `runs/<run-id>/`.
- The inspector reads the same persisted jobs, so API runs remain visible after restart.
- `artifacts[].content` is the simplest way to send text artifacts over HTTP.
- `artifacts[].source_path` refers to a path on the API server's filesystem, not a client-side upload path.
- `/api/v1/catalog` is intentionally rich: it exposes profiles, prompts, skills, tools, pipelines, and resolved server-local config paths.
- For HDFS ablations, `hdfs_eval` now uses the richer few-shot HDFS prompts, while `hdfs_eval_zero_shot` uses the matching zero-shot variants.

## Documentation

- [Architecture](docs/architecture.md)
- [Evaluation](docs/evaluation.md)
- [Extending](docs/extending.md)

## Future work

- Build a serious INTEND evaluation suite with realistic multi-artifact cases.
- Tighten BGL v2 evidence scoring and compare against smaller local models.
- Add preprocessing tools for data, such as SQL ingestion and querying, only where a suite clearly needs it.
- Add observation throttling and summarization for intent bundles so large GraphDB observation sets do not overwhelm the model.
