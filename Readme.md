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

