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

## Set API keys:
```
export OPENAI_API_KEY=...
export GEMINI_API_KEY=...
```
### Run evaluation:

`python run_evaluation.py`

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

