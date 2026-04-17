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

This section converts the strategy and model above into delivery phases.

## Phase 1: Contract adapter from evaluator outputs

Input artifacts from current evaluator runs:

* `runs.jsonl`
* `document_aggregates.csv`
* `corpus_summary.json`
* optional hybrid outputs (`hybrid_component_trends.csv`, `hybrid_path_breakdown.csv`)

Deliverables:

* parser/loader that maps evaluator artifacts into the business schema in this document
* strict validation and clear errors for missing/invalid artifacts

## Phase 2: Business metric engine

Implement and test:

* stability
* agreement
* expected cost of failure (ECF)
* critical failure rate
* five-number summaries

Deliverables:

* per-item aggregate builder
* scenario-level aggregate builder
* deterministic metric functions with unit tests

## Phase 3: Decision layer

Implement deployment recommendation logic:

* readiness score
* recommendation classes (`go`, `conditional`, `hold`)
* threshold config per scenario/domain

Deliverables:

* `dashboard_summary.json` generation
* explainability fields (top drivers, failing items, risk hotspots)

## Phase 4: Management output interfaces

Deliverables:

* JSON output contracts for product/ops stakeholders
* CSV tables for BI tools
* optional lightweight CLI summary view for leadership

## Phase 5: Governance and operational hardening

Deliverables:

* contract versioning
* reproducibility metadata
* regression suite for business decision outputs
* documentation of interpretation guidelines and risk caveats

## Phase 6: Optional extraction to separate service (deferred)

Only after split triggers are met:

* wrap business module behind API
* keep evaluator as producer and business module as consumer
* preserve exact same schema contracts to minimize migration risk

---

# ✅ 7. Definition of done for this plan

The plan is considered complete when:

1. A single command can produce business decision JSON from evaluator outputs.
2. All core metrics in Section 2 are computed and tested.
3. Dashboard JSON in Section 3 is generated with real run data.
4. Recommendation logic is configurable and scenario-aware.
5. Contract tests prevent breaking downstream consumers.

---

# 💡 Final insight

What you’ve effectively built here is:

> **A probabilistic risk model over LLM behavior — not just an evaluation.**

That’s the key shift:

* from “model quality measurement”
* to **“deployment risk quantification”**

