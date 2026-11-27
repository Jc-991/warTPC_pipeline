#!/usr/bin/env bash
# ./workflow.sh -i decoded_data/<dataset> -o output/path/to/directory
#               [--runs LIST] [--kind pressure|voltage] [--sparks on|off] [--veto B,A|off]
#               [--rebin-x off|N]
#
# Starts from data decoded beforehand with scripts/stages/decode.sh (done once,
# when a dataset is imported). Runs the optical stages in scripts/stages/ in
# order (each can also be run on its own; see scripts/workflow.md):
#   fit.sh --spark off (before/) -> fit.sh --spark remove
#   -> plot.sh --from before -> plot.sh -> pair.sh
# Optical only. Charge reads the raw dataset and is run on its own:
#   build/charge -i <raw_dataset_dir> -o <output_dir>/<name>_results

set -uo pipefail

REPO=$(cd -- "$(dirname -- "$0")/.." && pwd)
BUILD="${WARTPC_BUILD:-$REPO/build}"

usage() {
  cat <<EOF
Usage: $(basename "$0") -i <decoded_dataset_dir> -o <output_dir> [--runs LIST]
                         [--kind pressure|voltage] [--sparks on|off] [--veto B,A|off]
                         [--rebin-x off|N]

  -i, --input     decoded dataset from decode.sh, e.g. ~/warTPC/decoded_data/<dataset>
                  (holds optical/<run>/output.hdf5 and settings.csv)
  -o, --output    results go to <output_dir>/<name>_results/ (analysis and plots)
                  each completed optical run writes a table and a readable summary
  --runs LIST     comma-separated run folder names (default: all). If
                  <name>_results exists, selected runs go to <name>_results-01, -02, ...
  --kind K        pressure or voltage: marker type in the plots (default: guessed
                  from the dataset name, e.g. pressure-pass-06 or prp*)
  --sparks on|off  grouped optical spark removal (default: on): runs
                  before/after fits and export ten PNGs plus both summaries
                  per run under <name>_results/plots/optical_per_run/
  --veto B,A|off  with sparks on, also remove hits B s before to A s after each
                  flagged 5 ms window (default: 1,20; "off" = only the 5 ms
                  windows). WARTPC_SPARK_VETO_BEFORE_S / _AFTER_S also set it
  --rebin-x off|N  merge N adjacent X pixels in the optical fits (2, 4, 8, 16);
                  default: off
  -h, --help      show this help

The two directories can also be passed as positional arguments.
Decode a new dataset first:
  bash scripts/stages/decode.sh -i <raw_dataset_dir> -o ~/warTPC/decoded_data
Charge is not part of this workflow; run build/charge on the raw dataset.
EOF
}
die() { echo "$*" >&2; exit 1; }

cmdline="$0${*:+ $*}"
name="" outdir="" kind="" sparks=on rebin_x=off selection="" veto="" veto_given=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    -i|--input)
      [[ $# -ge 2 && -n "$2" && "$2" != -* ]] || die "$1 needs a dataset directory"
      [[ -z "$name" ]] || die "dataset directory already specified"
      name="$2"; shift 2 ;;
    -o|--output)
      [[ $# -ge 2 && -n "$2" && "$2" != -* ]] || die "$1 needs an output directory"
      [[ -z "$outdir" ]] || die "output directory already specified"
      outdir="$2"; shift 2 ;;
    --plot) shift ;;  # plots are always made; accepted for older commands
    --no-plot) die "--no-plot was removed; for fits only run: bash scripts/stages/fit.sh -r <results> -d <decoded_dataset> --spark remove --veto 1,20" ;;
    --run)
      # Kept so older "--run optical" commands still work; charge has moved out.
      [[ $# -ge 2 && "$2" == optical ]] \
        || die "workflow.sh is optical only; run charge with: build/charge -i <raw_dataset_dir> -o <results_dir>"
      shift 2 ;;
    --runs)
      [[ $# -ge 2 && "$2" =~ ^[^,]+(,[^,]+)*$ ]] || die "--runs needs comma-separated run folder names"
      selection="$2"; shift 2 ;;
    --kind)
      [[ $# -ge 2 && ( "$2" == pressure || "$2" == voltage ) ]] || die "--kind must be pressure or voltage"
      kind="$2"; shift 2 ;;
    --sparks)
      [[ $# -ge 2 && ( "$2" == on || "$2" == off ) ]] || die "--sparks must be on or off"
      sparks="$2"; shift 2 ;;
    --veto)
      [[ $# -ge 2 && ( "$2" == off || "$2" =~ ^[0-9.]+,[0-9.]+$ ) ]] \
        || die "--veto needs BEFORE,AFTER in seconds (e.g. 1,20) or off"
      veto="$2"; veto_given=1; shift 2 ;;
    --rebin-x)
      [[ $# -ge 2 && "$2" =~ ^(off|1|2|4|8|16|on)$ ]] \
        || die "--rebin-x must be off or a bin width of 2, 4, 8 or 16"
      case "$2" in
        1|off) rebin_x=off ;;
        on) rebin_x=2 ;; # Compatibility with existing commands.
        *) rebin_x="$2" ;;
      esac
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

# 1. The decoded dataset
[[ -d "$name" ]] || die "$name does not exist"
dataset=$(cd "$name" && pwd)
stem=$(basename "$dataset")
decode_hint="decode it first: bash scripts/stages/decode.sh -i $name -o ~/warTPC/decoded_data"
if compgen -G "$dataset/optical/*/rawdata_000000.tpx3" >/dev/null; then
  die "$name holds raw .tpx3 data; $decode_hint"
fi
[[ -d "$dataset/optical" ]] || die "$name has no optical/ folder; pass the decoded dataset (decoded_data/<dataset>)"

# 2. Run selection and tools
if [[ -n "$selection" ]]; then
  IFS=, read -r -a selected_runs <<< "$selection"
  for run in "${selected_runs[@]}"; do
    [[ "$run" != */* && "$run" != .* && "$run" != -* && "$run" != results ]] || die "invalid run folder name: $run"
    [[ -d "$dataset/optical/$run" ]] || die "run '$run' not found in $dataset/optical"
  done
fi
# Veto around each spark: --veto, else the environment variables, else 1 s / 20 s.
if [[ $veto_given -eq 0 ]]; then
  if [[ -n "${WARTPC_SPARK_VETO_BEFORE_S:-}${WARTPC_SPARK_VETO_AFTER_S:-}" ]]; then
    veto="${WARTPC_SPARK_VETO_BEFORE_S:-0},${WARTPC_SPARK_VETO_AFTER_S:-0}"
  else
    veto="1,20"
  fi
fi
[[ "$veto" == off || "$veto" =~ ^0*\.?0*,0*\.?0*$ ]] && veto=""
if [[ "$sparks" == off ]]; then
  [[ $veto_given -eq 0 || -z "$veto" ]] || die "--veto needs --sparks on"
  veto=""
fi
[[ -x "$BUILD/plot" ]] || die "$BUILD/plot not found; rebuild the project"

# 3. Results folder and log
mkdir -p "$outdir" || die "cannot create $outdir"
outdir=$(cd "$outdir" && pwd)
results="$outdir/${stem}_results"
if [[ -n "$selection" ]]; then
  # A rerun of selected runs gets the next free <name>_results-01, -02, ... instead of reusing it.
  if ! mkdir -- "$results" 2>/dev/null; then
    for n in $(seq -w 1 99); do
      if mkdir -- "$outdir/${stem}_results-$n" 2>/dev/null; then results="$outdir/${stem}_results-$n"; break; fi
      [[ $n == 99 ]] && die "cannot create selected-run results: ${stem}_results-01 to -99 all exist"
    done
  fi
fi

# From here on, everything printed also goes to <results>/logs/workflow_*.log.
mkdir -p "$results/logs" || die "cannot create $results/logs"
log="$results/logs/workflow_$(date +%Y%m%d-%H%M%S).log"
exec 3>&1 4>&2
exec > >(tee -a "$log") 2>&1
tee_pid=${!:-}
echo "# workflow started $(date '+%Y-%m-%d %H:%M:%S') on $(hostname)"
echo "# command: $cmdline"
echo "# dataset: $dataset"
echo "# selection: ${selection:-all}"
echo "# sparks:  $sparks (optical)$([[ "$sparks" == on ]] && { [[ -n "$veto" ]] && echo ", veto -${veto%,*} s / +${veto#*,} s" || echo ", no veto (5 ms windows only)"; })"
echo "# rebin-x: $rebin_x (optical)"
echo "# log:     $log"

# 4. Analysis
echo
echo "Dataset: $dataset"
echo "Results: $results"
STAGES="$REPO/scripts/stages"
status=0
pairing=0
[[ "$sparks" == on ]] && pairing=1

echo; echo "=== optical ==="
fit_opts=(-d "$dataset" --rebin-x "$rebin_x" ${selection:+--runs "$selection"})
if [[ $pairing -eq 1 ]]; then
  echo "--- 1a. fit without spark removal (before/) ---"
  bash "$STAGES/fit.sh" -r "$results" --spark off "${fit_opts[@]}" || status=1
fi
if [[ "$sparks" == on ]]; then
  echo "--- 1b. fit with spark removal ---"
  bash "$STAGES/fit.sh" -r "$results" --spark remove ${veto:+--veto "$veto"} "${fit_opts[@]}" || status=1
else
  echo "--- 1. fit (spark removal off) ---"
  bash "$STAGES/fit.sh" -r "$results" --spark off --into . "${fit_opts[@]}" || status=1
fi

# 5. Plots, made from whatever the fits produced, so runs that failed above
#    show up as missing in plots/status.txt.
echo; echo "=== plot ==="
if [[ -d "$results/optical" ]]; then
  if [[ $pairing -eq 1 ]]; then
    echo "--- 2a. plot before/ ---"
    bash "$STAGES/plot.sh" -r "$results" --from before --dataset "$stem" ${kind:+--kind "$kind"} || status=1
    echo "--- 2b. plot ---"
    if bash "$STAGES/plot.sh" -r "$results" --dataset "$stem" ${kind:+--kind "$kind"}; then
      echo "--- 3. pair before/after ---"
      bash "$STAGES/pair.sh" -r "$results" ${selection:+--runs "$selection"} || status=1
    else
      status=1
    fi
  else
    echo "--- 2. plot ---"
    bash "$STAGES/plot.sh" -r "$results" --dataset "$stem" ${kind:+--kind "$kind"} --organise || status=1
  fi
else
  status=1; echo "plot skipped: no analysis results in $results"
fi
# Only plots/ (with the before/after pairs in optical_per_run/), optical/ fit
# tables and logs/ are kept, whatever happened above. Problems are in this log.
rm -rf -- "$results/before" "$results/paired"

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
