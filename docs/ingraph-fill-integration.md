# inGraph FILL Integration

This document explains the first `inGraph` integration that has been added to iExplain. It assumes the reader is new to `inGraph`.

## What inGraph Is

The `inGraph` repository is not just "another GraphDB setup". It is a small Flask service that sits in front of GraphDB and exposes a few convenience endpoints:

- `/repositories` to list repositories
- `/repositories/create` to create a repository
- `/upload` to upload JSON-LD
- `/query` to run SPARQL queries
- `/update` to run SPARQL updates

For the current code, the most important endpoint is `/query`. That endpoint accepts:

- a repository name
- a SPARQL query
- `format=json`

and then forwards the request to GraphDB.

In other words, `inGraph` is currently best understood as a GraphDB access layer plus ingestion helper. It does not yet provide a strong semantic API like "get machine summary" or "get service neighborhood". That semantic layer is what iExplain now adds for the first FILL use case.

## How This Differs From The Existing TM Forum Integration

The existing TM Forum integration in iExplain talks directly to GraphDB and normalizes the result into an intent-specific bundle:

- `GraphDBIntentClient` fetches one intent and related lifecycle data
- `fetch_intent_bundle` exposes that bundle as a bounded runtime tool
- the `intent_summary` pipeline uses the tool once and asks the model to explain the result

The new inGraph work follows the same pattern, but for one FILL entity instead of one TM Forum intent:

- `InGraphFillClient` talks to the `inGraph` `/query` endpoint
- `fetch_fill_entity_bundle` exposes a bounded FILL-specific tool
- the `ingraph_fill_summary` pipeline uses the tool once and asks the model to explain the result

This is intentionally narrow. The goal of the first slice is not to solve every inGraph use case. The goal is to prove that iExplain can sit on top of inGraph in a clean way.

## What Was Implemented

The implementation adds a first read-only integration for the FILL graph.

New code:

- `src/iexplain/ingraph_fill.py`
- `prompts/log_explainer/ingraph_fill.md`

Updated runtime wiring:

- `src/iexplain/runtime/tools.py`
- `src/iexplain/runtime/pipelines.py`
- `config/app.toml`

Tests:

- `tests/test_ingraph_fill.py`

### New Runtime Pieces

#### 1. `InGraphFillClient`

This client is responsible for querying `inGraph` and turning raw SPARQL results into a compact Python structure.

The client currently does three SPARQL `SELECT` queries for one target entity:

1. A root entity query
2. An outgoing-neighbor query
3. An incoming-neighbor query

That gives us the entity plus its direct graph neighborhood.

#### 2. `fetch_fill_entity_bundle`

This is the bounded tool exposed to the runtime.

It accepts:

- `entity_id`

It returns a compact JSON-like structure with:

- the entity IRI
- the entity name
- the entity type
- the external ID if present
- the description if present
- grouped outgoing relations
- grouped incoming relations
- small relation counts

The tool is intentionally read-only and intentionally narrow. It does not allow arbitrary SPARQL from the model.

#### 3. `ingraph_fill_summary`

This is a single-stage pipeline.

It tells the model to:

- call `fetch_fill_entity_bundle` exactly once
- use the returned bundle
- produce a compact explanation with these headings:
  - `Entity`
  - `Direct Relationships`
  - `Interpretation`
  - `Open Questions`

#### 4. `ingraph_fill_demo`

This is the profile that activates the pipeline.

It is analogous to `intent_demo`, but for the new FILL integration.

## Why FILL Was Chosen First

The `inGraph` repository contains several different graph shapes:

- `FILL`
- `GATE`
- `Telenor`

They are not all shaped the same way.

The FILL graph is a good first slice because it is relatively small and has clear structural relationships:

- `Service -> hasComponent -> Component`
- `Component -> hasContainer -> Container`
- `Container -> canBeDeployedOn -> Machine`
- `Machine -> hasService / hasContainer -> ...`

That makes it a good place to test the pattern "fetch one entity, normalize its immediate neighborhood, and explain it".

## Why The Integration Talks To inGraph Instead Of GraphDB Directly

This was a deliberate choice for the first prototype.

Reasons:

- The user request was specifically to explore integration with `inGraph`.
- `inGraph` is the actual service boundary that an external caller would likely see.
- If this integration works well, it becomes clearer what `inGraph` is missing as a semantic API.

This does not mean `inGraph` must always remain in the middle. It only means this first experiment is intentionally evaluating `inGraph` as the integration surface.

## Current Limitations

This first slice is intentionally limited.

- It only supports the FILL graph.
- It only fetches one-hop neighborhood data.
- It does not yet support arbitrary search or repository discovery from the model.
- It does not try to infer higher-level stories beyond the direct graph structure.
- It does not yet have dedicated support for GATE or Telenor.

These are acceptable limitations for a first integration because they keep the runtime bounded and testable.

## How The Bundle Is Structured

The normalized bundle is intentionally simple.

It contains:

- one root entity
- zero or more outgoing relation groups
- zero or more incoming relation groups

Each relation group contains:

- a predicate name such as `hasService` or `canBeDeployedOn`
- a list of related entities

Each related entity contains:

- IRI
- name
- type
- external ID when present

This shape is enough for explanation while still being much easier for the model to work with than raw SPARQL bindings.

## How To Run It

### 1. Start inGraph and GraphDB

From the `inGraph` repository:

```bash
docker compose up -d
```

This starts:

- GraphDB on `http://localhost:7200`
- inGraph on `http://localhost:5000`

### 2. Create a repository for FILL

You can use the existing inGraph API directly. For example:

```bash
curl -X POST http://localhost:5000/repositories/create \
  -F "id=FILL" \
  -F "title=FILL" \
  -F "ruleset=rdfsplus-optimized"
```

### 3. Upload the FILL graph

```bash
curl -X POST http://localhost:5000/upload \
  -F "repository=FILL" \
  -F "file=@inGraph/KG/fillKG.jsonld"
```

### 4. Run iExplain with the new profile

From the iExplain repository:

```bash
OPENAI_API_KEY="$OPENAI_API_KEY" \
IEXPLAIN_INGRAPH_URL="http://localhost:5000" \
IEXPLAIN_INGRAPH_FILL_REPOSITORY="FILL" \
uv run python3 -m iexplain run \
  "Target FILL entity id: Machine5

Explain what this entity is, what it is directly connected to, and what that suggests about its role in the FILL graph." \
  --profile ingraph_fill_demo
```

You can replace `Machine5` with another FILL entity such as:

- `Service3`
- `Component1`
- `Container4`

## Environment Variables

The new integration uses these environment variables:

- `IEXPLAIN_INGRAPH_URL`
  - default: `http://localhost:5000`
- `IEXPLAIN_INGRAPH_FILL_REPOSITORY`
  - default: `FILL`
- `IEXPLAIN_INGRAPH_FILL_RESOURCE_PREFIX`
  - default: `https://intendproject.eu/fill/`

These defaults are meant for local experimentation.

## Why No New Skill Was Added

No new skill was added for this first integration.

That was intentional.

Skills in this codebase mostly add prompt guidance. The main problem here was not prompt guidance. The main problem was creating a bounded semantic tool over `inGraph`.

The higher-value step was therefore:

- build a client
- normalize the data
- expose a tool
- connect it to a pipeline

A skill may still become useful later if we build more advanced multi-step inGraph workflows.

## Why No Generic inGraph Profile Was Added Yet

It is technically possible to imagine one generic `inGraph` profile, but it would likely be too vague at this stage.

The current `inGraph` data is use-case specific, and the graph structure differs noticeably across:

- FILL
- GATE
- Telenor

So the better first design is:

- one domain-shaped integration per use case
- one bounded tool per use case
- one pipeline per use case

If several of those begin to converge, then a more generic shared inGraph layer can be introduced later.

## Recommended Next Steps

The next useful steps are:

1. Add a small search tool for FILL entities so the user does not need to know the exact identifier up front.
2. Add a second profile for either GATE or Telenor, but only after deciding what one "good explanation unit" should be in that graph.
3. Decide whether iExplain should keep talking to `inGraph`, or whether `inGraph` should eventually expose more semantic endpoints itself.

For now, the important result is that a similar integration pattern does work with inGraph, but the semantic normalization must happen in iExplain, because `inGraph` itself is still mostly a transport and repository layer.
