from __future__ import annotations

import math
import sys
import builtins
from pathlib import Path
from types import SimpleNamespace

from evaluation.run_record import CanonicalRunRecord, CorpusAggregateRecord, DocumentAggregateRecord, FiveNumberSummary
from mlflow_utils import MLflowTracker


class FakeMLflow:
    def __init__(self):
        self.tracking_uri = None
        self.experiment = None
        self.run_name = None
        self.ended = False
        self.tags = None
        self.logged_params = []
        self.logged_metrics = []
        self.logged_artifacts = []

    def set_tracking_uri(self, uri):
        self.tracking_uri = uri

    def set_experiment(self, name):
        self.experiment = name

    def start_run(self, run_name):
        self.run_name = run_name
        return SimpleNamespace(info=SimpleNamespace(run_id="run-123"))

    def end_run(self):
        self.ended = True

    def set_tags(self, tags):
        self.tags = tags

    def log_param(self, key, value):
        self.logged_params.append((key, value))

    def log_metrics(self, metrics, step=None):
        self.logged_metrics.append((metrics, step))

    def log_artifact(self, path):
        self.logged_artifacts.append(path)


def _record() -> CanonicalRunRecord:
    return CanonicalRunRecord(
        experiment_id="exp",
        document_id="doc1",
        provider="openai",
        model="gpt-4o-mini",
        prompt_id="p1",
        dataset_id="d1",
        run_index=0,
        timestamp="t",
        raw_response_text="{}",
        parsed_output_json={"methods": []},
        parse_status="success",
        error_message=None,
        latency_ms=10.0,
        input_tokens=2,
        output_tokens=3,
        estimated_cost=0.1,
        precision=0.5,
        recall=0.5,
        f1=0.5,
        exact_match_with_gold=False,
    )


def _five() -> FiveNumberSummary:
    return FiveNumberSummary(min=0.1, q1=0.2, median=0.3, q3=0.4, max=0.5)


def _doc_agg() -> DocumentAggregateRecord:
    return DocumentAggregateRecord(
        experiment_id="exp",
        document_id="doc1",
        provider="openai",
        model="gpt-4o-mini",
        prompt_id="p1",
        dataset_id="d1",
        run_count=2,
        mean_precision=0.5,
        std_precision=0.1,
        ci95_precision=0.1,
        mean_recall=0.5,
        std_recall=0.1,
        ci95_recall=0.1,
        mean_f1=0.5,
        std_f1=0.1,
        ci95_f1=0.1,
        exact_match_consistency_rate=0.5,
        parse_error_rate=0.0,
        latency_mean=11.0,
        latency_std=1.0,
        cost_mean=0.2,
        cost_std=0.0,
        precision_five_number=_five(),
        recall_five_number=_five(),
        f1_five_number=_five(),
    )


def _corpus_agg() -> CorpusAggregateRecord:
    return CorpusAggregateRecord(
        experiment_id="exp",
        provider="openai",
        model="gpt-4o-mini",
        prompt_id="p1",
        dataset_id="d1",
        document_count=1,
        run_count=0,
        timestamp="t",
        mean_precision=0.5,
        std_precision=math.nan,
        ci95_precision=0.1,
        mean_recall=0.5,
        std_recall=0.1,
        ci95_recall=0.1,
        mean_f1=0.5,
        std_f1=0.1,
        ci95_f1=0.1,
        exact_match_consistency_rate=0.5,
        parse_error_rate=0.0,
        latency_mean=11.0,
        latency_std=math.inf,
        cost_mean=0.2,
        cost_std=0.0,
        precision_five_number=_five(),
        recall_five_number=_five(),
        f1_five_number=_five(),
    )


def test_mlflow_tracker_start_disabled() -> None:
    tracker = MLflowTracker(
        enabled=False,
        tracking_uri="sqlite:///mlflow.db",
        experiment_name="exp",
        run_name="run",
        tags={},
    )
    ctx = tracker.start()
    assert ctx.enabled is False
    assert ctx.run_id is None


def test_mlflow_tracker_start_and_log(monkeypatch, tmp_path: Path) -> None:
    fake = FakeMLflow()
    monkeypatch.setitem(sys.modules, "mlflow", fake)

    tracker = MLflowTracker(
        enabled=True,
        tracking_uri="sqlite:///mlflow.db",
        experiment_name="exp",
        run_name="run",
        tags={"k": "v"},
    )

    ctx = tracker.start()
    assert ctx.enabled is True
    assert ctx.run_id == "run-123"

    tracker.log_global_params({"a": 1, "b": None})
    tracker.log_run_record_metrics(_record(), step=2)
    tracker.log_document_aggregates([_doc_agg()])
    tracker.log_corpus_aggregate(_corpus_agg(), total_failures=1)

    artifact = tmp_path / "a.json"
    artifact.write_text("{}", encoding="utf-8")
    missing = tmp_path / "missing.json"
    tracker.log_artifacts([artifact, missing])

    tracker.end()

    assert fake.tracking_uri == "sqlite:///mlflow.db"
    assert fake.experiment == "exp"
    assert fake.tags == {"k": "v"}
    assert ("a", 1) in fake.logged_params
    assert fake.ended is True
    assert str(artifact) in fake.logged_artifacts
    assert str(missing) not in fake.logged_artifacts

    corpus_metrics = fake.logged_metrics[-1][0]
    assert "corpus_std_precision" not in corpus_metrics
    assert "corpus_latency_std" not in corpus_metrics


def test_mlflow_tracker_start_handles_import_error(monkeypatch) -> None:
    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "mlflow":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    tracker = MLflowTracker(
        enabled=True,
        tracking_uri="sqlite:///mlflow.db",
        experiment_name="exp",
        run_name="run",
        tags={},
    )

    ctx = tracker.start()
    assert ctx.enabled is False
    assert tracker.enabled is False


def test_mlflow_tracker_noop_when_not_active(tmp_path: Path) -> None:
    tracker = MLflowTracker(
        enabled=False,
        tracking_uri="sqlite:///mlflow.db",
        experiment_name="exp",
        run_name="run",
        tags={},
    )
    tracker.log_global_params({"a": 1})
    tracker.log_run_record_metrics(_record(), step=0)
    tracker.log_document_aggregates([_doc_agg()])
    tracker.log_corpus_aggregate(_corpus_agg(), total_failures=0)
    tracker.log_artifacts([tmp_path / "missing.json"])
    tracker.end()
