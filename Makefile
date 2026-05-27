PYTHON ?= .venv/bin/python
EXPERIMENT_DIR ?= outputs/experiments/exp-0837df5b02be
RUNS_JSONL ?= $(EXPERIMENT_DIR)/runs.jsonl
SCHEMA_JSON ?= demo/cv_recruiting_enterprise/schema/cv_extraction_output.schema.json
INSPECTION_OUT_DIR ?= outputs/inspection
DOCUMENT_ID ?=
GOLD_DIR ?= demo/cv_recruiting_enterprise/gold
SCENARIO ?= default
HOST ?= 127.0.0.1
PORT ?= 8000
BASE_URL ?= http://$(HOST):$(PORT)
MLFLOW_PORT ?= 5000
MLFLOW_FILE_STORE_DIR ?= mlflow_file_store

.PHONY: business-eval business-api business-api-smoke test-business mlflow-ui mlflow-ui-file-store inspect-runs

business-eval:
	$(PYTHON) run_business_evaluation.py --experiment-dir $(EXPERIMENT_DIR) --scenario $(SCENARIO)

business-api:
	$(PYTHON) run_business_api.py --host $(HOST) --port $(PORT)

business-api-smoke:
	./scripts/business_api_smoke.sh $(BASE_URL) $(EXPERIMENT_DIR) $(SCENARIO)

test-business:
	$(PYTHON) -m pytest tests/test_business_adapter.py tests/test_business_metrics.py tests/test_business_recommender.py tests/test_business_reporting.py tests/test_business_contract_regression.py tests/test_business_service.py tests/test_business_api_runtime.py -q

mlflow-ui:
	mlflow ui --backend-store-uri sqlite:///mlflow.db --host 127.0.0.1 --port $(MLFLOW_PORT)

mlflow-ui-file-store:
	mlflow ui --backend-store-uri ./$(MLFLOW_FILE_STORE_DIR) --host 127.0.0.1 --port $(MLFLOW_PORT)

inspect-runs:
	$(PYTHON) scripts/export_run_inspection.py --runs-jsonl $(RUNS_JSONL) --schema-json $(SCHEMA_JSON) --out-dir $(INSPECTION_OUT_DIR) $(if $(DOCUMENT_ID),--document-id $(DOCUMENT_ID),) --gold-dir $(GOLD_DIR)
