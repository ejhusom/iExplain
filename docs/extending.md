# Extending iExplain

This project is designed to be extended by editing files, not by adding hidden runtime behavior.

## Add A Prompt

1. Create a Markdown file under `prompts/<role>/<variant>.md`.
2. Keep the prompt narrow and task-specific.
3. Select it through `prompt_overrides` in a profile or experiment.

Example:

```toml
[profiles.hdfs_eval.prompt_overrides]
log_anomaly_detector = "hdfs_few_shot"
```

## Add A Skill

1. Create `skills/<skill-name>/SKILL.md`.
2. Use YAML frontmatter with at least `name` and `description`.
3. Keep the body short and operational.

Example:

```markdown
---
name: example-skill
description: Explain when to use this skill and what it does.
metadata:
  owner: iexplain
  version: "1"
---

## Workflow

1. Describe the steps.
```

Rules:

- `name` should match the folder name
- use lowercase letters, numbers, and hyphens
- put long references in separate files later if needed

## Add A Pipeline

1. Add a named pipeline in [src/iexplain/runtime/pipelines.py](../src/iexplain/runtime/pipelines.py).
2. Define one or more `PipelineStage` entries.
3. Reference the pipeline from a profile in [config/app.toml](../config/app.toml).

Each stage should define:

- `name`
- `role`
- `task_template`
- `tools`

Prefer short fixed pipelines over agentic loops when the task is evaluated.

## Add An Experiment

1. Create a JSON file under [experiments](../experiments).
2. Pick a suite type and point it at files under [data](../data).
3. Choose a runtime profile and model override.

Example:

```json
{
  "name": "bgl-smoke-gpt4o-mini",
  "suite": {
    "type": "bgl",
    "settings": {
      "log_file": "data/bgl/bgl_2k.log",
      "ground_truth_file": "data/bgl/ground_truth.json",
      "tier": "smoke"
    }
  },
  "runtime": {
    "profile": "bgl_eval",
    "overrides": {
      "provider": "openai",
      "model": "gpt-4o-mini"
    }
  },
  "output_dir": "runs",
  "tags": {
    "suite": "bgl",
    "mode": "pipeline"
  }
}
```

## Run And Compare

Run one experiment:

```bash
iexplain eval-run experiments/bgl_smoke.json
```

Rebuild the report:

```bash
iexplain eval-analyze runs --markdown-output runs/report.md --json-output runs/report.json
```

Use the report to compare:

- model
- profile
- mode
- pipeline
- prompt variants
- tools and skills
- token usage and latency

## Add A Matrix

1. Create a JSON file under [experiments](../experiments).
2. Put a normal experiment under `base_experiment`.
3. Add one or more named `axes`.
4. For each axis value, provide a `label` and a deep `patch`.

Example:

```json
{
  "name": "bgl-v2-model-matrix",
  "base_experiment": {
    "name": "bgl-v2-challenge",
    "suite": {
      "type": "bgl_v2",
      "settings": {
        "log_file": "data/bgl/bgl_2k.log",
        "ground_truth_file": "data/bgl/ground_truth_v2.json",
        "tier": "challenge"
      }
    },
    "runtime": {
      "profile": "bgl_v2_eval",
      "overrides": {
        "provider": "openai"
      }
    },
    "output_dir": "runs",
    "tags": {
      "suite": "bgl_v2",
      "mode": "pipeline"
    }
  },
  "axes": [
    {
      "name": "model",
      "values": [
        {
          "label": "gpt-4o-mini",
          "patch": {
            "runtime": {
              "overrides": {
                "model": "gpt-4o-mini"
              }
            }
          }
        },
        {
          "label": "gpt-4o",
          "patch": {
            "runtime": {
              "overrides": {
                "model": "gpt-4o"
              }
            }
          }
        }
      ]
    }
  ]
}
```

Run it with:

```bash
iexplain eval-matrix experiments/bgl_v2_model_matrix.json
```

During the run, the terminal output shows:

- current experiment index out of the total matrix size
- current case index inside that experiment
- overall case progress across the whole matrix
