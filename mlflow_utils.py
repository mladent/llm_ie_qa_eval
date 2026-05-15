from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from evaluation.run_record import CanonicalRunRecord, CorpusAggregateRecord, DocumentAggregateRecord


@dataclass
class MLflowRunContext:
    enabled: bool
    run_id: Optional[str]


class MLflowTracker:
    """Small MLflow utility layer for experiment logging.

    This wrapper keeps MLflow concerns isolated from orchestration code and
    gracefully degrades to no-op when tracking is disabled or mlflow is missing.
    """

    def __init__(
        self,
        *,
        enabled: bool,
        tracking_uri: str,
        experiment_name: str,
        run_name: str,
        tags: Dict[str, str],
    ) -> None:
        self.enabled = enabled
        self.tracking_uri = tracking_uri
        self.experiment_name = experiment_name
        self.run_name = run_name
        self.tags = tags
        self._mlflow = None
        self._active = False
        self._run_id: Optional[str] = None

    def start(self) -> MLflowRunContext:
        if not self.enabled:
            return MLflowRunContext(enabled=False, run_id=None)

        try:
            import mlflow  # type: ignore[import-not-found]
        except ImportError:
            print("[warning] MLflow enabled but 'mlflow' is not installed. Continuing without MLflow logging.")
            self.enabled = False
            return MLflowRunContext(enabled=False, run_id=None)

        self._mlflow = mlflow
        mlflow.set_tracking_uri(self.tracking_uri)
        mlflow.set_experiment(self.experiment_name)
        run = mlflow.start_run(run_name=self.run_name)
        self._touch_experiment_last_update_time(getattr(run.info, "experiment_id", None))
        self._active = True
        self._run_id = run.info.run_id

        if self.tags:
            mlflow.set_tags(self.tags)

        return MLflowRunContext(enabled=True, run_id=self._run_id)

    def end(self) -> None:
        if self._active and self._mlflow is not None:
            self._mlflow.end_run()
        self._active = False

    def _touch_experiment_last_update_time(self, experiment_id: Optional[str]) -> None:
        """Keep the MLflow experiment list aligned with recent run activity.

        MLflow's SQL-backed create_run path does not update the experiment row's
        last_update_time, so the UI experiment table can look stale even when new
        runs have been recorded. This best-effort touch is limited to the local
        SQLAlchemy store and safely no-ops for other backends.
        """

        if self._mlflow is None or experiment_id is None:
            return

        try:
            client = self._mlflow.tracking.MlflowClient()
            store = client._tracking_client.store
            managed_session_maker = getattr(store, "ManagedSessionMaker", None)
            if store.__class__.__name__ != "SqlAlchemyStore" or managed_session_maker is None:
                return

            from mlflow.store.tracking.dbmodels.models import SqlExperiment  # type: ignore[import-not-found]

            with managed_session_maker() as session:
                experiment = (
                    session.query(SqlExperiment)
                    .filter(SqlExperiment.experiment_id == int(experiment_id))
                    .one_or_none()
                )
                if experiment is None:
                    return
                experiment.last_update_time = int(time.time() * 1000)
                session.add(experiment)
        except Exception:
            return

    def log_global_params(self, params: Dict[str, Any]) -> None:
        if not self._active or self._mlflow is None:
            return
        for key, value in params.items():
            if value is None:
                continue
            self._mlflow.log_param(key, value)

    def log_run_record_metrics(self, record: CanonicalRunRecord, *, step: int) -> None:
        if not self._active or self._mlflow is None:
            return

        metrics = {
            "run_precision": float(record.precision),
            "run_recall": float(record.recall),
            "run_f1": float(record.f1),
            "run_hybrid_total_score": float(record.hybrid_total_score),
            "run_hybrid_schema_score": float(record.hybrid_schema_score),
            "run_hybrid_value_score": float(record.hybrid_value_score),
            "run_hybrid_unknown_penalty": float(record.hybrid_unknown_penalty),
            "run_hybrid_rule_coverage": float(record.hybrid_rule_coverage),
            "run_exact_match_with_gold": 1.0 if record.exact_match_with_gold else 0.0,
            "run_parse_success": 1.0 if record.parse_status == "success" else 0.0,
            "run_provider_error": 1.0 if record.parse_status == "provider_error" else 0.0,
            "run_parse_error": 1.0 if record.parse_status == "parse_error" else 0.0,
            "run_schema_error": 1.0 if record.parse_status == "schema_error" else 0.0,
            "run_latency_ms": float(record.latency_ms),
        }

        if record.estimated_cost is not None:
            metrics["run_estimated_cost"] = float(record.estimated_cost)
        if record.input_tokens is not None:
            metrics["run_input_tokens"] = float(record.input_tokens)
        if record.output_tokens is not None:
            metrics["run_output_tokens"] = float(record.output_tokens)

        self._mlflow.log_metrics(metrics, step=step)

    def log_document_aggregates(self, aggregates: Iterable[DocumentAggregateRecord]) -> None:
        """Log compact document-level metrics for quick comparison in MLflow UI."""

        if not self._active or self._mlflow is None:
            return

        for index, agg in enumerate(aggregates):
            metrics = {
                "document_mean_precision": float(agg.mean_precision),
                "document_std_precision": float(agg.std_precision),
                "document_ci95_precision": float(agg.ci95_precision),
                "document_precision_min": float(agg.precision_five_number.min),
                "document_precision_q1": float(agg.precision_five_number.q1),
                "document_precision_median": float(agg.precision_five_number.median),
                "document_precision_q3": float(agg.precision_five_number.q3),
                "document_precision_max": float(agg.precision_five_number.max),
                "document_mean_recall": float(agg.mean_recall),
                "document_std_recall": float(agg.std_recall),
                "document_ci95_recall": float(agg.ci95_recall),
                "document_recall_min": float(agg.recall_five_number.min),
                "document_recall_q1": float(agg.recall_five_number.q1),
                "document_recall_median": float(agg.recall_five_number.median),
                "document_recall_q3": float(agg.recall_five_number.q3),
                "document_recall_max": float(agg.recall_five_number.max),
                "document_mean_f1": float(agg.mean_f1),
                "document_std_f1": float(agg.std_f1),
                "document_ci95_f1": float(agg.ci95_f1),
                "document_f1_min": float(agg.f1_five_number.min),
                "document_f1_q1": float(agg.f1_five_number.q1),
                "document_f1_median": float(agg.f1_five_number.median),
                "document_f1_q3": float(agg.f1_five_number.q3),
                "document_f1_max": float(agg.f1_five_number.max),
                "document_exact_match_consistency_rate": float(agg.exact_match_consistency_rate),
                "document_parse_error_rate": float(agg.parse_error_rate),
                "document_mean_hybrid_score": float(agg.mean_hybrid_score),
                "document_std_hybrid_score": float(agg.std_hybrid_score),
                "document_ci95_hybrid_score": float(agg.ci95_hybrid_score),
                "document_latency_mean": float(agg.latency_mean),
                "document_latency_std": float(agg.latency_std),
                "document_cost_mean": float(agg.cost_mean),
                "document_cost_std": float(agg.cost_std),
            }
            self._mlflow.log_metrics(metrics, step=index)

    def log_corpus_aggregate(self, aggregate: CorpusAggregateRecord, *, total_failures: int) -> None:
        if not self._active or self._mlflow is None:
            return

        metrics = {
            "corpus_mean_precision": float(aggregate.mean_precision),
            "corpus_std_precision": float(aggregate.std_precision),
            "corpus_ci95_precision": float(aggregate.ci95_precision),
            "corpus_precision_min": float(aggregate.precision_five_number.min),
            "corpus_precision_q1": float(aggregate.precision_five_number.q1),
            "corpus_precision_median": float(aggregate.precision_five_number.median),
            "corpus_precision_q3": float(aggregate.precision_five_number.q3),
            "corpus_precision_max": float(aggregate.precision_five_number.max),
            "corpus_mean_recall": float(aggregate.mean_recall),
            "corpus_std_recall": float(aggregate.std_recall),
            "corpus_ci95_recall": float(aggregate.ci95_recall),
            "corpus_recall_min": float(aggregate.recall_five_number.min),
            "corpus_recall_q1": float(aggregate.recall_five_number.q1),
            "corpus_recall_median": float(aggregate.recall_five_number.median),
            "corpus_recall_q3": float(aggregate.recall_five_number.q3),
            "corpus_recall_max": float(aggregate.recall_five_number.max),
            "corpus_mean_f1": float(aggregate.mean_f1),
            "corpus_std_f1": float(aggregate.std_f1),
            "corpus_ci95_f1": float(aggregate.ci95_f1),
            "corpus_f1_min": float(aggregate.f1_five_number.min),
            "corpus_f1_q1": float(aggregate.f1_five_number.q1),
            "corpus_f1_median": float(aggregate.f1_five_number.median),
            "corpus_f1_q3": float(aggregate.f1_five_number.q3),
            "corpus_f1_max": float(aggregate.f1_five_number.max),
            "corpus_mean_hybrid_score": float(aggregate.mean_hybrid_score),
            "corpus_std_hybrid_score": float(aggregate.std_hybrid_score),
            "corpus_ci95_hybrid_score": float(aggregate.ci95_hybrid_score),
            "corpus_exact_match_consistency_rate": float(aggregate.exact_match_consistency_rate),
            "corpus_parse_error_rate": float(aggregate.parse_error_rate),
            "corpus_latency_mean": float(aggregate.latency_mean),
            "corpus_latency_std": float(aggregate.latency_std),
            "corpus_cost_mean": float(aggregate.cost_mean),
            "corpus_cost_std": float(aggregate.cost_std),
            "corpus_total_failures": float(total_failures),
            "corpus_failure_rate": float(total_failures / aggregate.run_count) if aggregate.run_count else 0.0,
        }

        cleaned: Dict[str, float] = {
            key: float(value)
            for key, value in metrics.items()
            if not (isinstance(value, float) and (math.isnan(value) or math.isinf(value)))
        }
        self._mlflow.log_metrics(cleaned)

    def log_artifacts(self, artifact_paths: Iterable[Path]) -> None:
        if not self._active or self._mlflow is None:
            return

        for artifact_path in artifact_paths:
            if artifact_path.exists():
                self._mlflow.log_artifact(str(artifact_path))
