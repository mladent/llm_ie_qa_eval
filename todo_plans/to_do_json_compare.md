# Hybrid JSON Rubric Scoring Implementation Plan

## Goal
Add a configurable hybrid JSON scoring layer that augments the current evaluation pipeline with:
- schema-aware scoring
- path-level value similarity scoring
- policy-driven handling for unknown fields
- weighted aggregation into a single hybrid score

This must remain backward-compatible with existing precision/recall/F1 outputs.

## Confirmed Decisions
- Keep current precision/recall/F1 behavior unchanged, and add hybrid outputs.
- Use a dedicated JSON Schema file referenced from config.
- Unknown field handling is configurable per project with policies:
  - ignore
  - penalize
  - fail_schema
- Use JSONPath for path-level rubric rules.
- Use lexical text similarity only in v1 (no embeddings).
- Arrays of objects use key-based matching by default.
- Array key-missing behavior is configurable; default fallback: best-overlap matching.
- parse_error/provider_error runs get hybrid score forced to 0.

## [x] Phase 1: Config and Contract Foundation
### Objective
Introduce hybrid-scoring configuration as first-class runtime input.

### Libraries
- Existing: PyYAML
- New: jsonschema

### Files
- Update: config/eval_settings.yaml
- Update: config/project_eval_example.yaml
- Update: config_loader.py
- New: config/hybrid_scoring.yaml
- New: config/extraction_output.schema.json

### Implementation
1. Add hybrid section in config defaults and YAML:
   - enabled
   - schema_path
   - rubric_path
   - parse_error_behavior
   - path_syntax
2. Add dataclasses in config_loader.py:
   - HybridScoringConfig
   - SchemaScoringConfig
   - RubricRuleConfig
   - ComparatorConfig
   - UnknownFieldPolicyConfig
3. Extend validation in config_loader.py:
   - ensure schema/rubric files exist
   - validate enum values (unknown field policy, parse behavior, fallback strategy)
   - validate non-negative weights and total-weight consistency where applicable
4. Keep precedence model unchanged: CLI > env > file > defaults.

### Deliverable
Config loader can reliably construct and validate a hybrid scoring config object.

Status note:
- Completed: hybrid config dataclasses, default config wiring, validation branches, and config files (`config/hybrid_scoring.yaml`, `config/extraction_output.schema.json`).
- Verified via focused tests:
   - `pytest tests/test_config_loader_branches.py tests/test_project_config.py -q`

## [ ] Phase 2: Build Hybrid Scoring Engine Modules
### Objective
Implement composable scoring primitives and orchestrator logic.

### Libraries
- New: jsonschema
- New: jsonpath-ng
- New: rapidfuzz

### Files
- New: evaluation/hybrid_types.py
- New: evaluation/hybrid_normalize.py
- New: evaluation/hybrid_comparators.py
- New: evaluation/hybrid_schema.py
- New: evaluation/hybrid_scoring.py

### Implementation
1. evaluation/hybrid_types.py
   - Add dataclasses for explainable output:
     - PathScoreDetail
     - SchemaScoreDetail
     - HybridScoreResult
2. evaluation/hybrid_normalize.py
   - Deterministic normalization helpers:
     - trim/casefold/whitespace normalization
     - list/object canonicalization where needed
3. evaluation/hybrid_comparators.py
   - Comparator functions:
     - exact_match
     - set_jaccard_match
     - fuzzy_lexical_match (rapidfuzz)
     - key_based_array_object_match
     - best_overlap_fallback_match
4. evaluation/hybrid_schema.py
   - Validate prediction against JSON Schema.
   - Convert validation findings into schema score component.
   - Apply unknown-field policy from config.
5. evaluation/hybrid_scoring.py
   - Orchestrator entry point:
     - evaluate_hybrid(predicted, gold, rubric_cfg, schema_cfg, parse_status)
   - Compose schema + value components and aggregate weighted total.
   - Enforce parse failure => total score 0 policy.

### Deliverable
A standalone, testable hybrid scoring engine that returns both final score and detailed per-component breakdown.

## [ ] Phase 3: Integrate into Runtime Evaluation Pipeline
### Objective
Score each run with hybrid rubric and store results without breaking existing flow.

### Libraries
- No new integration library beyond Phase 2 requirements.

### Files
- Update: evaluation/run_record.py
- Update: run_evaluation.py
- Update: evaluation/metrics.py

### Implementation
1. evaluation/run_record.py
   - Extend CanonicalRunRecord with hybrid fields:
     - hybrid_total_score
     - hybrid_schema_score
     - hybrid_value_score
     - hybrid_unknown_penalty
     - hybrid_rule_coverage
2. run_evaluation.py
   - Load schema + rubric config at startup.
   - Compute hybrid score per run after parse result and before run record append.
   - Ensure non-success parse statuses map to hybrid score 0 as configured.
3. evaluation/metrics.py
   - Add hybrid aggregate statistics:
     - mean/std/ci95 for hybrid score at document and corpus levels

### Deliverable
Hybrid metrics are computed and available for every run in memory and aggregates.

## [ ] Phase 4: Persistence, Analysis, and MLflow
### Objective
Expose hybrid outputs in artifacts and experiment tracking.

### Libraries
- Existing: pandas
- Existing: mlflow

### Files
- Update: persistence.py
- Update: mlflow_utils.py
- Update: evaluation/analysis_questions.py
- Update: evaluation/variance_analysis.py

### Implementation
1. persistence.py
   - Include hybrid fields in JSONL and summary payloads.
   - Add CSV outputs for hybrid details, e.g.:
     - hybrid_path_breakdown.csv
     - hybrid_component_trends.csv
2. mlflow_utils.py
   - Log run-level hybrid metrics.
   - Log document/corpus-level hybrid aggregates.
3. analysis/variance modules
   - Add hybrid stability/variance calculations and table generation.

### Deliverable
Hybrid scoring is observable through local artifacts and MLflow UI.

## [ ] Phase 5: Tests
### Objective
Guarantee correctness and backward compatibility.

### Libraries
- Existing: pytest

### Files
- New: tests/test_hybrid_schema.py
- New: tests/test_hybrid_comparators.py
- New: tests/test_hybrid_scoring.py
- Update: tests/test_metrics.py
- Update: tests/test_config_loader_branches.py
- Update: tests/test_project_run.py

### Implementation
1. Add unit tests for comparator behavior and edge cases.
2. Add schema scoring tests for each unknown-field policy.
3. Add orchestrator tests for weighted aggregation and parse-error zeroing.
4. Add config loader branch tests for hybrid config validation.
5. Add project run integration tests verifying new artifacts and metrics.

### Deliverable
Reliable hybrid scoring behavior with regression protection.

## [ ] Phase 6: Documentation and Usability
### Objective
Document configuration and operational usage.

### Libraries
- None

### Files
- Update: Readme.md
- Update: config/hybrid_scoring.yaml (annotated examples)

### Implementation
1. Add README section:
   - architecture of hybrid scoring
   - config examples
   - explanation of output metrics/artifacts
2. Document defaults and override strategy per project config.
3. Document comparator choices and JSONPath rule syntax.

### Deliverable
Users can configure and interpret hybrid scoring without source-code diving.

## Required Dependency Additions
Update requirements.txt with:
- jsonschema
- jsonpath-ng
- rapidfuzz

## End-to-End Verification Checklist
1. Static checks and diagnostics on modified files.
2. Run focused hybrid tests:
   - pytest tests/test_hybrid_schema.py tests/test_hybrid_comparators.py tests/test_hybrid_scoring.py
3. Run regression tests:
   - pytest tests/test_metrics.py tests/test_config_loader_branches.py tests/test_project_run.py
4. Run one full evaluation command with project config and verify:
   - legacy outputs remain intact
   - hybrid metrics appear in run and aggregate artifacts
   - parse errors yield hybrid_total_score = 0
   - MLflow includes hybrid metrics

## Suggested Rollout Strategy
1. Implement Phases 1-2 behind config.enabled flag.
2. Integrate Phases 3-4 with additive fields only.
3. Land tests (Phase 5) before enabling by default.
4. Finish docs and example configs (Phase 6).
