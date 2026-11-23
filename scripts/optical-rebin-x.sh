#!/usr/bin/env bash
# Run Matt's optical analysis with X rebinning at the 2D fit only.
set -uo pipefail

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <unzipped_dataset_dir> <new_results_dir>" >&2
  exit 2
fi

repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
dataset=$1
output=$2
converter=${TPX3DUMP:-"$repo/blackbox/tpx3dump"}

[[ -d "$dataset/optical" ]] || { echo "Missing $dataset/optical" >&2; exit 1; }
[[ -x "$converter" ]] || { echo "Missing executable $converter" >&2; exit 1; }

shopt -s nullglob
runs=("$dataset"/optical/*/)
(( ${#runs[@]} > 0 )) || { echo "No optical run directories in $dataset" >&2; exit 1; }

mkdir -p -- "$(dirname -- "$output")" || exit 1
mkdir -- "$output" || { echo "Use a new results directory" >&2; exit 1; }
optical="$output/optical"
mkdir -p -- "$optical/results" "$output/logs/optical" || exit 1

status=0
for input in "${runs[@]}"; do
  run=$(basename -- "$input")
  [[ "$run" == results ]] && continue
  dest="$optical/$run"
  log="$output/logs/optical/$run.log"
  echo "Processing $run (log: $log)"

  if ! (
    mkdir -- "$dest" || exit 1
    cp -- "$input/settings.csv" "$dest/settings.csv" || exit 1
    "$converter" -i "$input/rawdata_000000.tpx3" -o "$dest/output.hdf5" || exit 1
    python3 "$repo/blackbox/optical-analysis-rebin-x.py" "$optical" "$run" output.hdf5 || exit 1
    test -s "$dest/integral.csv"
  ) >"$log" 2>&1; then
    echo "$run failed (see $log)" >&2
    status=1
  fi
done

echo "Results: $output"
exit "$status"
