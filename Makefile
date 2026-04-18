PYTHON ?= .venv/bin/python
EXPERIMENT_DIR ?= outputs/experiments/exp-0837df5b02be
SCENARIO ?= default
HOST ?= 127.0.0.1
PORT ?= 8000
BASE_URL ?= http://$(HOST):$(PORT)

.PHONY: business-eval business-api business-api-smoke test-business

business-eval:
	$(PYTHON) run_business_evaluation.py --experiment-dir $(EXPERIMENT_DIR) --scenario $(SCENARIO)

business-api:
	$(PYTHON) run_business_api.py --host $(HOST) --port $(PORT)

business-api-smoke:
	./scripts/business_api_smoke.sh $(BASE_URL) $(EXPERIMENT_DIR) $(SCENARIO)

test-business:
	$(PYTHON) -m pytest tests/test_business_adapter.py tests/test_business_metrics.py tests/test_business_recommender.py tests/test_business_reporting.py tests/test_business_contract_regression.py tests/test_business_service.py tests/test_business_api_runtime.py -q
