# Plan: Generate PRD for `llm_ie_qa_eval`

**TL;DR**: Produce a single `PRD.md` at the project root — a complete, implementation-accurate product requirements document synthesized from all existing docs, configs, source code, and tests. A dedicated §13 covers the AI-agent/vibecoding setup as already implemented, referencing the actual `AGENTS.md` rules and the project's own module structure.

---

## Source Inventory

| Source | Feeds into |
|---|---|
| `Readme.md` | §1 summary, §2 background, §12 CLI |
| `AGENTS.md` | §13 vibecoding section |
| `todo_plans/*.md` (4 files) | §3 goals/non-goals, historical decisions |
| `config/*.yaml` + `*.json` | §8 configuration reference |
| `run_evaluation.py`, `run_business_evaluation.py`, `run_business_api.py` | §12 CLI reference |
| `business/` modules | §7 business layer requirements, §10 API contract |
| `evaluation/` modules | §6 evaluation requirements |
| `extraction/`, `providers/` | §6 provider requirements |
| `config_loader.py`, `persistence.py`, `mlflow_utils.py` | §8, §9 cross-cutting concerns |
| `tests/` (22 files) | §9 NFRs, behavioral specs |
| `Makefile` | §12 developer workflow |

---

## PRD Document Structure

### §1 — Executive Summary
- What the system does, for whom, and why it exists.
- Source: `Readme.md` + synthesis of project goals.

### §2 — Background & Problem Statement
- The need for deterministic LLM evaluation and business risk quantification.
- Source: `Readme.md`, `todo_plans/to_do_list.md`, `todo_plans/LLM_business_eval_plan_1.md`.

### §3 — Goals & Non-Goals
- **Goals**: multi-run variance measurement, hybrid scoring, business readiness recommendation, reproducibility, MLflow tracking.
- **Non-goals**: online serving, fine-tuning, data annotation UI.
- Source: `todo_plans/*` + codebase design decisions.

### §4 — User Personas & Use Cases

**Personas**:
- **ML Engineer** — runs evaluations, configures models, inspects per-document variance.
- **Business Analyst** — reads dashboards, interprets item-level cost breakdowns and failure modes.
- **Platform Engineer** — integrates the API, manages MLflow, operates the evaluation pipeline.
- **Management / Business Decision Makers** — consumes deployment readiness recommendations (GO/CONDITIONAL/HOLD/NO_GO) and high-level risk/cost summaries to authorize production rollouts.

Use cases derived from CLI entry points, API endpoints, and business layer outputs.

### §5 — System Architecture Overview
- Component diagram (text/ASCII): Providers → Extraction → Evaluation → Business Layer → Outputs.
- Data flow narrative covering the full pipeline from dataset ingestion to dashboard export.
- Key design principles: reproducibility, graceful degradation, modular boundaries, stable contracts.

### §6 — Functional Requirements: Evaluation Pipeline
- Repeated runs (`num_runs`), per-document variance and instability metrics.
- Hybrid scoring: schema validation + rubric-based path comparators (6 comparator types: exact, fuzzy lexical, set Jaccard, key-based array object, best-overlap fallback).
- Provider abstraction (OpenAI, Gemini) with unified output schema.
- JSON parsing resilience (markdown fences, bracket extraction).
- MLflow tracking (optional, graceful degradation).
- Artifact exports (JSONL, CSV, Parquet, JSON).
- Source: `evaluation/`, `extraction/`, `providers/`, `persistence.py`.

### §7 — Functional Requirements: Business Evaluation Layer
- Item-level business metric computation (success rate, stability, quality score, expected cost).
- Failure mode taxonomy (`parse_error`, `runtime_error`, `incorrect`) with configurable cost penalties.
- Weighted readiness score formula (configurable per scenario).
- Hard gates: `max_critical_failure_rate`, `max_expected_cost_per_1000`, `min_stability_score`.
- Deployment recommendation: GO / CONDITIONAL / HOLD / NO_GO.
- Explainability payloads: metric contributions, threshold proximity, dominant failure modes, top failing items.
- Reproducibility: config snapshot + hash (replay metadata).
- Optional FastAPI endpoint (`POST /business/evaluate`).
- Source: `business/` modules.

### §8 — Configuration System
- Hierarchy: file defaults → scenario overrides → CLI args.
- Full schema reference:
  - `config/eval_settings.yaml` — experiment, data, model, execution, tracking, exports, hybrid.
  - `config/business_settings.yaml` — readiness weights, normalization, warning margins.
  - `config/business_thresholds.yaml` — per-scenario GO/CONDITIONAL thresholds and hard gates.
  - `config/business_costs.yaml` — per-scenario failure mode cost penalties.
  - `config/business_contract.yaml` — contract version.
  - `config/hybrid_scoring.yaml` — rubric rules (path, comparator, options).
  - `config/extraction_output.schema.json` — JSON Schema for extracted output validation.
- Source: `config_loader.py`, all `config/*` files.

### §9 — Non-Functional Requirements
- **Reproducibility**: provenance metadata (git commit, config hash, file SHAs, timestamp) in every experiment.
- **Resilience**: retry logic with exponential backoff, `continue_on_error` flag for partial runs, graceful degradation for optional components (MLflow, hybrid scoring, API).
- **Testability**: 22 test files (~70% unit / ~20% integration), mock patterns for all LLM provider calls.
- **Extensibility**: new providers and comparators can be added without changing evaluation or business logic.
- **Observability**: per-run latency (`latency_ms`), token counts, and cost estimation tracked and exported.

### §10 — API Contract (Business API)
- `POST /business/evaluate` — full request payload and `BusinessServiceResponse` schema.
- Source: `business/api.py`, `business/service.py`, `run_business_api.py`.

### §11 — Data Schemas & Contracts
- `CanonicalRunRecord` — all fields (from `evaluation/run_record.py`).
- `DocumentAggregateRecord` and `CorpusAggregateRecord`.
- Business contract input schema (`BUSINESS_CONTRACT_SCHEMA` from `business/contracts.py`).
- Provider output unified dict format (model, raw_response_text, parsed_output_json, parse_status, error_message, latency_ms, input_tokens, output_tokens, estimated_cost).
- Extraction output schema (`config/extraction_output.schema.json`).

### §12 — Developer Workflow & CLI Reference
- Full flag-by-flag CLI for `run_evaluation.py`, `run_business_evaluation.py`, `run_business_api.py`.
- Makefile commands (`make business-eval`, `make business-api`, `make business-api-smoke`, `make test-business`).
- Environment setup (`.env`, `OPENAI_API_KEY`, `GEMINI_API_KEY`).
- Virtual environment activation (`.venv/bin/activate`).

### §13 — AI Agent Workflow (Vibecoding)
Documents the as-implemented conventions for working on this project with AI coding agents (Claude-powered). Covers:

**a. CLAUDE-First Operating Rules** (from `AGENTS.md`)
- Think before coding: state assumptions, name uncertainty, prefer clarifying questions on ambiguous requirements.
- Simplicity first: minimum viable change, no speculative abstractions.
- Surgical changes: touch only required files/code paths, match existing style.
- Goal-driven verification: define success criteria before coding; treat completion as "implemented + verified".

**b. Project-Specific Module Map for AI Agents**
- Which file(s) to touch for each common change type:

| Task | Files to change |
|---|---|
| Add a new LLM provider | `providers/<new>_provider.py`, `extraction/extractor.py`, `config_loader.py` |
| Add a new value comparator | `evaluation/hybrid_comparators.py`, `config/hybrid_scoring.yaml` |
| Add a new evaluation metric | `evaluation/metrics.py`, `evaluation/run_record.py`, `persistence.py` |
| Add a new business failure mode | `config/business_costs.yaml`, `business/metrics.py` |
| Change readiness scoring weights | `config/business_settings.yaml` |
| Add a new CLI flag | `run_evaluation.py` (argparse), `config_loader.py` (`EvalConfig`) |
| Add a new artifact export format | `persistence.py` |
| Add a new business scenario | `config/business_thresholds.yaml`, `config/business_costs.yaml` |

**c. Research Protocol for This Codebase**
- For any change: start with `config_loader.py` (understand config shape) → relevant module → `run_record.py` (if new fields needed) → `persistence.py` (if new exports needed).
- For business changes: start with `business/types.py` → `business/metrics.py` → `business/recommender.py`.
- Use `grep_search` for exact symbol lookups; `semantic_search` for concept discovery.

**d. Testing Conventions**
- All tests in `tests/`, named `test_{module}.py`.
- Mock LLM provider calls with `unittest.mock.patch` on the provider function.
- Use `pytest` fixtures for config objects and dataset stubs.
- Parametrized tests for comparator variants and threshold edge cases.
- Run tests: `python -m pytest tests/` (with `.venv` activated).

**e. Commit & Branch Conventions**
- Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`.
- Imperative mood; subject ≤72 chars; no emojis.
- Branch naming: `feature/<desc>`, `fix/<desc>`, `test/<desc>`, `docs/<desc>`.

**f. Error Handling Patterns**
- Validate at system boundaries: config load, API endpoint, provider call.
- Graceful degradation for optional components (MLflow, hybrid scoring, Parquet).
- Actionable error messages (e.g., "No experiment dir found. Run: python run_evaluation.py first").

### §14 — Glossary
Key terms: `CanonicalRunRecord`, hybrid scoring, rubric rule, comparator, deployment readiness, GO/CONDITIONAL/HOLD/NO_GO, scenario, business contract, corpus, document aggregate, provenance, parse_status, hard gate, stability score, expected cost.

---

## Step-by-Step Generation Checklist

### Phase 1 — Source Collection (parallel reads)
- [ ] Full read of `Readme.md` → §1, §2, §12
- [ ] All 4 `todo_plans/*.md` files → §3, §4 (decisions, non-goals)
- [ ] `run_evaluation.py`, `run_business_evaluation.py`, `run_business_api.py` → §12 (exact CLI flags)
- [ ] `business/service.py`, `business/api.py`, `business/contracts.py`, `business/types.py` → §10, §11
- [ ] `evaluation/run_record.py` → §11 (`CanonicalRunRecord` exact fields)
- [ ] `config_loader.py` → §8 (`EvalConfig` exact fields)
- [ ] 5 representative test files (e.g., `test_business_recommender.py`, `test_hybrid_comparators.py`, `test_repeated_runs.py`, `test_metrics.py`, `test_business_api_runtime.py`) → §9

### Phase 2 — Draft Writing (sequential)
- [ ] §1–§5 narrative sections
- [ ] §6–§8 functional requirements
- [ ] §9–§11 NFRs, API contract, data schemas
- [ ] §12 CLI reference (exact flags)
- [ ] §13 vibecoding (synthesize AGENTS.md + project-specific module map above)
- [ ] §14 glossary

### Phase 3 — Review & Finalize
- [ ] Cross-reference checks (§6 → §11 schemas; §12 → §8 config keys)
- [ ] Gap check: any undocumented config key or CLI flag
- [ ] Consistency pass: uniform terminology, correct linked file paths, no broken references

---

## Output

- **File**: `PRD.md` at project root
- **Format**: Markdown — headers, tables, fenced code blocks for CLI/schema examples, linked file references
- **Estimated length**: 2,000–3,500 lines

---

## Decisions & Scope

- PRD is **descriptive** (what exists), not aspirational.
- §13 documents **as-implemented** conventions only; no new rules are introduced.
- Non-goals explicitly exclude: frontend/UI, fine-tuning pipelines, data annotation tooling.
- `PRD.md` placed at project root for maximum discoverability alongside `Readme.md` and `AGENTS.md`.
- CLI detail level: **full flag-by-flag reference** (no other API docs exist in the repo).
- §13 vibecoding depth: synthesize AGENTS.md as baseline + project-specific module map (not a verbatim copy).
