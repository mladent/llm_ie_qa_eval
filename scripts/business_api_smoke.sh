#!/usr/bin/env bash
set -euo pipefail

base_url="${1:-http://127.0.0.1:8000}"
experiment_dir="${2:-outputs/experiments/exp-0837df5b02be}"
scenario="${3:-default}"

payload=$(cat <<JSON
{
  "experiment_dir": "${experiment_dir}",
  "scenario": "${scenario}",
  "write_artifacts": false
}
JSON
)

echo "POST ${base_url}/business/evaluate"
curl --silent --show-error \
  --header "Content-Type: application/json" \
  --data "${payload}" \
  "${base_url}/business/evaluate"
echo
