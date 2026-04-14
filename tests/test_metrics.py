from __future__ import annotations

import pytest

from evaluation.metrics import (
    compute_corpus_aggregate,
    compute_document_aggregate,
    compute_metrics,
    exact_json_match_rate,
    structural_validity_rate,
)
from evaluation.run_record import CanonicalRunRecord, utc_now_iso


def _record(
    *,
    document_id: str,
    run_index: int,
    parsed_output_json: dict,
    parse_status: str = "success",
    precision: float = 1.0,
    recall: float = 1.0,
    f1: float = 1.0,
    estimated_cost: float | None = 0.01,
) -> CanonicalRunRecord:
    return CanonicalRunRecord(
        experiment_id="exp-test",
        document_id=document_id,
        provider="openai",
        model="gpt-4o-mini",
        prompt_id="prompt-v1",
        dataset_id="dataset-v1",
        run_index=run_index,
        timestamp=utc_now_iso(),
        raw_response_text="{}",
        parsed_output_json=parsed_output_json,
        parse_status=parse_status,
        error_message=None,
        latency_ms=100.0,
        input_tokens=10,
        output_tokens=5,
        estimated_cost=estimated_cost,
        precision=precision,
        recall=recall,
        f1=f1,
        exact_match_with_gold=(f1 == 1.0),
    )


def test_compute_metrics_basic_overlap() -> None:
    pred = {"methods": ["A", "B"], "tasks": ["T1"], "datasets": []}
    gold = {"methods": ["A"], "tasks": ["T1", "T2"], "datasets": []}

    metrics = compute_metrics(pred, gold)

    assert metrics["precision"] == 2 / 3
    assert metrics["recall"] == 2 / 3
    assert metrics["f1"] == 2 / 3


def test_document_aggregate_parse_error_and_five_number() -> None:
    records = [
        _record(document_id="doc1", run_index=0, parsed_output_json={"methods": ["A"], "tasks": ["T"], "datasets": []}, f1=1.0),
        _record(document_id="doc1", run_index=1, parsed_output_json={"methods": ["A"], "tasks": ["T"], "datasets": []}, f1=0.5, precision=0.5, recall=0.5),
        _record(document_id="doc1", run_index=2, parsed_output_json={}, parse_status="parse_error", f1=0.0, precision=0.0, recall=0.0),
    ]

    agg = compute_document_aggregate(records)

    assert agg.run_count == 3
    assert agg.parse_error_rate == pytest.approx(1 / 3)
    assert agg.f1_five_number.min == 0.5
    assert agg.f1_five_number.max == 1.0


def test_consistency_metrics() -> None:
    same = {"methods": ["A"], "tasks": ["T"], "datasets": []}
    diff = {"methods": ["B"], "tasks": ["T"], "datasets": []}
    records = [
        _record(document_id="doc1", run_index=0, parsed_output_json=same),
        _record(document_id="doc1", run_index=1, parsed_output_json=same),
        _record(document_id="doc1", run_index=2, parsed_output_json=diff),
    ]

    assert exact_json_match_rate(records) == 2 / 3
    assert structural_validity_rate(records) == 1.0


def test_corpus_aggregate_shape() -> None:
    records = [
        _record(document_id="doc1", run_index=0, parsed_output_json={"methods": ["A"], "tasks": ["T"], "datasets": []}, f1=1.0),
        _record(document_id="doc1", run_index=1, parsed_output_json={}, parse_status="parse_error", f1=0.0, precision=0.0, recall=0.0),
        _record(document_id="doc2", run_index=0, parsed_output_json={"methods": ["B"], "tasks": ["X"], "datasets": []}, f1=0.2, precision=0.2, recall=0.2),
    ]

    agg = compute_corpus_aggregate(
        records,
        experiment_id="exp-test",
        provider="openai",
        model="gpt-4o-mini",
        prompt_id="prompt-v1",
        dataset_id="dataset-v1",
        timestamp=utc_now_iso(),
    )

    assert agg.document_count == 2
    assert agg.run_count == 3
    assert 0.0 <= agg.exact_match_consistency_rate <= 1.0
