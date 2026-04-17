from __future__ import annotations

import math
import statistics
from collections import defaultdict
from typing import Any, Dict, Iterable, List

from evaluation.run_record import CanonicalRunRecord, DocumentAggregateRecord
from evaluation.variance_analysis import (
    compute_field_level_overlap,
    per_document_instability_summary,
)


def _five_number(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"min": 0.0, "q1": 0.0, "median": 0.0, "q3": 0.0, "max": 0.0}
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    q1 = statistics.median(sorted_vals[: n // 2]) if n >= 2 else sorted_vals[0]
    q3 = statistics.median(sorted_vals[(n + 1) // 2 :]) if n >= 2 else sorted_vals[-1]
    return {
        "min": sorted_vals[0],
        "q1": q1,
        "median": statistics.median(sorted_vals),
        "q3": q3,
        "max": sorted_vals[-1],
    }


def _pearson(x: List[float], y: List[float]) -> float | None:
    if len(x) < 2 or len(y) < 2 or len(x) != len(y):
        return None
    mean_x = statistics.mean(x)
    mean_y = statistics.mean(y)
    centered = [(a - mean_x, b - mean_y) for a, b in zip(x, y)]
    denom_x = math.sqrt(sum(a * a for a, _ in centered))
    denom_y = math.sqrt(sum(b * b for _, b in centered))
    if denom_x == 0.0 or denom_y == 0.0:
        return None
    num = sum(a * b for a, b in centered)
    return num / (denom_x * denom_y)


def build_phase8_analysis(
    run_records: List[CanonicalRunRecord],
    document_aggregates: Iterable[DocumentAggregateRecord],
) -> Dict[str, Any]:
    """Build analysis outputs that answer Phase 8 corpus and within-document questions."""

    doc_aggregates = list(document_aggregates)
    records_by_doc: Dict[str, List[CanonicalRunRecord]] = defaultdict(list)
    for record in run_records:
        records_by_doc[record.document_id].append(record)

    instability_rows = per_document_instability_summary(records_by_doc)
    instability_by_doc = {row["document_id"]: row for row in instability_rows}

    run_counts_by_doc = {doc_id: len(records) for doc_id, records in records_by_doc.items()}
    provider_fail_rate_by_doc = {
        doc_id: (
            sum(1 for r in records if r.parse_status == "provider_error") / len(records)
            if records
            else 0.0
        )
        for doc_id, records in records_by_doc.items()
    }

    score_variation_rows: List[Dict[str, Any]] = []
    for doc_id, records in records_by_doc.items():
        successful_f1 = [r.f1 for r in records if r.parse_status == "success"]
        hybrid_scores = [r.hybrid_total_score for r in records]
        unique_scores = len({round(v, 12) for v in successful_f1})
        unique_hybrid = len({round(v, 12) for v in hybrid_scores})
        score_variation_rows.append(
            {
                "document_id": doc_id,
                "successful_run_count": len(successful_f1),
                "score_changes_while_structurally_valid": unique_scores > 1,
                "unique_successful_f1_count": unique_scores,
                "hybrid_score_changes": unique_hybrid > 1,
                "unique_hybrid_score_count": unique_hybrid,
            }
        )

    score_variation_rate = (
        sum(1 for row in score_variation_rows if row["score_changes_while_structurally_valid"])
        / len(score_variation_rows)
        if score_variation_rows
        else 0.0
    )

    field_stats: Dict[str, List[float]] = defaultdict(list)
    for records in records_by_doc.values():
        per_field = compute_field_level_overlap(records)
        for field, overlap in per_field.items():
            field_stats[field].append(overlap)

    least_stable_fields = sorted(
        [
            {
                "field": field,
                "mean_overlap": statistics.mean(overlaps),
                "docs_observed": len(overlaps),
            }
            for field, overlaps in field_stats.items()
        ],
        key=lambda row: row["mean_overlap"],
    )

    doc_rows: List[Dict[str, Any]] = []
    for agg in doc_aggregates:
        inst = instability_by_doc.get(agg.document_id, {})
        doc_rows.append(
            {
                "document_id": agg.document_id,
                "mean_f1": agg.mean_f1,
                "mean_precision": agg.mean_precision,
                "mean_recall": agg.mean_recall,
                "exact_match_consistency_rate": agg.exact_match_consistency_rate,
                "parse_error_rate": agg.parse_error_rate,
                "latency_mean": agg.latency_mean,
                "cost_mean": agg.cost_mean,
                "mean_hybrid_score": agg.mean_hybrid_score,
                "std_hybrid_score": agg.std_hybrid_score,
                "run_count": run_counts_by_doc.get(agg.document_id, agg.run_count),
                "provider_failure_rate": provider_fail_rate_by_doc.get(agg.document_id, 0.0),
                "exact_match_stability": inst.get("exact_match_stability", 0.0),
                "field_instability": inst.get("field_instability", 0.0),
                "structural_validity_rate": inst.get("structural_validity_rate", 0.0),
                "instability_score": 1.0 - inst.get("exact_match_stability", 0.0),
                "hybrid_score_mean": inst.get("hybrid_score_mean", 0.0),
                "hybrid_score_std": inst.get("hybrid_score_std", 0.0),
            }
        )

    sorted_low_quality = sorted(doc_rows, key=lambda row: row["mean_f1"])
    sorted_unstable = sorted(doc_rows, key=lambda row: row["instability_score"], reverse=True)

    quality_values = [row["mean_f1"] for row in doc_rows]
    quality_spread = {
        "five_number": _five_number(quality_values),
        "std": statistics.stdev(quality_values) if len(quality_values) > 1 else 0.0,
        "range": (max(quality_values) - min(quality_values)) if quality_values else 0.0,
    }

    instability_vals = [row["instability_score"] for row in doc_rows]
    latency_vals = [row["latency_mean"] for row in doc_rows]
    cost_vals = [row["cost_mean"] for row in doc_rows]
    provider_failure_vals = [row["provider_failure_rate"] for row in doc_rows]

    correlations = {
        "instability_vs_latency_mean": _pearson(instability_vals, latency_vals),
        "instability_vs_cost_mean": _pearson(instability_vals, cost_vals),
        "instability_vs_provider_failure_rate": _pearson(instability_vals, provider_failure_vals),
        "instability_vs_hybrid_score_mean": _pearson(
            instability_vals,
            [row["hybrid_score_mean"] for row in doc_rows],
        ),
    }

    hybrid_component_trends = [
        {
            "document_id": row["document_id"],
            "mean_hybrid_score": row["mean_hybrid_score"],
            "std_hybrid_score": row["std_hybrid_score"],
            "hybrid_score_mean": row["hybrid_score_mean"],
            "hybrid_score_std": row["hybrid_score_std"],
            "provider_failure_rate": row["provider_failure_rate"],
        }
        for row in doc_rows
    ]

    hybrid_path_breakdown = [
        {
            "path": f"$.{row['field']}",
            "mean_overlap": row["mean_overlap"],
            "mean_instability": 1.0 - row["mean_overlap"],
            "docs_observed": row["docs_observed"],
        }
        for row in least_stable_fields
    ]

    return {
        "corpus_questions": {
            "lowest_mean_quality_documents": sorted_low_quality[:10],
            "most_unstable_documents": sorted_unstable[:10],
            "quality_spread_across_corpus": quality_spread,
            "quality_stability_tradeoff_table": sorted(
                doc_rows,
                key=lambda row: (row["mean_f1"], -row["instability_score"]),
                reverse=True,
            ),
            "quality_cost_tradeoff_table": sorted(
                doc_rows,
                key=lambda row: (row["mean_f1"], -row["cost_mean"]),
                reverse=True,
            ),
        },
        "within_document_questions": {
            "output_change_rate_by_document": [
                {
                    "document_id": row["document_id"],
                    "output_change_rate": row["instability_score"],
                    "exact_match_stability": row["exact_match_stability"],
                }
                for row in sorted_unstable
            ],
            "score_variation_while_structurally_valid": {
                "documents": sorted(score_variation_rows, key=lambda row: row["document_id"]),
                "corpus_rate": score_variation_rate,
            },
            "least_stable_fields": least_stable_fields,
            "instability_correlations": correlations,
        },
        "tables": {
            "document_analysis": doc_rows,
            "field_stability": least_stable_fields,
            "score_variation": sorted(score_variation_rows, key=lambda row: row["document_id"]),
            "hybrid_component_trends": sorted(
                hybrid_component_trends,
                key=lambda row: row["document_id"],
            ),
            "hybrid_path_breakdown": hybrid_path_breakdown,
        },
    }
