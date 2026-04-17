# LLM Information Extraction Evaluation Platform

---
## TOC



---

## Architecture Overview

```
llm_ie_eval/
│
├── data/
│   └── dataset.json
│
├── prompts/
│   └── extraction_prompt.txt
│
├── providers/
│   ├── openai_provider.py
│   └── gemini_provider.py
│
├── evaluation/
│   └── metrics.py
│
├── extraction/
│   └── extractor.py
│
├── run_evaluation.py
│
└── requirements.txt
```

### Pipeline:
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
```
----
## Run the Platform

### Install dependencies:

`pip install -r requirements.txt`

### Set API keys:

Copy `.env-template` to `.env` and add your API keys:

```bash
cp .env-template .env
# Edit .env and add your actual API keys
```

### Run evaluation:

Use a single project YAML file as the source of truth for the run. A sample is available at `config/project_eval_example.yaml`.

```bash
python run_evaluation.py --config config/project_eval_example.yaml
```

To scaffold a private local project from the `.local` template:

```bash
scripts/new_local_eval_project.sh my-cv-project
python run_evaluation.py --config .local/eval_projects/my-cv-project/project.yaml
```

### Project file shape

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

### Hybrid JSON Rubric Scoring

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

- comparator catalog (`exact_match`, `set_jaccard_match`, `fuzzy_lexical_match`, `key_based_array_object_match`)
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

### 11. Expected Output

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

