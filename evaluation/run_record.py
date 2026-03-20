from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


ParseStatus = str


@dataclass
class CanonicalRunRecord:
    """Canonical run-level record used across the evaluation pipeline."""

    experiment_id: str
    document_id: str
    provider: str
    model: str
    prompt_id: str
    dataset_id: str
    run_index: int
    timestamp: str
    raw_response_text: str
    parsed_output_json: Dict[str, Any]
    parse_status: ParseStatus
    error_message: Optional[str]
    latency_ms: float
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    estimated_cost: Optional[float]
    precision: float
    recall: float
    f1: float
    exact_match_with_gold: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    """Return an ISO-8601 UTC timestamp for run metadata."""

    return datetime.now(timezone.utc).isoformat()


@dataclass
class FiveNumberSummary:
    """Five-number summary for a metric distribution."""

    min: float
    q1: float
    median: float
    q3: float
    max: float


@dataclass
class AggregateRecordBase:
    """Shared aggregate schema required for repeated-run summaries."""

    mean_precision: float
    std_precision: float
    ci95_precision: float
    mean_recall: float
    std_recall: float
    ci95_recall: float
    mean_f1: float
    std_f1: float
    ci95_f1: float
    exact_match_consistency_rate: float
    parse_error_rate: float
    latency_mean: float
    latency_std: float
    cost_mean: float
    cost_std: float
    precision_five_number: FiveNumberSummary
    recall_five_number: FiveNumberSummary
    f1_five_number: FiveNumberSummary

    def to_flat_dict(self) -> Dict[str, Any]:
        """Flatten nested five-number summaries for table exports."""

        data = asdict(self)
        for metric in ("precision", "recall", "f1"):
            five = data.pop(f"{metric}_five_number")
            data[f"{metric}_min"] = five["min"]
            data[f"{metric}_q1"] = five["q1"]
            data[f"{metric}_median"] = five["median"]
            data[f"{metric}_q3"] = five["q3"]
            data[f"{metric}_max"] = five["max"]
        return data


@dataclass
class DocumentAggregateRecord(AggregateRecordBase):
    """Per-document repeated-run summary record."""

    experiment_id: str
    document_id: str
    provider: str
    model: str
    prompt_id: str
    dataset_id: str
    run_count: int


@dataclass
class CorpusAggregateRecord(AggregateRecordBase):
    """Corpus-level summary record."""

    experiment_id: str
    provider: str
    model: str
    prompt_id: str
    dataset_id: str
    document_count: int
    run_count: int
    timestamp: str


@dataclass
class ProviderModelComparisonRecord(AggregateRecordBase):
    """Optional provider/model comparison summary record."""

    experiment_id: str
    provider: str
    model: str
    prompt_id: str
    dataset_id: str
    document_count: int
    run_count: int
