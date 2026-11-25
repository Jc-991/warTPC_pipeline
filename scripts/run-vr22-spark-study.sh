#!/usr/bin/env bash
# Run the paired optical spark study in a Hammer compute session.
set -uo pipefail

repo=$(cd -- "$(dirname -- "$0")/.." && pwd) || exit 1
if [[ "${1:-}" == --help || "${1:-}" == -h ]]; then
  echo "Usage: $0 [vr22-06 ... vr22-13]"
  echo "With no arguments, analyse vr22-06 and vr22-07."
  exit 0
fi
if [[ $# -eq 0 ]]; then
  set -- vr22-06 vr22-07
fi
for run in "$@"; do
  if [[ ! "$run" =~ ^vr22-(0[6-9]|1[0-3])$ ]]; then
    echo "Unknown study run: $run. Use vr22-06 through vr22-13." >&2
    exit 2
  fi
done
runs=$(IFS=,; printf '%s' "$*")

dataset=${WARTPC_VR22_DATASET:-"$HOME/warTPC/data/voltage-run-22-11-2026"}
results=${WARTPC_VR22_RESULTS:-"$HOME/warTPC/results"}
settings=${BLACKBOX_SETUP:-"$repo/blackbox/setup_blackbox.sh"}
if [[ ! -d "$dataset/optical" ]]; then
  echo "Missing optical dataset: $dataset/optical" >&2
  exit 1
fi
source "$settings" || exit 1
mkdir -p -- "$results" || exit 1
base=$(mktemp -d "$results/vr22-spark-study.XXXXXX") || exit 1
work=$(mktemp -d "$base/.work.XXXXXX") || exit 1
trap 'rm -rf -- "$work"' EXIT
name="$(basename -- "$dataset")_results"
printf 'Study results: %s\n' "$base"

status=0
WARTPC_SPARK_MODE=off WARTPC_REBIN=1 WARTPC_SIGNAL_PLOTS=0 \
  bash "$repo/scripts/optical-analysis.sh" "$dataset" "$work/before" \
  --runs "$runs" --rebin-x off || status=1
WARTPC_SPARK_MODE=remove WARTPC_REBIN=1 WARTPC_SIGNAL_PLOTS=0 \
  bash "$repo/scripts/optical-analysis.sh" "$dataset" "$work/after" \
  --runs "$runs" --rebin-x off || status=1
if [[ $status -ne 0 ]]; then
  mv -- "$work" "$base/work" || exit 1
  printf 'Analysis failed. Work files: %s/work/\n' "$base" >&2
  exit "$status"
fi

if ! python3 "$repo/scripts/report-vr22-sparks.py" \
  "$work/before/$name" "$work/after/$name" "$work/report" --runs "$@"; then
  mv -- "$work" "$base/work" || exit 1
  printf 'Report failed. Work files: %s/work/\n' "$base" >&2
  exit 1
fi

mv -- "$work/report/optical_per_run" "$base/" || exit 1
printf '\nRun summary folders: %s/optical_per_run/\n' "$base"
