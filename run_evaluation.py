import json
from pathlib import Path

from extraction.extractor import run_extraction
from evaluation.metrics import compute_metrics


def load_prompt():

    with open("prompts/extraction_prompt.txt") as f:
        return f.read()


def main(provider="openai"):

    dataset = json.load(open("data/dataset.json"))
    prompt_template = load_prompt()

    results = []

    for doc in dataset:

        prompt = prompt_template.replace("{text}", doc["text"])

        prediction = run_extraction(provider, prompt)

        metrics = compute_metrics(prediction, doc["gold"])

        results.append(metrics)

        print("\nDOCUMENT:", doc["id"])
        print("Prediction:", prediction)
        print("Gold:", doc["gold"])
        print("Metrics:", metrics)

    avg_precision = sum(r["precision"] for r in results) / len(results)
    avg_recall = sum(r["recall"] for r in results) / len(results)
    avg_f1 = sum(r["f1"] for r in results) / len(results)

    print("\n=== FINAL RESULTS ===")
    print("Precision:", avg_precision)
    print("Recall:", avg_recall)
    print("F1:", avg_f1)


if __name__ == "__main__":
    main("openai")
