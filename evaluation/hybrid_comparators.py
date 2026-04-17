from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence, Tuple

from rapidfuzz import fuzz  # type: ignore[import-not-found]

from evaluation.hybrid_normalize import normalize_json_value, normalize_text


def exact_match(predicted: Any, gold: Any, **_: Any) -> float:
    """Strict equality score in [0, 1]."""

    return 1.0 if normalize_json_value(predicted) == normalize_json_value(gold) else 0.0


def set_jaccard_match(predicted: Any, gold: Any, **_: Any) -> float:
    """Jaccard similarity for scalar collections in [0, 1]."""

    pred_set = _as_normalized_set(predicted)
    gold_set = _as_normalized_set(gold)
    if not pred_set and not gold_set:
        return 1.0
    if not pred_set or not gold_set:
        return 0.0
    return len(pred_set & gold_set) / len(pred_set | gold_set)


def fuzzy_lexical_match(
    predicted: Any,
    gold: Any,
    *,
    min_similarity: float = 0.85,
    normalize_case: bool = True,
    **_: Any,
) -> float:
    """Fuzzy lexical similarity in [0, 1] with optional thresholding."""

    pred_text = _as_text(predicted, normalize_case=normalize_case)
    gold_text = _as_text(gold, normalize_case=normalize_case)
    if not pred_text and not gold_text:
        return 1.0
    if not pred_text or not gold_text:
        return 0.0
    score = fuzz.ratio(pred_text, gold_text) / 100.0
    return score if score >= min_similarity else 0.0


def key_based_array_object_match(
    predicted: Any,
    gold: Any,
    *,
    key_fields: Sequence[str] | None = None,
    fallback_strategy: str = "best_overlap",
    **kwargs: Any,
) -> float:
    """Match arrays of objects by identity keys; fallback is configurable."""

    pred_list = _as_object_list(predicted)
    gold_list = _as_object_list(gold)
    if not pred_list and not gold_list:
        return 1.0
    if not pred_list or not gold_list:
        return 0.0

    keys = tuple(key_fields or ())
    if not keys:
        return best_overlap_fallback_match(pred_list, gold_list)

    pred_keyed = _build_keyed_map(pred_list, keys)
    gold_keyed = _build_keyed_map(gold_list, keys)
    if pred_keyed is None or gold_keyed is None:
        if fallback_strategy == "best_overlap":
            return best_overlap_fallback_match(pred_list, gold_list)
        if fallback_strategy == "strict_non_match":
            return 0.0
        if fallback_strategy == "error":
            raise ValueError("Missing key fields for key-based array matching.")
        return best_overlap_fallback_match(pred_list, gold_list)

    all_keys = set(pred_keyed.keys()) | set(gold_keyed.keys())
    if not all_keys:
        return 1.0

    total = 0.0
    for item_key in all_keys:
        pred_item = pred_keyed.get(item_key)
        gold_item = gold_keyed.get(item_key)
        if pred_item is None or gold_item is None:
            continue
        total += _object_similarity(pred_item, gold_item)

    return total / len(all_keys)


def best_overlap_fallback_match(predicted: Any, gold: Any, **_: Any) -> float:
    """Greedy best-overlap matching for arrays of objects."""

    pred_list = _as_object_list(predicted)
    gold_list = _as_object_list(gold)
    if not pred_list and not gold_list:
        return 1.0
    if not pred_list or not gold_list:
        return 0.0

    remaining = list(pred_list)
    scores: List[float] = []
    for gold_item in gold_list:
        if not remaining:
            scores.append(0.0)
            continue
        best_idx, best_score = max(
            enumerate(remaining),
            key=lambda pair: _object_similarity(pair[1], gold_item),
        )
        scores.append(_object_similarity(remaining[best_idx], gold_item))
        remaining.pop(best_idx)

    if len(pred_list) > len(gold_list):
        scores.extend([0.0] * (len(pred_list) - len(gold_list)))

    return sum(scores) / max(len(pred_list), len(gold_list))


def _as_normalized_set(value: Any) -> set[Any]:
    if isinstance(value, list):
        return {normalize_json_value(v) if not isinstance(v, (dict, list)) else str(normalize_json_value(v)) for v in value}
    if value is None:
        return set()
    return {normalize_json_value(value)}


def _as_text(value: Any, *, normalize_case: bool) -> str:
    if isinstance(value, list):
        text = " | ".join(str(v) for v in value)
    else:
        text = "" if value is None else str(value)
    return normalize_text(text, casefold=normalize_case)


def _as_object_list(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _build_keyed_map(items: Iterable[Dict[str, Any]], keys: Sequence[str]) -> Dict[Tuple[Any, ...], Dict[str, Any]] | None:
    keyed: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    for item in items:
        key_tuple = []
        for key in keys:
            if key not in item:
                return None
            key_tuple.append(normalize_json_value(item[key]))
        keyed[tuple(key_tuple)] = item
    return keyed


def _object_similarity(left: Dict[str, Any], right: Dict[str, Any]) -> float:
    all_keys = set(left.keys()) | set(right.keys())
    if not all_keys:
        return 1.0
    matched = 0.0
    for key in all_keys:
        lv = left.get(key)
        rv = right.get(key)
        if isinstance(lv, str) or isinstance(rv, str):
            matched += fuzz.ratio(str(lv or ""), str(rv or "")) / 100.0
        else:
            matched += 1.0 if normalize_json_value(lv) == normalize_json_value(rv) else 0.0
    return matched / len(all_keys)
