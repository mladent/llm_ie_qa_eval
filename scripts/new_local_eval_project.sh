#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/new_local_eval_project.sh <project-name>

Creates a new local evaluation project under:
  .local/eval_projects/<project-name>

It copies the template from:
  .local/eval_projects/_template

Then replaces <name> placeholders in project.yaml with <project-name>.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 1 ]]; then
  echo "Error: expected exactly one argument: <project-name>" >&2
  usage >&2
  exit 1
fi

project_name="$1"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
template_dir="$repo_root/.local/eval_projects/_template"
target_dir="$repo_root/.local/eval_projects/$project_name"

if [[ ! -d "$template_dir" ]]; then
  echo "Error: template directory not found: $template_dir" >&2
  exit 1
fi

if [[ -e "$target_dir" ]]; then
  echo "Error: target already exists: $target_dir" >&2
  exit 1
fi

mkdir -p "$target_dir"
cp -R "$template_dir"/. "$target_dir"

project_yaml="$target_dir/project.yaml"
if [[ -f "$project_yaml" ]]; then
  sed -i "s|<name>|$project_name|g" "$project_yaml"
fi

echo "Created local evaluation project: $target_dir"
echo "Next steps:"
echo "  1) Add CV files to $target_dir/docs"
echo "  2) Add gold JSON files to $target_dir/gold"
echo "  3) Review $project_yaml"
echo "  4) Run: python run_evaluation.py --config .local/eval_projects/$project_name/project.yaml"
