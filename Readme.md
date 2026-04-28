# LLM Evaluation and Probabilistic Risk Decision Platform

[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-pytest%20passing-brightgreen.svg)](#project-status)
[![Business%20Risk](https://img.shields.io/badge/business%20risk-modeling-enabled.svg)](#project-status)
[![API](https://img.shields.io/badge/api-fastapi%20optional-0ea5e9.svg)](#optional-api-runtime)
[![Contracts](https://img.shields.io/badge/contracts-regression%20covered-6f42c1.svg)](#project-status)

Aggregate metrics can mislead. A system reporting 0.83 precision across a document corpus
can still fail catastrophically on 20% of inputs, and those failures are exactly
what end users notice.

This platform evaluates LLM-based structured information extraction using a
5-number summary (min, Q1, median, Q3, max) per field and per document,
alongside precision/recall/F1 and an optional hybrid JSON rubric scoring layer.
The goal is to make worst-case behavior visible and traceable before it reaches
production, and to keep evaluation runs reproducible across model versions,
providers, and prompt iterations.

**What this is:** A working evaluation and business-decision platform for LLM
information extraction tasks, designed around the principle that distribution
shape matters more than averages. Runs are YAML-configured, MLflow-tracked,
provider-agnostic (OpenAI and Gemini included), and include a business
evaluation layer with reporting artifacts, optional API runtime, and browser UI.

**What this is not:** A polished open-source product. It is a structured
engineering sample built to solve a specific class of evaluation and risk
decision problem.


---
## TOC

- Project Status
- Documentation
- Public Repo Requirements
- Architecture Overview
- Pipeline Overview
- Run the Platform
- MLflow tracking and UI
- Run business evaluation from historical artifacts
- Service boundary scaffold
- Optional API runtime
- Add-ons: command aliases and smoke check
- Project file shape
- Hybrid JSON Rubric Scoring
- Expected output
- Running tests
- Easy Future Extensions

---

## Project Status

Current implementation status in this repository:

- Completed: Core evaluator pipeline with precision/recall/F1 outputs.
- Completed: Hybrid JSON rubric scoring modules and integration path.
- Completed: Business evaluation pipeline with reporting artifacts.
- Completed: Replay metadata and contract regression checks.
- Completed: Optional API runtime path for business evaluation.
- Completed: Browser UI for business evaluation (`business/ui_app.html`, served at `/ui`).

Scope note:

- Sections under Easy Future Extensions are roadmap ideas, not shipped features.

## Documentation

For full architecture details, data schemas, CLI reference, business logic, and AI agent conventions, see [PRD.md](PRD.md).

## Public Repo Requirements

For public repository usage, install one of these dependency sets:

- Core runtime and tests:
   - `pip install -r requirements.txt`
- Optional API runtime:
   - `pip install -r requirements-api.txt`

Required environment setup:

- Copy `.env-template` to `.env` and provide provider API keys.
- Use a Python virtual environment (recommended `.venv`).

Public artifact expectations:

- Evaluator outputs are written under `outputs/experiments/<experiment-id>/`.
- Business outputs are written under `outputs/experiments/<experiment-id>/business/`.
- API dependencies are optional and separated from core requirements.

## Architecture Overview

```
llm_ie_eval/
│
├── business/
│   ├── aggregates.py
│   ├── api.py
│   ├── artifacts_loader.py
│   ├── contracts.py
│   ├── explainability.py
│   ├── metrics.py
│   ├── recommender.py
│   ├── replay.py
│   ├── reporting.py
│   ├── service.py
│   ├── types.py
│   └── ui_app.html
│
├── config/
│   ├── business_contract.yaml
│   ├── business_costs.yaml
│   ├── business_settings.yaml
│   ├── business_thresholds.yaml
│   ├── eval_settings.yaml
│   ├── extraction_output.schema.json
│   ├── hybrid_scoring.yaml
│   └── project_eval_example.yaml
│
├── data/
│   └── dataset.json
│
├── prompts/
│   └── extraction_prompt.txt
│
├── providers/
│   ├── gemini_provider.py
│   ├── json_parsing.py
│   └── openai_provider.py
│
├── evaluation/
│   ├── analysis_questions.py
│   ├── dataset_validation.py
│   ├── hybrid_comparators.py
│   ├── hybrid_normalize.py
│   ├── hybrid_schema.py
│   ├── hybrid_scoring.py
│   ├── hybrid_types.py
│   ├── metrics.py
│   ├── run_record.py
│   └── variance_analysis.py
│
├── extraction/
│   └── extractor.py
│
├── config_loader.py
├── mlflow_utils.py
├── persistence.py
├── run_evaluation.py
├── run_business_evaluation.py
├── run_business_api.py
├── Makefile
│
└── requirements.txt
```

### Pipeline Overview
```
Dataset
   ↓
Prompt Template
   ↓
LLM Provider
   ↓
JSON Extraction
   ↓
Evaluation
   ↓
Metrics Report
   ↓
Business Metrics + Recommendation
   ↓
Dashboard JSON + BI CSV + Replay Metadata
```
----
## Run the Platform

### Install dependencies

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# Install core dependencies
pip install -r requirements.txt

# Install optional API dependencies
pip install -r requirements-api.txt
```

### Set API keys

Copy `.env-template` to `.env` and add your API keys:

```bash
cp .env-template .env
# Edit .env and set OPENAI_API_KEY and/or GEMINI_API_KEY
```

### Run evaluation

Use a single project YAML file as the source of truth for the run. A sample is available at `config/project_eval_example.yaml`.

```bash
python run_evaluation.py --config config/project_eval_example.yaml
```

To scaffold a private local project from the `.local` template:

```bash
scripts/new_local_eval_project.sh my-cv-project
python run_evaluation.py --config .local/eval_projects/my-cv-project/project.yaml
```

#### `run_evaluation.py` CLI flags

| Flag | Type | Description |
|---|---|---|
| `--config` | str | Path to evaluation config YAML (default: `config/eval_settings.yaml`) |
| `--provider` | str | Override: LLM provider (`openai` \| `gemini`) |
| `--model` | str | Override: model ID |
| `--dataset-path` | str | Override: path to dataset JSON (legacy mode) |
| `--prompt-path` | str | Override: path to prompt template file |
| `--prompt-id` | str | Override: prompt version identifier |
| `--num-runs` | int | Override: number of repeated runs per document |
| `--output-dir` | str | Override: root output directory |
| `--experiment-name` | str | Override: MLflow experiment name |
| `--tracking-uri` | str | Override: MLflow tracking URI |
| `--enable-mlflow` | flag | Enable MLflow tracking |
| `--disable-mlflow` | flag | Disable MLflow tracking |
| `--max-retries` | int | Override: max provider retry attempts |
| `--retry-backoff` | int | Override: base retry backoff in seconds |
| `--temperature` | float | Override: model temperature |
| `--top-p` | float | Override: nucleus sampling parameter |
| `--max-tokens` | int | Override: maximum output tokens |

Examples:

```bash
# Run with explicit provider and run count, MLflow off
python run_evaluation.py --config config/eval_settings.yaml \
  --provider gemini --model gemini-1.5-pro --num-runs 10 \
  --disable-mlflow

# Override via environment variables
LIE_NUM_RUNS=3 LIE_PROVIDER=openai python run_evaluation.py
```

Outputs written to `outputs/experiments/<experiment-id>/`:
- `runs.jsonl`, `failures.jsonl`
- `document_aggregates.csv` / `document_aggregates.parquet`
- `corpus_summary.json`
- `provenance.json`, `config.json`
- `phase8_analysis.json` and Phase 8 table CSVs
- `hybrid_component_trends.csv`, `hybrid_path_breakdown.csv` (if hybrid enabled)

## MLflow tracking and UI

MLflow is included in the core dependency set and is enabled by default in the
sample project config.

Default tracking configuration:

- `tracking.enable_mlflow: true`
- `tracking.tracking_uri: "sqlite:///mlflow.db"`
- Artifacts under `mlruns/`

Run an evaluation with tracking enabled:

```bash
python run_evaluation.py --config config/project_eval_example.yaml
```

Optional CLI overrides:

- Force enable: `--enable-mlflow`
- Force disable: `--disable-mlflow`
- Override URI: `--tracking-uri <uri>`

Start the MLflow UI against the same backend store:

```bash
mlflow ui --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port 5000
```

Then open `http://127.0.0.1:5000` in your browser.

### Metrics logged

**Per run** (step = global run index):

- `run_precision`, `run_recall`, `run_f1`
- `run_hybrid_total_score`, `run_hybrid_schema_score`, `run_hybrid_value_score`, `run_hybrid_unknown_penalty`, `run_hybrid_rule_coverage`
- `run_exact_match_with_gold`, `run_parse_success`, `run_parse_error`, `run_schema_error`, `run_provider_error`
- `run_latency_ms`, `run_estimated_cost`, `run_input_tokens`, `run_output_tokens`

**Per document** (step = document index):

- `document_mean_precision`, `document_std_precision`, `document_ci95_precision`
- `document_precision_min`, `document_precision_q1`, `document_precision_median`, `document_precision_q3`, `document_precision_max`
- `document_mean_recall`, `document_std_recall`, `document_ci95_recall`
- `document_recall_min`, `document_recall_q1`, `document_recall_median`, `document_recall_q3`, `document_recall_max`
- `document_mean_f1`, `document_std_f1`, `document_ci95_f1`
- `document_f1_min`, `document_f1_q1`, `document_f1_median`, `document_f1_q3`, `document_f1_max`
- `document_exact_match_consistency_rate`, `document_parse_error_rate`
- `document_mean_hybrid_score`, `document_std_hybrid_score`, `document_ci95_hybrid_score`
- `document_latency_mean`, `document_latency_std`, `document_cost_mean`, `document_cost_std`

**Corpus** (single step):

- `corpus_mean_precision`, `corpus_std_precision`, `corpus_ci95_precision`
- `corpus_precision_min`, `corpus_precision_q1`, `corpus_precision_median`, `corpus_precision_q3`, `corpus_precision_max`
- `corpus_mean_recall`, `corpus_std_recall`, `corpus_ci95_recall`
- `corpus_recall_min`, `corpus_recall_q1`, `corpus_recall_median`, `corpus_recall_q3`, `corpus_recall_max`
- `corpus_mean_f1`, `corpus_std_f1`, `corpus_ci95_f1`
- `corpus_f1_min`, `corpus_f1_q1`, `corpus_f1_median`, `corpus_f1_q3`, `corpus_f1_max`
- `corpus_mean_hybrid_score`, `corpus_std_hybrid_score`, `corpus_ci95_hybrid_score`
- `corpus_exact_match_consistency_rate`, `corpus_parse_error_rate`
- `corpus_latency_mean`, `corpus_latency_std`, `corpus_cost_mean`, `corpus_cost_std`
- `corpus_total_failures`, `corpus_failure_rate`

All experiment artifacts (runs JSONL, CSVs, Phase 8 tables, hybrid breakdowns, provenance, config snapshot) are also uploaded as MLflow artifacts.

## Run business evaluation from historical artifacts

After an evaluator run completes, generate business decision artifacts from an experiment folder:

```bash
python run_business_evaluation.py \
   --experiment-dir outputs/experiments/exp-0837df5b02be \
   --scenario default
```

This writes:

- `dashboard_summary.json`
- `replay_metadata.json`
- `scenario_business_summary.csv`
- `item_business_breakdown.csv`

By default outputs are written to `<experiment-dir>/business`.

#### `run_business_evaluation.py` CLI flags

| Flag | Type | Required | Default | Description |
|---|---|---|---|---|
| `--experiment-dir` | str | **Yes** | — | Path to evaluator output directory |
| `--scenario` | str | No | `default` | Business scenario name |
| `--settings-config` | str | No | `config/business_settings.yaml` | Business settings YAML |
| `--thresholds-config` | str | No | `config/business_thresholds.yaml` | Business thresholds YAML |
| `--costs-config` | str | No | `config/business_costs.yaml` | Business costs YAML |
| `--contract-config` | str | No | `config/business_contract.yaml` | Business contract version YAML |
| `--output-dir` | str | No | `<experiment-dir>/business` | Output directory for business artifacts |

Examples:

```bash
# Named scenario
python run_business_evaluation.py \
  --experiment-dir outputs/experiments/exp-0837df5b02be \
  --scenario refund_handling

# Custom cost and threshold files, custom output dir
python run_business_evaluation.py \
  --experiment-dir outputs/experiments/exp-0837df5b02be \
  --scenario refund_handling \
  --thresholds-config config/custom_thresholds.yaml \
  --costs-config config/custom_costs.yaml \
  --output-dir /tmp/business-reports
```

## Service boundary scaffold

The business layer now includes a stable service contract for future API extraction.

- `business.service.BusinessServiceRequest`
- `business.service.BusinessServiceResponse`
- `business.service.run_business_service(...)`

This keeps API/service integration decoupled from evaluator internals while preserving the same output contracts.

## Optional API runtime

Install optional API dependencies:

```bash
pip install -r requirements-api.txt
```

You can run an API wrapper around the business service boundary:

```bash
python run_business_api.py --host 127.0.0.1 --port 8000
```

Endpoints:

- `GET /ui` (serves the browser UI)
- `GET /business/experiment-info` (loads `corpus_summary.json` for UI metadata preview)
- `POST /business/evaluate-inline` (evaluate with inline costs/weights/thresholds and return YAML blocks)
- `POST /business/evaluate` (existing file-driven evaluation endpoint)

Example payload:

```json
{
   "experiment_dir": "outputs/experiments/exp-0837df5b02be",
   "scenario": "default",
   "write_artifacts": true
}
```

Inline evaluation payload example:

```json
{
   "experiment_dir": "outputs/experiments/exp-0837df5b02be",
   "scenario_name": "balanced_custom",
   "costs": {
      "parse_error": 10,
      "runtime_error": 8,
      "incorrect": 5
   },
   "weights": {
      "success": 0.35,
      "stability": 0.20,
      "quality": 0.25,
      "risk": 0.12,
      "critical": 0.08
   },
   "go_threshold": 0.73,
   "conditional_threshold": 0.55,
   "max_critical_failure_rate": 0.05,
   "max_expected_cost_per_1000": 6000,
   "min_stability_score": 0.60
}
```

To use the browser UI after starting the API server, open `http://127.0.0.1:8000/ui`.

`fastapi` and `uvicorn` are optional dependencies for this runtime path.

## Add-ons: command aliases and smoke check

This repository now includes optional add-ons for faster local workflows.

#### Makefile aliases

Use these shortcuts from the project root:

```bash
make business-eval EXPERIMENT_DIR=outputs/experiments/exp-0837df5b02be SCENARIO=default
make business-api HOST=127.0.0.1 PORT=8000
make business-api-smoke BASE_URL=http://127.0.0.1:8000 EXPERIMENT_DIR=outputs/experiments/exp-0837df5b02be
make test-business
```

Available variables:

- `PYTHON` (default: `.venv/bin/python`)
- `EXPERIMENT_DIR`
- `SCENARIO`
- `HOST`
- `PORT`
- `BASE_URL`

#### API smoke script

There is also a direct smoke-check helper:

```bash
./scripts/business_api_smoke.sh http://127.0.0.1:8000 outputs/experiments/exp-0837df5b02be default
```

Arguments are optional and default to:

- `base_url=http://127.0.0.1:8000`
- `experiment_dir=outputs/experiments/exp-0837df5b02be`
- `scenario=default`

## Project file shape

The project YAML keeps the run repeatable in one place:

- experiment metadata such as name, output directory, and number of repeated runs
- prompt file path and prompt identifier
- one provider/model configuration
- execution and MLflow tracking settings
- explicit document entries, where each entry includes:
   - `id`
   - `document_path`
   - `gold_path`

Each `gold_path` file must contain JSON with the evaluator's expected schema:

```json
{
   "methods": ["Python"],
   "tasks": ["Information Extraction"],
   "datasets": []
}
```

If you still want the legacy dataset mode, `data.dataset_path` continues to work. Project mode uses `data.documents` instead.

## Hybrid JSON Rubric Scoring

The evaluator now supports an optional hybrid scoring layer in addition to existing
precision/recall/F1 metrics.

Hybrid score is a weighted combination of:

- schema component: JSON Schema-aware structural validation
- value component: JSONPath rule-based value similarity with configurable comparators

Current defaults are deterministic and lexical (no embeddings).

Enable hybrid scoring in your project config:

```yaml
hybrid:
   enabled: true
   schema_path: "config/extraction_output.schema.json"
   rubric_path: "config/hybrid_scoring.yaml"
   parse_error_behavior: "force_zero"
   path_syntax: "jsonpath"
   unknown_field_policy:
      mode: "penalize"   # ignore | penalize | fail_schema
      penalty_weight: 0.1
   array_matching:
      fallback_strategy: "best_overlap"  # best_overlap | strict_non_match | error
   schema_scoring:
      required_weight: 0.4
      type_weight: 0.3
      enum_weight: 0.2
      additional_properties_weight: 0.1
```

`config/hybrid_scoring.yaml` defines:

- comparator catalog (`exact_match`, `set_jaccard_match`, `fuzzy_lexical_match`, `key_based_array_object_match`, `best_overlap_fallback_match`)
- per-path rules with JSONPath selectors and per-rule weights

Run-level outputs include hybrid fields in `runs.jsonl`:

- `hybrid_total_score`
- `hybrid_schema_score`
- `hybrid_value_score`
- `hybrid_unknown_penalty`
- `hybrid_rule_coverage`

Additional analysis artifacts are generated per experiment:

- `hybrid_component_trends.csv`
- `hybrid_path_breakdown.csv`

Aggregate artifacts (`document_aggregates.csv`, `corpus_summary.json`) include
hybrid aggregate stats:

- `mean_hybrid_score`
- `std_hybrid_score`
- `ci95_hybrid_score`

## Expected output

```
Example:

DOCUMENT: doc1
Prediction: {'methods': ['BERT'], 'tasks': ['named entity recognition'], 'datasets': ['CoNLL']}
Gold: {'methods': ['BERT'], 'tasks': ['named entity recognition'], 'datasets': ['CoNLL']}
Metrics: {'precision': 1.0, 'recall': 1.0, 'f1': 1.0}

=== FINAL RESULTS ===
Precision: 0.83
Recall: 0.78
F1: 0.80
```

## Running tests

```bash
# All tests
python -m pytest tests/ -q

# Business layer only
make test-business

# Specific test file
python -m pytest tests/test_business_recommender.py -v

# With coverage
python -m pytest tests/ --cov=. --cov-report=term-missing
```

---

## Easy Future Extensions

This architecture easily supports:

### More providers

Add files:
```
providers/
claude_provider.py
mistral_provider.py
```
### Multilingual evaluation

Add datasets in:
```
data/
dataset_en.json
dataset_de.json
dataset_hr.json
```
### Semantic matching

Add embeddings via

`sentence-transformers`

### Experiment tracking

Add:
```
results/
openai_results.json
gemini_results.json
```

