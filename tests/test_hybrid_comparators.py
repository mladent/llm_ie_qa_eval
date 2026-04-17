from __future__ import annotations

import pytest

from evaluation.hybrid_comparators import (
    exact_match,
    fuzzy_lexical_match,
    key_based_array_object_match,
    set_jaccard_match,
)


def test_exact_match() -> None:
    assert exact_match({"a": ["X"]}, {"a": ["X"]}) == 1.0
    assert exact_match({"a": ["X"]}, {"a": ["Y"]}) == 0.0


def test_set_jaccard_match() -> None:
    assert set_jaccard_match(["python", "mlflow"], ["python"]) == pytest.approx(0.5)
    assert set_jaccard_match([], []) == 1.0


def test_fuzzy_lexical_match_threshold() -> None:
    assert fuzzy_lexical_match("Prompt Engineering", "prompt engineering") > 0.0
    assert fuzzy_lexical_match("abc", "xyz", min_similarity=0.9) == 0.0


def test_key_based_array_object_match_with_keys() -> None:
    predicted = [{"id": "a", "name": "Python"}, {"id": "b", "name": "MLflow"}]
    gold = [{"id": "a", "name": "Python"}, {"id": "b", "name": "Mlflow"}]

    score = key_based_array_object_match(predicted, gold, key_fields=["id"])
    assert 0.9 <= score <= 1.0


def test_key_based_array_object_match_fallback_strict_non_match() -> None:
    predicted = [{"name": "Python"}]
    gold = [{"id": "a", "name": "Python"}]

    assert (
        key_based_array_object_match(
            predicted,
            gold,
            key_fields=["id"],
            fallback_strategy="strict_non_match",
        )
        == 0.0
    )
