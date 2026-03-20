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
