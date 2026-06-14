from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass
class BusinessRunInput:
    """Normalized run-level payload consumed by business metrics."""

    run_id: int
    output: str
    scores: Dict[str, float]
    failure_modes: List[str]
    parse_status: str
    error_message: Optional[str]


@dataclass
class BusinessItemInput:
    """Per-item payload with all run outcomes and evaluator aggregates."""

    item_id: str
    runs: List[BusinessRunInput]
    evaluator_aggregates: Dict[str, float]


@dataclass
class BusinessCorpusInput:
    """Corpus-level evaluator summary required by business layer."""

    experiment_id: str
    provider: str
    model: str
    prompt_id: str
    dataset_id: str
    run_count: int
    document_count: int
    mean_f1: float
    parse_error_rate: float
    failure_rate: float


@dataclass
class BusinessContractInput:
    """Top-level business contract built from evaluator artifacts."""

    business_contract_version: str
    source_experiment_dir: str
    corpus: BusinessCorpusInput
    items: List[BusinessItemInput]

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable representation of the contract payload."""

        return asdict(self)
