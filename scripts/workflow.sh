#!/usr/bin/env bash
# ./workflow.sh path/to/unzipped/dataset output/path/to/directory
#               [--run optical|charge|both] [--kind pressure|voltage]
#               [--rebin-x on|off] [--no-plot]
#
# Analyses an already unzipped dataset. To unzip an uploaded ZIP first:
#   ./unzip.sh example.zip path/to/data     -> path/to/data/example/

set -uo pipefail

REPO=$(cd -- "$(dirname -- "$0")/.." && pwd)
BUILD="${WARTPC_BUILD:-$REPO/build}"

usage() {
  cat <<EOF
Usage: $(basename "$0") <dataset_dir> <output_dir> [--run optical|charge|both]
                         [--kind pressure|voltage] [--rebin-x on|off] [--no-plot]

  <dataset_dir>   unzipped dataset folder (with optical/ and/or charge/);
                  use unzip.sh first to unzip an uploaded ZIP
  <output_dir>    results go to <output_dir>/<name>_results/ (analysis and plots)
  --run WHAT      which analysis to run: optical, charge or both (default: both)
  --kind K        pressure or voltage: marker type in the plots (default: guessed
                  from the dataset name, e.g. pressure-pass-06 or prp*)
  --rebin-x on|off  optical: rebinX(2), merge neighbouring X pixels in pairs for
                  the 2D fit and the X sideband fits (default: off = Matt's original)
  --no-plot       skip the PLOT_GUIDE plots (made in <name>_results/plots)
  -h, --help      show this help
EOF
}
die() { echo "$*" >&2; exit 1; }

cmdline="$0${*:+ $*}"
name="" outdir="" do_plot=1 kind="" run_what=both
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --plot) do_plot=1; shift ;;      # default; kept for older commands
    --no-plot) do_plot=0; shift ;;
    --run)
      [[ $# -ge 2 && ( "$2" == optical || "$2" == charge || "$2" == both ) ]] \
        || die "--run must be optical, charge or both"
      run_what="$2"; shift 2 ;;
    --kind)
      [[ $# -ge 2 && ( "$2" == pressure || "$2" == voltage ) ]] || die "--kind must be pressure or voltage"
      kind="$2"; shift 2 ;;
    --rebin-x)
      [[ $# -ge 2 && ( "$2" == on || "$2" == off ) ]] || die "--rebin-x must be on or off"
      [[ "$2" == on ]] && export WARTPC_REBIN_X=1 || export WARTPC_REBIN_X=0
      shift 2 ;;
    -*) usage >&2; die "unknown option: $1" ;;
    *)
      if [[ -z "$name" ]]; then name="$1"
      elif [[ -z "$outdir" ]]; then outdir="$1"
      else usage >&2; die "too many arguments: '$1'"
      fi
      shift ;;
  esac
done
[[ -n "$name" && -n "$outdir" ]] || { usage >&2; exit 2; }

# 1. The dataset folder
if [[ ! -d "$name" ]]; then
  if [[ "$name" == *.zip || -f "$name" ]]; then
    die "$name is not an unzipped folder; unzip it first: $(dirname "$0")/unzip.sh $(basename "$name") <data_dir>"
  fi
  die "$name does not exist"
fi
[[ -d "$name/optical" || -d "$name/charge" ]] || die "$name has no optical/ or charge/ folder"
dataset=$(cd "$name" && pwd)
stem=$(basename "$dataset")

# 2. Tools needed below
case "$run_what" in
  optical) steps=(optical) ;;
  charge)  steps=(charge) ;;
  both)    steps=(optical charge) ;;
esac
for tool in "${steps[@]}"; do
  [[ -x "$BUILD/$tool" ]] || die "$BUILD/$tool not found; build first: cmake -S $REPO -B $REPO/build && cmake --build $REPO/build"
done
[[ $do_plot -eq 0 || -x "$BUILD/plot" ]] || die "$BUILD/plot not found; rebuild the project"

# 3. Results folder and log
mkdir -p "$outdir" || die "cannot create $outdir"
outdir=$(cd "$outdir" && pwd)
results="$outdir/${stem}_results"

# From here on, everything printed also goes to <results>/logs/workflow_*.log.
mkdir -p "$results/logs" || die "cannot create $results/logs"
log="$results/logs/workflow_$(date +%Y%m%d-%H%M%S).log"
exec 3>&1 4>&2
exec > >(tee -a "$log") 2>&1
tee_pid=${!:-}
echo "# workflow started $(date '+%Y-%m-%d %H:%M:%S') on $(hostname)"
echo "# command: $cmdline"
echo "# dataset: $dataset"
echo "# run:     ${steps[*]}"
echo "# rebin-x: $([[ "${WARTPC_REBIN_X:-0}" == 1 ]] && echo on || echo off) (optical)"
echo "# log:     $log"

# 4. Analysis
echo
echo "Dataset: $dataset"
echo "Results: $results"
status=0
for step in "${steps[@]}"; do
  echo; echo "=== $step ==="
  if [[ ! -d "$dataset/$step" ]]; then
    # Asked for explicitly: a missing folder is an error. With "both", a
    # dataset that only has one kind of data is fine.
    if [[ "$run_what" == both ]]; then
      echo "No $step/ folder in $stem; skipping $step"
    else
      status=1; echo "$step requested, but $stem has no $step/ folder"
    fi
    continue
  fi
  "$BUILD/$step" -i "$dataset" -o "$results" \
    || { status=1; echo "$step: some runs failed (see $results/${step}_status.txt)"; }
done

# 5. Plots (PLOT_GUIDE.md), made from whatever optical/charge produced, so
#    runs that failed above show up as missing in plots/status.txt.
if [[ $do_plot -eq 1 ]]; then
  echo; echo "=== plot ==="
  if [[ -d "$results/optical" || -d "$results/charge" ]]; then
    "$BUILD/plot" -i "$results" -o "$results/plots" --dataset "$stem" ${kind:+--kind "$kind"} \
      || { status=1; echo "plot failed"; }
  else
    status=1; echo "plot skipped: no analysis results in $results"
  fi
fi

echo
if [[ $status -eq 0 ]]; then
  echo "Workflow finished: $results"
else
  echo "Workflow finished with failures: $results"
fi
echo "Log: $log"

# Stop logging and let tee finish writing before exiting.
exec 1>&3 2>&4 3>&- 4>&-
[[ -n "$tee_pid" ]] && wait "$tee_pid" 2>/dev/null
exit $status
