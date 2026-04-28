from __future__ import annotations

import pytest

from evaluation.dataset_validation import validate_dataset_shape


def test_validate_dataset_shape_requires_list_top_level() -> None:
    with pytest.raises(ValueError, match="top-level JSON must be a list"):
        validate_dataset_shape({"id": "doc1"})


def test_validate_dataset_shape_requires_non_empty_list() -> None:
    with pytest.raises(ValueError, match="no documents found"):
        validate_dataset_shape([])


def test_validate_dataset_shape_uses_inferred_gold_fields() -> None:
    dataset = [
        {
            "id": "doc1",
            "text": "text",
            "gold": {"field_a": ["x"], "field_b": ["y"]},
        }
    ]

    validate_dataset_shape(dataset)


def test_validate_dataset_shape_rejects_missing_id() -> None:
    dataset = [{"text": "text", "gold": {"methods": [], "tasks": [], "datasets": []}}]
    with pytest.raises(ValueError, match="missing required key 'id'"):
        validate_dataset_shape(dataset)


def test_validate_dataset_shape_rejects_non_mapping_document() -> None:
    with pytest.raises(ValueError, match="expected object"):
        validate_dataset_shape(["bad-doc"])


def test_validate_dataset_shape_rejects_missing_text_key() -> None:
    dataset = [{"id": "doc1", "gold": {"methods": [], "tasks": [], "datasets": []}}]
    with pytest.raises(ValueError, match="missing required key 'text'"):
        validate_dataset_shape(dataset)


def test_validate_dataset_shape_rejects_blank_text() -> None:
    dataset = [{"id": "doc1", "text": "   ", "gold": {"methods": [], "tasks": [], "datasets": []}}]
    with pytest.raises(ValueError, match="must be a non-empty string"):
        validate_dataset_shape(dataset)


def test_validate_dataset_shape_rejects_invalid_gold_shape() -> None:
    dataset = [{"id": "doc1", "text": "text", "gold": []}]
    with pytest.raises(ValueError, match="missing or invalid 'gold' object"):
        validate_dataset_shape(dataset)


def test_validate_dataset_shape_rejects_missing_required_gold_field() -> None:
    dataset = [{"id": "doc1", "text": "text", "gold": {"methods": [], "tasks": []}}]
    with pytest.raises(ValueError, match="missing field 'datasets'"):
        validate_dataset_shape(dataset, required_gold_fields=["methods", "tasks", "datasets"])


def test_validate_dataset_shape_rejects_non_list_gold_field() -> None:
    dataset = [{"id": "doc1", "text": "text", "gold": {"methods": "A", "tasks": [], "datasets": []}}]
    with pytest.raises(ValueError, match="field 'methods' must be a list"):
        validate_dataset_shape(dataset)


def test_validate_dataset_shape_rejects_non_string_item() -> None:
    dataset = [{"id": "doc1", "text": "text", "gold": {"methods": [1], "tasks": [], "datasets": []}}]
    with pytest.raises(ValueError, match=r"methods\[0\].*must be a string"):
        validate_dataset_shape(dataset)
