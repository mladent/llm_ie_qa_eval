# UI Implementation Plan — Business Evaluation UI for Decision Makers

**Goal**: Add a FastAPI + HTML web UI to the existing API runtime that lets business managers
load static experiment artifacts, define a new business scenario (costs, thresholds, weights)
interactively, run the evaluation, view results, and download the scenario config as YAML.

No LLM calls are re-run. The UI operates entirely on pre-existing experiment artifacts.

---

## Decisions

| Decision | Choice |
|---|---|
| Framework | FastAPI + HTML (vanilla JS, no framework — extends existing `run_business_api.py`) |
| Config persistence | Downloadable YAML export only — no writes to disk config files |
| Scenario scope | Create new named scenarios; existing scenarios are read-only defaults |
| New files | `business/ui_app.html` (UI page), edits to `business/api.py` and `business/service.py` |

---

## Task List

### Phase 1 — Backend

- [x] **T1** Add `BusinessInlineConfig` dataclass to `business/service.py`
  - Fields: `experiment_dir`, `scenario_name`, `costs`, `weights`, `go_threshold`, `conditional_threshold`, `max_critical_failure_rate`, `max_expected_cost_per_1000`, `min_stability_score`, `cost_cap`
  - No file paths — configs are passed as in-memory values

- [x] **T2** Add `run_business_service_inline()` function to `business/service.py`
  - Signature: `(config: BusinessInlineConfig) -> Dict[str, Any]`
  - Builds settings/thresholds/costs values from inline fields
  - Calls the same reporting/business pipeline via `build_business_report_inline()`
  - Returns `dashboard_summary`, replay/CSV rows, and YAML export strings (`thresholds_yaml`, `costs_yaml`)

- [x] **T3** Add `POST /business/evaluate-inline` endpoint to `business/api.py`
  - Request body: JSON object validated in endpoint code
  - Calls `run_business_service_inline()`
  - Returns `dashboard_summary` plus `thresholds_yaml` and `costs_yaml`
  - Error responses: 400 on invalid input; 500 on unexpected error

- [x] **T4** Add `GET /ui` endpoint to `business/api.py`
  - Reads and returns `business/ui_app.html` as `HTMLResponse`

### Phase 2 — Frontend

- [x] **T5** Create `business/ui_app.html` — single-page UI with four sections:

  **Section 1 — Experiment Loader**
  - Text input: experiment directory path
  - "Load" button — fetches `corpus_summary.json` from the path client-side or POSTs to a `/business/experiment-info` helper endpoint
  - Summary card: model, provider, run count, document count, mean F1, parse error rate, failure rate

  **Section 2 — Scenario Builder form**
  - Text input: scenario name (becomes YAML block key)
  - Preset buttons: "Conservative", "Balanced", "Aggressive" — auto-populate all fields
  - Costs group: `parse_error`, `runtime_error`, `incorrect` (numeric, ≥ 0)
  - Weights group: `success`, `stability`, `quality`, `risk`, `critical` (numeric, each 0–1; must sum to 1.0; live validation)
  - Thresholds group: `go_threshold`, `conditional_threshold` (numeric 0–1; conditional < go enforced)
  - Hard gates group: `max_critical_failure_rate` (0–1), `max_expected_cost_per_1000` (≥ 0), `min_stability_score` (0–1)
  - "Evaluate" button — submits to `POST /business/evaluate-inline`

  **Section 3 — Results**
  - Recommendation banner: GO (green) / CONDITIONAL (amber) / HOLD (red)
  - Readiness score: numeric display
  - Hard gate status: pass/fail indicators for each gate
  - Soft warnings list
  - Risk panel: expected cost per 1,000, tail risk P95, critical failure rate
  - Metric contributions table: signed contribution of each weight component
  - Dominant failure modes table: mode + rate
  - Top failing items table: item_id + failure_probability + expected_cost
  - Threshold proximity table: distance to each decision boundary

  **Section 4 — Export**
  - YAML preview: rendered text block showing the two generated YAML file contents
  - Download buttons: "Download thresholds YAML" and "Download costs YAML" (client-side Blob download)
  - Reset button: clears results and resets form to defaults

- [x] **T6** Add `GET /business/experiment-info` endpoint to `business/api.py`
  - Query param: `experiment_dir`
  - Reads and returns `corpus_summary.json` from that directory
  - Used by Section 1 "Load" button

### Phase 3 — Wiring and Presets

- [x] **T7** Define three preset configurations (Conservative, Balanced, Aggressive):
  - Balanced: mirrors existing `default` scenario values from config files
  - Conservative: tighter thresholds, lower weights on quality, higher weight on stability/risk
  - Aggressive: looser thresholds, higher weight on quality, lower weight on risk/critical
  - Presets are encoded in the HTML (no server call needed)

- [x] **T8** Input validation (client-side):
  - Weights must sum to 1.0 (within ±0.005 tolerance) — show live error
  - `conditional_threshold` < `go_threshold` — show error if violated
  - All cost and gate values ≥ 0
  - Scenario name: non-empty, alphanumeric + underscore only (becomes YAML key)

### Phase 4 — Quality

- [x] **T9** Verify `get_errors()` on all modified files
- [x] **T10** Manual smoke test and test-suite verification completed for API/UI path
- [x] **T11** Commit: `feat: add business evaluation UI (GET /ui, POST /business/evaluate-inline)`

---

## Files Changed

| File | Change |
|---|---|
| `business/reporting.py` | Add `build_business_report_inline()` |
| `business/service.py` | Add `BusinessInlineConfig`, `run_business_service_inline()` |
| `business/api.py` | Add `GET /ui`, `GET /business/experiment-info`, `POST /business/evaluate-inline` |
| `business/ui_app.html` | New file — single-page UI |

No changes to: `run_business_api.py`, `business/recommender.py`, `business/metrics.py`,
`business/aggregates.py`, config files, or any evaluation modules.

---

## Default Values (pre-populate form from `default` scenario)

| Input | Default |
|---|---|
| `parse_error` cost | 10.0 |
| `runtime_error` cost | 8.0 |
| `incorrect` cost | 5.0 |
| weight: success | 0.35 |
| weight: stability | 0.20 |
| weight: quality | 0.25 |
| weight: risk | 0.12 |
| weight: critical | 0.08 |
| `go_threshold` | 0.73 |
| `conditional_threshold` | 0.55 |
| `max_critical_failure_rate` | 0.05 |
| `max_expected_cost_per_1000` | 6000.0 |
| `min_stability_score` | 0.60 |
