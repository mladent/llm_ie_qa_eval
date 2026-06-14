from __future__ import annotations

import json
from pathlib import Path

from business.api import evaluate_business_payload
from business.service import BusinessServiceRequest, run_business_service


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


def test_run_business_service_with_artifact_write(tmp_path: Path) -> None:
    exp_dir = tmp_path / "exp"
    exp_dir.mkdir(parents=True)
    _write_sample_artifacts(exp_dir)

    out_dir = tmp_path / "svc_out"
    response = run_business_service(
        BusinessServiceRequest(
            experiment_dir=str(exp_dir),
            output_dir=str(out_dir),
            write_artifacts=True,
        )
    )

    assert response.dashboard_summary["scenario"] == "default"
    assert response.replay_metadata["source_experiment_id"] == "exp"
    assert Path(response.artifact_paths["dashboard_summary"]).exists()
    assert Path(response.artifact_paths["replay_metadata"]).exists()


def test_evaluate_business_payload_without_writes(tmp_path: Path) -> None:
    exp_dir = tmp_path / "exp"
    exp_dir.mkdir(parents=True)
    _write_sample_artifacts(exp_dir)

    payload = evaluate_business_payload(
        {
            "experiment_dir": str(exp_dir),
            "scenario": "default",
            "write_artifacts": False,
        }
    )

    assert payload["dashboard_summary"]["deployment_readiness"]["recommendation"] in {
        "go",
        "conditional",
        "hold",
    }
    assert payload["artifact_paths"] == {}
