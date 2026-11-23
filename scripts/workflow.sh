#!/usr/bin/env bash
# ./workflow.sh example.zip output/path/to/directory [--run optical|charge|both]
#                [--kind pressure|voltage] [--no-plot]



set -uo pipefail

STORAGE="${WARTPC_STORAGE:-/storage/phsccs_grp}"
TRANSFER="${WARTPC_TRANSFER:-$STORAGE/transfer}"
REPO=$(cd -- "$(dirname -- "$0")/.." && pwd)
BUILD="${WARTPC_BUILD:-$REPO/build}"

usage() {
  cat <<EOF
Usage: $(basename "$0") <file.zip> <output_dir> [--run optical|charge|both]
                         [--kind pressure|voltage] [--no-plot]

  <file.zip>      ZIP name in $TRANSFER (or a path to a ZIP)
  <output_dir>    where everything goes: <output_dir>/<name>/ (unzipped data)
                  and <output_dir>/<name>_results/ (analysis and plots)
  --run WHAT      which analysis to run: optical, charge or both (default: both)
  --kind K        pressure or voltage: marker type in the plots (default: guessed
                  from the ZIP name, e.g. pressure-pass-06.zip or prp*.zip)
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

# 1. Access to the group storage
if [[ ! -d "$STORAGE" || ! -r "$STORAGE" || ! -x "$STORAGE" ]]; then
  die "no access to the data"
fi
if [[ ! -d "$TRANSFER" || ! -r "$TRANSFER" || ! -x "$TRANSFER" ]]; then
  die "no access to the data ($TRANSFER is not readable)"
fi

# 2. The ZIP itself
if [[ "$name" == */* ]]; then zip="$name"; else zip="$TRANSFER/$name"; fi
[[ -f "$zip" || "$zip" == *.zip || ! -f "$zip.zip" ]] || zip="$zip.zip"
[[ -f "$zip" ]] || die "$(basename "$zip") does not exist"
[[ -r "$zip" ]] || die "no access to the data ($(basename "$zip") is not readable)"

# Tools needed below
command -v unzip >/dev/null || die "unzip is not installed"
case "$run_what" in
  optical) steps=(optical) ;;
  charge)  steps=(charge) ;;
  both)    steps=(optical charge) ;;
esac
for tool in "${steps[@]}"; do
  [[ -x "$BUILD/$tool" ]] || die "$BUILD/$tool not found; build first: cmake -S $REPO -B $REPO/build && cmake --build $REPO/build"
done
[[ $do_plot -eq 0 || -x "$BUILD/plot" ]] || die "$BUILD/plot not found; rebuild the project"

# 3. Unzip into <output_dir>/<name>
mkdir -p "$outdir" || die "cannot create $outdir"
outdir=$(cd "$outdir" && pwd)
stem=$(basename "$zip" .zip)
dataset="$outdir/$stem"
results="$outdir/${stem}_results"

# From here on, everything printed also goes to <results>/logs/workflow_*.log.
# (Earlier messages are only the access/file checks, which stop before any
# output folder is created.)
mkdir -p "$results/logs" || die "cannot create $results/logs"
log="$results/logs/workflow_$(date +%Y%m%d-%H%M%S).log"
exec 3>&1 4>&2
exec > >(tee -a "$log") 2>&1
tee_pid=${!:-}
echo "# workflow started $(date '+%Y-%m-%d %H:%M:%S') on $(hostname)"
echo "# command: $cmdline"
echo "# zip:     $zip"
echo "# run:     ${steps[*]}"
echo "# log:     $log"
echo

if [[ -d "$dataset" ]]; then
  echo "Already extracted, reusing: $dataset"
else
  echo "Checking $zip"
  unzip -tq "$zip" >/dev/null || die "$(basename "$zip") is damaged or not a ZIP file"
  need=$(unzip -Zt "$zip" | awk '{print $3}')
  avail=$(df -Pk "$outdir" | awk 'NR==2 {print $4 * 1024}')
  if [[ -n "$need" && -n "$avail" ]] && (( need > avail )); then
    die "not enough space in $outdir: need $((need / 1048576)) MiB, have $((avail / 1048576)) MiB"
  fi

  tmp=$(mktemp -d "$outdir/.unzip_${stem}.XXXXXX") || die "cannot write to $outdir"
  trap 'rm -rf "$tmp"' EXIT
  echo "Extracting to $dataset"
  unzip -q "$zip" -d "$tmp" || die "extracting $(basename "$zip") failed"
  rm -rf "$tmp/__MACOSX"   # resource-fork folder added by macOS's zip

  # The dataset folder holds optical/ and/or charge/; it may be the ZIP's top
  # level or a single folder inside it.
  root=""
  if [[ -d "$tmp/optical" || -d "$tmp/charge" ]]; then
    root="$tmp"
  else
    for d in "$tmp"/*/; do
      [[ -d "$d/optical" || -d "$d/charge" ]] || continue
      [[ -z "$root" ]] || die "$(basename "$zip") contains more than one dataset folder"
      root="${d%/}"
    done
  fi
  [[ -n "$root" ]] || die "$(basename "$zip") has no optical/ or charge/ folder"
  mv "$root" "$dataset" || die "cannot move the extracted data to $dataset"
  rm -rf "$tmp"
  trap - EXIT
fi

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
  if [[ -d "$results" ]]; then
    "$BUILD/plot" -i "$results" -o "$results/plots" --dataset "$stem" ${kind:+--kind "$kind"} \
      || { status=1; echo "plot failed"; }
  else
    status=1; echo "plot skipped: no results in $results"
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


