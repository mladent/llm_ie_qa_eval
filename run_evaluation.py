import argparse
import json
from pathlib import Path
import subprocess
from uuid import uuid4

from config_loader import DEFAULT_SETTINGS_PATH, load_eval_config
from extraction.extractor import run_extraction
from evaluation.metrics import compute_metrics
from evaluation.run_record import CanonicalRunRecord, ExperimentProvenance, utc_now_iso


def load_prompt(prompt_path):

    with open(prompt_path, encoding="utf-8") as f:
        return f.read()


def parse_args():
    parser = argparse.ArgumentParser(description="Run JSON extraction evaluation experiments.")
    parser.add_argument("--config", default=DEFAULT_SETTINGS_PATH)
    parser.add_argument("--provider")
    parser.add_argument("--model")
    parser.add_argument("--dataset-path")
    parser.add_argument("--prompt-path")
    parser.add_argument("--prompt-id")
    parser.add_argument("--num-runs", type=int)
    parser.add_argument("--output-dir")
    parser.add_argument("--experiment-name")
    parser.add_argument("--tracking-uri")
    parser.add_argument("--enable-mlflow", action="store_true", default=None)
    parser.add_argument("--disable-mlflow", action="store_false", dest="enable_mlflow")
    parser.add_argument("--max-retries", type=int)
    parser.add_argument("--retry-backoff", type=int)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--top-p", type=float)
    parser.add_argument("--max-tokens", type=int)
    return parser.parse_args()


def get_git_commit_hash() -> str | None:
    """Return current git commit hash, or None when unavailable."""

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def persist_provenance(provenance: ExperimentProvenance, output_dir: str) -> str:
    """Persist experiment provenance metadata to an analysis-friendly JSON artifact."""

    experiment_dir = Path(output_dir) / "experiments" / provenance.experiment_id
    experiment_dir.mkdir(parents=True, exist_ok=True)
    provenance_path = experiment_dir / "provenance.json"

    with provenance_path.open("w", encoding="utf-8") as provenance_file:
        json.dump(provenance.to_dict(), provenance_file, ensure_ascii=True, indent=2)

    return str(provenance_path.resolve())


def main():

    args = parse_args()
    config = load_eval_config(args)

    with open(config.data.dataset_path, encoding="utf-8") as dataset_file:
        dataset = json.load(dataset_file)

    prompt_template = load_prompt(config.data.prompt_path)
    experiment_id = f"exp-{uuid4().hex[:12]}"
    dataset_id = str(Path(config.data.dataset_path).resolve())
    prompt_path = str(Path(config.data.prompt_path).resolve())
    prompt_id = config.data.prompt_id
    evaluation_timestamp = utc_now_iso()

    provenance = ExperimentProvenance(
        experiment_id=experiment_id,
        experiment_name=config.experiment.name,
        dataset_path=dataset_id,
        prompt_path=prompt_path,
        prompt_id=prompt_id,
        provider=config.model.provider,
        model=config.model.model,
        evaluation_timestamp=evaluation_timestamp,
        git_commit_hash=get_git_commit_hash(),
    )
    provenance_path = persist_provenance(provenance, config.experiment.output_dir)

    run_records = []

    for doc in dataset:

        prompt = prompt_template.replace("{text}", doc["text"])

        extraction_result = run_extraction(
            config.model.provider,
            prompt,
            model=config.model.model,
        )
        prediction = extraction_result["parsed_output_json"]

        metrics = compute_metrics(prediction, doc["gold"])
        exact_match_with_gold = prediction == doc["gold"]

        run_record = CanonicalRunRecord(
            experiment_id=experiment_id,
            document_id=str(doc["id"]),
            provider=extraction_result["provider"],
            model=extraction_result["model"],
            prompt_id=prompt_id,
            dataset_id=dataset_id,
            # Single-pass baseline: repeated-run orchestration will increment this later.
            run_index=0,
            timestamp=utc_now_iso(),
            raw_response_text=extraction_result["raw_response_text"],
            parsed_output_json=prediction,
            parse_status=extraction_result["parse_status"],
            error_message=extraction_result["error_message"],
            latency_ms=extraction_result["latency_ms"],
            input_tokens=extraction_result["input_tokens"],
            output_tokens=extraction_result["output_tokens"],
            estimated_cost=extraction_result["estimated_cost"],
            precision=metrics["precision"],
            recall=metrics["recall"],
            f1=metrics["f1"],
            exact_match_with_gold=exact_match_with_gold,
        )

        run_records.append(run_record)

        print("\nDOCUMENT:", doc["id"])
        print("Prediction:", run_record.parsed_output_json)
        print("Gold:", doc["gold"])
        print("Parse status:", run_record.parse_status)
        print("Metrics:", {
            "precision": run_record.precision,
            "recall": run_record.recall,
            "f1": run_record.f1,
            "exact_match_with_gold": run_record.exact_match_with_gold,
        })

    avg_precision = sum(r.precision for r in run_records) / len(run_records)
    avg_recall = sum(r.recall for r in run_records) / len(run_records)
    avg_f1 = sum(r.f1 for r in run_records) / len(run_records)

    print("\n=== FINAL RESULTS ===")
    print("Experiment ID:", experiment_id)
    print("Experiment Name:", config.experiment.name)
    print("Provider:", config.model.provider)
    print("Model:", config.model.model)
    print("Dataset:", dataset_id)
    print("Prompt ID:", prompt_id)
    print("Prompt Path:", prompt_path)
    print("Evaluation Timestamp:", evaluation_timestamp)
    print("Git Commit Hash:", provenance.git_commit_hash)
    print("Provenance Artifact:", provenance_path)
    print("Tracking URI:", config.tracking.tracking_uri)
    print("MLflow Enabled:", config.tracking.enable_mlflow)
    print("Configured num_runs:", config.experiment.num_runs)
    print("Precision:", avg_precision)
    print("Recall:", avg_recall)
    print("F1:", avg_f1)


if __name__ == "__main__":
    main()
