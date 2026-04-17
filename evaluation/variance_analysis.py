"""Within-document and corpus-level variance analysis for repeated evaluation runs.

Responsibilities (Phase 5.4):
  - compute exact-match stability across repeated runs of the same document
  - compute field-level overlap across repeated runs
  - summarize per-document instability for corpus-wide ranking
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from typing import Dict, List

from evaluation.run_record import CanonicalRunRecord


def compute_exact_match_stability(records: List[CanonicalRunRecord]) -> float:
    """Fraction of successful runs producing the modal (most common) JSON output.

    1.0 = all successful runs produced identical JSON.
    0.0 = no successful runs, or every run produced a unique JSON.

    Args:
        records: Run records for a single document (mixed parse statuses accepted).

    Returns:
        Stability score in [0, 1].
    """
    successful = [r for r in records if r.parse_status == "success"]
    if len(successful) < 2:
        return 1.0 if successful else 0.0
    keys = [json.dumps(r.parsed_output_json, sort_keys=True) for r in successful]
    mode_count = max(keys.count(k) for k in set(keys))
    return mode_count / len(successful)


def compute_field_level_overlap(
    records: List[CanonicalRunRecord],
) -> Dict[str, float]:
    """Per-field agreement rate across successful repeated runs.

    For each observed field, computes the fraction of runs whose value set
    matches the modal value for that field.

    Args:
        records: Run records for a single document.

    Returns:
        Dict mapping field name → agreement rate in [0, 1].
        Returns an empty dict when no successful runs exist.
    """
    successful = [r for r in records if r.parse_status == "success" and r.parsed_output_json]
    if not successful:
        return {}
    if len(successful) == 1:
        return {k: 1.0 for k in successful[0].parsed_output_json}

    all_fields: set[str] = set()
    for r in successful:
        all_fields.update(r.parsed_output_json.keys())

    result: Dict[str, float] = {}
    for field in all_fields:
        values = [frozenset(r.parsed_output_json.get(field, [])) for r in successful]
        mode_count = max(values.count(v) for v in set(values))
        result[field] = mode_count / len(successful)
    return result


def per_document_instability_summary(
    records_by_doc: Dict[str, List[CanonicalRunRecord]],
) -> List[Dict]:
    """Return a per-document instability summary sorted from most to least unstable.

    Each entry contains:
      - document_id
      - exact_match_stability  : fraction of runs matching the modal JSON output
      - field_instability      : mean (1 - agreement_rate) across all observed fields
      - structural_validity_rate: fraction of runs with parse_status == 'success'
      - run_count              : total runs attempted for this document

    Args:
        records_by_doc: Dict mapping document_id → list of CanonicalRunRecord.

    Returns:
        List of summary dicts, sorted ascending by exact_match_stability
        (most unstable documents first).
    """
    summaries = []
    for doc_id, records in records_by_doc.items():
        n = len(records)
        valid_count = sum(1 for r in records if r.parse_status == "success")
        validity_rate = valid_count / n if n else 0.0

        exact_stability = compute_exact_match_stability(records)
        field_overlap = compute_field_level_overlap(records)
        hybrid_scores = [r.hybrid_total_score for r in records]
        field_instability = (
            statistics.mean([1.0 - v for v in field_overlap.values()])
            if field_overlap
            else 0.0
        )

        summaries.append(
            {
                "document_id": doc_id,
                "exact_match_stability": exact_stability,
                "field_instability": field_instability,
                "structural_validity_rate": validity_rate,
                "run_count": n,
                "hybrid_score_mean": statistics.mean(hybrid_scores) if hybrid_scores else 0.0,
                "hybrid_score_std": (statistics.stdev(hybrid_scores) if len(hybrid_scores) > 1 else 0.0),
            }
        )

    return sorted(summaries, key=lambda x: x["exact_match_stability"])
