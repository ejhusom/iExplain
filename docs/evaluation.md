# Evaluation

## Goal

The evaluation layer should make experiments easy to define, run, and compare without leaking evaluation-specific complexity into the runtime.

## Core Structure

- Experiment definition:
  - JSON file in [experiments](../experiments)
- Experiment runner:
  - [src/iexplain/eval/runner.py](../src/iexplain/eval/runner.py)
- Suite adapters:
  - [src/iexplain/eval/suites/hdfs.py](../src/iexplain/eval/suites/hdfs.py)
  - [src/iexplain/eval/suites/bgl.py](../src/iexplain/eval/suites/bgl.py)
  - [src/iexplain/eval/suites/bgl_v2.py](../src/iexplain/eval/suites/bgl_v2.py)
- Report builder:
  - [src/iexplain/eval/analyze.py](../src/iexplain/eval/analyze.py)

## Experiment File Shape

```json
{
  "name": "hdfs-smoke-gpt4o-mini",
  "suite": {
    "type": "hdfs",
    "settings": {
      "labels_csv": "data/hdfs/HDFS_anomaly_label_385_sampled_balanced.csv",
      "sessions_dir": "data/hdfs/HDFS_385_balanced_sampled_sessions",
      "sample_limit": 40,
      "seed": 42
    }
  },
  "runtime": {
    "profile": "hdfs_eval",
    "overrides": {
      "model": "gpt-4o-mini",
      "provider": "openai"
    }
  },
  "output_dir": "runs",
  "tags": {
    "suite": "hdfs",
    "mode": "pipeline"
  }
}
```

## Matrix File Shape

Matrix files expand one base experiment into a Cartesian product of named factors.

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
        }
      ]
    }
  ]
}
```

Each axis value applies a deep patch to the base experiment. The generated child runs record their factor values in `summary.json.matrix_context`.

## Current Suites

### HDFS

- Input: labels CSV + per-session log files
- Runtime profile: usually `hdfs_eval`
- Metric summary: accuracy, precision, recall, F1, confusion counts

### BGL v2

- Input: one BGL log file + one case-based ground-truth JSON file
- Runtime profile: usually `bgl_v2_eval`
- Metric summary: overall pass rate plus `by_tier` and `by_category`
- Tiers:
  - `smoke` for fast regression checks
  - `full` for normal comparisons
  - `challenge` for harder multi-artifact and grounded cases
- Main experiments:
  - [experiments/bgl_v2_smoke.json](../experiments/bgl_v2_smoke.json)
  - [experiments/bgl_v2_full.json](../experiments/bgl_v2_full.json)
  - [experiments/bgl_v2_challenge.json](../experiments/bgl_v2_challenge.json)
  - [experiments/bgl_v2_model_matrix.json](../experiments/bgl_v2_model_matrix.json)

### BGL v1

- Input: one BGL log file + one simple question JSON file
- Runtime profile: usually `bgl_eval`
- Metric summary: question pass rate
- Status: legacy benchmark kept for reference; use `bgl_v2` for new comparisons

## Output Layout

Each run produces:

```text
runs/<run_id>/
  experiment.json
  results.jsonl
  summary.json
```

`results.jsonl` keeps one line per case. `summary.json` is the stable input for later analysis.

Current `summary.json` also includes:

- `suite_settings`
- `resolved_runtime`
- `performance`
- `prompt_variants_seen`

For `bgl_v2`, `summary.json` also includes:

- `metrics.by_tier`
- `metrics.by_category`

Matrix-generated runs also include:

- `matrix_context.name`
- `matrix_context.combination`
- `matrix_context.combination_index`
- `matrix_context.combination_total`

`eval-analyze` now also writes SVG plots by default to `runs/plots/` unless another `--plots-dir` is provided.

Typical files:

```text
runs/plots/
  bgl_v2_score_by_run.svg
  bgl_v2_tokens_vs_score.svg
  bgl_v2_latency_vs_score.svg
  bgl_v2_score_by_model.svg
```

## Running

Run one experiment with terminal progress:

```bash
iexplain eval-run experiments/bgl_v2_challenge.json
```

Run a matrix with terminal progress:

```bash
iexplain eval-matrix experiments/bgl_v2_model_matrix.json
```

Rebuild markdown, JSON, and plots:

```bash
iexplain eval-analyze runs --markdown-output runs/report.md --json-output runs/report.json
```

## Key Separation

The suite adapter owns:

- how cases are loaded
- how responses are scored
- how suite metrics are summarized

The runtime owns:

- prompts
- skills
- execution mode
- tool use

That separation is deliberate. It keeps evaluation logic from bleeding into the product runtime.
