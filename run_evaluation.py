import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
import subprocess
from typing import Optional
from uuid import uuid4

from config_loader import DEFAULT_SETTINGS_PATH, EvalConfig, load_eval_config
from evaluation.metrics import (
    compute_corpus_aggregate,
    compute_document_aggregate,
    compute_metrics,
)
from evaluation.run_record import CanonicalRunRecord, ExperimentProvenance, utc_now_iso
from extraction.extractor import run_extraction
from mlflow_utils import MLflowTracker
from persistence import (
    append_run_record,
    ensure_experiment_dir,
    write_config_snapshot,
    write_corpus_summary,
    write_document_aggregates,
    write_provenance,
)


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


def _call_with_retry(config: EvalConfig, prompt: str) -> dict:
    """Call run_extraction with bounded exponential-backoff retries for transient failures."""

    last_exc: Optional[Exception] = None
    for attempt in range(config.execution.max_retries + 1):
        try:
            return run_extraction(
                config.model.provider,
                prompt,
                model=config.model.model,
                temperature=config.model.temperature,
                top_p=config.model.top_p,
                max_tokens=config.model.max_tokens,
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < config.execution.max_retries:
                backoff = config.execution.retry_backoff_seconds * (2 ** attempt)
                print(f"  [retry {attempt + 1}/{config.execution.max_retries}] "
                      f"provider error: {exc}. Retrying in {backoff}s…")
                time.sleep(backoff)

    raise last_exc  # type: ignore[misc]


def _make_failed_run_record(
    *,
    experiment_id: str,
    document_id: str,
    config: EvalConfig,
    prompt_id: str,
    dataset_id: str,
    run_index: int,
    error_message: str,
) -> CanonicalRunRecord:
    """Create a zero-metric run record representing a hard provider failure."""

    return CanonicalRunRecord(
        experiment_id=experiment_id,
        document_id=document_id,
        provider=config.model.provider,
        model=config.model.model,
        prompt_id=prompt_id,
        dataset_id=dataset_id,
        run_index=run_index,
        timestamp=utc_now_iso(),
        raw_response_text="",
        parsed_output_json={},
        parse_status="provider_error",
        error_message=error_message,
        latency_ms=0.0,
        input_tokens=None,
        output_tokens=None,
        estimated_cost=None,
        precision=0.0,
        recall=0.0,
        f1=0.0,
        exact_match_with_gold=False,
    )


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

    experiment_dir = ensure_experiment_dir(config.experiment.output_dir, experiment_id)
    provenance_path = experiment_dir / "provenance.json"
    config_snapshot_path = experiment_dir / "config.json"
    runs_jsonl_path = experiment_dir / "runs.jsonl"
    failures_jsonl_path = experiment_dir / "failures.jsonl"
    document_aggregates_csv_path = experiment_dir / "document_aggregates.csv"
    document_aggregates_parquet_path = experiment_dir / "document_aggregates.parquet"
    corpus_summary_path = experiment_dir / "corpus_summary.json"

    write_provenance(provenance_path, provenance)
    write_config_snapshot(config_snapshot_path, config)

    tracker = MLflowTracker(
        enabled=config.tracking.enable_mlflow,
        tracking_uri=config.tracking.tracking_uri,
        experiment_name=config.experiment.name,
        run_name=experiment_id,
        tags={
            **config.tracking.tags,
            "experiment_id": experiment_id,
            "provider": config.model.provider,
            "model": config.model.model,
            "prompt_id": prompt_id,
        },
    )
    tracker_ctx = tracker.start()
    tracker.log_global_params(
        {
            "experiment_id": experiment_id,
            "experiment_name": config.experiment.name,
            "provider": config.model.provider,
            "model": config.model.model,
            "prompt_id": prompt_id,
            "dataset_id": dataset_id,
            "dataset_path": config.data.dataset_path,
            "prompt_path": config.data.prompt_path,
            "num_runs": config.experiment.num_runs,
            "max_retries": config.execution.max_retries,
            "retry_backoff_seconds": config.execution.retry_backoff_seconds,
            "temperature": config.model.temperature,
            "top_p": config.model.top_p,
            "max_tokens": config.model.max_tokens,
            "tracking_uri": config.tracking.tracking_uri,
        }
    )

    run_records: list[CanonicalRunRecord] = []
    total_failures = 0

    try:
        # 4.1 — deterministic document order, N repeated calls per document
        for doc in sorted(dataset, key=lambda d: str(d["id"])):
            prompt = prompt_template.replace("{text}", doc["text"])
            doc_id = str(doc["id"])

            for run_index in range(config.experiment.num_runs):
                print(f"\nDOCUMENT {doc_id}  run {run_index + 1}/{config.experiment.num_runs}")

                # 4.3 — bounded retries with backoff
                try:
                    extraction_result = _call_with_retry(config, prompt)
                except Exception as exc:  # 4.2 — record failure, continue if allowed
                    total_failures += 1
                    error_msg = str(exc)
                    print(f"  [FAILED] {error_msg}")
                    failed_record = _make_failed_run_record(
                        experiment_id=experiment_id,
                        document_id=doc_id,
                        config=config,
                        prompt_id=prompt_id,
                        dataset_id=dataset_id,
                        run_index=run_index,
                        error_message=error_msg,
                    )
                    run_records.append(failed_record)
                    if config.exports.write_jsonl:
                        append_run_record(runs_jsonl_path, failed_record)
                        append_run_record(failures_jsonl_path, failed_record)
                    tracker.log_run_record_metrics(failed_record, step=len(run_records) - 1)
                    if not config.execution.continue_on_error:
                        raise
                    continue

                prediction = extraction_result["parsed_output_json"]
                metrics = compute_metrics(prediction, doc["gold"])
                exact_match_with_gold = prediction == doc["gold"]

                run_record = CanonicalRunRecord(
                    experiment_id=experiment_id,
                    document_id=doc_id,
                    provider=extraction_result["provider"],
                    model=extraction_result["model"],
                    prompt_id=prompt_id,
                    dataset_id=dataset_id,
                    run_index=run_index,
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
                # 4.1 — persist each run immediately
                if config.exports.write_jsonl:
                    append_run_record(runs_jsonl_path, run_record)
                tracker.log_run_record_metrics(run_record, step=len(run_records) - 1)

                print(f"  Parse status: {run_record.parse_status}")
                print(f"  Metrics: precision={run_record.precision:.3f}  "
                    f"recall={run_record.recall:.3f}  f1={run_record.f1:.3f}  "
                    f"exact_match={run_record.exact_match_with_gold}")

        # Phase 6.2/6.3 - aggregate artifact persistence for analysis.
        by_doc: dict[str, list[CanonicalRunRecord]] = defaultdict(list)
        for record in run_records:
            by_doc[record.document_id].append(record)

        document_aggregates = [
            compute_document_aggregate(by_doc[doc_id])
            for doc_id in sorted(by_doc)
        ]

        corpus_aggregate = compute_corpus_aggregate(
            run_records,
            experiment_id=experiment_id,
            provider=config.model.provider,
            model=config.model.model,
            prompt_id=prompt_id,
            dataset_id=dataset_id,
            timestamp=evaluation_timestamp,
        )

        export_status = write_document_aggregates(
            document_aggregates,
            document_aggregates_csv_path,
            document_aggregates_parquet_path,
            write_csv=config.exports.write_csv,
            write_parquet=config.exports.write_parquet,
        )
        write_corpus_summary(
            corpus_summary_path,
            corpus_aggregate,
            total_failures=total_failures,
        )

        tracker.log_document_aggregates(document_aggregates)
        tracker.log_corpus_aggregate(corpus_aggregate, total_failures=total_failures)
        tracker.log_artifacts(
            [
                provenance_path,
                config_snapshot_path,
                corpus_summary_path,
                runs_jsonl_path,
                failures_jsonl_path,
                document_aggregates_csv_path,
                document_aggregates_parquet_path,
            ]
        )
    finally:
        tracker.end()

    successful_records = [r for r in run_records if r.parse_status not in ("provider_error",)]
    avg_precision = sum(r.precision for r in successful_records) / len(successful_records) if successful_records else 0.0
    avg_recall = sum(r.recall for r in successful_records) / len(successful_records) if successful_records else 0.0
    avg_f1 = sum(r.f1 for r in successful_records) / len(successful_records) if successful_records else 0.0
    failure_rate = total_failures / len(run_records) if run_records else 0.0

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
    print("Provenance Artifact:", str(provenance_path.resolve()))
    print("Config Snapshot:", str(config_snapshot_path.resolve()))
    if config.exports.write_jsonl:
        print("Runs JSONL:", str(runs_jsonl_path.resolve()))
        print("Failures JSONL:", str(failures_jsonl_path.resolve()))
    if export_status["csv_written"]:
        print("Document Aggregates CSV:", str(document_aggregates_csv_path.resolve()))
    if export_status["parquet_written"]:
        print("Document Aggregates Parquet:", str(document_aggregates_parquet_path.resolve()))
    print("Corpus Summary:", str(corpus_summary_path.resolve()))
    print("Tracking URI:", config.tracking.tracking_uri)
    print("MLflow Enabled:", tracker_ctx.enabled)
    if tracker_ctx.enabled:
        print("MLflow Run ID:", tracker_ctx.run_id)
    print(f"Total runs: {len(run_records)}  "
          f"(docs={len(dataset)}, num_runs={config.experiment.num_runs})")
    print(f"Failures: {total_failures}  failure_rate={failure_rate:.1%}")
    print(f"Precision: {avg_precision:.4f}")
    print(f"Recall:    {avg_recall:.4f}")
    print(f"F1:        {avg_f1:.4f}")


if __name__ == "__main__":
    main()
