from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class PathScoreDetail:
    """One rubric rule score for explainable hybrid scoring outputs."""

    path: str
    comparator: str
    raw_score: float
    weight: float
    weighted_score: float
    notes: str = ""


@dataclass
class SchemaScoreDetail:
    """Schema validation component output with weighted score and diagnostics."""

    score: float
    is_valid: bool
    required_error_count: int
    type_error_count: int
    enum_error_count: int
    additional_properties_error_count: int
    unknown_field_penalty: float
    errors: List[str] = field(default_factory=list)


@dataclass
class HybridScoreResult:
    """Final hybrid score and component-level breakdown."""

    total_score: float
    schema_score: float
    value_score: float
    unknown_field_penalty: float
    rule_coverage: float
    path_scores: List[PathScoreDetail]
    schema_detail: SchemaScoreDetail

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
