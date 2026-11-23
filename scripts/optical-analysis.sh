#!/usr/bin/env bash
# Optical analysis of selected runs only.
#
#   ./optical-analysis.sh <dataset_dir> <output_dir> [--runs LIST] [--kind K] [--no-plot]
#   ./optical-analysis.sh <dataset_dir> --list
#
# Results go to <output_dir>/<name>_results/ (the same folder workflow.sh uses).

set -uo pipefail

REPO=$(cd -- "$(dirname -- "$0")/.." && pwd)
BUILD="${WARTPC_BUILD:-$REPO/build}"

usage() {
  cat <<EOF
Usage: $(basename "$0") <dataset_dir> <output_dir> [--runs LIST] [--kind pressure|voltage] [--no-plot]
       $(basename "$0") <dataset_dir> --list

  <dataset_dir>   unzipped dataset folder (with optical/<run>/)
  <output_dir>    results go to <output_dir>/<name>_results/
  --runs LIST     runs to analyse, separated by commas or spaces:
                    3          run number 3 in the list (see --list)
                    2-5        run numbers 2 to 5
                    vr22-07    a run name
                    'vr22-1*'  a name pattern (quote it)
                    all        every run
                  without --runs you are asked interactively
  --list          only list the runs with their numbers
  --kind K        pressure or voltage: marker type in the plots
  --rebin N       test: merge N x N pixels before the 2D fit (N = 2, 4, ...;
                  default 1 = no rebinning); also prints the rebinned plots
  --analysis FILE use FILE instead of blackbox/optical-analysis.py, e.g.
                  ../blackbox/optical-analysis-rebin-x.py (Matt's code with rebinX(2))
  --no-plot       skip the plots
  -h, --help      show this help
EOF
}
die() { echo "$*" >&2; exit 1; }

cmdline="$0${*:+ $*}"
name="" outdir="" selection="" list_only=0 do_plot=1 kind="" analysis=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --list) list_only=1; shift ;;
    --runs) [[ $# -ge 2 ]] || die "--runs needs a list"; selection="$2"; shift 2 ;;
    --no-plot) do_plot=0; shift ;;
    --analysis) [[ $# -ge 2 ]] || die "--analysis needs a file"; analysis="$2"; shift 2 ;;
    --rebin)
      [[ $# -ge 2 && "$2" =~ ^(1|2|4|8|16)$ ]] || die "--rebin must be 1, 2, 4, 8 or 16"
      export WARTPC_REBIN="$2"; shift 2 ;;
    --kind)
      [[ $# -ge 2 && ( "$2" == pressure || "$2" == voltage ) ]] || die "--kind must be pressure or voltage"
      kind="$2"; shift 2 ;;
    -*) usage >&2; die "unknown option: $1" ;;
    *)
      if [[ -z "$name" ]]; then name="$1"
      elif [[ -z "$outdir" ]]; then outdir="$1"
      else usage >&2; die "too many arguments: '$1'"
      fi
      shift ;;
  esac
done
[[ -n "$name" ]] || { usage >&2; exit 2; }

# 1. Dataset and its optical runs
[[ "$name" != *.zip ]] || die "$name is a ZIP; unzip it first: $(dirname "$0")/unzip.sh $(basename "$name") <data_dir>"
[[ -d "$name" ]] || die "$name does not exist"
[[ -d "$name/optical" ]] || die "$name has no optical/ folder"
dataset=$(cd "$name" && pwd)
stem=$(basename "$dataset")

runs=()
while IFS= read -r r; do runs+=("$r"); done < <(
  find "$dataset/optical" -mindepth 1 -maxdepth 1 -type d ! -name results -exec basename {} \; | sort)
(( ${#runs[@]} > 0 )) || die "no runs in $dataset/optical"

list_runs() {
  echo "Optical runs in $stem:"
  local i
  for i in "${!runs[@]}"; do printf '  %3d  %s\n' $((i + 1)) "${runs[$i]}"; done
}
if [[ $list_only -eq 1 ]]; then list_runs; exit 0; fi
[[ -n "$outdir" ]] || { usage >&2; exit 2; }

# 2. Which runs
if [[ -z "$selection" ]]; then
  [[ -t 0 ]] || die "no --runs given (and no terminal to ask); e.g. --runs 1,3-5 or --runs all"
  list_runs
  read -r -p "Runs to analyse (e.g. 1,3-5 or vr22-07 or all): " selection
  [[ -n "$selection" ]] || die "nothing selected"
fi

chosen=()
add_run() {
  local c
  for c in "${chosen[@]+"${chosen[@]}"}"; do [[ "$c" == "$1" ]] && return; done
  chosen+=("$1")
}
for tok in ${selection//,/ }; do
  if [[ "$tok" == all ]]; then
    for r in "${runs[@]}"; do add_run "$r"; done
  elif [[ "$tok" =~ ^[0-9]+$ ]]; then
    (( tok >= 1 && tok <= ${#runs[@]} )) || die "run number $tok is not in 1-${#runs[@]} (see --list)"
    add_run "${runs[$((tok - 1))]}"
  elif [[ "$tok" =~ ^([0-9]+)-([0-9]+)$ ]]; then
    a=${BASH_REMATCH[1]} b=${BASH_REMATCH[2]}
    (( a >= 1 && b <= ${#runs[@]} && a <= b )) || die "range $tok is not within 1-${#runs[@]} (see --list)"
    for ((k = a; k <= b; k++)); do add_run "${runs[$((k - 1))]}"; done
  else
    found=0
    for r in "${runs[@]}"; do
      # shellcheck disable=SC2053  # pattern match on purpose
      if [[ "$r" == $tok ]]; then add_run "$r"; found=1; fi
    done
    [[ $found -eq 1 ]] || die "no run matches '$tok' (see --list)"
  fi
done
(( ${#chosen[@]} > 0 )) || die "nothing selected"

if [[ -n "$analysis" ]]; then
  [[ -f "$analysis" ]] || die "--analysis: $analysis does not exist"
  analysis="$(cd "$(dirname "$analysis")" && pwd)/$(basename "$analysis")"
fi
[[ -x "$BUILD/optical" ]] || die "$BUILD/optical not found; build first: cmake -S $REPO -B $REPO/build && cmake --build $REPO/build"
[[ $do_plot -eq 0 || -x "$BUILD/plot" ]] || die "$BUILD/plot not found; rebuild the project"

# 3. Results folder and log
mkdir -p "$outdir" || die "cannot create $outdir"
outdir=$(cd "$outdir" && pwd)
results="$outdir/${stem}_results"
mkdir -p "$results/logs" "$results/optical/results" || die "cannot create $results"
stamp=$(date +%Y%m%d-%H%M%S)
log="$results/logs/optical-analysis_$stamp.log"
exec 3>&1 4>&2
exec > >(tee -a "$log") 2>&1
tee_pid=${!:-}
echo "# optical-analysis started $(date '+%Y-%m-%d %H:%M:%S') on $(hostname)"
echo "# command: $cmdline"
echo "# dataset: $dataset"
echo "# runs:    ${chosen[*]} (${#chosen[@]} of ${#runs[@]})"
echo "# rebin:   ${WARTPC_REBIN:-1} (2D fit)"
echo "# analysis: ${analysis:-blackbox/optical-analysis.py}"
echo "# log:     $log"

# 4. Analyse the chosen runs in a staging folder. optical_run.sh processes
#    every run folder it finds, so it gets a view with only the chosen runs.
view="$results/.select_view_$stamp"
stage="$results/.select_stage_$stamp"
bbdir=""
trap 'rm -rf "$view" "$stage" ${bbdir:+"$bbdir"}' EXIT
mkdir -p "$view/optical"
for r in "${chosen[@]}"; do ln -s "$dataset/optical/$r" "$view/optical/$r"; done

echo; echo "=== optical (${#chosen[@]} runs) ==="
# Another analysis file: a temporary Blackbox folder holding the usual files,
# with that file in place of optical-analysis.py.
if [[ -n "$analysis" ]]; then
  bb_src="${WARTPC_BLACKBOX:-$REPO/blackbox}"
  bbdir="$results/.select_blackbox_$stamp"
  mkdir -p "$bbdir"
  for f in "$bb_src"/*; do ln -s "$f" "$bbdir/$(basename "$f")"; done
  rm -f "$bbdir/optical-analysis.py"
  ln -s "$analysis" "$bbdir/optical-analysis.py"
  export WARTPC_BLACKBOX="$bbdir"
fi
"$BUILD/optical" -i "$view" -o "$stage"
status=$?

# 5. Move the new results in, replacing only the chosen runs.
mkdir -p "$results/logs/optical"
for r in "${chosen[@]}"; do
  if [[ -d "$stage/optical/$r" ]]; then
    rm -rf "$results/optical/$r"
    mv "$stage/optical/$r" "$results/optical/$r"
  fi
  [[ -f "$stage/logs/optical/$r.log" ]] && mv "$stage/logs/optical/$r.log" "$results/logs/optical/$r.log"
done
for f in "$stage"/logs/optical_*.log; do [[ -f "$f" ]] && mv "$f" "$results/logs/"; done

# Rebuild the combined tables and the status from every run's own files.
: > "$results/optical/results/signals.csv"
: > "$results/optical/results/signals_inspect.csv"
done_n=0 total_n=0 failed=()
for d in "$results"/optical/*/; do
  r=$(basename "$d")
  [[ "$r" == results ]] && continue
  total_n=$((total_n + 1))
  if [[ -s "$d/integral.csv" ]]; then
    done_n=$((done_n + 1))
    cat "$d/integral.csv" >> "$results/optical/results/signals.csv"
    [[ -f "$d/integral-inspect.csv" ]] && cat "$d/integral-inspect.csv" >> "$results/optical/results/signals_inspect.csv"
  else
    failed+=("$r")
  fi
done
{
  echo "# completed $done_n/$total_n runs (last updated by optical-analysis.sh, $(date '+%Y-%m-%d %H:%M:%S'))"
  for r in "${failed[@]+"${failed[@]}"}"; do
    echo "# FAILED $r: no optical/$r/integral.csv (log: logs/optical/$r.log)"
  done
} > "$results/optical_status.txt"
echo
cat "$results/optical_status.txt"

# 6. Plots, from all runs in the results folder
if [[ $do_plot -eq 1 ]]; then
  echo; echo "=== plot ==="
  "$BUILD/plot" -i "$results" -o "$results/plots" --dataset "$stem" ${kind:+--kind "$kind"} \
    || { status=1; echo "plot failed"; }
fi

echo
if [[ $status -eq 0 ]]; then
  echo "Finished: ${#chosen[@]} runs analysed into $results"
else
  echo "Finished with failures: $results"
fi
echo "Log: $log"

exec 1>&3 2>&4 3>&- 4>&-
[[ -n "$tee_pid" ]] && wait "$tee_pid" 2>/dev/null
exit $status
