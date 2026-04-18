from __future__ import annotations

import json
from pathlib import Path

from business.reporting import build_business_report


def _write_sample_artifacts(exp_dir: Path) -> None:
    (exp_dir / "runs.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "document_id": "doc1",
                        "run_index": 0,
                        "raw_response_text": "ok output",
                        "parse_status": "success",
                        "error_message": None,
                        "precision": 0.9,
                        "recall": 0.8,
                        "f1": 0.85,
                        "exact_match_with_gold": True,
                    }
                ),
                json.dumps(
                    {
                        "document_id": "doc2",
                        "run_index": 0,
                        "raw_response_text": "broken output",
                        "parse_status": "parse_error",
                        "error_message": "decode fail",
                        "precision": 0.0,
                        "recall": 0.0,
                        "f1": 0.0,
                        "exact_match_with_gold": False,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    (exp_dir / "document_aggregates.csv").write_text(
        "mean_precision,std_precision,ci95_precision,mean_recall,std_recall,ci95_recall,mean_f1,std_f1,ci95_f1,"
        "exact_match_consistency_rate,parse_error_rate,latency_mean,latency_std,cost_mean,cost_std,experiment_id,"
        "document_id,provider,model,prompt_id,dataset_id,run_count,precision_min,precision_q1,precision_median,"
        "precision_q3,precision_max,recall_min,recall_q1,recall_median,recall_q3,recall_max,f1_min,f1_q1,"
        "f1_median,f1_q3,f1_max\n"
        "0.9,0,0,0.8,0,0,0.85,0,0,1.0,0.0,100,0,0,0,exp-x,doc1,openai,gpt-4o-mini,prompt-a,dataset-a,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0\n"
        "0.0,0,0,0.0,0,0,0.0,0,0,0.0,1.0,120,0,0,0,exp-x,doc2,openai,gpt-4o-mini,prompt-a,dataset-a,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0\n",
        encoding="utf-8",
    )

    (exp_dir / "corpus_summary.json").write_text(
        json.dumps(
            {
                "experiment_id": "exp-x",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "prompt_id": "prompt-a",
                "dataset_id": "dataset-a",
                "run_count": 2,
                "document_count": 2,
                "mean_f1": 0.425,
                "parse_error_rate": 0.5,
                "failure_rate": 0.5,
            }
        ),
        encoding="utf-8",
    )


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _normalize_dashboard(payload: dict) -> dict:
    normalized = dict(payload)
    normalized["business_config_hash"] = "<dynamic>"
    normalized["source_experiment_dir"] = "<dynamic>"
    return normalized


def test_business_dashboard_contract_regression(tmp_path: Path) -> None:
    exp_dir = tmp_path / "exp"
    exp_dir.mkdir(parents=True)
    _write_sample_artifacts(exp_dir)

    report = build_business_report(
        experiment_dir=str(exp_dir),
        scenario="default",
        settings_config_path="config/business_settings.yaml",
        thresholds_config_path="config/business_thresholds.yaml",
        costs_config_path="config/business_costs.yaml",
        contract_config_path="config/business_contract.yaml",
    )

    golden_dashboard = _load_json("tests/golden/business_outputs/dashboard_summary.json")
    key_contract = _load_json("tests/golden/business_outputs/required_contract_keys.json")

    dashboard = report["dashboard_summary"]
    replay = report["replay_metadata"]

    for key in key_contract["dashboard_required_keys"]:
        assert key in dashboard

    for key in key_contract["replay_metadata_required_keys"]:
        assert key in replay

    assert _normalize_dashboard(dashboard) == _normalize_dashboard(golden_dashboard)

    assert replay["business_contract_version"] == dashboard["business_contract_version"]
    assert replay["business_config_version"] == dashboard["business_config_version"]
    assert replay["business_config_hash"] == dashboard["business_config_hash"]
