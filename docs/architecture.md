# Architecture

## Design Rules

1. Runtime and evaluation stay separate.
2. Autonomy is a configuration choice, not a separate framework.
3. Prompts and skills are files on disk, not code.
4. The API submits jobs against named profiles.
5. Every major behavior should be testable without a real model.

## Runtime Layers

### 1. Config

[config/app.toml](../config/app.toml) defines:

- base model settings
- filesystem paths
- API worker settings
- named runtime profiles

Each profile controls:

- execution mode
- optional pipeline name
- allowed tools
- active skills
- prompt overrides
- turn and delegation limits

### 2. Catalogs

[src/iexplain/runtime/catalog.py](../src/iexplain/runtime/catalog.py) loads:

- prompts from `prompts/<role>/<variant>.md`
- skills from `skills/<name>/SKILL.md`
  - metadata comes from YAML frontmatter
  - full instructions are loaded only when a profile activates the skill

This keeps behavioral customization visible in files instead of buried in Python.

### 3. Tools

[src/iexplain/runtime/tools.py](../src/iexplain/runtime/tools.py) exposes a small fixed tool set:

- `bgl_query`
- `bgl_answer_question`
- `bgl_file_stats`
- `list_files`
- `read_file`
- `search_text`
- `fetch_url`

There is no dynamic tool creation in this version.

`bgl_query` is the main structured access path for the current BGL v2 benchmark. `bgl_answer_question` remains as a narrower legacy helper for the older BGL v1 path.

### 4. Agent

[src/iexplain/runtime/agent.py](../src/iexplain/runtime/agent.py) is the only tool-calling loop. It does not know about workflows, the API, or evaluation.

### 5. Service

[src/iexplain/runtime/service.py](../src/iexplain/runtime/service.py) is the main orchestration layer. It chooses one of three explicit modes:

- `pipeline`
  - fixed stages from [src/iexplain/runtime/pipelines.py](../src/iexplain/runtime/pipelines.py)
  - best for evaluation and ablations
- `agent`
  - one general analyst with bounded tools
  - best default for broad but understandable tasks
- `planner`
  - one planner with fixed delegation tools
  - best when more autonomy is needed without dynamic agent creation

## API

[src/iexplain/api/app.py](../src/iexplain/api/app.py) exposes:

- `GET /api/v1/health`
- `GET /api/v1/catalog`
- `GET /api/v1/jobs`
- `POST /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/sessions`
- `POST /api/v1/sessions`
- `GET /api/v1/sessions/{session_id}`
- `PATCH /api/v1/sessions/{session_id}`
- `DELETE /api/v1/sessions/{session_id}`
- `GET /api/v1/sessions/{session_id}/jobs`
- `POST /api/v1/sessions/{session_id}/tasks`
- `GET /api/v1/inspector/context`
- `GET /api/v1/inspector/runs`
- `GET /api/v1/inspector/runs/{run_id}`

The machine-readable contract is available from FastAPI at:

- `/openapi.json`
- `/docs`
- `/redoc`

Behavior is split across two small managers:

- [src/iexplain/api/jobs.py](../src/iexplain/api/jobs.py) handles asynchronous job execution and persistence under `runs/jobs/`
- [src/iexplain/api/sessions.py](../src/iexplain/api/sessions.py) handles session defaults and persistence under `runs/sessions/`

The API is still intentionally narrow:

- direct jobs are the stateless entry point
- sessions are a thin state layer for carrying profile, override, and metadata defaults across tasks
- inspector routes expose persisted runs and API state for local debugging, without introducing a separate backend service

## Why This Is Simpler

- No import-time side effects beyond explicit directory creation when the service starts
- No registries persisted into workspaces
- No dynamic code generation
- No second architecture for “workflows” versus “supervisor”; execution modes are just profiles
- One service interface for CLI, API, and evaluation
