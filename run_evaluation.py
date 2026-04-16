import argparse
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path
import subprocess
from typing import Any, Optional
from uuid import uuid4

from config_loader import DEFAULT_SETTINGS_PATH, EvalConfig, load_eval_config
from evaluation.dataset_validation import validate_dataset_shape
from evaluation.analysis_questions import build_phase8_analysis
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
    write_json_artifact,
    write_rows_csv,
    write_provenance,
)


def load_prompt(prompt_path):

    with open(prompt_path, encoding="utf-8") as f:
        return f.read()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_json(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
    ).hexdigest()


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


def _call_with_retry(config: EvalConfig, prompt: str, expected_fields: list[str]) -> dict:
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
                expected_fields=expected_fields,
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


def _infer_extraction_fields(dataset: list[dict[str, Any]], configured_fields: list[str]) -> list[str]:
    if configured_fields:
        return configured_fields
    first_gold = dataset[0].get("gold", {}) if dataset else {}
    if isinstance(first_gold, dict) and first_gold:
        return [str(key) for key in first_gold.keys()]
    return ["methods", "tasks", "datasets"]


def _load_dataset_from_project_spec(config: EvalConfig) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    documents = []
    manifest_documents = []

    for document in config.data.documents:
        document_path = Path(document.document_path).resolve()
        gold_path = Path(document.gold_path).resolve()
        document_text = document_path.read_text(encoding="utf-8")
        gold = json.loads(gold_path.read_text(encoding="utf-8"))
        documents.append({"id": document.id, "text": document_text, "gold": gold})
        manifest_documents.append(
            {
                "id": document.id,
                "document_path": str(document_path),
                "document_sha256": sha256_file(document_path),
                "gold_path": str(gold_path),
                "gold_sha256": sha256_file(gold_path),
            }
        )

    project_manifest = {
        "project_config_path": str(Path(config.config_path).resolve()),
        "prompt_path": str(Path(config.data.prompt_path).resolve()),
        "prompt_id": config.data.prompt_id,
        "documents": manifest_documents,
    }
    return documents, project_manifest


def _load_runtime_dataset(config: EvalConfig) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if config.data.documents:
        dataset, project_manifest = _load_dataset_from_project_spec(config)
        extraction_fields = _infer_extraction_fields(dataset, config.data.extraction_fields)
        validate_dataset_shape(dataset, required_gold_fields=extraction_fields)
        project_manifest["extraction_fields"] = extraction_fields
        dataset_id = f"project:{Path(config.config_path).resolve()}"
        dataset_sha256 = sha256_json(project_manifest)
        return dataset, {
            "input_mode": "project",
            "dataset_id": dataset_id,
            "dataset_sha256": dataset_sha256,
            "document_count": len(dataset),
            "extraction_fields": extraction_fields,
            "project_manifest": project_manifest,
            "project_spec_sha256": sha256_file(Path(config.config_path).resolve()),
        }

    dataset_path = Path(config.data.dataset_path or "").resolve()
    with dataset_path.open(encoding="utf-8") as dataset_file:
        dataset = json.load(dataset_file)
    extraction_fields = _infer_extraction_fields(dataset, config.data.extraction_fields)
    validate_dataset_shape(dataset, required_gold_fields=extraction_fields)
    return dataset, {
        "input_mode": "dataset",
        "dataset_id": str(dataset_path),
        "dataset_sha256": sha256_file(dataset_path),
        "document_count": len(dataset),
        "extraction_fields": extraction_fields,
        "project_manifest": None,
        "project_spec_sha256": None,
    }


def main():

    args = parse_args()
    config = load_eval_config(args)

    dataset, runtime_input = _load_runtime_dataset(config)

    prompt_template = load_prompt(config.data.prompt_path)
    experiment_id = f"exp-{uuid4().hex[:12]}"
    dataset_id = runtime_input["dataset_id"]
    dataset_sha256 = runtime_input["dataset_sha256"]
    prompt_path = str(Path(config.data.prompt_path).resolve())
    prompt_sha256 = sha256_text(prompt_template)
    prompt_id = config.data.prompt_id
    evaluation_timestamp = utc_now_iso()

    provenance = ExperimentProvenance(
        experiment_id=experiment_id,
        experiment_name=config.experiment.name,
        input_mode=runtime_input["input_mode"],
        dataset_path=dataset_id,
        dataset_sha256=dataset_sha256,
        prompt_path=prompt_path,
        prompt_id=prompt_id,
        prompt_sha256=prompt_sha256,
        document_count=runtime_input["document_count"],
        project_config_path=(str(Path(config.config_path).resolve()) if runtime_input["input_mode"] == "project" else None),
        project_spec_sha256=runtime_input["project_spec_sha256"],
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
    project_manifest_path = experiment_dir / "project_manifest.json"
    phase8_summary_path = experiment_dir / "phase8_analysis_summary.json"
    phase8_doc_table_path = experiment_dir / "phase8_document_analysis.csv"
    phase8_field_table_path = experiment_dir / "phase8_field_stability.csv"
    phase8_score_table_path = experiment_dir / "phase8_score_variation.csv"

    write_provenance(provenance_path, provenance)
    write_config_snapshot(config_snapshot_path, config)
    if runtime_input["project_manifest"] is not None:
        write_json_artifact(project_manifest_path, runtime_input["project_manifest"])

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
            "prompt_sha256": prompt_sha256,
            "dataset_id": dataset_id,
            "dataset_sha256": dataset_sha256,
            "dataset_path": config.data.dataset_path,
            "prompt_path": config.data.prompt_path,
            "num_runs": config.experiment.num_runs,
            "input_mode": runtime_input["input_mode"],
            "document_count": runtime_input["document_count"],
            "project_config_path": provenance.project_config_path,
            "project_spec_sha256": provenance.project_spec_sha256,
            "extraction_fields": ",".join(runtime_input["extraction_fields"]),
            "max_retries": config.execution.max_retries,
            "retry_backoff_seconds": config.execution.retry_backoff_seconds,
            "temperature": config.model.temperature,
            "top_p": config.model.top_p,
            "max_tokens": config.model.max_tokens,
            "tracking_uri": config.tracking.tracking_uri,
        }
    )

    run_records: list[CanonicalRunRecord] = []
    provider_failures = 0

    try:
        # 4.1 — deterministic document order, N repeated calls per document
        for doc in sorted(dataset, key=lambda d: str(d["id"])):
            prompt = prompt_template.replace("{text}", doc["text"])
            doc_id = str(doc["id"])

            for run_index in range(config.experiment.num_runs):
                print(f"\nDOCUMENT {doc_id}  run {run_index + 1}/{config.experiment.num_runs}")

                # 4.3 — bounded retries with backoff
                try:
                    extraction_result = _call_with_retry(
                        config,
                        prompt,
                        runtime_input["extraction_fields"],
                    )
                except Exception as exc:  # 4.2 — record failure, continue if allowed
                    provider_failures += 1
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
                    if run_record.parse_status != "success":
                        append_run_record(failures_jsonl_path, run_record)
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
        total_failures = sum(1 for record in run_records if record.parse_status != "success")
        write_corpus_summary(
            corpus_summary_path,
            corpus_aggregate,
            total_failures=total_failures,
        )

        phase8_analysis = build_phase8_analysis(run_records, document_aggregates)
        write_json_artifact(phase8_summary_path, phase8_analysis)
        write_rows_csv(phase8_doc_table_path, phase8_analysis["tables"]["document_analysis"])
        write_rows_csv(phase8_field_table_path, phase8_analysis["tables"]["field_stability"])
        write_rows_csv(phase8_score_table_path, phase8_analysis["tables"]["score_variation"])

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
                project_manifest_path,
                phase8_summary_path,
                phase8_doc_table_path,
                phase8_field_table_path,
                phase8_score_table_path,
            ]
        )
    finally:
        tracker.end()

    successful_records = [r for r in run_records if r.parse_status == "success"]
    avg_precision = sum(r.precision for r in successful_records) / len(successful_records) if successful_records else 0.0
    avg_recall = sum(r.recall for r in successful_records) / len(successful_records) if successful_records else 0.0
    avg_f1 = sum(r.f1 for r in successful_records) / len(successful_records) if successful_records else 0.0
    total_failures = sum(1 for r in run_records if r.parse_status != "success")
    failure_rate = total_failures / len(run_records) if run_records else 0.0

    print("\n=== FINAL RESULTS ===")
    print("Experiment ID:", experiment_id)
    print("Experiment Name:", config.experiment.name)
    print("Provider:", config.model.provider)
    print("Model:", config.model.model)
    print("Dataset:", dataset_id)
    print("Input Mode:", runtime_input["input_mode"])
    print("Document Count:", runtime_input["document_count"])
    print("Extraction Fields:", ", ".join(runtime_input["extraction_fields"]))
    print("Prompt ID:", prompt_id)
    print("Prompt SHA256:", prompt_sha256)
    print("Prompt Path:", prompt_path)
    print("Dataset SHA256:", dataset_sha256)
    print("Evaluation Timestamp:", evaluation_timestamp)
    print("Git Commit Hash:", provenance.git_commit_hash)
    print("Provenance Artifact:", str(provenance_path.resolve()))
    print("Config Snapshot:", str(config_snapshot_path.resolve()))
    if runtime_input["project_manifest"] is not None:
        print("Project Manifest:", str(project_manifest_path.resolve()))
    if config.exports.write_jsonl:
        print("Runs JSONL:", str(runs_jsonl_path.resolve()))
        print("Failures JSONL:", str(failures_jsonl_path.resolve()))
    if export_status["csv_written"]:
        print("Document Aggregates CSV:", str(document_aggregates_csv_path.resolve()))
    if export_status["parquet_written"]:
        print("Document Aggregates Parquet:", str(document_aggregates_parquet_path.resolve()))
    print("Corpus Summary:", str(corpus_summary_path.resolve()))
    print("Phase 8 Summary:", str(phase8_summary_path.resolve()))
    print("Phase 8 Document Analysis:", str(phase8_doc_table_path.resolve()))
    print("Phase 8 Field Stability:", str(phase8_field_table_path.resolve()))
    print("Phase 8 Score Variation:", str(phase8_score_table_path.resolve()))
    print("Tracking URI:", config.tracking.tracking_uri)
    print("MLflow Enabled:", tracker_ctx.enabled)
    if tracker_ctx.enabled:
        print("MLflow Run ID:", tracker_ctx.run_id)
    print(f"Total runs: {len(run_records)}  "
          f"(docs={len(dataset)}, num_runs={config.experiment.num_runs})")
    print(f"Failures: {total_failures}  failure_rate={failure_rate:.1%}")
    print(f"Provider failures: {provider_failures}")
    print(f"Precision: {avg_precision:.4f}")
    print(f"Recall:    {avg_recall:.4f}")
    print(f"F1:        {avg_f1:.4f}")


if __name__ == "__main__":
    main()
