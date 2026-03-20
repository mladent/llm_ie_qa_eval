# To-Do List: LLM JSON Extraction Evaluation Platform

## Objective

Extend the current evaluator from a single-pass script into an experiment framework for structured JSON extraction benchmarking. The platform should support repeated per-document LLM calls, variance analysis across repeated runs, local MLflow tracking, and analysis-friendly exports so quality variation can be measured both across a corpus and within repeated runs of the same document.

## Core Principles

1. Keep the current evaluation flow as the base rather than replacing it.
2. Add a stable internal schema before adding MLflow or exports.
3. Treat each repeated LLM call as a first-class run record.
4. Persist intermediate results immediately so partial failures do not lose completed work.
5. Separate orchestration, provider normalization, metrics, persistence, and tracking concerns.
6. Optimize for observability and correctness before adding concurrency.

## Phase 1: Define the Experiment Contract ✅

### 1.1 Define a canonical run-level record

Create a single internal schema that every part of the system will use.

Required fields:

- `experiment_id`
- `document_id`
- `provider`
- `model`
- `prompt_id` or `prompt_version`
- `dataset_id` or dataset path/hash
- `run_index`
- `timestamp`
- `raw_response_text`
- `parsed_output_json`
- `parse_status`
- `error_message`
- `latency_ms`
- `input_tokens`
- `output_tokens`
- `estimated_cost`
- `precision`
- `recall`
- `f1`
- `exact_match_with_gold`

Reason:

Everything else depends on this. MLflow logging, CSV or Parquet export, repeated-run aggregation, and failure analysis all become much simpler once the run schema is fixed.

### 1.2 Define aggregate record schemas

Create explicit aggregate record types for:

1. Per-document repeated-run summary
2. Corpus-level summary
3. Optional provider/model comparison summary

Required aggregate fields:

- `mean_precision`, `std_precision`, `ci95_precision`
- `mean_recall`, `std_recall`, `ci95_recall`
- `mean_f1`, `std_f1`, `ci95_f1`
- `exact_match_consistency_rate`
- `parse_error_rate`
- `latency_mean`, `latency_std`
- `cost_mean`, `cost_std`
- Five-number summary for key metrics:
  - `min`
  - `q1`
  - `median`
  - `q3`
  - `max`

## Phase 2: Add Configuration and CLI Control ✅

### 2.1 Refactor [run_evaluation.py](run_evaluation.py)

Turn the current script into the main experiment orchestrator.

Add CLI options for:

- `--provider`
- `--model`
- `--dataset-path`
- `--prompt-path`
- `--num-runs`
- `--output-dir`
- `--experiment-name`
- `--tracking-uri`
- `--enable-mlflow`
- `--max-retries`
- `--retry-backoff`

### 2.2 Add a config loader module

Suggested new file:

- `config_loader.py`

Responsibilities:

1. Merge CLI args, environment variables, and defaults.
2. Support local MLflow by default.
3. Expose one normalized config object for the rest of the pipeline.

### 2.2.1 Add a settings-file schema

Use a single experiment settings file (YAML) as the baseline configuration, then allow CLI and environment overrides.

Suggested file:

- `config/eval_settings.yaml`

Suggested schema:

```yaml
experiment:
   name: "llm-json-eval"
   seed: 42
   output_dir: "outputs"
   num_runs: 5

data:
   dataset_path: "data/dataset.json"
   prompt_path: "prompts/extraction_prompt.txt"
   prompt_id: "extraction-v1"

model:
   provider: "openai" # openai | gemini
   model: "gpt-4o-mini"
   temperature: 0.2
   top_p: 1.0
   max_tokens: 2048

execution:
   max_retries: 3
   retry_backoff_seconds: 2
   timeout_seconds: 60
   continue_on_error: true

tracking:
   enable_mlflow: true
   tracking_uri: "file:./mlruns"
   tags:
      project: "llm_ie_qa_eval"
      corpus: "default"

exports:
   write_jsonl: true
   write_csv: true
   write_parquet: true
```

Required behavior:

1. Validate required keys and value ranges at load time.
2. Fail fast with actionable error messages when config is invalid.
3. Support one command-line option to choose the settings file path, for example `--config`.

### 2.2.2 Define config precedence and override rules

Use this precedence order (highest to lowest):

1. CLI arguments
2. Environment variables
3. Settings file (`config/eval_settings.yaml`)
4. Internal defaults

Recommended environment variable mapping examples:

- `LIE_PROVIDER`
- `LIE_MODEL`
- `LIE_NUM_RUNS`
- `LIE_DATASET_PATH`
- `LIE_PROMPT_PATH`
- `LIE_OUTPUT_DIR`
- `LIE_ENABLE_MLFLOW`
- `LIE_TRACKING_URI`

### 2.3 Record provenance metadata

Every experiment should capture:

- dataset path
- prompt path
- prompt version or identifier
- provider
- model
- evaluation timestamp
- git commit hash if available later

Reason:

Without provenance, repeated runs cannot be compared reliably over time.

## Phase 3: Normalize Provider Outputs ✅

### 3.1 Update [extractor.py](extraction/extractor.py)

Use this file as the provider-agnostic normalization boundary.

Responsibilities:

1. Route calls to the selected provider.
2. Normalize the returned payload into the canonical run schema.
3. Ensure provider-specific details do not leak into evaluation logic.

### 3.2 Update [openai_provider.py](providers/openai_provider.py)

Change the provider so it returns structured metadata in addition to parsed JSON.

Required outputs:

- raw text response
- parsed JSON
- parse success or failure
- provider error details
- latency
- token usage if available
- estimated cost if available
- model parameters used

### 3.3 Update [gemini_provider.py](providers/gemini_provider.py)

Mirror the same return contract as the OpenAI provider.

### 3.4 Add explicit parse validation

Do not rely on a bare exception handler. Validate that the parsed output matches the expected schema.

Expected schema example:

- `methods: list[str]`
- `tasks: list[str]`
- `datasets: list[str]`

## Phase 4: Implement Repeated-Run Evaluation ✅

### 4.1 Add nested evaluation loops in [run_evaluation.py](run_evaluation.py)

New logical loop:

1. Iterate documents in deterministic order
2. For each document, run the selected model/provider `N` times
3. Compute metrics for each run independently
4. Persist each run immediately

This is the step that enables measurement of non-deterministic variation.

### 4.2 Make failure handling explicit

If a provider call fails:

1. record the failure as a run-level event
2. continue the experiment if possible
3. include failure rates in the aggregate statistics

### 4.3 Add retry support

Use bounded retries with backoff for transient API failures.

Do not retry indefinitely.

## Phase 5: Extend the Metrics Layer ✅

### 5.1 Preserve and extend [metrics.py](evaluation/metrics.py)

Keep the current precision, recall, and F1 scoring logic as the base metric implementation.

Add helpers for repeated-run aggregation.

### 5.2 Add repeated-run aggregate statistics

For each document and corpus:

1. mean precision, recall, F1
2. standard deviation for each
3. 95% confidence interval for each
4. min, Q1, median, Q3, max
5. parse-error rate
6. failure rate
7. latency mean and dispersion
8. cost mean and dispersion

### 5.3 Add consistency metrics

Priority consistency metrics:

1. exact JSON match rate across repeated runs
2. exact field-level match rate across repeated runs
3. structural validity rate

### 5.4 Add within-document variance analysis

Suggested new file:

- `evaluation/variance_analysis.py`

Responsibilities:

1. compute exact-match stability
2. compute field-level overlap across repeated runs
3. summarize how unstable each document is

This directly supports your goal of measuring variation within repeated runs of the same document.

## Phase 6: Add Persistence for Analysis and Recovery ✅

### 6.1 Create a structured output directory

Suggested layout:

```text
outputs/
  experiments/
    <experiment_id>/
      config.json
      runs.jsonl
      document_aggregates.csv
      document_aggregates.parquet
      corpus_summary.json
      failures.jsonl
```

### 6.2 Add a persistence module

Suggested new file:

- `persistence.py`

Responsibilities:

1. append each run record to JSONL
2. write document-level aggregate tables
3. write corpus-level summary artifacts
4. support later reload for analysis

### 6.3 Prefer flat exports early

First outputs should be easy to consume in notebooks, pandas, BI tools, and MLflow artifacts:

1. CSV
2. JSONL
3. Parquet if dependency friction stays acceptable

## Phase 7: Integrate MLflow ✅

### 7.1 Add a small MLflow utility layer

Suggested new file:

- `mlflow_utils.py`

Responsibilities:

1. initialize or select experiment
2. log global parameters
3. log per-run metrics
4. log document-level aggregates
5. log output artifacts

### 7.2 Use local filesystem MLflow by default

Default target:

- local `mlruns/` inside the project or configured output root

This matches the current requirement and avoids operational overhead.

### 7.3 What to log in MLflow

Parameters:

- provider
- model
- prompt id
- dataset id or path
- num runs
- retry settings

Metrics:

- run-level precision, recall, F1
- latency and cost
- parse/failure indicators
- aggregate means, std, and confidence intervals
- exact-match consistency rate

Artifacts:

- run-level export files
- aggregate CSV or Parquet tables
- config snapshot

## Phase 8: Enable Corpus-Level and Within-Document Analysis ✅

### 8.1 Corpus-level questions the system must answer

The exported tables and MLflow logs should make it easy to answer:

1. Which documents have the lowest mean quality?
2. Which documents are most unstable across repeated runs?
3. Which provider/model has the best tradeoff between quality and stability?
4. Which provider/model has the best tradeoff between quality and cost?
5. How large is the spread of quality across the corpus?

### 8.2 Within-document questions the system must answer

1. How often does the same document produce a different JSON output?
2. How often does the same document produce a different score while still looking structurally valid?
3. Which fields are the least stable across runs?
4. Are unstable outputs correlated with cost, latency, or provider failures?

## Phase 9: Dataset and Prompt Governance ✅

### 9.1 Validate the dataset shape

Use [dataset.json](data/dataset.json) as the current reference schema.

Validate:

- every document has an `id`
- every document has `text`
- every gold annotation contains the required fields

### 9.2 Track prompt identity

Use [extraction_prompt.txt](prompts/extraction_prompt.txt) as the current prompt source, but record a prompt identifier or path in every experiment.

### 9.3 Plan for domain-specific corpora later

The same framework should support:

1. CV extraction
2. research paper extraction
3. other complex document parsing tasks

That means the run schema and metric exports should stay domain-agnostic.

## Phase 10: Add Test Coverage

### 10.1 Add unit tests

Suggested areas:

1. per-run metric correctness
2. repeated-run aggregation correctness
3. five-number summary correctness
4. exact-match consistency correctness
5. parse-error accounting

### 10.2 Add provider-mocking integration tests

Simulate repeated runs without consuming live API budget.

Verify:

1. correct run count is persisted
2. aggregates are computed correctly
3. failures are logged, not swallowed
4. MLflow logging does not break the run

### 10.3 Add a small smoke test path

Run one provider, a small dataset, and three repeated runs to verify the end-to-end flow.

## Phase 11: Operational Hardening

### 11.1 Add resumability

If a long experiment fails mid-run, the platform should be able to resume from persisted artifacts rather than restarting from zero.

### 11.2 Add budget guardrails

Before large experiments, estimate likely API spend and warn the user.

### 11.3 Delay concurrency until observability is stable

Parallel API calls will matter later, but only after:

1. run-level persistence works
2. failure logging works
3. MLflow tracking works
4. aggregates are correct

## Concrete File-Level Work Plan

### Existing files to change

1. [run_evaluation.py](run_evaluation.py)
   - convert into experiment orchestrator
   - add CLI/config integration
   - add repeated-run loops
   - connect persistence and MLflow

2. [metrics.py](evaluation/metrics.py)
   - keep current scoring
   - add repeated-run aggregate computations
   - add confidence intervals and five-number summaries

3. [extractor.py](extraction/extractor.py)
   - normalize provider responses
   - return structured run record pieces

4. [openai_provider.py](providers/openai_provider.py)
   - expose metadata and structured parse status
   - allow model parameter control

5. [gemini_provider.py](providers/gemini_provider.py)
   - mirror the same normalized contract

6. [Readme.md](Readme.md)
   - update usage instructions once the new flow exists

### Suggested new files

1. `config_loader.py`
2. `persistence.py`
3. `mlflow_utils.py`
4. `evaluation/variance_analysis.py`
5. `tests/test_metrics.py`
6. `tests/test_repeated_runs.py`
7. `tests/test_provider_normalization.py`

## Verification Checklist

1. Run a smoke test with one provider, two documents, and three repeated calls each.
2. Confirm that a distinct run record is generated for every repeated call.
3. Confirm that document-level aggregates and corpus-level aggregates are exported.
4. Confirm that parse failures are visible in both raw outputs and aggregate summaries.
5. Confirm that MLflow records parameters, per-run metrics, and output artifacts.
6. Confirm that exported CSV or Parquet files are easy to use in pandas or BI tools.
7. Confirm that the system can answer both categories of questions:
   - quality variation across the corpus
   - quality variation across repeated runs of the same document

## Priority Order

1. Canonical run schema
2. CLI/config layer
3. Provider normalization
4. Repeated-run orchestration
5. Metrics aggregation and variance analysis
6. Persistence layer
7. MLflow integration
8. Flat exports
9. Tests
10. Operational hardening

## Deferred for Later

These should not block the first implementation:

1. remote MLflow server support
2. custom dashboards beyond MLflow UI
3. semantic agreement metrics beyond exact or field-level overlap
4. large-scale concurrency optimization
5. advanced experiment scheduling

## Final Outcome Target

At the end of this plan, the platform should let you:

1. run repeated JSON extraction experiments over a document corpus
2. measure quality and stability per document and across the whole corpus
3. quantify within-document output variation caused by repeated LLM calls
4. track experiments and metrics locally with MLflow
5. export analysis-ready tables for downstream visualization and reporting