#!/usr/bin/env bash
# Stage 3: plots and tables for one fit folder.
#
#   plot.sh -r <results_dir> [--from DIR] [--kind pressure|voltage] [--dataset NAME] [--organise]
#
# Runs build/plot on <results_dir>/<DIR> (default: the top level, i.e. the
# after-cut fits; use --from before for the uncut fits) and writes
# <results_dir>/<DIR>/plots/: per-run, streaming and physics plots, results.csv
# and run_summary.txt. Charge results in <DIR>/charge/ are included when present.
# --organise gives the plots their IDs (S05, 010_..., ...). Only use it when
# pair.sh will not run next: pair.sh needs the unrenamed files and organises itself.

set -uo pipefail
source "$(dirname -- "$0")/common.sh"

usage() { sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; }

results="" from="." kind="" dataset="" organise=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    -r|--results) [[ $# -ge 2 ]] || die "$1 needs a value"; results="$2"; shift 2 ;;
    --from) [[ $# -ge 2 ]] || die "--from needs a folder"; from="$2"; shift 2 ;;
    --kind)
      [[ $# -ge 2 && ( "$2" == pressure || "$2" == voltage ) ]] || die "--kind must be pressure or voltage"
      kind="$2"; shift 2 ;;
    --dataset) [[ $# -ge 2 ]] || die "--dataset needs a name"; dataset="$2"; shift 2 ;;
    --organise) organise=1; shift ;;
    *) usage >&2; die "unknown argument: $1" ;;
  esac
done
[[ -n "$results" ]] || { usage >&2; exit 2; }
[[ -d "$results" ]] || die "$results not found"
results=$(cd "$results" && pwd)
[[ "$from" != /* && "$from" != *..* ]] || die "--from must be a folder inside the results directory"
src="$results/$from"; src=${src%/.}
[[ -d "$src/optical" || -d "$src/charge" ]] || die "$src has no optical/ or charge/ results; run fit.sh first"
[[ -x "$BUILD/plot" ]] || die "$BUILD/plot not found; build first: cmake -S $REPO -B $REPO/build && cmake --build $REPO/build"
dataset="${dataset:-$(dataset_name "$results")}"
load_environment

echo "# plot: $src -> $src/plots (dataset $dataset)"
# plots/ is fully generated; start clean so old renamed files cannot clash.
rm -rf -- "$src/plots"
"$BUILD/plot" -i "$src" -o "$src/plots" --dataset "$dataset" --no-comparisons ${kind:+--kind "$kind"} \
  || die "plot failed for $src"
if [[ $organise -eq 1 ]]; then
  "$PYTHON" "$REPO/scripts/organise-optical-plots.py" --workflow-export "$src/plots" \
    || die "cannot organise $src/plots"
fi
echo "# plot: done -> $src/plots"
