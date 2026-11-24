#!/usr/bin/env bash
# Collect all saved optical run counts into the dataset results directory.
set -euo pipefail

results=$1
table=$(mktemp "$results/.spark_counts.XXXXXX")
trap 'rm -f -- "$table"' EXIT
shopt -s nullglob
{
  printf 'run,spark_count\n'
  for dir in "$results"/optical/*/; do
    run=$(basename -- "$dir")
    [[ "$run" != results ]] || continue
    count=""
    report="$dir/diagnostics/spark_status.txt"
    if [[ -r "$report" ]]; then
      count=$(awk '/^Spark count: [0-9]+$/ {print $3; exit}' "$report")
    fi
    printf '"%s",%s\n' "${run//\"/\"\"}" "$count"
  done
} > "$table"
mv -f -- "$table" "$results/spark_counts.csv"
