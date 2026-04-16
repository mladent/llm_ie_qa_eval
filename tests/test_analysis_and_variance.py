from __future__ import annotations

from evaluation.analysis_questions import _five_number, _pearson
from evaluation.run_record import CanonicalRunRecord
from evaluation.variance_analysis import compute_field_level_overlap


def _record(parsed_output_json, parse_status="success") -> CanonicalRunRecord:
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
        parsed_output_json=parsed_output_json,
        parse_status=parse_status,
        error_message=None,
        latency_ms=1.0,
        input_tokens=1,
        output_tokens=1,
        estimated_cost=0.0,
        precision=1.0,
        recall=1.0,
        f1=1.0,
        exact_match_with_gold=True,
    )


def test_analysis_private_helpers_edge_cases() -> None:
    assert _five_number([]) == {"min": 0.0, "q1": 0.0, "median": 0.0, "q3": 0.0, "max": 0.0}
    assert _pearson([1.0], [2.0]) is None
    assert _pearson([1.0, 1.0], [2.0, 3.0]) is None


def test_variance_field_overlap_single_successful_run() -> None:
    rows = [_record({"methods": ["A"], "tasks": ["T"]})]
    assert compute_field_level_overlap(rows) == {"methods": 1.0, "tasks": 1.0}
