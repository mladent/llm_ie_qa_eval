# Product Requirements Document

## LLM Evaluation and Probabilistic Risk Decision Platform

**Version**: 1.0.0  
**Date**: April 2026  
**Status**: Implementation-accurate (descriptive, not aspirational)

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Background & Problem Statement](#2-background--problem-statement)
3. [Goals & Non-Goals](#3-goals--non-goals)
4. [User Personas & Use Cases](#4-user-personas--use-cases)
5. [System Architecture Overview](#5-system-architecture-overview)
6. [Functional Requirements: Evaluation Pipeline](#6-functional-requirements-evaluation-pipeline)
7. [Functional Requirements: Business Evaluation Layer](#7-functional-requirements-business-evaluation-layer)
8. [Configuration System](#8-configuration-system)
9. [Non-Functional Requirements](#9-non-functional-requirements)
10. [API Contract](#10-api-contract)
11. [Data Schemas & Contracts](#11-data-schemas--contracts)
12. [Developer Workflow & CLI Reference](#12-developer-workflow--cli-reference)
13. [AI Agent Workflow (Vibecoding)](#13-ai-agent-workflow-vibecoding)
14. [Glossary](#14-glossary)

---

## 1. Executive Summary

This platform provides deterministic evaluation, probabilistic risk modeling, and decision support for LLM behavior in business workflows. It answers two questions that organizations must answer before deploying an LLM-powered extraction system into production:

1. **How well does the model perform?** — Measured through repeated evaluation runs with precision, recall, F1, and hybrid schema/rubric scoring.
2. **Is it safe to deploy?** — Measured through business risk quantification: failure mode costs, deployment readiness scores, and a structured GO/CONDITIONAL/HOLD/NO_GO recommendation.

The platform is designed for teams that use LLMs for JSON information extraction tasks (e.g., CV parsing, document classification, structured data extraction). It is not a general-purpose LLM benchmark; it is a purpose-built, configuration-driven evaluation and risk pipeline that plugs into existing ML engineering workflows via CLI, file-based artifacts, optional MLflow tracking, and an optional FastAPI endpoint.

**Key properties**:
- **Reproducible**: Every experiment ships provenance metadata (git commit, config hash, file SHAs, timestamp).
- **Modular**: Providers, comparators, metrics, and business logic are independently swappable.
- **Gracefully degrading**: MLflow, hybrid scoring, Parquet export, and the API are all optional.
- **Config-driven**: Behavior is controlled through YAML files; no code changes required to adjust thresholds, scoring weights, or failure cost penalties.

---

## 2. Background & Problem Statement

### 2.1 The Extraction Evaluation Problem

LLMs are increasingly used to extract structured JSON from unstructured documents (CVs, contracts, research papers, support tickets). Standard ML benchmarks measure accuracy on fixed datasets. But accuracy alone is insufficient for production deployment because:

- **LLM outputs are stochastic**: The same prompt produces different outputs across runs, even at low temperature.
- **Parse failures are common**: Models may return malformed JSON, markdown-wrapped JSON, or refuse to respond.
- **Field-level quality varies**: A model may extract `methods` correctly but consistently fail on `datasets`.
- **Business risk is non-uniform**: A parse error on a refund-handling document costs more than one on a low-stakes document.

### 2.2 The Business Risk Problem

Existing evaluation tooling stops at aggregate metrics (mean F1). This is not enough for deployment decisions. A 0.85 mean F1 hides:
- Documents where the model fails 100% of the time.
- Scenarios where repeated runs produce different answers (instability).
- High-cost failure modes that occur rarely but are operationally devastating.

Business decision-makers need a structured recommendation — with quantified risk — not a raw metric.

### 2.3 Solution Approach

The platform solves both problems with a two-stage pipeline:

**Stage 1 — Evaluation**: Run each document N times, capture variance, compute precision/recall/F1 and optional hybrid scores, persist all run records.

**Stage 2 — Business Evaluation**: Load evaluator artifacts, apply business-specific cost models and thresholds per scenario, compute a weighted readiness score, apply hard gates, and issue a structured deployment recommendation with explainability payloads.

---

## 3. Goals & Non-Goals

### 3.1 Goals

| Goal | Description |
|---|---|
| Multi-run variance measurement | Run each document N times and report per-document and corpus-level variance statistics |
| Hybrid scoring | Optional JSON Schema + rubric-based value scoring alongside precision/recall/F1 |
| Business readiness recommendation | Configurable weighted scoring and hard gates producing GO/CONDITIONAL/HOLD/NO_GO |
| Business risk quantification | Failure mode taxonomy with per-scenario cost penalties and expected cost per 1,000 items |
| Reproducibility | Full provenance metadata for every experiment (git commit, config hash, file SHAs) |
| MLflow integration | Optional experiment tracking with graceful degradation when unavailable |
| Provider abstraction | OpenAI and Gemini supported with unified output schema; new providers addable without changing evaluation logic |
| Scenario-based configuration | Business thresholds and costs configurable per business scenario without code changes |
| Stable service contract | Business evaluation exposed via a stable service boundary for API or pipeline integration |
| Optional API runtime | FastAPI endpoint for programmatic business evaluation against existing experiment artifacts |

### 3.2 Non-Goals

| Non-Goal | Rationale |
|---|---|
| Online serving / real-time inference | The platform evaluates offline; it does not serve extraction results in production |
| Model fine-tuning | Out of scope; the platform evaluates models, it does not train them |
| Data annotation UI | No frontend; all interaction is CLI- or file-based |
| Semantic similarity scoring (embeddings) | Current comparators are lexical; embedding-based matching is a future extension |
| Multi-modal inputs | Text documents only |
| Streaming evaluation | All runs are batch; no streaming output |
| Streamlit / dashboard UI | `business/ui_app.py` is referenced but not implemented in this repository |

---

## 4. User Personas & Use Cases

### 4.1 Personas

#### ML Engineer
Runs evaluation experiments, configures model parameters, inspects per-document variance and instability, and iterates on prompts.

**Primary interactions**: `run_evaluation.py` CLI, `config/eval_settings.yaml`, `runs.jsonl`, `document_aggregates.csv`, MLflow UI.

#### Business Analyst
Reads business dashboards, interprets item-level cost breakdowns and failure mode distributions, and tracks whether specific documents consistently fail.

**Primary interactions**: `dashboard_summary.json`, `item_business_breakdown.csv`, `scenario_business_summary.csv`.

#### Platform Engineer
Integrates the business evaluation API into CI/CD or data pipelines, manages MLflow infrastructure, operates the evaluation pipeline at scale, and owns environment configuration.

**Primary interactions**: `run_business_api.py`, `POST /business/evaluate`, `Makefile`, `.env`, MLflow tracking URI configuration.

#### Management / Business Decision Makers
Consumes the structured deployment recommendation (GO/CONDITIONAL/HOLD/NO_GO) and high-level risk and cost summaries to authorize or block production rollouts of LLM-powered extraction features.

**Primary interactions**: `dashboard_summary.json` (specifically `deployment_recommendation`, `readiness_score`, `hard_gate_failures`, `soft_warnings`), and summary reports generated from `scenario_business_summary.csv`.

### 4.2 Use Cases

#### UC-1: Evaluate a New Model Before Deployment
An ML Engineer configures a project YAML, runs the evaluator with `num_runs: 5`, and reviews variance metrics to determine if the model is stable enough to send to business evaluation.

#### UC-2: Compare Two Models or Prompts
An ML Engineer runs two separate experiments (different `model` or `prompt_id`) and compares `corpus_summary.json` or MLflow run comparisons.

#### UC-3: Run Business Risk Analysis After an Evaluation
A Platform Engineer or Business Analyst runs `run_business_evaluation.py` against an existing experiment directory for a specific business scenario (e.g., `refund_handling`) to get deployment recommendation artifacts.

#### UC-4: Integrate Business Evaluation into a CI/CD Pipeline
A Platform Engineer calls `POST /business/evaluate` against the running API server from a CI script. On `"NO_GO"` or `"HOLD"` recommendation, the pipeline is blocked.

#### UC-5: Authorize a Production Rollout
A Management Decision Maker reviews `dashboard_summary.json`: checks `deployment_recommendation == "GO"`, confirms `hard_gate_failures` is empty, reviews `readiness_score` against the `go_threshold`, and signs off.

#### UC-6: Investigate a High-Instability Document
An ML Engineer reads `per_document_instability_summary` from the phase-8 analysis artifacts and identifies documents with low `exact_match_stability`. They review field-level overlap to understand which extraction fields are unstable.

#### UC-7: Adjust Risk Tolerance for a New Business Scenario
A Business Analyst adds a new scenario to `config/business_thresholds.yaml` and `config/business_costs.yaml` with scenario-specific thresholds and cost penalties, then re-runs business evaluation without code changes.

---

## 5. System Architecture Overview

### 5.1 Component Map

```
┌─────────────────────────────────────────────────────────────────────┐
│  INPUTS                                                             │
│  dataset.json / project YAML + documents                            │
│  prompts/extraction_prompt.txt                                      │
│  config/eval_settings.yaml                                          │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  EVALUATION PIPELINE  (run_evaluation.py)                           │
│                                                                     │
│  config_loader.py ──► EvalConfig                                    │
│                                                                     │
│  For each document × num_runs:                                      │
│    extraction/extractor.py                                          │
│      ├── providers/openai_provider.py  ──► OpenAI API               │
│      └── providers/gemini_provider.py  ──► Gemini API               │
│    providers/json_parsing.py           (JSON resilience)            │
│    evaluation/metrics.py              ──► precision / recall / F1   │
│    evaluation/hybrid_scoring.py       ──► hybrid score (optional)   │
│      ├── evaluation/hybrid_schema.py  (JSON Schema validation)      │
│      ├── evaluation/hybrid_comparators.py (6 comparator types)      │
│      └── evaluation/hybrid_normalize.py  (JSONPath + normalization) │
│    evaluation/run_record.py           ──► CanonicalRunRecord        │
│    persistence.py                     ──► runs.jsonl                │
│    mlflow_utils.py                    ──► MLflow (optional)         │
│                                                                     │
│  evaluation/metrics.py  ──► DocumentAggregateRecord                │
│  evaluation/variance_analysis.py ──► instability summaries          │
│  evaluation/analysis_questions.py ──► phase-8 analysis              │
│  persistence.py  ──► document_aggregates.csv / .parquet             │
│                   ──► corpus_summary.json                           │
│                   ──► provenance.json, config.json                  │
└────────────────────────────┬────────────────────────────────────────┘
                             │  outputs/experiments/<experiment-id>/
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  BUSINESS EVALUATION LAYER  (run_business_evaluation.py)            │
│                                                                     │
│  business/artifacts_loader.py  ──► BusinessContractInput            │
│  business/contracts.py         (schema validation)                  │
│  business/metrics.py           ──► per-item metrics                 │
│  business/aggregates.py        ──► scenario-level aggregation       │
│  business/recommender.py       ──► readiness score + recommendation │
│  business/explainability.py    ──► metric contributions + proximity │
│  business/replay.py            ──► config snapshot + hash           │
│  business/reporting.py         ──► report assembly                  │
│                                                                     │
│  Output: dashboard_summary.json, replay_metadata.json              │
│          scenario_business_summary.csv, item_business_breakdown.csv │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
            ┌─────────────┴──────────────┐
            │                            │
            ▼                            ▼
  business/service.py           business/api.py
  (stable service boundary)     (optional FastAPI)
                                POST /business/evaluate
```

### 5.2 Data Flow Narrative

1. **Config loading**: `config_loader.py` merges defaults → YAML file → environment variables → CLI args into a typed `EvalConfig`.
2. **Dataset loading**: Either from a `data.documents` project spec (explicit document + gold path pairs) or from a legacy `data.dataset_path` JSON file.
3. **Per-document evaluation**: For each document, the prompt template is loaded and the model is called `num_runs` times. Each call goes through the provider → JSON parsing → schema normalization → metric computation → optional hybrid scoring pipeline.
4. **Run record persistence**: Each run produces a `CanonicalRunRecord` appended to `runs.jsonl`.
5. **Aggregation**: After all runs for a document complete, `compute_document_aggregate()` produces a `DocumentAggregateRecord`. After all documents, `compute_corpus_aggregate()` produces a `CorpusAggregateRecord`.
6. **MLflow logging**: If enabled, per-run metrics, document aggregates, and corpus aggregates are logged to MLflow.
7. **Business evaluation (separate stage)**: `artifacts_loader.py` reads evaluator outputs and constructs a `BusinessContractInput`. Per-item business metrics are computed, aggregated at scenario level, and a deployment recommendation is generated with full explainability.
8. **Artifact export**: All outputs are written to `outputs/experiments/<experiment-id>/` (evaluator) and `outputs/experiments/<experiment-id>/business/` (business layer).

### 5.3 Key Design Principles

| Principle | Implementation |
|---|---|
| Single source of truth | `EvalConfig` YAML is authoritative; CLI args override only specific keys |
| Stable contracts | Business layer consumes evaluator artifacts as immutable inputs; it never imports evaluator internals |
| Reproducibility | `provenance.json` captures git commit hash, all file SHAs, config hash, and timestamp |
| Graceful degradation | MLflow, hybrid scoring, Parquet, and the API runtime are all independently optional |
| Provider abstraction | OpenAI and Gemini return the same unified dict; `run_extraction()` routes between them |
| Fail fast | Config and contract validation happen at the earliest possible boundary |
| Config-driven behavior | Thresholds, weights, costs, and rubric rules are in YAML; no code changes required |

---

## 6. Functional Requirements: Evaluation Pipeline

### 6.1 Repeated Runs

- The evaluator executes each document `num_runs` times (configurable, default: `5`).
- All run records for a document are aggregated to compute variance statistics.
- Each run is independently recorded with its own timestamp, latency, tokens, and scores.

### 6.2 LLM Provider Abstraction

- **Supported providers**: `openai` (via `providers/openai_provider.py`) and `gemini` (via `providers/gemini_provider.py`).
- Both providers return the same unified output dict (see §11.4 for schema).
- Provider is selected via `config.model.provider`; new providers are added by creating a new `providers/<name>_provider.py` file and registering it in `extraction/extractor.py`.
- API keys are loaded from `.env` via `python-dotenv` (`OPENAI_API_KEY`, `GEMINI_API_KEY`).
- Model parameters: `model`, `temperature`, `top_p`, `max_tokens` — all configurable.

### 6.3 JSON Parsing Resilience

`providers/json_parsing.py` implements `parse_json_object_text()` which handles:
- Raw JSON responses.
- JSON wrapped in markdown fences (` ```json ... ``` `).
- Bracket-extracted JSON (finds first `{` / `[` and attempts parse from there).

`parse_status` values:
- `"success"` — JSON parsed and schema-validated successfully.
- `"parse_error"` — Response received but JSON could not be extracted.
- `"schema_error"` — JSON parsed but field normalization or type validation failed.
- `"provider_error"` — Hard provider failure (network error, API timeout, etc.).

### 6.4 Extraction Schema Validation

After successful JSON parsing, `extraction/extractor.py` applies `normalize_extraction_output()` and `validate_extraction_schema()`:
- Each expected field must be present.
- Each field must be a list of strings (or a coercible type: string → `[string]`, null → `[]`).
- Normalization errors set `parse_status = "schema_error"`.

### 6.5 Metric Computation

`evaluation/metrics.py` computes per-run precision, recall, and F1 using set-based token overlap:

$$\text{precision} = \frac{|P \cap G|}{|P|}, \quad \text{recall} = \frac{|P \cap G|}{|G|}, \quad F_1 = \frac{2 \cdot \text{precision} \cdot \text{recall}}{\text{precision} + \text{recall}}$$

Where $P$ is the predicted set of values and $G$ is the gold set, computed across all extraction fields.

### 6.6 Document-Level Aggregation

`compute_document_aggregate()` produces per-document statistics across all runs:

| Statistic | Metrics |
|---|---|
| Mean, std, CI95 | precision, recall, F1, hybrid_score |
| Five-number summary | min, Q1, median, Q3, max for precision, recall, F1 |
| Consistency metrics | `exact_match_consistency_rate`, `parse_error_rate` |
| Performance metrics | `latency_mean`, `latency_std`, `cost_mean`, `cost_std` |

CI95 uses the standard formula: $1.96 \times \sigma / \sqrt{n}$.

### 6.7 Corpus-Level Aggregation

`compute_corpus_aggregate()` produces corpus-level summaries aggregating across all documents and all runs, with the same metric structure as document-level aggregation.

### 6.8 Variance & Instability Analysis

`evaluation/variance_analysis.py` provides:
- **`compute_exact_match_stability(records)`**: Fraction of successful runs producing the modal JSON output. `1.0` = all runs agree; `0.0` = all runs differ.
- **`compute_field_level_overlap(records)`**: Per-field agreement rate — for each field, the fraction of runs whose value set matches the modal value.
- **`per_document_instability_summary(records_by_doc)`**: Corpus-wide ranking of documents by instability (sorted ascending by `exact_match_stability`).

Each instability summary entry includes:
```
document_id, exact_match_stability, field_instability,
structural_validity_rate, run_count,
hybrid_score_mean, hybrid_score_std
```

### 6.9 Hybrid Scoring (Optional)

Hybrid scoring is disabled by default (`hybrid.enabled: false`). When enabled, each run receives additional scores:

**Schema component** (weight: 35%): JSON Schema-aware structural validation using `evaluation/hybrid_schema.py`. Scores four axes: required field presence, type correctness, enum compliance, and additional properties policy.

**Value component** (weight: 65%): JSONPath rubric-rule scoring using `evaluation/hybrid_scoring.py`. Each rule specifies a JSONPath selector, a comparator, and a weight.

**Composite formula**:

$$\text{hybrid\_total\_score} = 0.35 \times \text{schema\_score} + 0.65 \times \text{value\_score}$$

**Comparator types** (defined in `evaluation/hybrid_comparators.py`):

| Comparator | Type key | Description |
|---|---|---|
| `exact_match` | `exact_match` | Strict JSON-normalized equality |
| `set_jaccard_match` | `set_jaccard_match` | Jaccard similarity for unordered list fields |
| `fuzzy_lexical_match` | `fuzzy_lexical_match` | Sequence-ratio fuzzy match with configurable `min_similarity` threshold |
| `key_based_array_object_match` | `key_based_array_object_match` | Array-of-object match using key-based identity fields |
| `best_overlap_fallback_match` | `best_overlap_fallback_match` | Best-overlap fallback when primary strategy fails |

**Unknown field policy** (configurable):
- `"ignore"` — Unknown fields do not affect the score.
- `"penalize"` — Unknown fields apply a weighted penalty.
- `"fail_schema"` — Unknown fields set the schema score to zero.

**Parse error behavior**: When `parse_error_behavior: "force_zero"` (default), any run with `parse_status != "success"` receives `hybrid_total_score = 0.0`.

**Per-run hybrid fields in `runs.jsonl`**:
- `hybrid_total_score`, `hybrid_schema_score`, `hybrid_value_score`
- `hybrid_unknown_penalty`, `hybrid_rule_coverage`

**Additional hybrid artifacts**:
- `hybrid_component_trends.csv` — Per-run schema vs value score breakdown.
- `hybrid_path_breakdown.csv` — Per-path score details for each run.

### 6.10 MLflow Tracking (Optional)

`mlflow_utils.py` provides `MLflowTracker` — a wrapper that degrades gracefully:
- If `tracking.enable_mlflow: false` → no-op.
- If `mlflow` package not installed but enabled → warning printed, continues without tracking.

**What is logged**:
- Global params: provider, model, prompt_id, dataset_id, num_runs, temperature, etc.
- Per-run metrics (step = global run index): precision, recall, F1, hybrid scores, parse status, latency, tokens, cost.
- Per-document aggregate metrics (step = document index): mean F1, consistency rate, hybrid scores, latency, cost.
- Corpus aggregate metrics: final means, std, CI95 for all metrics.

**Default configuration**:
- Tracking URI: `sqlite:///mlflow.db`
- MLflow artifacts stored in `mlruns/`

### 6.11 Phase-8 Analysis

`evaluation/analysis_questions.py` `build_phase8_analysis()` produces a structured analysis payload covering:
- Corpus-level metric overview.
- Model consistency questions (parse error rate, exact match rate).
- Variance and instability ranking across documents.
- Hybrid score distribution (when enabled).
- This payload is written as a JSON artifact per experiment.

### 6.12 Retry Logic

Provider calls use bounded exponential-backoff retry via `_call_with_retry()`:
- Maximum attempts: `execution.max_retries` (default: `3`).
- Backoff: `retry_backoff_seconds × 2^attempt` seconds between retries.
- On exhausted retries: a zero-metric `CanonicalRunRecord` with `parse_status = "provider_error"` is recorded.
- If `execution.continue_on_error: true` (default), evaluation continues to the next document on hard failure.

### 6.13 Artifact Export

All artifacts are written to `outputs/experiments/<experiment-id>/`.

| File | Format | Description |
|---|---|---|
| `runs.jsonl` | JSONL | All `CanonicalRunRecord` instances, one per line |
| `document_aggregates.csv` | CSV | Flat `DocumentAggregateRecord` table |
| `document_aggregates.parquet` | Parquet | Same, Parquet format (optional, requires `pyarrow`) |
| `corpus_summary.json` | JSON | `CorpusAggregateRecord` + failure rate |
| `provenance.json` | JSON | `ExperimentProvenance` metadata |
| `config.json` | JSON | Normalized config snapshot |
| `phase8_analysis.json` | JSON | Phase-8 variance analysis |
| `hybrid_component_trends.csv` | CSV | Hybrid schema/value trends (if hybrid enabled) |
| `hybrid_path_breakdown.csv` | CSV | Per-path hybrid scores (if hybrid enabled) |

Export formats are controlled by `exports.write_jsonl`, `exports.write_csv`, `exports.write_parquet`.

---

## 7. Functional Requirements: Business Evaluation Layer

The business evaluation layer is a separate stage that consumes evaluator artifacts. It does not re-run the LLM; it re-analyzes existing run records through a business risk lens.

### 7.1 Input: Business Contract

`business/artifacts_loader.py` reads `runs.jsonl` and aggregate artifacts from an experiment directory and assembles a `BusinessContractInput` (see §11.3). The contract is validated against `BUSINESS_CONTRACT_SCHEMA` (Draft 2020-12 JSON Schema) before any computation begins.

### 7.2 Item-Level Business Metrics

`business/metrics.py` `evaluate_item()` computes per-item metrics across all runs:

| Metric | Definition |
|---|---|
| `success_rate` | `1 - (failed_runs / total_runs)` |
| `mean_score` | Mean of per-run average scores |
| `variance` | Score variance across runs |
| `agreement_rate` | Fraction of runs matching the most common output (exact-match majority) |
| `expected_cost` | Mean failure cost across runs: `sum(cost_map[failure]) / run_count` |
| `worst_case_cost` | Maximum single-run failure cost |
| `failure_probability` | `failed_runs / total_runs` |
| `failure_mode_rates` | Per-mode failure rate (e.g., `parse_error: 0.2`, `incorrect: 0.4`) |
| `five_number_summary` | min, Q1, median, Q3, max of per-run scores |
| `run_count` | Total runs attempted for this item |

### 7.3 Failure Mode Taxonomy

Three failure modes with configurable cost penalties per scenario in `config/business_costs.yaml`:

| Mode | Default Cost | Meaning |
|---|---|---|
| `parse_error` | 10.0 | Model returned a response that could not be parsed as valid JSON |
| `runtime_error` | 8.0 | Provider returned an error or extraction failed with an exception |
| `incorrect` | 5.0 | JSON parsed successfully but scores below success threshold |

Costs are unitless business-defined penalties (e.g., proportional to remediation cost in dollars or story points).

### 7.4 Scenario-Level Aggregation

`business/aggregates.py` `aggregate_scenario()` aggregates item-level metrics into scenario-level summaries:

| Summary Metric | Description |
|---|---|
| `success_rate_mean` | Mean of per-item success rates |
| `stability_score` | Mean of per-item agreement rates |
| `critical_failure_rate` | Fraction of items with `failure_probability > 0` |
| `expected_cost_per_1000` | `mean(expected_cost) × 1000` |
| `failure_breakdown` | Corpus-level rate for each failure mode |

### 7.5 Deployment Readiness Scoring

`business/recommender.py` `recommend_deployment()` computes a weighted readiness score:

$$\text{readiness\_score} = w_{\text{success}} \cdot r_{\text{success}} + w_{\text{stability}} \cdot r_{\text{stability}} + w_{\text{quality}} \cdot \bar{s}_{\text{quality}} - w_{\text{risk}} \cdot \hat{c}_{\text{cost}} - w_{\text{critical}} \cdot r_{\text{critical}}$$

Where:
- $w_x$ are the normalized readiness weights from `config/business_settings.yaml`
- $r_{\text{success}}$ = `success_rate_mean`
- $r_{\text{stability}}$ = `stability_score`
- $\bar{s}_{\text{quality}}$ = mean of per-item `mean_score`
- $\hat{c}_{\text{cost}}$ = `min(1, expected_cost_per_1000 / cap)` (normalized to [0, 1])
- $r_{\text{critical}}$ = `critical_failure_rate`

**Default weights** (from `config/business_settings.yaml`):

| Component | Weight |
|---|---|
| success | 0.35 |
| stability | 0.20 |
| quality | 0.25 |
| risk | 0.12 |
| critical | 0.08 |

Weights are normalized to sum to 1.0 before use.

### 7.6 Hard Gates

Before the readiness score is used for a GO/CONDITIONAL decision, three hard gates are evaluated. Any gate failure overrides the readiness score and forces a `"HOLD"` decision:

| Gate | Default Threshold | Effect on breach |
|---|---|---|
| `max_critical_failure_rate` | 0.05 | Forces `"HOLD"` |
| `max_expected_cost_per_1000` | 6000.0 | Forces `"HOLD"` |
| `min_stability_score` | 0.60 | Forces `"HOLD"` |

### 7.7 Deployment Recommendation Logic

```
IF any hard gate fails:
    recommendation = "HOLD"
ELIF readiness_score >= go_threshold:
    recommendation = "GO"
ELIF readiness_score >= conditional_threshold:
    recommendation = "CONDITIONAL"
ELSE:
    recommendation = "NO_GO"
```

**Default thresholds** (from `config/business_thresholds.yaml`, `default` scenario):
- `go_threshold`: 0.73
- `conditional_threshold`: 0.55

### 7.8 Soft Warnings

In addition to hard gates, `recommend_deployment()` emits soft warnings when metrics are near threshold boundaries (within `warnings.soft_warning_margin: 0.01`):

| Warning | Condition |
|---|---|
| `readiness_near_go_threshold` | `0 < go_threshold - readiness_score ≤ margin` |
| `critical_failure_rate_near_gate` | Critical failure rate within margin of its gate |
| `stability_near_gate` | Stability score within margin of its gate |
| `expected_cost_near_gate` | Expected cost per 1,000 within relative margin of its gate |

### 7.9 Explainability Payloads

`business/explainability.py` provides three explainability functions included in `dashboard_summary.json`:

**`metric_contributions()`**: Signed contribution of each readiness score component:
```json
{
  "success": 0.287,
  "stability": 0.156,
  "quality": 0.201,
  "risk": -0.043,
  "critical": -0.012
}
```

**`threshold_proximity()`**: Absolute distances to all decision thresholds and hard gates:
```json
{
  "to_go_threshold": 0.042,
  "to_conditional_threshold": 0.235,
  "to_max_critical_failure_rate": 0.031,
  "to_max_expected_cost_per_1000": 1823.4,
  "to_min_stability_score": 0.089
}
```

**`dominant_failure_modes()`**: Top-K failure modes by rate (default K=3):
```json
[
  {"mode": "parse_error", "rate": 0.12},
  {"mode": "incorrect", "rate": 0.08}
]
```

**`top_failing_items()`**: Top-K items by failure probability and expected cost (default K=3):
```json
[
  {"item_id": "doc-005", "failure_probability": 0.6, "expected_cost": 7.2},
  {"item_id": "doc-012", "failure_probability": 0.4, "expected_cost": 5.0}
]
```

### 7.10 Scenario-Based Configuration

Business thresholds and costs support named scenarios. Scenario config is merged on top of `default`:

```
default thresholds + costs
    ↓ deep merge
scenario-specific thresholds + costs
```

Example: running with `--scenario refund_handling` applies tighter thresholds and higher cost penalties defined in `refund_handling:` blocks in the relevant YAML files.

### 7.11 Replay Metadata

`business/replay.py` `build_replay_metadata()` captures a snapshot of the effective business configuration (all four config files merged) and a SHA-256 hash of that snapshot. This enables verification that business evaluation was run with the same configuration at a later date.

### 7.12 Business Report Artifacts

All business outputs are written to `<experiment-dir>/business/`:

| File | Format | Description |
|---|---|---|
| `dashboard_summary.json` | JSON | Full recommendation payload with explainability |
| `replay_metadata.json` | JSON | Config snapshot + hash for reproducibility |
| `scenario_business_summary.csv` | CSV | Scenario-level aggregate metrics |
| `item_business_breakdown.csv` | CSV | Per-item business metrics |

---

## 8. Configuration System

### 8.1 Configuration Hierarchy

Configuration is resolved through a four-layer merge (later layers override earlier ones):

```
1. Hardcoded defaults (config_loader.py DEFAULT_CONFIG)
      ↓
2. YAML file (--config path, default: config/eval_settings.yaml)
      ↓
3. Environment variables (LIE_* prefix)
      ↓
4. CLI arguments (--flag style)
```

### 8.2 Environment Variable Overrides

| Variable | Config path | Type |
|---|---|---|
| `LIE_PROVIDER` | `model.provider` | str |
| `LIE_MODEL` | `model.model` | str |
| `LIE_NUM_RUNS` | `experiment.num_runs` | int |
| `LIE_DATASET_PATH` | `data.dataset_path` | str |
| `LIE_PROMPT_PATH` | `data.prompt_path` | str |
| `LIE_OUTPUT_DIR` | `experiment.output_dir` | str |
| `LIE_ENABLE_MLFLOW` | `tracking.enable_mlflow` | bool |
| `LIE_TRACKING_URI` | `tracking.tracking_uri` | str |
| `LIE_EXPERIMENT_NAME` | `experiment.name` | str |
| `LIE_PROMPT_ID` | `data.prompt_id` | str |
| `LIE_MAX_RETRIES` | `execution.max_retries` | int |
| `LIE_RETRY_BACKOFF` | `execution.retry_backoff_seconds` | int |

### 8.3 Evaluation Config (`config/eval_settings.yaml`)

```yaml
experiment:
  name: "llm-json-eval"      # Experiment label (MLflow + output dir)
  seed: 42                    # Random seed (for reproducibility metadata)
  output_dir: "outputs"       # Root output directory
  num_runs: 5                 # Repeated runs per document

data:
  dataset_path: "data/dataset.json"             # Legacy dataset mode
  prompt_path: "prompts/extraction_prompt.txt"  # Prompt template file
  prompt_id: "extraction-v1"                    # Prompt version identifier
  documents:                                    # Project mode (overrides dataset_path)
    - id: "doc-001"
      document_path: "path/to/document.txt"
      gold_path: "path/to/gold.json"

model:
  provider: "openai"          # openai | gemini
  model: "gpt-4o-mini"        # Model ID
  temperature: 0.2            # Sampling temperature
  top_p: 1.0                  # Nucleus sampling parameter
  max_tokens: 2048            # Maximum output tokens

execution:
  max_retries: 3              # Retry attempts on provider error
  retry_backoff_seconds: 2    # Base backoff (doubled per attempt)
  timeout_seconds: 60         # Request timeout (passed to provider)
  continue_on_error: true     # Continue to next document on hard failure

tracking:
  enable_mlflow: true         # Toggle MLflow logging
  tracking_uri: "sqlite:///mlflow.db"  # MLflow backend store
  tags:                       # Custom MLflow tags
    project: "llm_ie_qa_eval"
    corpus: "default"

exports:
  write_jsonl: true           # Write runs.jsonl
  write_csv: true             # Write document_aggregates.csv
  write_parquet: true         # Write document_aggregates.parquet (requires pyarrow)

hybrid:
  enabled: false              # Enable hybrid scoring
  schema_path: "config/extraction_output.schema.json"
  rubric_path: "config/hybrid_scoring.yaml"
  parse_error_behavior: "force_zero"  # force_zero | score_partial
  path_syntax: "jsonpath"
  unknown_field_policy:
    mode: "penalize"          # ignore | penalize | fail_schema
    penalty_weight: 0.1
  array_matching:
    fallback_strategy: "best_overlap"  # best_overlap | strict_non_match | error
  schema_scoring:
    required_weight: 0.4      # Weight for required-field presence
    type_weight: 0.3          # Weight for type correctness
    enum_weight: 0.2          # Weight for enum compliance
    additional_properties_weight: 0.1  # Weight for no-extra-fields
```

### 8.4 Business Settings (`config/business_settings.yaml`)

```yaml
business_config_version: "1.0.0"

rounding:
  precision: 4                # Decimal places for reported metrics

readiness:
  weights:
    success: 0.35             # Weight for success_rate_mean
    stability: 0.20           # Weight for stability_score
    quality: 0.25             # Weight for mean quality score
    risk: 0.12                # Weight for normalized expected cost (subtracted)
    critical: 0.08            # Weight for critical_failure_rate (subtracted)

normalization:
  expected_cost_per_1000_cap: 10000.0  # Cap for cost normalization to [0,1]

warnings:
  soft_warning_margin: 0.01   # Distance margin for soft warning triggers
```

### 8.5 Business Thresholds (`config/business_thresholds.yaml`)

Defines scenario-specific decision gates. All scenarios merge on top of `default`.

```yaml
business_config_version: "1.0.0"
default:
  go_threshold: 0.73
  conditional_threshold: 0.55
  hard_gates:
    max_critical_failure_rate: 0.05
    max_expected_cost_per_1000: 6000.0
    min_stability_score: 0.6

refund_handling:              # Tighter thresholds for high-risk scenario
  go_threshold: 0.72
  conditional_threshold: 0.5
  hard_gates:
    max_critical_failure_rate: 0.04
    max_expected_cost_per_1000: 5200.0
    min_stability_score: 0.62
```

### 8.6 Business Costs (`config/business_costs.yaml`)

```yaml
business_config_version: "1.0.0"
default:
  parse_error: 10.0
  runtime_error: 8.0
  incorrect: 5.0

refund_handling:              # Higher penalties for high-stakes scenario
  parse_error: 12.0
  runtime_error: 10.0
  incorrect: 7.0
```

### 8.7 Hybrid Scoring Rubric (`config/hybrid_scoring.yaml`)

```yaml
comparators:
  - name: "exact"
    type: "exact_match"
    enabled: true
    params: {}

  - name: "set_jaccard"
    type: "set_jaccard_match"
    enabled: true
    params: {}

  - name: "fuzzy_lexical"
    type: "fuzzy_lexical_match"
    enabled: true
    params:
      min_similarity: 0.85

  - name: "keyed_array"
    type: "key_based_array_object_match"
    enabled: true
    params:
      default_keys: ["id", "name"]

rules:
  - path: "$.programming_languages[*]"
    comparator: "set_jaccard"
    weight: 0.25
    options: {}

  - path: "$.education_degree[*]"
    comparator: "fuzzy_lexical"
    weight: 0.30
    options:
      normalize_case: true
```

### 8.8 Project YAML Spec (`config/project_eval_example.yaml`)

Single-file project mode keeps all run configuration in one file and uses explicit document + gold path pairs instead of a flat dataset JSON:

```yaml
experiment:
  name: "cv-eval-project"
  num_runs: 3
  ...
data:
  prompt_path: "prompts/extraction_prompt.txt"
  prompt_id: "cv-extraction-v1"
  documents:
    - id: "cv-001"
      document_path: "examples/cvs/cv_001.txt"
      gold_path: "examples/gold/cv_001.json"
```

### 8.9 Extraction Output JSON Schema (`config/extraction_output.schema.json`)

A JSON Schema (Draft 2020-12) specifying the expected shape of LLM extraction output. Used by the hybrid schema scoring component. Defines required fields, type constraints, and enum values for the target extraction domain.

### 8.10 EvalConfig Dataclass Reference

All config sections map to typed dataclasses in `config_loader.py`:

| Dataclass | Section | Key fields |
|---|---|---|
| `EvalConfig` | root | experiment, data, model, execution, tracking, exports, hybrid, config_path |
| `ExperimentConfig` | experiment | name, seed, output_dir, num_runs |
| `DataConfig` | data | dataset_path, prompt_path, prompt_id, documents, extraction_fields |
| `ProjectDocumentConfig` | data.documents[] | id, document_path, gold_path |
| `ModelConfig` | model | provider, model, temperature, top_p, max_tokens |
| `ExecutionConfig` | execution | max_retries, retry_backoff_seconds, timeout_seconds, continue_on_error |
| `TrackingConfig` | tracking | enable_mlflow, tracking_uri, tags |
| `ExportConfig` | exports | write_jsonl, write_csv, write_parquet |
| `HybridScoringConfig` | hybrid | enabled, schema_path, rubric_path, parse_error_behavior, path_syntax, unknown_field_policy, array_matching, schema_scoring, comparators, rules |
| `UnknownFieldPolicyConfig` | hybrid.unknown_field_policy | mode, penalty_weight |
| `ArrayMatchingConfig` | hybrid.array_matching | fallback_strategy |
| `SchemaScoringConfig` | hybrid.schema_scoring | required_weight, type_weight, enum_weight, additional_properties_weight |
| `ComparatorConfig` | hybrid comparators[] | name, type, enabled, params |
| `RubricRuleConfig` | hybrid rules[] | path, comparator, weight, options |

---

## 9. Non-Functional Requirements

### 9.1 Reproducibility

Every experiment captures a `provenance.json` containing:
- `experiment_id` — UUID-based unique identifier.
- `experiment_name` — Human-readable label from config.
- `input_mode` — `"project"` or `"dataset"`.
- `dataset_path` and `dataset_sha256` — File path and SHA-256 hash of the input dataset.
- `prompt_path` and `prompt_sha256` — File path and SHA-256 hash of the prompt.
- `project_config_path` and `project_spec_sha256` — Project YAML path and hash (project mode only).
- `provider` and `model` — Provider and model ID used.
- `evaluation_timestamp` — UTC ISO-8601 timestamp.
- `git_commit_hash` — Git HEAD hash at evaluation time (or `null` if unavailable).

Business evaluation adds `replay_metadata.json` with a SHA-256 hash of the effective merged business config.

### 9.2 Resilience

- **Retry logic**: Bounded exponential-backoff on provider failures (`max_retries`, `retry_backoff_seconds`).
- **Continue on error**: When `continue_on_error: true`, a failed document is recorded as a zero-metric run and evaluation continues.
- **Optional components**: MLflow, hybrid scoring, Parquet export, and the API runtime can all be absent without breaking the core pipeline.
- **Config validation**: `load_eval_config()`, `load_business_settings()`, `load_business_thresholds()`, and `validate_business_contract()` all fail fast with actionable error messages.

### 9.3 Testability

- 22 test files in `tests/`, covering unit and integration scenarios.
- All LLM provider calls are mocked with `unittest.mock.patch`.
- Parametrized tests for comparator variants, threshold edge cases, and metric aggregation.
- Contract regression tests (`test_business_contract_regression.py`) verify the business contract schema does not change unintentionally.
- Test pyramid: ~70% unit, ~20% integration.

**Test file coverage map**:

| File | Coverage |
|---|---|
| `test_providers.py` | OpenAI and Gemini provider call/response mocking |
| `test_json_parsing.py` | JSON extraction from fenced, raw, and bracket formats |
| `test_config_loader_branches.py` | Config merge hierarchy, env vars, CLI overrides |
| `test_project_config.py` | Project YAML parsing and document materialization |
| `test_project_run.py` | End-to-end mocked run from project YAML |
| `test_repeated_runs.py` | Multi-run aggregate consistency |
| `test_metrics.py` | Precision/recall/F1, document and corpus aggregation |
| `test_hybrid_schema.py` | Schema scoring and unknown field handling |
| `test_hybrid_comparators.py` | All five comparator types |
| `test_analysis_and_variance.py` | Variance analysis, phase-8 questions, instability metrics |
| `test_dataset_validation.py` | Dataset shape validation |
| `test_provider_normalization.py` | Extraction output normalization and schema validation |
| `test_business_adapter.py` | Business contract loading from evaluator artifacts |
| `test_business_metrics.py` | Item-level metric computation, five-number summaries |
| `test_business_recommender.py` | Readiness recommendation logic, hard gate enforcement |
| `test_business_reporting.py` | Report building and explainability payloads |
| `test_business_contract_regression.py` | Business contract schema regression |
| `test_business_service.py` | Service boundary request/response contract |
| `test_business_api_runtime.py` | FastAPI endpoint payload validation |
| `test_persistence_extra.py` | Artifact I/O: JSONL, CSV, Parquet, provenance |
| `test_mlflow_utils.py` | MLflow tracker initialization, metric logging, graceful failures |

### 9.4 Extensibility

The system is designed for low-friction extension at defined seams:

| Extension point | How |
|---|---|
| New LLM provider | Add `providers/<name>_provider.py`, register in `extraction/extractor.py` |
| New value comparator | Add function in `evaluation/hybrid_comparators.py`, register in `hybrid_scoring.py` `_resolve_comparator_fn()` |
| New evaluation metric | Add to `evaluation/metrics.py`, add field to `evaluation/run_record.py`, add export in `persistence.py` |
| New business failure mode | Add to `config/business_costs.yaml`, add detection logic in `business/metrics.py` |
| New business scenario | Add named block to `config/business_thresholds.yaml` and `config/business_costs.yaml` |
| New export format | Add writer function in `persistence.py`, add config flag in `ExportConfig` |
| New CLI flag | Add `argparse` argument in `run_evaluation.py`, add mapping in `config_loader.py` `_cli_overrides()` |

### 9.5 Observability

Every run captures:
- `latency_ms` — Wall-clock time for the provider call in milliseconds.
- `input_tokens` and `output_tokens` — Token counts from the provider response (where available).
- `estimated_cost` — Cost estimate (provider-specific, may be `null`).
- `parse_status` — Categorical outcome: `success`, `parse_error`, `schema_error`, `provider_error`.

All of these are aggregated into document and corpus summaries and logged to MLflow.

---

## 10. API Contract

### 10.1 Server

Optional FastAPI server started via `run_business_api.py`. Requires `fastapi` and `uvicorn` from `requirements-api.txt`.

**App title**: `"Business Evaluation API"`, version `"1.0.0"`.

### 10.2 Endpoint

```
POST /business/evaluate
Content-Type: application/json
```

### 10.3 Request Payload

```json
{
  "experiment_dir": "outputs/experiments/exp-0837df5b02be",
  "scenario": "default",
  "settings_config_path": "config/business_settings.yaml",
  "thresholds_config_path": "config/business_thresholds.yaml",
  "costs_config_path": "config/business_costs.yaml",
  "contract_config_path": "config/business_contract.yaml",
  "output_dir": null,
  "write_artifacts": true
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `experiment_dir` | string | **Yes** | — | Path to experiment artifacts directory |
| `scenario` | string | No | `"default"` | Business scenario name |
| `settings_config_path` | string | No | `"config/business_settings.yaml"` | Business settings YAML |
| `thresholds_config_path` | string | No | `"config/business_thresholds.yaml"` | Business thresholds YAML |
| `costs_config_path` | string | No | `"config/business_costs.yaml"` | Business costs YAML |
| `contract_config_path` | string | No | `"config/business_contract.yaml"` | Business contract YAML |
| `output_dir` | string\|null | No | `null` | Output directory; defaults to `<experiment_dir>/business` |
| `write_artifacts` | boolean | No | `true` | Whether to write output files to disk |

### 10.4 Response Payload

On success (`200 OK`), returns the serialized `BusinessServiceResponse`:

```json
{
  "dashboard_summary": {
    "scenario": "default",
    "deployment_recommendation": "GO",
    "readiness_score": 0.7412,
    "go_threshold": 0.73,
    "conditional_threshold": 0.55,
    "hard_gate_failures": [],
    "soft_warnings": ["readiness_near_go_threshold"],
    "metric_contributions": { "success": 0.287, "stability": 0.156, ... },
    "threshold_proximity": { "to_go_threshold": 0.0012, ... },
    "dominant_failure_modes": [ {"mode": "parse_error", "rate": 0.08} ],
    "top_failing_items": [ {"item_id": "doc-005", "failure_probability": 0.4, ...} ],
    "scenario_summary": { "success_rate_mean": 0.82, ... }
  },
  "replay_metadata": {
    "effective_config_hash": "sha256:abcd...",
    "effective_config": { ... },
    "generated_at": "2026-04-26T10:00:00+00:00"
  },
  "scenario_csv_rows": [ { ... } ],
  "item_csv_rows": [ { ... }, ... ],
  "artifact_paths": {
    "dashboard_summary": "outputs/experiments/.../business/dashboard_summary.json",
    "replay_metadata": "outputs/experiments/.../business/replay_metadata.json",
    "scenario_csv": "outputs/experiments/.../business/scenario_business_summary.csv",
    "item_csv": "outputs/experiments/.../business/item_business_breakdown.csv"
  }
}
```

### 10.5 Error Responses

| HTTP Status | Condition |
|---|---|
| `400 Bad Request` | `experiment_dir` is missing/empty, or business contract validation fails |
| `500 Internal Server Error` | Unexpected runtime error |

### 10.6 Internal Service Boundary

The API is a thin adapter over `business/service.py`. The `BusinessServiceRequest` / `BusinessServiceResponse` contract is the stable boundary — it can be used directly in Python code without the API:

```python
from business.service import BusinessServiceRequest, run_business_service

request = BusinessServiceRequest(
    experiment_dir="outputs/experiments/exp-0837df5b02be",
    scenario="default",
)
response = run_business_service(request)
print(response.dashboard_summary["deployment_recommendation"])
```

---

## 11. Data Schemas & Contracts

### 11.1 `CanonicalRunRecord`

Defined in `evaluation/run_record.py`. One record per LLM call.

| Field | Type | Description |
|---|---|---|
| `experiment_id` | str | Unique experiment identifier (`exp-<uuid12>`) |
| `document_id` | str | Document identifier from dataset |
| `provider` | str | LLM provider name (`openai` \| `gemini`) |
| `model` | str | Model ID used for this run |
| `prompt_id` | str | Prompt version identifier |
| `dataset_id` | str | Dataset path or project spec path |
| `run_index` | int | 0-based run index within the document |
| `timestamp` | str | UTC ISO-8601 timestamp of this run |
| `raw_response_text` | str | Raw text returned by the provider |
| `parsed_output_json` | dict | Parsed and normalized JSON output (empty dict on failure) |
| `parse_status` | str | `success` \| `parse_error` \| `schema_error` \| `provider_error` |
| `error_message` | str\|null | Error detail when parse_status != success |
| `latency_ms` | float | Provider call wall-clock time in milliseconds |
| `input_tokens` | int\|null | Input token count from provider |
| `output_tokens` | int\|null | Output token count from provider |
| `estimated_cost` | float\|null | Estimated API cost (provider-specific) |
| `precision` | float | Set-overlap precision vs gold |
| `recall` | float | Set-overlap recall vs gold |
| `f1` | float | Harmonic mean of precision and recall |
| `exact_match_with_gold` | bool | Whether parsed output exactly matches gold JSON |
| `hybrid_total_score` | float | Combined hybrid score (0.0 if hybrid disabled) |
| `hybrid_schema_score` | float | Schema component score |
| `hybrid_value_score` | float | Value/rubric component score |
| `hybrid_unknown_penalty` | float | Applied unknown-field penalty |
| `hybrid_rule_coverage` | float | Fraction of rubric rules matched |

### 11.2 `DocumentAggregateRecord` and `CorpusAggregateRecord`

Both extend `AggregateRecordBase` (defined in `evaluation/run_record.py`).

**`AggregateRecordBase` fields** (shared):

| Field | Type | Description |
|---|---|---|
| `mean_precision` | float | Mean precision across runs |
| `std_precision` | float | Standard deviation of precision |
| `ci95_precision` | float | 95% CI half-width for precision |
| `mean_recall` | float | Mean recall |
| `std_recall` | float | Std deviation of recall |
| `ci95_recall` | float | 95% CI half-width for recall |
| `mean_f1` | float | Mean F1 |
| `std_f1` | float | Std deviation of F1 |
| `ci95_f1` | float | 95% CI half-width for F1 |
| `exact_match_consistency_rate` | float | Fraction of runs matching modal JSON output |
| `parse_error_rate` | float | Fraction of runs with non-success parse_status |
| `latency_mean` | float | Mean latency (ms) |
| `latency_std` | float | Std deviation of latency |
| `cost_mean` | float | Mean estimated cost |
| `cost_std` | float | Std deviation of cost |
| `precision_five_number` | FiveNumberSummary | min/Q1/median/Q3/max for precision |
| `recall_five_number` | FiveNumberSummary | min/Q1/median/Q3/max for recall |
| `f1_five_number` | FiveNumberSummary | min/Q1/median/Q3/max for F1 |

**`DocumentAggregateRecord` additional fields**:

| Field | Type |
|---|---|
| `experiment_id` | str |
| `document_id` | str |
| `provider` | str |
| `model` | str |
| `prompt_id` | str |
| `dataset_id` | str |
| `run_count` | int |
| `mean_hybrid_score` | float |
| `std_hybrid_score` | float |
| `ci95_hybrid_score` | float |

**`CorpusAggregateRecord` additional fields**:

| Field | Type |
|---|---|
| `experiment_id` | str |
| `provider` | str |
| `model` | str |
| `prompt_id` | str |
| `dataset_id` | str |
| `document_count` | int |
| `run_count` | int |
| `timestamp` | str |
| `mean_hybrid_score` | float |
| `std_hybrid_score` | float |
| `ci95_hybrid_score` | float |

### 11.3 Business Contract Input Schema

Defined in `business/contracts.py` as `BUSINESS_CONTRACT_SCHEMA` (Draft 2020-12 JSON Schema).

Top-level required fields:
- `business_contract_version` (string)
- `source_experiment_dir` (string)
- `corpus` (object — see below)
- `items` (array — see below)

**`corpus` object** (required fields):
```
experiment_id, provider, model, prompt_id, dataset_id,
run_count (int≥0), document_count (int≥0),
mean_f1 (number), parse_error_rate ([0,1]), failure_rate ([0,1])
```

**`items` array elements** (required fields per item):
```
item_id (string)
runs (array of run objects):
    run_id (int≥0), output (string),
    scores (object with precision/recall/f1 + any additional numeric scores),
    failure_modes (array of strings),
    parse_status (string), error_message (string|null)
evaluator_aggregates (object with at minimum):
    mean_precision, mean_recall, mean_f1,
    parse_error_rate, exact_match_consistency_rate, run_count
```

### 11.4 Provider Output Dict

Unified output schema from both `providers/openai_provider.py` and `providers/gemini_provider.py`:

```python
{
    "provider": str,                  # "openai" | "gemini"
    "model": str,                     # Model ID
    "raw_response_text": str,         # Raw text from provider
    "parsed_output_json": dict,       # Parsed JSON (empty dict on failure)
    "parse_status": str,              # "success" | "parse_error" | "provider_error"
    "error_message": str | None,      # Error detail
    "latency_ms": float,              # Wall-clock latency
    "input_tokens": int | None,       # Prompt token count
    "output_tokens": int | None,      # Completion token count
    "estimated_cost": float | None,   # API cost estimate
    "model_params_used": {
        "temperature": float,
        "top_p": float,
        "max_tokens": int,
    }
}
```

### 11.5 Dataset JSON Schema (Legacy Mode)

```json
[
  {
    "id": "doc-001",
    "text": "Full document text...",
    "gold": {
      "methods": ["BERT"],
      "tasks": ["named entity recognition"],
      "datasets": ["CoNLL"]
    }
  }
]
```

- `id`: unique document identifier
- `text`: full document text passed to the prompt template
- `gold`: expected extraction output; field values must be lists of strings

### 11.6 Gold File Schema (Project Mode)

Each `gold_path` file contains a JSON object matching the extraction target fields:

```json
{
  "methods": ["Python"],
  "tasks": ["Information Extraction"],
  "datasets": []
}
```

---

## 12. Developer Workflow & CLI Reference

### 12.1 Environment Setup

```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows

# 2. Install core dependencies
pip install -r requirements.txt

# 3. Install API dependencies (optional)
pip install -r requirements-api.txt

# 4. Configure API keys
cp .env-template .env
# Edit .env and add:
#   OPENAI_API_KEY=sk-...
#   GEMINI_API_KEY=AI...
```

### 12.2 Scaffold a New Local Project

```bash
scripts/new_local_eval_project.sh my-project-name
python run_evaluation.py --config .local/eval_projects/my-project-name/project.yaml
```

### 12.3 `run_evaluation.py` — Full CLI Reference

```
python run_evaluation.py [OPTIONS]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--config` | str | `config/eval_settings.yaml` | Path to evaluation config YAML |
| `--provider` | str | — | Override: LLM provider (`openai` \| `gemini`) |
| `--model` | str | — | Override: model ID |
| `--dataset-path` | str | — | Override: path to dataset JSON (legacy mode) |
| `--prompt-path` | str | — | Override: path to prompt template file |
| `--prompt-id` | str | — | Override: prompt version identifier |
| `--num-runs` | int | — | Override: number of repeated runs per document |
| `--output-dir` | str | — | Override: root output directory |
| `--experiment-name` | str | — | Override: MLflow experiment name |
| `--tracking-uri` | str | — | Override: MLflow tracking URI |
| `--enable-mlflow` | flag | — | Enable MLflow tracking |
| `--disable-mlflow` | flag | — | Disable MLflow tracking |
| `--max-retries` | int | — | Override: max provider retry attempts |
| `--retry-backoff` | int | — | Override: base retry backoff in seconds |
| `--temperature` | float | — | Override: model temperature |
| `--top-p` | float | — | Override: nucleus sampling parameter |
| `--max-tokens` | int | — | Override: maximum output tokens |

**Examples**:
```bash
# Run with project YAML
python run_evaluation.py --config config/project_eval_example.yaml

# Run with overrides
python run_evaluation.py --config config/eval_settings.yaml \
  --provider gemini --model gemini-1.5-pro --num-runs 10 \
  --disable-mlflow

# Run with environment variable overrides
LIE_NUM_RUNS=3 LIE_PROVIDER=openai python run_evaluation.py
```

**Outputs** written to `outputs/experiments/<experiment-id>/`:
- `runs.jsonl`
- `document_aggregates.csv` / `document_aggregates.parquet`
- `corpus_summary.json`
- `provenance.json`
- `config.json`
- `phase8_analysis.json`
- `hybrid_component_trends.csv` (if hybrid enabled)
- `hybrid_path_breakdown.csv` (if hybrid enabled)

### 12.4 `run_business_evaluation.py` — Full CLI Reference

```
python run_business_evaluation.py [OPTIONS]
```

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `--experiment-dir` | str | **Yes** | — | Path to evaluator output directory |
| `--scenario` | str | No | `"default"` | Business scenario name |
| `--settings-config` | str | No | `config/business_settings.yaml` | Business settings YAML |
| `--thresholds-config` | str | No | `config/business_thresholds.yaml` | Business thresholds YAML |
| `--costs-config` | str | No | `config/business_costs.yaml` | Business costs YAML |
| `--contract-config` | str | No | `config/business_contract.yaml` | Business contract version YAML |
| `--output-dir` | str | No | `<experiment-dir>/business` | Output directory for business artifacts |

**Examples**:
```bash
# Default scenario
python run_business_evaluation.py \
  --experiment-dir outputs/experiments/exp-0837df5b02be

# Custom scenario
python run_business_evaluation.py \
  --experiment-dir outputs/experiments/exp-0837df5b02be \
  --scenario refund_handling

# Custom config files
python run_business_evaluation.py \
  --experiment-dir outputs/experiments/exp-0837df5b02be \
  --scenario refund_handling \
  --thresholds-config config/custom_thresholds.yaml \
  --costs-config config/custom_costs.yaml \
  --output-dir /tmp/business-reports
```

**Outputs** written to `<experiment-dir>/business/`:
- `dashboard_summary.json`
- `replay_metadata.json`
- `scenario_business_summary.csv`
- `item_business_breakdown.csv`

### 12.5 `run_business_api.py` — Full CLI Reference

```
python run_business_api.py [OPTIONS]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--host` | str | `127.0.0.1` | Bind host for the API server |
| `--port` | int | `8000` | Bind port |
| `--reload` | flag | — | Enable auto-reload (development mode) |

**Examples**:
```bash
# Production-like local run
python run_business_api.py --host 127.0.0.1 --port 8000

# Development mode with auto-reload
python run_business_api.py --port 8000 --reload
```

### 12.6 Makefile Commands

Run from the project root with `.venv` activated (or set `PYTHON` variable):

| Command | Description |
|---|---|
| `make business-eval` | Run business evaluation for `EXPERIMENT_DIR` and `SCENARIO` |
| `make business-api` | Start the FastAPI server on `HOST:PORT` |
| `make business-api-smoke` | Run the API smoke-check script against `BASE_URL` |
| `make test-business` | Run all business-layer tests |

**Makefile variables** (with defaults):

| Variable | Default | Description |
|---|---|---|
| `PYTHON` | `.venv/bin/python` | Python interpreter path |
| `EXPERIMENT_DIR` | `outputs/experiments/exp-0837df5b02be` | Target experiment directory |
| `SCENARIO` | `default` | Business scenario name |
| `HOST` | `127.0.0.1` | API server bind host |
| `PORT` | `8000` | API server bind port |
| `BASE_URL` | `http://$(HOST):$(PORT)` | Base URL for smoke test |

**Examples**:
```bash
make business-eval EXPERIMENT_DIR=outputs/experiments/my-exp SCENARIO=refund_handling
make business-api PORT=9000
make business-api-smoke BASE_URL=http://127.0.0.1:9000 EXPERIMENT_DIR=outputs/experiments/my-exp
make test-business
```

### 12.7 Running Tests

```bash
# All tests
python -m pytest tests/ -q

# Business layer tests only
make test-business

# Specific test file
python -m pytest tests/test_business_recommender.py -v

# With coverage
python -m pytest tests/ --cov=. --cov-report=term-missing
```

### 12.8 API Smoke Check

```bash
# Via Makefile
make business-api-smoke

# Directly
./scripts/business_api_smoke.sh http://127.0.0.1:8000 outputs/experiments/exp-0837df5b02be default
```

Arguments are positional and optional (defaults shown above).

---

## 13. AI Agent Workflow (Vibecoding)

This section documents the conventions for working on this project with AI coding agents (Claude-powered, GitHub Copilot, and similar). These are as-implemented conventions derived from `AGENTS.md` and the codebase structure — not aspirational guidelines.

### 13.1 CLAUDE-First Operating Rules

These rules take highest priority over all other guidance. They are defined in `AGENTS.md` §0.

**Think Before Coding** — State assumptions explicitly before implementation. If multiple interpretations of a request are plausible, present options. Do not hide uncertainty or guess silently.

**Simplicity First** — Implement the minimum code needed to satisfy the request. Do not add speculative flexibility, extensibility, or configuration not requested by the user. Avoid over-engineering.

**Surgical Changes** — Touch only files and code paths required for the task. Do not refactor unrelated code. Match existing style and conventions in every file touched.

**Goal-Driven Verification** — Define explicit success criteria before coding. Treat completion as "implemented + verified", not just "code written". For bug fixes: reproduce the failure, then verify the fix. For feature changes: verify with focused tests and realistic sample data.

### 13.2 Project-Specific Module Map

Before making any change, identify the minimal set of files to touch using this map:

| Task | Files to change |
|---|---|
| Add a new LLM provider | `providers/<new>_provider.py` (new) → `extraction/extractor.py` (`run_extraction` routing) → `config_loader.py` (validation if needed) |
| Add a new value comparator | `evaluation/hybrid_comparators.py` (new function) → `evaluation/hybrid_scoring.py` (`_resolve_comparator_fn` mapping) |
| Add a new evaluation metric (per-run) | `evaluation/metrics.py` (computation) → `evaluation/run_record.py` (`CanonicalRunRecord` field) → `persistence.py` (ensure field is serialized) |
| Add a new document/corpus aggregate metric | `evaluation/metrics.py` → `evaluation/run_record.py` (`DocumentAggregateRecord` / `CorpusAggregateRecord`) → `persistence.py` |
| Add a new business failure mode | `config/business_costs.yaml` (new key) → `business/metrics.py` (detection logic) |
| Change readiness scoring weights | `config/business_settings.yaml` only — no code change |
| Add a new business scenario | `config/business_thresholds.yaml` (new named block) → `config/business_costs.yaml` (new named block) — no code change |
| Add a new CLI flag | `run_evaluation.py` (argparse `add_argument`) → `config_loader.py` (`_cli_overrides()` mapping) |
| Add a new artifact export format | `persistence.py` (new writer function) → `config_loader.py` (`ExportConfig` dataclass) → `config/eval_settings.yaml` |
| Add a new business output artifact | `business/reporting.py` (`write_business_report_artifacts`) |
| Change hard gate logic | `business/recommender.py` (`recommend_deployment`) |
| Change readiness score formula | `business/recommender.py` + `business/explainability.py` (`metric_contributions`) |

### 13.3 Research Protocol for This Codebase

Use this sequence before writing any code:

**For evaluation changes**:
1. Read `config_loader.py` — understand the full config shape and all typed dataclasses.
2. Read the relevant `evaluation/` module.
3. Check `evaluation/run_record.py` — does the change require a new field on `CanonicalRunRecord`, `DocumentAggregateRecord`, or `CorpusAggregateRecord`?
4. Check `persistence.py` — does the change require a new export or writer?
5. Use `grep_search` to find all call sites of the function being changed.

**For business evaluation changes**:
1. Read `business/types.py` — understand `BusinessRunInput`, `BusinessItemInput`, `BusinessCorpusInput`.
2. Read `business/metrics.py` — understand `evaluate_item()`.
3. Read `business/recommender.py` — understand `recommend_deployment()`.
4. Check `business/contracts.py` — does the change require updating `BUSINESS_CONTRACT_SCHEMA`?
5. Use `semantic_search` for concept discovery, `grep_search` for exact symbol lookups.

**For config changes**:
1. Read `config_loader.py` `DEFAULT_CONFIG` first — this defines all defaults.
2. Trace the relevant YAML section to its dataclass.
3. Check if the config key needs a CLI override mapping in `_cli_overrides()`.
4. Check if it needs an env var mapping in `_env_overrides()`.

### 13.4 Testing Conventions

**Test location**: All tests in `tests/`, named `test_{module}.py`.

**LLM provider mocking** — Always mock at the provider function boundary:
```python
from unittest.mock import patch

with patch("extraction.extractor.run_openai") as mock_run:
    mock_run.return_value = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "parse_status": "success",
        "parsed_output_json": {"methods": ["BERT"], "tasks": [], "datasets": []},
        ...
    }
```

**Config stubs** — Use `EvalConfig` dataclasses directly for isolated unit tests rather than loading YAML files.

**Parametrized tests** — Use `@pytest.mark.parametrize` for comparator variants, threshold edge cases, and metric boundary conditions.

**Contract regression** — `test_business_contract_regression.py` validates `BUSINESS_CONTRACT_SCHEMA` against sample payloads. Add a new fixture if you change the contract schema.

**Running tests**:
```bash
source .venv/bin/activate
python -m pytest tests/ -q
```

**After any code change**: run `get_errors()` on modified files before committing.

### 13.5 Architecture Patterns to Follow

**Pure functions for computation, orchestration functions for I/O** — `evaluate_item()`, `recommend_deployment()`, `compute_metrics()` are pure functions. `build_business_report()`, `run_extraction()`, `main()` orchestrate I/O. Keep them separate.

**Dataclasses for structured data** — All data contracts use Python `@dataclass`. Do not use plain dicts for new inter-module data.

**Config objects passed explicitly** — Functions receive `EvalConfig` or specific sub-configs as arguments. Do not read YAML files inside computation functions.

**Fail fast at boundaries** — Validate inputs at the earliest possible point: config load, contract validation, or API endpoint entry. Use actionable error messages:
```python
raise ValueError(
    f"Experiment directory '{experiment_dir}' does not exist. "
    "Run: python run_evaluation.py first."
)
```

**Graceful degradation pattern** — Wrap optional dependencies in try/except at the call site; degrade to no-op with a warning print, not an exception:
```python
try:
    import mlflow
except ImportError:
    print("[warning] MLflow not installed. Continuing without tracking.")
    self.enabled = False
    return MLflowRunContext(enabled=False, run_id=None)
```

### 13.6 Commit & Branch Conventions

**Commit type prefixes** (mandatory):

| Type | Use for |
|---|---|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `test` | Tests only |
| `refactor` | Code restructuring, no behavior change |
| `perf` | Performance improvement |
| `chore` | Dependency updates, tooling, config changes |

**Commit message rules**:
- Imperative mood: "Add feature" not "Added feature".
- Subject line ≤72 characters.
- No emojis.
- Reference issue numbers in footer: `Fixes #123`.
- No vague messages: no "fix stuff", "updates", "wip".

**Branch naming**:
- `feature/<description>`
- `fix/<description>`
- `test/<description>`
- `docs/<description>`
- `refactor/<description>`

**Documentation-only commits** (if pre-commit hooks are in use):
```bash
git commit --no-verify -m "docs: update PRD with API contract details"
```

### 13.7 Error Handling Patterns

- **Validate at system boundaries**: config load (`load_eval_config`), API endpoint entry (`evaluate_business_payload`), provider call (`run_extraction`).
- **Actionable error messages**: always tell the user what to do next, not just what went wrong.
- **Graceful degradation for optional components**: MLflow, Parquet, hybrid scoring, and the FastAPI runtime can all be absent without breaking the core pipeline.
- **Do not validate inside pure computation functions**: validation belongs at the boundary; computation functions may assume valid input.

### 13.8 AGENTS.md Reference

The full agent coding guide lives in [`AGENTS.md`](AGENTS.md) at the project root. It covers:
- §0: CLAUDE-First Operating Rules (highest priority)
- §1: Coding best practices (architecture patterns, error handling, function length)
- §2: Documentation policy (where to document, when not to create new .md files)
- §3: Testing best practices (test pyramid, fixtures, parametrization)
- §4: AI agent workflow protocols (context gathering, incremental implementation, verification checklists)
- §5: Common patterns and anti-patterns (DRY, type-safe returns, config injection)
- §6: Project-specific guidelines (engine/pipeline patterns, config file roles)
- §7: Summary checklists (pre/during/post-implementation)
- §9: Version control best practices (commit structure, branch naming)

---

## 14. Glossary

| Term | Definition |
|---|---|
| `CanonicalRunRecord` | The per-run data record written to `runs.jsonl`. Contains all LLM call outputs, parsed JSON, metric scores, and hybrid scores for a single document × run combination. |
| Business contract | The structured input payload consumed by the business evaluation layer. Assembled from evaluator artifacts by `business/artifacts_loader.py` and validated against `BUSINESS_CONTRACT_SCHEMA`. |
| Business scenario | A named configuration variant for business thresholds and costs. Defined as named blocks in `config/business_thresholds.yaml` and `config/business_costs.yaml`. Default scenario is `"default"`. |
| CI95 | 95% confidence interval half-width: $1.96 \times \sigma / \sqrt{n}$. Reported for precision, recall, F1, and hybrid score in aggregate records. |
| Comparator | A value comparison strategy in the hybrid scoring pipeline. Compares predicted and gold values extracted by a JSONPath rule. Five types: exact, set Jaccard, fuzzy lexical, key-based array object, best-overlap fallback. |
| Corpus | The full set of documents in an evaluation run. Corpus-level metrics aggregate all document-level results. |
| `corpus_summary.json` | Experiment-level output containing the `CorpusAggregateRecord` and total failure counts. |
| `dashboard_summary.json` | Business evaluation output containing the full deployment recommendation, readiness score, explainability payloads, and scenario summary metrics. |
| Deployment readiness | A scalar score in [0, 1] computed by the business recommender as a weighted combination of success rate, stability, quality, expected cost, and critical failure rate. |
| `document_aggregates.csv` | Flat table output containing one `DocumentAggregateRecord` row per document. |
| Document aggregate | Per-document summary statistics computed over all repeated runs: means, standard deviations, CI95s, five-number summaries, and consistency metrics. |
| Expected cost | Business metric: mean failure cost per item across all repeated runs. Computed as `sum(cost_map[failure_mode] for all failures) / run_count`. |
| Exact match consistency rate | Fraction of successful runs for a document that produce the modal (most common) JSON output. 1.0 = all runs agree. |
| `ExperimentProvenance` | Dataclass containing all reproducibility metadata for an experiment: git hash, file SHAs, config path, timestamps. Serialized to `provenance.json`. |
| Failure mode | A categorical classification of a run's failure: `parse_error`, `runtime_error`, `incorrect`. Each mode carries a configurable business cost penalty. |
| Field instability | Mean of `(1 - agreement_rate)` across all observed fields for a document. Higher = more unstable field-level outputs. |
| Five-number summary | Statistical distribution summary: min, Q1, median, Q3, max. Computed for precision, recall, and F1 in aggregate records. |
| GO | Deployment recommendation: all hard gates pass and readiness score ≥ `go_threshold`. |
| NO_GO | Deployment recommendation: hard gates pass but readiness score < `conditional_threshold`. |
| CONDITIONAL | Deployment recommendation: hard gates pass but readiness score is between `conditional_threshold` and `go_threshold`. Deploy with conditions or additional monitoring. |
| HOLD | Deployment recommendation: one or more hard gates failed. Readiness score is irrelevant. |
| Hard gate | A deployment blocker that forces a `"HOLD"` recommendation regardless of the readiness score. Three gates: `max_critical_failure_rate`, `max_expected_cost_per_1000`, `min_stability_score`. |
| Hybrid scoring | Optional dual-component scoring combining JSON Schema structural validation (schema score) and JSONPath rubric-rule value comparison (value score). Weighted combination: 35% schema + 65% value. |
| `parse_status` | Categorical outcome of a provider call: `success`, `parse_error`, `schema_error`, `provider_error`. |
| Parse error rate | Fraction of runs with `parse_status != "success"`. Tracked at both document and corpus level. |
| Provenance | Reproducibility metadata recorded with each experiment: git commit, all file SHA-256 hashes, config hash, and UTC timestamp. |
| Readiness score | The scalar deployment readiness metric produced by the business recommender. Range [0, 1]. |
| Replay metadata | Business evaluation output capturing the effective merged business configuration and its SHA-256 hash, enabling later verification that the same config was used. |
| `runs.jsonl` | Newline-delimited JSON file containing one `CanonicalRunRecord` per line. Primary evaluator output. |
| Rubric rule | A JSONPath-based value scoring rule in `config/hybrid_scoring.yaml`: specifies a path selector, a comparator name, a weight, and optional per-rule options. |
| Schema score | The JSON Schema validation component of the hybrid score. Combines required-field presence, type correctness, enum compliance, and additional-properties penalty into a single score. |
| Soft warning | A non-blocking advisory emitted when a metric is near a decision threshold or hard gate boundary (within `soft_warning_margin`). Does not change the deployment recommendation. |
| Stability score | Business layer metric: mean of per-item `agreement_rate` across all items. Measures how consistently the model produces the same output across repeated runs. |
| Value score | The rubric-rule component of the hybrid score. Weighted mean of per-path comparator scores across all active rubric rules. |

---

*This PRD was generated from the implementation as of April 2026. It is a descriptive document of the existing system, not a specification for future features. For roadmap and future extensions, see `todo_plans/` and the "Easy Future Extensions" section of `Readme.md`.*
