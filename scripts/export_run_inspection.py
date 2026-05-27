#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_text(value: Any) -> str:
    return str(value).strip().lower()


def _as_list_of_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            content = line.strip()
            if not content:
                continue
            try:
                payload = json.loads(content)
            except json.JSONDecodeError:
                payload = {
                    "document_id": "unknown",
                    "run_index": -1,
                    "parse_status": "jsonl_decode_error",
                    "error_message": f"Failed to decode JSONL line {line_no}",
                    "parsed_output_json": {},
                }
            rows.append(payload)
    return rows


def _load_schema(schema_path: Path) -> tuple[list[str], set[str]]:
    payload = json.loads(schema_path.read_text(encoding="utf-8"))
    required_fields = [str(field) for field in payload.get("required", [])]
    schema_fields = {str(field) for field in payload.get("properties", {}).keys()}
    return required_fields, schema_fields


def _find_gold_record(gold_dir: Path | None, document_id: str) -> dict[str, Any] | None:
    if gold_dir is None:
        return None

    normalized = document_id.replace("-", "_")
    candidates = sorted(gold_dir.glob(f"{normalized}*.json"))
    if not candidates:
        candidates = sorted(gold_dir.glob(f"{document_id}*.json"))
    if not candidates:
        return None

    try:
        payload = json.loads(candidates[0].read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

    return payload if isinstance(payload, dict) else None


def _token_overlap_metrics(
    prediction: dict[str, Any],
    gold: dict[str, Any],
    required_fields: list[str],
) -> dict[str, float]:
    pred_tokens: list[str] = []
    gold_tokens: list[str] = []

    for field in required_fields:
        pred_values = [_normalize_text(item) for item in _as_list_of_strings(prediction.get(field, []))]
        gold_values = [_normalize_text(item) for item in _as_list_of_strings(gold.get(field, []))]
        pred_tokens.extend([f"{field}::{value}" for value in pred_values])
        gold_tokens.extend([f"{field}::{value}" for value in gold_values])

    pred_set = set(pred_tokens)
    gold_set = set(gold_tokens)
    overlap = len(pred_set & gold_set)

    precision = overlap / len(pred_set) if pred_set else 0.0
    recall = overlap / len(gold_set) if gold_set else 0.0
    f1 = 0.0 if (precision + recall) == 0 else (2 * precision * recall) / (precision + recall)

    return {
        "gold_precision": precision,
        "gold_recall": recall,
        "gold_f1": f1,
    }


def _flatten_paths(obj: Any, prefix: str = "$") -> list[tuple[str, str]]:
    paths: list[tuple[str, str]] = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            next_prefix = f"{prefix}.{key}"
            paths.append((next_prefix, type(value).__name__))
            paths.extend(_flatten_paths(value, next_prefix))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            next_prefix = f"{prefix}[{index}]"
            paths.append((next_prefix, type(value).__name__))
            paths.extend(_flatten_paths(value, next_prefix))

    return paths


def _resolve_inputs(args: argparse.Namespace) -> tuple[Path, Path | None, Path | None]:
    if args.experiment_dir:
        experiment_dir = args.experiment_dir.resolve()
        runs_jsonl_path = (experiment_dir / "runs.jsonl").resolve()
        provenance_path = (experiment_dir / "provenance.json").resolve()
        config_snapshot_path = (experiment_dir / "config.json").resolve()
        return runs_jsonl_path, provenance_path, config_snapshot_path

    if not args.runs_jsonl:
        raise ValueError("Provide either --experiment-dir or --runs-jsonl.")

    return args.runs_jsonl.resolve(), None, None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export per-document run artifacts and inspection summaries from runs.jsonl.",
    )
    parser.add_argument("--experiment-dir", type=Path, help="Path to outputs/experiments/<exp-id>.")
    parser.add_argument("--runs-jsonl", type=Path, help="Path to runs.jsonl when experiment dir is not provided.")
    parser.add_argument("--schema-json", type=Path, required=True, help="Path to extraction schema JSON.")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output folder for inspection exports.")
    parser.add_argument(
        "--document-id",
        action="append",
        default=[],
        help="Filter to one or more document IDs. Repeat the flag for multiple values.",
    )
    parser.add_argument("--gold-dir", type=Path, help="Optional folder with gold JSON files for overlap scoring.")
    parser.add_argument(
        "--include-raw",
        action="store_true",
        help="Include raw_response_text in exported per-run files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    runs_jsonl_path, provenance_path, config_snapshot_path = _resolve_inputs(args)
    required_fields, schema_fields = _load_schema(args.schema_json.resolve())
    all_rows = _load_jsonl(runs_jsonl_path)

    wanted_doc_ids = set(args.document_id)
    selected_rows: list[dict[str, Any]] = []
    for row in all_rows:
        doc_id = str(row.get("document_id", "unknown"))
        if wanted_doc_ids and doc_id not in wanted_doc_ids:
            continue
        selected_rows.append(row)

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    selected_jsonl_path = out_dir / "selected_runs.jsonl"
    with selected_jsonl_path.open("w", encoding="utf-8") as handle:
        for row in selected_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    if provenance_path and provenance_path.exists():
        (out_dir / "provenance.json").write_text(provenance_path.read_text(encoding="utf-8"), encoding="utf-8")
    if config_snapshot_path and config_snapshot_path.exists():
        (out_dir / "config.json").write_text(config_snapshot_path.read_text(encoding="utf-8"), encoding="utf-8")

    parse_status_counts: Counter[str] = Counter()
    nested_path_counts: Counter[tuple[str, str]] = Counter()
    per_document_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    run_overview_rows: list[dict[str, Any]] = []
    field_overview_rows: list[dict[str, Any]] = []

    for row in selected_rows:
        document_id = str(row.get("document_id", "unknown"))
        run_index = int(row.get("run_index", -1))
        parse_status = str(row.get("parse_status", "unknown"))
        prediction_raw = row.get("parsed_output_json", {})
        prediction = prediction_raw if isinstance(prediction_raw, dict) else {}

        parse_status_counts[parse_status] += 1
        per_document_rows[document_id].append(row)

        predicted_fields = set(prediction.keys())
        missing_required = sorted(set(required_fields) - predicted_fields)
        extra_fields = sorted(predicted_fields - schema_fields)

        nonempty_required_count = 0
        predicted_values_total = 0

        for field in required_fields:
            values = _as_list_of_strings(prediction.get(field, []))
            predicted_values_total += len(values)
            if values:
                nonempty_required_count += 1
            field_overview_rows.append(
                {
                    "document_id": document_id,
                    "run_index": run_index,
                    "field": field,
                    "value_count": len(values),
                    "is_empty": int(len(values) == 0),
                }
            )

        for path, value_type in _flatten_paths(prediction):
            nested_path_counts[(path, value_type)] += 1

        gold = _find_gold_record(args.gold_dir.resolve(), document_id) if args.gold_dir else None
        overlap_metrics = _token_overlap_metrics(prediction, gold, required_fields) if gold else {}

        run_payload: dict[str, Any] = {
            "document_id": document_id,
            "run_index": run_index,
            "parse_status": parse_status,
            "metrics_from_run": {
                "precision": _safe_float(row.get("precision")),
                "recall": _safe_float(row.get("recall")),
                "f1": _safe_float(row.get("f1")),
                "hybrid_total_score": _safe_float(row.get("hybrid_total_score")),
            },
            "field_stats": {
                "required_field_count": len(required_fields),
                "predicted_field_count": len(predicted_fields),
                "nonempty_required_field_count": nonempty_required_count,
                "total_predicted_values": predicted_values_total,
                "missing_required_fields": missing_required,
                "extra_fields": extra_fields,
            },
            "parsed_output_json": prediction,
        }
        if overlap_metrics:
            run_payload["gold_overlap"] = overlap_metrics
        if args.include_raw:
            run_payload["raw_response_text"] = row.get("raw_response_text", "")

        doc_dir = out_dir / document_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        (doc_dir / f"run_{run_index:03d}.json").write_text(
            json.dumps(run_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        run_overview_row = {
            "document_id": document_id,
            "run_index": run_index,
            "parse_status": parse_status,
            "precision": _safe_float(row.get("precision")),
            "recall": _safe_float(row.get("recall")),
            "f1": _safe_float(row.get("f1")),
            "hybrid_total_score": _safe_float(row.get("hybrid_total_score")),
            "latency_ms": _safe_float(row.get("latency_ms")),
            "input_tokens": _safe_float(row.get("input_tokens")),
            "output_tokens": _safe_float(row.get("output_tokens")),
            "predicted_field_count": len(predicted_fields),
            "nonempty_required_field_count": nonempty_required_count,
            "total_predicted_values": predicted_values_total,
            "missing_required_count": len(missing_required),
            "extra_fields_count": len(extra_fields),
        }
        if overlap_metrics:
            run_overview_row.update(overlap_metrics)
        run_overview_rows.append(run_overview_row)

    if run_overview_rows:
        overview_csv_path = out_dir / "overview_runs.csv"
        with overview_csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(run_overview_rows[0].keys()))
            writer.writeheader()
            writer.writerows(run_overview_rows)

    if field_overview_rows:
        field_csv_path = out_dir / "overview_fields.csv"
        with field_csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(field_overview_rows[0].keys()))
            writer.writeheader()
            writer.writerows(field_overview_rows)

    nested_csv_path = out_dir / "nested_path_stats.csv"
    with nested_csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["json_path", "value_type", "count"])
        writer.writeheader()
        for (json_path, value_type), count in sorted(
            nested_path_counts.items(),
            key=lambda item: (-item[1], item[0][0]),
        ):
            writer.writerow({"json_path": json_path, "value_type": value_type, "count": count})

    per_document_summary: dict[str, dict[str, Any]] = {}
    for document_id, rows in sorted(per_document_rows.items()):
        f1_values = [_safe_float(item.get("f1")) for item in rows]
        latency_values = [_safe_float(item.get("latency_ms")) for item in rows]
        parse_counts = Counter(str(item.get("parse_status", "unknown")) for item in rows)

        per_document_summary[document_id] = {
            "run_count": len(rows),
            "f1_mean": mean(f1_values) if f1_values else 0.0,
            "f1_std": pstdev(f1_values) if len(f1_values) > 1 else 0.0,
            "f1_min": min(f1_values) if f1_values else 0.0,
            "f1_max": max(f1_values) if f1_values else 0.0,
            "latency_ms_mean": mean(latency_values) if latency_values else 0.0,
            "parse_status_counts": dict(parse_counts),
        }

    summary_payload = {
        "runs_jsonl": str(runs_jsonl_path),
        "schema_json": str(args.schema_json.resolve()),
        "selected_document_ids": sorted({str(row.get("document_id", "unknown")) for row in selected_rows}),
        "total_selected_runs": len(selected_rows),
        "parse_status_counts": dict(parse_status_counts),
        "required_field_count": len(required_fields),
        "schema_field_count": len(schema_fields),
        "per_document_summary": per_document_summary,
    }
    (out_dir / "overview_summary.json").write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Inspection artifacts written to: {out_dir}")


if __name__ == "__main__":
    main()