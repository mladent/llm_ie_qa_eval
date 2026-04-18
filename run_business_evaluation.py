from __future__ import annotations

import argparse
from pathlib import Path

from business.reporting import build_business_report, write_business_report_artifacts


DEFAULT_SETTINGS_PATH = "config/business_settings.yaml"
DEFAULT_THRESHOLDS_PATH = "config/business_thresholds.yaml"
DEFAULT_COSTS_PATH = "config/business_costs.yaml"
DEFAULT_CONTRACT_PATH = "config/business_contract.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build business evaluation artifacts from a completed evaluator experiment."
    )
    parser.add_argument(
        "--experiment-dir",
        required=True,
        help="Path to experiment artifacts directory containing runs.jsonl and aggregate outputs.",
    )
    parser.add_argument(
        "--scenario",
        default="default",
        help="Business scenario name used for thresholds and costs.",
    )
    parser.add_argument(
        "--settings-config",
        default=DEFAULT_SETTINGS_PATH,
        help="Path to business settings YAML.",
    )
    parser.add_argument(
        "--thresholds-config",
        default=DEFAULT_THRESHOLDS_PATH,
        help="Path to business thresholds YAML.",
    )
    parser.add_argument(
        "--costs-config",
        default=DEFAULT_COSTS_PATH,
        help="Path to business costs YAML.",
    )
    parser.add_argument(
        "--contract-config",
        default=DEFAULT_CONTRACT_PATH,
        help="Path to business contract YAML.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory. Defaults to <experiment-dir>/business.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    experiment_dir = Path(args.experiment_dir).resolve()
    if not experiment_dir.exists():
        raise ValueError(f"Experiment directory '{experiment_dir}' does not exist.")

    output_dir = Path(args.output_dir).resolve() if args.output_dir else experiment_dir / "business"

    report = build_business_report(
        experiment_dir=str(experiment_dir),
        scenario=args.scenario,
        settings_config_path=args.settings_config,
        thresholds_config_path=args.thresholds_config,
        costs_config_path=args.costs_config,
        contract_config_path=args.contract_config,
    )
    paths = write_business_report_artifacts(report_payload=report, output_dir=str(output_dir))

    print("Business evaluation artifacts written:")
    for key, value in paths.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
