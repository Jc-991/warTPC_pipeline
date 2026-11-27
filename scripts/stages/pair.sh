#!/usr/bin/env bash
# Stage 4: before/after pairs for each run, then the final plot IDs.
#
#   pair.sh -r <results_dir> [--runs LIST]
#
# Needs both plot folders from plot.sh:
#   <results_dir>/before/plots/   (fit.sh --spark off, plot.sh --from before)
#   <results_dir>/plots/          (fit.sh --spark remove, plot.sh)
# Writes the pairs to <results_dir>/paired/ (kept for checking), then replaces
# <results_dir>/plots/optical_per_run/ with them: per run nine PNGs,
# run_summary.txt and run_summary_readable.txt. If some pairs are incomplete,
# the available before/after plots are added to the after-only export instead.
# Finally the plots get their IDs (organise-optical-plots.py).

set -uo pipefail
source "$(dirname -- "$0")/common.sh"

usage() { sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; }

results="" RUN_SELECTION=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    -r|--results) [[ $# -ge 2 ]] || die "$1 needs a value"; results="$2"; shift 2 ;;
    --runs) [[ $# -ge 2 ]] || die "--runs needs a list"; RUN_SELECTION="$2"; shift 2 ;;
    *) usage >&2; die "unknown argument: $1" ;;
  esac
done
[[ -n "$results" ]] || { usage >&2; exit 2; }
[[ -d "$results" ]] || die "$results not found"
results=$(cd "$results" && pwd)
before="$results/before"
[[ -d "$before/plots" ]] || die "$before/plots not found; run fit.sh --spark off and plot.sh --from before"
[[ -d "$results/plots" ]] || die "$results/plots not found; run fit.sh --spark remove and plot.sh"

available=()
while IFS= read -r r; do available+=("$r"); done < <(list_run_dirs "$results/optical")
select_runs "${available[@]+"${available[@]}"}"
(( ${#SELECTED[@]} > 0 )) || die "no runs in $results/optical"
load_environment

paired_root="$results/paired"
rm -rf -- "$paired_root"
echo "# pair: ${#SELECTED[@]} runs -> $paired_root"
status=0
"$PYTHON" "$REPO/scripts/report-vr22-sparks.py" "$before" "$results" "$paired_root" \
  --runs "${SELECTED[@]}" || status=$?

export_dir="$results/plots/optical_per_run"
paired="$paired_root/optical_per_run"
if [[ $status -eq 0 ]]; then
  rm -rf -- "$export_dir" && cp -R -- "$paired" "$export_dir" || die "cannot publish the paired plots"
  echo "# pair: complete -> $export_dir"
elif [[ -f "$paired_root/run_summary.csv" ]]; then
  # Incomplete pairs: add what exists to the after-only export, replacing the
  # unsuffixed after plots with their _after copies.
  for run in "${SELECTED[@]}"; do
    [[ -d "$export_dir/$run" ]] || continue
    for plot in "$paired/$run/"*_before.png "$paired/$run/"*_after.png \
                "$paired/$run/"projection_variations_{before,after}.csv; do
      [[ -f "$plot" ]] || continue
      cp -- "$plot" "$export_dir/$run/" || die "cannot publish $plot"
      name=${plot##*/}
      case $name in
        x_projection_signal_after.png|y_projection_signal_after.png|combined_integral_distribution_after.png)
          rm -f -- "$export_dir/$run/${name%_after.png}.png" ;;
        projection_variations_after.csv)
          rm -f -- "$export_dir/$run/projection_variations.csv" ;;
      esac
    done
    for plot in "$paired/$run"_*_fit_distribution_{before,after}.png; do
      [[ -f "$plot" ]] || continue
      cp -- "$plot" "$export_dir/" || die "cannot publish $plot"
      name=${plot##*/}
      [[ $name == *_after.png ]] && rm -f -- "$export_dir/${name%_after.png}.png"
    done
  done
  echo "# pair: INCOMPLETE, available pairs added to $export_dir (issues in $paired_root/run_summary.csv)"
else
  echo "# pair: FAILED, nothing published (see output above)"
fi

"$PYTHON" "$REPO/scripts/organise-optical-plots.py" --workflow-export "$results/plots" \
  || die "cannot organise $results/plots"
exit $(( status != 0 ))
