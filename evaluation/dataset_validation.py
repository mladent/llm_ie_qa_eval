from __future__ import annotations

from typing import Any, Iterable, Mapping


_REQUIRED_GOLD_FIELDS = ("methods", "tasks", "datasets")


def validate_dataset_shape(dataset: Any) -> None:
    """Fail-fast validation for dataset structure used by the evaluator.

    Expected structure:
      - top-level list of document objects
      - each document has id, text, and gold
      - gold contains methods/tasks/datasets as list[str]
    """

    if not isinstance(dataset, list):
        raise ValueError(
            "Invalid dataset: top-level JSON must be a list of documents. "
            "Check data/dataset.json format."
        )

    if not dataset:
        raise ValueError(
            "Invalid dataset: no documents found. Provide at least one document entry."
        )

    for index, doc in enumerate(dataset):
        _validate_document(doc, index)


def _validate_document(doc: Any, index: int) -> None:
    if not isinstance(doc, Mapping):
        raise ValueError(
            f"Invalid dataset document at index {index}: expected object, got {type(doc).__name__}."
        )

    if "id" not in doc:
        raise ValueError(f"Invalid dataset document at index {index}: missing required key 'id'.")

    if "text" not in doc:
        raise ValueError(
            f"Invalid dataset document '{doc.get('id', index)}': missing required key 'text'."
        )

    if not isinstance(doc["text"], str) or not doc["text"].strip():
        raise ValueError(
            f"Invalid dataset document '{doc['id']}': 'text' must be a non-empty string."
        )

    if "gold" not in doc or not isinstance(doc["gold"], Mapping):
        raise ValueError(
            f"Invalid dataset document '{doc['id']}': missing or invalid 'gold' object."
        )

    _validate_gold_fields(doc["id"], doc["gold"], _REQUIRED_GOLD_FIELDS)


def _validate_gold_fields(doc_id: Any, gold: Mapping[str, Any], required_fields: Iterable[str]) -> None:
    for field in required_fields:
        if field not in gold:
            raise ValueError(
                f"Invalid gold annotation for document '{doc_id}': missing field '{field}'."
            )
        value = gold[field]
        if not isinstance(value, list):
            raise ValueError(
                f"Invalid gold annotation for document '{doc_id}': field '{field}' must be a list."
            )
        for i, item in enumerate(value):
            if not isinstance(item, str):
                raise ValueError(
                    f"Invalid gold annotation for document '{doc_id}': "
                    f"field '{field}[{i}]' must be a string."
                )
