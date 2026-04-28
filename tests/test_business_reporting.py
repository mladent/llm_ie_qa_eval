from __future__ import annotations

import json
from pathlib import Path

from business.reporting import build_business_report, load_business_costs, write_business_report_artifacts


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


def test_load_business_costs_with_scenario_override(tmp_path: Path) -> None:
    cfg = tmp_path / "costs.yaml"
    cfg.write_text(
        "default:\n"
        "  incorrect: 5\n"
        "  parse_error: 10\n"
        "refund_handling:\n"
        "  incorrect: 8\n",
        encoding="utf-8",
    )

    costs = load_business_costs(str(cfg), "refund_handling")
    assert costs["incorrect"] == 8.0
    assert costs["parse_error"] == 10.0


def test_build_and_write_business_report(tmp_path: Path) -> None:
    exp_dir = tmp_path / "exp"
    exp_dir.mkdir(parents=True)
    _write_sample_artifacts(exp_dir)

    report = build_business_report(
        experiment_dir=str(exp_dir),
        scenario="default",
        settings_config_path="config/business_settings.yaml",
        thresholds_config_path="config/business_thresholds.yaml",
        costs_config_path="config/business_costs.yaml",
    )

    assert "dashboard_summary" in report
    assert report["dashboard_summary"]["deployment_readiness"]["recommendation"] in {
        "go",
        "conditional",
        "hold",
    }
    assert len(report["item_csv_rows"]) == 2

    out_dir = tmp_path / "business_out"
    paths = write_business_report_artifacts(report_payload=report, output_dir=str(out_dir))

    dashboard = json.loads((out_dir / "dashboard_summary.json").read_text(encoding="utf-8"))
    replay_metadata = json.loads((out_dir / "replay_metadata.json").read_text(encoding="utf-8"))
    assert dashboard["scenario"] == "default"
    assert "business_config_hash" in dashboard
    assert replay_metadata["source_experiment_id"] == "exp"
    assert Path(paths["scenario_business_summary"]).exists()
    assert Path(paths["item_business_breakdown"]).exists()
    assert Path(paths["replay_metadata"]).exists()
