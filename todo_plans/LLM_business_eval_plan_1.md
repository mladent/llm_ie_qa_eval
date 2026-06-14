# LLM business evaluation platform 


1. **A clean data schema (JSON)**
2. **Metric definitions (formalized)**
3. **Example JSON outputs**
4. **A minimal Python pipeline (copy/paste ready)**

This is designed to be:

* simple enough to build quickly
* structured enough to evolve into a real product

---

# 🧭 0. Integration strategy decision (single source execution plan)

## Decision

Build the business/management layer in the same repository first, as a **modular monolith**.

This means:

* one codebase and release for now
* strict module boundaries between evaluator and business tooling
* data-contract-first interfaces so later extraction to a separate service is easy

## Why this decision now

At this stage, metrics and business logic are still evolving quickly. Keeping one repo optimizes iteration speed and debugging while avoiding early API/service overhead.

## Pros/cons considered

### Option A: separate project + API calls to evaluator

Pros:

* clear ownership boundaries
* independent deployments and scaling
* strong contract discipline from day one

Cons:

* extra infra early (API versioning, auth, deployment)
* slower iteration while metric definitions still change
* harder debugging across service boundaries

### Option B: one integrated project (chosen)

Pros:

* fastest feedback loop
* easiest integration testing and refactoring
* lower operational complexity

Cons:

* risk of coupling if boundaries are not enforced
* future split requires discipline in interfaces

## Non-negotiable boundary rules (to keep split possible)

1. Business module consumes evaluator artifacts as contracts, not internal evaluator functions.
2. No cross-imports from business logic into evaluator core.
3. Version output contract explicitly (for example `business_contract_version`).
4. Keep all business-facing payload builders under a dedicated package.

## Split-later triggers

Move to a separate service/project only when one or more become true:

* different team ownership
* need for independent release cadence
* multi-tenant online serving requirements
* scaling/economics require separate compute lifecycle
* contract churn stabilizes and API hardening is justified

---

# 🧱 1. Core data model (schema)

We model **runs → evaluations → aggregates → business metrics**

---

## A. Input definition

```json
{
  "dataset": "customer_support_v1",
  "scenario": "refund_handling",
  "items": [
    {
      "id": "cs_001",
      "input": "Customer asks for refund after 45 days...",
      "expected": "Refund denied politely with policy explanation",
      "risk_tags": ["policy", "customer_trust"],
      "severity_weights": {
        "incorrect": 5,
        "compliance": 10,
        "tone": 3
      }
    }
  ]
}
```

---

## B. Multi-run outputs

```json
{
  "item_id": "cs_001",
  "runs": [
    {
      "run_id": 1,
      "output": "...",
      "scores": {
        "correct": 1,
        "compliance": 1,
        "tone": 0.8
      },
      "failure_modes": []
    },
    {
      "run_id": 2,
      "output": "...",
      "scores": {
        "correct": 0,
        "compliance": 0,
        "tone": 0.6
      },
      "failure_modes": ["incorrect", "policy_violation"]
    }
  ]
}
```

---

## C. Per-item aggregation (THIS is key)

```json
{
  "item_id": "cs_001",
  "aggregates": {
    "success_rate": 0.6,
    "mean_score": 0.72,
    "variance": 0.18,
    "agreement_rate": 0.4,

    "five_number_summary": {
      "min": 0.2,
      "q1": 0.5,
      "median": 0.75,
      "q3": 0.9,
      "max": 1.0
    }
  },
  "risk": {
    "expected_cost": 4.2,
    "worst_case_cost": 10,
    "failure_probability": 0.4
  }
}
```

---

## D. Scenario-level aggregation (business view)

```json
{
  "scenario": "refund_handling",
  "summary": {
    "success_rate_mean": 0.81,
    "stability_score": 0.67,
    "expected_cost_per_1000": 5200,
    "p95_cost": 18,
    "critical_failure_rate": 0.03
  },
  "failure_breakdown": {
    "incorrect": 0.12,
    "compliance": 0.03,
    "tone": 0.08
  }
}
```

---

# 📐 2. Metric definitions (precise)

These are the core ones to implement:

---

## A. Stability score

```text
stability = 1 - (variance_normalized)
```

or simpler:

```text
stability = agreement_rate
```

---

## B. Agreement rate

```text
agreement = (# identical or semantically similar outputs) / N
```

(MVP: exact match or cosine similarity threshold)

---

## C. Expected Cost of Failure (ECF)

```text
ECF(item) = Σ P(failure_type) × cost(failure_type)
```

Approximation from runs:

```text
ECF = (sum of failure costs across runs) / N
```

---

## D. Critical failure rate

```text
# runs with severe failures / total runs
```

---

## E. Five-number summary

Over run-level scores:

```python
[min, Q1, median, Q3, max]
```

---

# 🧪 3. Example output (final dashboard JSON)

```json
{
  "deployment_readiness": {
    "score": 72,
    "recommendation": "conditional"
  },
  "risk": {
    "expected_cost_per_1000": 5200,
    "tail_risk_p95": 18,
    "critical_failure_rate": 0.03
  },
  "stability": {
    "overall": 0.67,
    "high_variance_items": 0.22
  },
  "top_failures": [
    {
      "item_id": "cs_014",
      "issue": "policy violation",
      "runs_failing": 3,
      "example_output": "..."
    }
  ]
}
```

---

# 🐍 4. Python pipeline (minimal but real)

This is a working skeleton you can extend.

---

## A. Setup

```python
import numpy as np
from collections import Counter
```

---

## B. Core helpers

```python
def five_number_summary(values):
    return {
        "min": float(np.min(values)),
        "q1": float(np.percentile(values, 25)),
        "median": float(np.median(values)),
        "q3": float(np.percentile(values, 75)),
        "max": float(np.max(values)),
    }
```

---

```python
def compute_agreement(outputs):
    counts = Counter(outputs)
    most_common = counts.most_common(1)[0][1]
    return most_common / len(outputs)
```

---

```python
def compute_expected_cost(runs, cost_map):
    total = 0
    for run in runs:
        for failure in run["failure_modes"]:
            total += cost_map.get(failure, 0)
    return total / len(runs)
```

---

## C. Per-item evaluation

```python
def evaluate_item(item_runs, cost_map):
    scores = []
    outputs = []
    failure_counts = 0

    for run in item_runs:
        score = np.mean(list(run["scores"].values()))
        scores.append(score)
        outputs.append(run["output"])

        if run["failure_modes"]:
            failure_counts += 1

    agreement = compute_agreement(outputs)

    return {
        "success_rate": 1 - (failure_counts / len(item_runs)),
        "mean_score": float(np.mean(scores)),
        "variance": float(np.var(scores)),
        "agreement_rate": agreement,
        "five_number_summary": five_number_summary(scores),
        "expected_cost": compute_expected_cost(item_runs, cost_map),
        "failure_probability": failure_counts / len(item_runs)
    }
```

---

## D. Scenario aggregation

```python
def aggregate_scenario(items):
    success_rates = [i["success_rate"] for i in items]
    costs = [i["expected_cost"] for i in items]
    variances = [i["variance"] for i in items]

    return {
        "success_rate_mean": float(np.mean(success_rates)),
        "stability_score": float(1 - np.mean(variances)),
        "expected_cost_per_1000": float(np.mean(costs) * 1000),
        "p95_cost": float(np.percentile(costs, 95)),
        "critical_failure_rate": float(
            sum(1 for i in items if i["failure_probability"] > 0.5) / len(items)
        )
    }
```

---

# 🚀 5. How this maps to your dashboard

This pipeline directly feeds:

* Executive view → `deployment_readiness`, `expected_cost`
* Risk view → `failure_probability`, `p95_cost`
* Stability → `variance`, `agreement_rate`
* Distribution → `five_number_summary`

---

# 🛠️ 6. Unified execution roadmap (implementation plan)

This roadmap is organized for fast implementation and clean future extraction.

## 6.1 Phase matrix

### Phase 1: Contract adapter from evaluator outputs ✅ Completed
Inputs:
* `runs.jsonl`, `document_aggregates.csv`, `corpus_summary.json`
* optional hybrid outputs (`hybrid_component_trends.csv`, `hybrid_path_breakdown.csv`)
New files:
* `business/artifacts_loader.py`
* `business/contracts.py`
* `business/types.py`
Changed files:
* `requirements.txt`
* `Readme.md`
Expected dependencies:
* `jsonschema` (new)
* `PyYAML`, `pandas` (already present)

### Phase 2: Business metric engine ✅ Completed
New files:
* `business/metrics.py`
* `business/aggregates.py`
* `tests/test_business_metrics.py`
* `tests/test_business_adapter.py`
Changed files:
* `Readme.md`
Expected dependencies:
* `numpy` (already used in this plan)
* `pytest` (already present)

### Phase 3: Decision layer ✅ Completed
New files:
* `business/recommender.py`
* `business/explainability.py`
* `tests/test_business_recommender.py`
Changed files:
* `config/business_thresholds.yaml`
* `config/business_settings.yaml`
Expected dependencies:
* no mandatory new libraries

### Phase 4A: Management outputs (mandatory) ✅ Completed
New files:
* `business/reporting.py`
* `run_business_evaluation.py`
Changed files:
* `Readme.md`
Deliverables:
* `dashboard_summary.json`
* CSV outputs for BI

### Phase 4B: Dynamic interface (optional track) ✅ Completed (API track)
New files:
* `business/api.py` (if API is enabled)
* `business/ui_app.py` (if UI is enabled)
Expected dependencies:
* `fastapi` + `uvicorn` (optional)
* `streamlit` (optional)

### Phase 5: Governance and hardening ✅ Completed
New files:
* `business/replay.py`
* `tests/test_business_contract_regression.py`
* `tests/golden/business_outputs/` fixtures
Changed files:
* `config/business_contract.yaml`
* `Readme.md`
Deliverables:
* versioned contracts, replay lineage, regression suite

### Phase 6: Optional service extraction (deferred)
Only after split triggers are met:
* wrap business module behind API service
* keep evaluator as producer and business module as consumer
* preserve contracts unchanged to minimize migration risk

## 6.2 Library decisions

Core expected additions:
* `jsonschema`

Optional (only if interface track starts now):
* `fastapi`
* `uvicorn`
* `streamlit`

Deferred until service extraction:
* additional API client libraries as needed

## 6.3 First implementation slice

Implement this minimal vertical slice first:

1. Load one historical experiment from `outputs/experiments/<id>`.
2. Map artifacts to business schema.
3. Compute item and scenario business metrics.
4. Apply recommendation logic with file-based thresholds.
5. Emit `dashboard_summary.json` and one CSV.
6. Add one regression test with golden output.

---

# ✅ 7. Definition of done for this plan

The plan is considered complete when:

1. A single command can produce business decision JSON from evaluator outputs.
2. All core metrics in Section 2 are computed and tested.
3. Dashboard JSON in Section 3 is generated with real run data.
4. Recommendation logic is configurable and scenario-aware.
5. Contract tests prevent breaking downstream consumers.
6. All business-evaluation knobs are configurable via files and runtime parameters.
7. Historical static evaluations can be replayed with new cost/threshold settings without re-running LLM inference.

---

# 8. Missing implementation details (must be resolved before coding)

## A. Contract and mapping gaps

* Define exact mapping from evaluator artifacts (`runs.jsonl`, `document_aggregates.csv`, `corpus_summary.json`) into business-layer schema.
* Define how business `scores` fields are derived when only evaluator metrics exist.
* Define canonical failure taxonomy and mapping from evaluator fields to business failure modes.

## B. Decision and risk gaps

* Define explicit readiness formula and signal weights.
* Define per-scenario thresholds for `go`, `conditional`, `hold`.
* Define downgrade rules (for example critical failure rule overrides high readiness score).

## C. Operational gaps

* Define config versioning and compatibility policy.
* Define replay lineage metadata and audit trail requirements.
* Define deterministic rounding and edge-case behavior for all metrics.

---

# 9. Full configurability model (files plus runtime parameters)

All business-side evaluations must be tunable without code edits.

## A. Required config files

* `config/business_settings.yaml`
: global defaults for metric weights, percentile targets, agreement mode, rounding.
* `config/business_thresholds.yaml`
: recommendation thresholds (`go`, `conditional`, `hold`) per scenario/domain.
* `config/business_costs.yaml`
: failure-mode cost maps and severity multipliers per scenario/domain.
* `config/business_contract.yaml`
: contract version, required artifact fields, compatibility rules.

## A1. Config schema requirements

Each config file must define:

* required keys
* optional keys with defaults
* type constraints and allowed ranges
* compatibility version key

Validation rules:

* fail fast on missing required keys,
* reject unknown keys in strict mode,
* normalize and record effective config after merge,
* persist `business_config_version` and `business_config_hash` in all outputs.

## B. Parameter precedence (highest to lowest)

1. Runtime override parameters (CLI/API/UI).
2. Project-level business config override.
3. Scenario-level config in `config/business_*.yaml`.
4. Global defaults in `config/business_settings.yaml`.

## C. Runtime override requirements

* Support partial override of costs (for example only `compliance` and `incorrect`).
* Support partial override of thresholds and weights.
* Persist an effective merged config snapshot with each decision artifact.
* Record who/what changed parameters and when.

## D. Minimum keys for first implementation

`config/business_settings.yaml`:
* normalization settings
* rounding precision
* default metric weights

`config/business_thresholds.yaml`:
* `go_threshold`
* `conditional_threshold`
* hard risk gates (`critical_failure_rate`, `expected_cost_per_1000`, `stability_min`)

`config/business_costs.yaml`:
* per-scenario failure-cost map
* default fallback costs

`config/business_contract.yaml`:
* `business_contract_version`
* required artifact fields
* backward compatibility policy

---

# 10. Dynamic web UI and historical replay model

The business interface must evaluate historical static runs under new parameters.

## A. Historical replay principle

* Raw evaluator outputs are immutable.
* Business recalculation is pure over artifacts plus effective config.
* No LLM call is required for replay.

## B. Replay inputs

* Source experiment artifact paths.
* Optional run/date filter.
* Effective config snapshot (base plus overrides).

## C. Replay outputs

* `dashboard_summary.json` (new decision view).
* `scenario_business_summary.csv`.
* `item_business_breakdown.csv`.
* `replay_metadata.json` including:
: source experiment id, config hash, replay timestamp, contract version.

## D. Dynamic UI requirements

* Scenario selector over historical experiments.
* Tunable cost controls per failure mode.
* Tunable threshold controls per decision rule.
* Immediate recomputation and side-by-side comparison with baseline.
* Save/load named parameter sets for governance.

---

# 11. Explicit recommendation logic and thresholds

## A. Readiness formula

Use a deterministic weighted score:

`readiness = w_success * success_rate + w_stability * stability_score + w_quality * mean_score - w_risk * normalized_expected_cost - w_critical * critical_failure_rate`

Constraints:

* All weights are file-configurable and normalized.
* All components are normalized into `[0, 1]` before aggregation.

## B. Decision classes

* `go` when score is above `go_threshold` and hard risk gates pass.
* `conditional` when score is between `conditional_threshold` and `go_threshold`, or when one soft warning is present.
* `hold` when score is below `conditional_threshold` or any hard risk gate fails.

## C. Hard risk gates (configurable)

* Maximum allowed `critical_failure_rate`.
* Maximum allowed `expected_cost_per_1000`.
* Minimum allowed agreement/stability.

## D. Explainability payload

Each recommendation must include:

* metric contributions to final score,
* top failing items,
* dominant failure modes,
* threshold proximity,
* effective config version/hash.

---

# 12. Optional regulatory concern markers (major warning only)

This layer adds configurable regulatory risk markers designed to raise major warnings,
without acting as automatic deployment blockers.

## A. Optional config keys

Add optional keys under business config:

* `regulatory_markers.enabled` (bool)
* `regulatory_markers.default_severity` (enum, default: `major_warning`)
* `regulatory_markers.domains` (list)
: examples: `data_protection`, `financial_disclosure`, `health_claims`, `consumer_rights`.
* `regulatory_markers.rules` (list of rule objects)
* `regulatory_markers.rule_overrides_by_scenario` (optional mapping)

Each rule should support:

* `rule_id`
* `domain`
* `match_failure_modes` (list)
* `match_risk_tags` (optional list)
* `warning_threshold` (rate/score threshold)
* `lookback_scope` (`item`, `scenario`, `experiment`)
* `message_template`
* `owner` (governance contact)

## B. Decision behavior (non-blocking)

When a regulatory marker rule is triggered:

* attach warning status `major_warning` to outputs,
* include rule id/domain and affected items,
* include recommended mitigation text,
* do not force `hold` by itself.

Recommendation interaction:

* `go` can remain `go` with one or more major warnings,
* if a warning plus existing hard-risk gate fails, normal hard-gate logic still applies,
* `conditional` should list triggered regulatory markers as primary review reasons.

## C. Output contract additions

Add to business output:

* `regulatory_markers.total_triggered`
* `regulatory_markers.highest_severity`
* `regulatory_markers.items[]` with:
  * `rule_id`
  * `domain`
  * `status` (`major_warning`)
  * `trigger_metric`
  * `threshold`
  * `affected_item_ids`
  * `recommended_action`

## D. Governance and UI expectations

* Marker thresholds must be editable via config and runtime overrides.
* UI must support toggling marker sets by domain.
* UI must show warnings separately from hard blockers.
* Every replay artifact must record marker config version/hash used for audit.


