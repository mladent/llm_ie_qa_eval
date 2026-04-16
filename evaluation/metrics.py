"""Metrics module: per-run scoring, repeated-run aggregation, and consistency metrics."""

from __future__ import annotations

import json
import math
import statistics
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from evaluation.run_record import (
    CanonicalRunRecord,
    CorpusAggregateRecord,
    DocumentAggregateRecord,
    FiveNumberSummary,
)


def compute_metrics(predicted, gold):

    tp = 0
    fp = 0
    fn = 0

    for key in gold.keys():

        gold_set = set(gold[key])
        pred_set = set(predicted.get(key, []))

        tp += len(gold_set & pred_set)
        fp += len(pred_set - gold_set)
        fn += len(gold_set - pred_set)

    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0

    if precision + recall == 0:
        f1 = 0
    else:
        f1 = 2 * precision * recall / (precision + recall)

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _five_number_summary(values: List[float]) -> FiveNumberSummary:
    if not values:
        return FiveNumberSummary(min=0.0, q1=0.0, median=0.0, q3=0.0, max=0.0)
    sv = sorted(values)
    n = len(sv)
    q1 = statistics.median(sv[: n // 2]) if n >= 2 else sv[0]
    q3 = statistics.median(sv[(n + 1) // 2 :]) if n >= 2 else sv[-1]
    return FiveNumberSummary(
        min=sv[0],
        q1=q1,
        median=statistics.median(sv),
        q3=q3,
        max=sv[-1],
    )


def _ci95(std: float, n: int) -> float:
    """95% confidence interval half-width: 1.96 * std / sqrt(n)."""
    return 1.96 * std / math.sqrt(n) if n > 1 else 0.0


def _mean_std(values: List[float]) -> Tuple[float, float]:
    if not values:
        return 0.0, 0.0
    mean = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    return mean, std


# ---------------------------------------------------------------------------
# Consistency metrics (5.3)
# ---------------------------------------------------------------------------

def structural_validity_rate(records: List[CanonicalRunRecord]) -> float:
    """Fraction of runs with parse_status == 'success'."""
    if not records:
        return 0.0
    return sum(1 for r in records if r.parse_status == "success") / len(records)


def exact_json_match_rate(records: List[CanonicalRunRecord]) -> float:
    """Fraction of successful runs producing the modal (most common) JSON output.

    Returns 1.0 when all successful runs agree, approaching 0 as diversity grows.
    """
    successful = [r for r in records if r.parse_status == "success"]
    if len(successful) < 2:
        return 1.0 if successful else 0.0
    keys = [json.dumps(r.parsed_output_json, sort_keys=True) for r in successful]
    mode_count = max(keys.count(k) for k in set(keys))
    return mode_count / len(successful)


def field_level_match_rate(records: List[CanonicalRunRecord]) -> float:
    """Average per-field agreement rate across successful repeated runs.

    For each field, computes the fraction of runs whose value set matches the
    modal value, then returns the mean across all observed fields.
    """
    successful = [r for r in records if r.parse_status == "success" and r.parsed_output_json]
    if len(successful) < 2:
        return 1.0 if successful else 0.0
    all_fields: set[str] = set()
    for r in successful:
        all_fields.update(r.parsed_output_json.keys())
    if not all_fields:
        return 1.0
    rates = []
    for field in all_fields:
        values = [frozenset(r.parsed_output_json.get(field, [])) for r in successful]
        mode_count = max(values.count(v) for v in set(values))
        rates.append(mode_count / len(successful))
    return statistics.mean(rates)


# ---------------------------------------------------------------------------
# Aggregate statistics (5.2)
# ---------------------------------------------------------------------------

def compute_document_aggregate(
    records: List[CanonicalRunRecord],
) -> DocumentAggregateRecord:
    """Compute per-document repeated-run aggregate statistics.

    Args:
        records: All run records for a single document (any parse status).

    Returns:
        DocumentAggregateRecord populated with means, std, CI95, five-number
        summaries, consistency rate, parse-error rate, latency, and cost stats.
    """
    if not records:
        raise ValueError("records must not be empty")

    first = records[0]
    n = len(records)
    successful = [r for r in records if r.parse_status == "success"]
    n_ok = len(successful)

    prec_vals = [r.precision for r in successful]
    rec_vals = [r.recall for r in successful]
    f1_vals = [r.f1 for r in successful]
    lat_vals = [r.latency_ms for r in records if r.latency_ms is not None]
    cost_vals = [r.estimated_cost for r in records if r.estimated_cost is not None]

    mean_p, std_p = _mean_std(prec_vals)
    mean_r, std_r = _mean_std(rec_vals)
    mean_f, std_f = _mean_std(f1_vals)
    lat_mean, lat_std = _mean_std(lat_vals)
    cost_mean, cost_std = _mean_std(cost_vals)

    return DocumentAggregateRecord(
        experiment_id=first.experiment_id,
        document_id=first.document_id,
        provider=first.provider,
        model=first.model,
        prompt_id=first.prompt_id,
        dataset_id=first.dataset_id,
        run_count=n,
        mean_precision=mean_p,
        std_precision=std_p,
        ci95_precision=_ci95(std_p, n_ok),
        mean_recall=mean_r,
        std_recall=std_r,
        ci95_recall=_ci95(std_r, n_ok),
        mean_f1=mean_f,
        std_f1=std_f,
        ci95_f1=_ci95(std_f, n_ok),
        exact_match_consistency_rate=exact_json_match_rate(records),
        parse_error_rate=1.0 - structural_validity_rate(records),
        latency_mean=lat_mean,
        latency_std=lat_std,
        cost_mean=cost_mean,
        cost_std=cost_std,
        precision_five_number=_five_number_summary(prec_vals),
        recall_five_number=_five_number_summary(rec_vals),
        f1_five_number=_five_number_summary(f1_vals),
    )


def compute_corpus_aggregate(
    all_records: List[CanonicalRunRecord],
    experiment_id: str,
    provider: str,
    model: str,
    prompt_id: str,
    dataset_id: str,
    timestamp: str,
) -> CorpusAggregateRecord:
    """Compute corpus-level aggregate statistics across all run records.

    Quality stats (precision/recall/F1) are pooled from successful runs only.
    The exact_match_consistency_rate is the mean per-document exact-match rate,
    so it reflects within-document stability rather than cross-document variety.
    """
    if not all_records:
        raise ValueError("all_records must not be empty")

    successful = [r for r in all_records if r.parse_status == "success"]
    n = len(all_records)
    n_ok = len(successful)

    doc_groups: Dict[str, List[CanonicalRunRecord]] = defaultdict(list)
    for r in all_records:
        doc_groups[r.document_id].append(r)

    prec_vals = [r.precision for r in successful]
    rec_vals = [r.recall for r in successful]
    f1_vals = [r.f1 for r in successful]
    lat_vals = [r.latency_ms for r in all_records if r.latency_ms is not None]
    cost_vals = [r.estimated_cost for r in all_records if r.estimated_cost is not None]

    mean_p, std_p = _mean_std(prec_vals)
    mean_r, std_r = _mean_std(rec_vals)
    mean_f, std_f = _mean_std(f1_vals)
    lat_mean, lat_std = _mean_std(lat_vals)
    cost_mean, cost_std = _mean_std(cost_vals)

    # Average per-document consistency — avoids inflating rate across docs
    per_doc_rates = [exact_json_match_rate(recs) for recs in doc_groups.values()]
    corpus_match_rate = statistics.mean(per_doc_rates) if per_doc_rates else 0.0

    return CorpusAggregateRecord(
        experiment_id=experiment_id,
        provider=provider,
        model=model,
        prompt_id=prompt_id,
        dataset_id=dataset_id,
        document_count=len(doc_groups),
        run_count=n,
        timestamp=timestamp,
        mean_precision=mean_p,
        std_precision=std_p,
        ci95_precision=_ci95(std_p, n_ok),
        mean_recall=mean_r,
        std_recall=std_r,
        ci95_recall=_ci95(std_r, n_ok),
        mean_f1=mean_f,
        std_f1=std_f,
        ci95_f1=_ci95(std_f, n_ok),
        exact_match_consistency_rate=corpus_match_rate,
        parse_error_rate=1.0 - structural_validity_rate(all_records),
        latency_mean=lat_mean,
        latency_std=lat_std,
        cost_mean=cost_mean,
        cost_std=cost_std,
        precision_five_number=_five_number_summary(prec_vals),
        recall_five_number=_five_number_summary(rec_vals),
        f1_five_number=_five_number_summary(f1_vals),
    )
