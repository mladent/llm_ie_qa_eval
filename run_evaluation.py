import json
from pathlib import Path
from uuid import uuid4

from extraction.extractor import run_extraction
from evaluation.metrics import compute_metrics
from evaluation.run_record import CanonicalRunRecord, utc_now_iso


def load_prompt():

    with open("prompts/extraction_prompt.txt") as f:
        return f.read()


def main(provider="openai"):

    dataset = json.load(open("data/dataset.json"))
    prompt_template = load_prompt()
    experiment_id = f"exp-{uuid4().hex[:12]}"
    dataset_id = str(Path("data/dataset.json").resolve())
    prompt_id = str(Path("prompts/extraction_prompt.txt").resolve())

    run_records = []

    for doc in dataset:

        prompt = prompt_template.replace("{text}", doc["text"])

        extraction_result = run_extraction(provider, prompt)
        prediction = extraction_result["parsed_output_json"]

        metrics = compute_metrics(prediction, doc["gold"])
        exact_match_with_gold = prediction == doc["gold"]

        run_record = CanonicalRunRecord(
            experiment_id=experiment_id,
            document_id=str(doc["id"]),
            provider=extraction_result["provider"],
            model=extraction_result["model"],
            prompt_id=prompt_id,
            dataset_id=dataset_id,
            # Single-pass baseline: repeated-run orchestration will increment this later.
            run_index=0,
            timestamp=utc_now_iso(),
            raw_response_text=extraction_result["raw_response_text"],
            parsed_output_json=prediction,
            parse_status=extraction_result["parse_status"],
            error_message=extraction_result["error_message"],
            latency_ms=extraction_result["latency_ms"],
            input_tokens=extraction_result["input_tokens"],
            output_tokens=extraction_result["output_tokens"],
            estimated_cost=extraction_result["estimated_cost"],
            precision=metrics["precision"],
            recall=metrics["recall"],
            f1=metrics["f1"],
            exact_match_with_gold=exact_match_with_gold,
        )

        run_records.append(run_record)

        print("\nDOCUMENT:", doc["id"])
        print("Prediction:", run_record.parsed_output_json)
        print("Gold:", doc["gold"])
        print("Parse status:", run_record.parse_status)
        print("Metrics:", {
            "precision": run_record.precision,
            "recall": run_record.recall,
            "f1": run_record.f1,
            "exact_match_with_gold": run_record.exact_match_with_gold,
        })

    avg_precision = sum(r.precision for r in run_records) / len(run_records)
    avg_recall = sum(r.recall for r in run_records) / len(run_records)
    avg_f1 = sum(r.f1 for r in run_records) / len(run_records)

    print("\n=== FINAL RESULTS ===")
    print("Experiment ID:", experiment_id)
    print("Precision:", avg_precision)
    print("Recall:", avg_recall)
    print("F1:", avg_f1)


if __name__ == "__main__":
    main("openai")
