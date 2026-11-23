#!/usr/bin/env bash
# Matt's optical analysis with rebinX(2): X pixels merged in pairs for the 2D
# Gaussian fit and for the X projection before the sideband fits.
#
#   ./optical-rebin-x.sh <dataset_dir> <output_dir> [--runs LIST] [--kind K] [--no-plot]
#
# 1. Runs optical-analysis.sh --rebin-x on (X columns merged in pairs for the
#    2D fit and the X sideband fits) on the chosen runs (same run selection,
#    logs, results folder and plots).
# 2. Saves the fit inputs, original vs X-rebinned, for every run
#    (scripts/plot-rebin-x-inputs.py) -> <results>/rebin_x_inputs/
# 3. Compares the original and rebinX fits for every run, including which
#    signal/sideband regions change (scripts/check-rebin-x-fit.py)
#    -> <results>/rebin_x_fit_check/<run>.txt
#
# Use a different <output_dir> from your normal runs, so the two can be compared.

set -uo pipefail

HERE=$(cd -- "$(dirname -- "$0")" && pwd)
REPO=$(cd -- "$HERE/.." && pwd)

usage() {
  cat <<EOF
Usage: $(basename "$0") <dataset_dir> <output_dir> [--runs LIST] [--kind pressure|voltage] [--no-plot]
       $(basename "$0") <dataset_dir> --list

Runs the optical analysis with rebinX(2) for the 2D Gaussian fit and the X
sideband fits (optical-analysis.sh --rebin-x on) on the chosen runs, then
compares the original and rebinned 2D fits. Options are those of optical-analysis.sh (see its --help).
Results: <output_dir>/<name>_results/, plus rebin_x_inputs/ and rebin_x_fit_check/.
EOF
}
die() { echo "$*" >&2; exit 1; }

[[ $# -ge 1 ]] || { usage >&2; exit 2; }
case "$1" in -h|--help) usage; exit 0 ;; esac
for a in "$@"; do
  [[ "$a" != --rebin-x && "$a" != --rebin ]] || die "$a is set by this script"
  [[ "$a" != --list ]] || exec "$HERE/optical-analysis.sh" "$@"
done

# Dataset and output folder: the first two arguments that are not options
# (or option values).
pos=() skip=0
for a in "$@"; do
  if [[ $skip -eq 1 ]]; then skip=0; continue; fi
  case "$a" in
    --runs|--kind|--rebin) skip=1 ;;
    -*) ;;
    *) pos+=("$a") ;;
  esac
done
[[ ${#pos[@]} -ge 2 ]] || { usage >&2; exit 2; }
dataset="${pos[0]%/}"
outdir="${pos[1]%/}"

# 1. The analysis
"$HERE/optical-analysis.sh" "$@" --rebin-x on
status=$?

results="$(cd "$outdir" 2>/dev/null && pwd)/$(basename "$dataset")_results"
[[ -d "$results/optical" ]] || { echo "no results in $results; skipping the comparisons"; exit 1; }

# Python for the comparison scripts: load the cluster modules first when there
# is a module system (as charge/optical/plot do).
PY="${WARTPC_PYTHON:-python3}"
setup="${BLACKBOX_SETUP:-$REPO/blackbox/setup_blackbox.sh}"
py() {
  if [[ -n "${MODULESHOME:-}${LMOD_CMD:-}" && -f "$setup" ]]; then
    bash -l -c 's="$1"; py="$2"; shift 2; source "$s" >/dev/null 2>&1; exec "$py" "$@"' py "$setup" "$PY" "$@"
  else
    "$PY" "$@"
  fi
}

# 2. Fit inputs, original vs X-rebinned
echo; echo "=== rebinX(2) fit inputs ==="
rm -rf "$results/rebin_x_inputs"
py "$HERE/plot-rebin-x-inputs.py" "$results" "$results/rebin_x_inputs" || status=1

# 3. Original vs rebinX fit, per run
echo; echo "=== original vs rebinX(2) fit ==="
mkdir -p "$results/rebin_x_fit_check"
for h in "$results"/optical/*/output.hdf5; do
  [[ -f "$h" ]] || continue
  run=$(basename "$(dirname "$h")")
  if py "$HERE/check-rebin-x-fit.py" "$h" > "$results/rebin_x_fit_check/$run.txt" 2>&1; then
    echo "$run: $(grep 'rounded region settings changed' "$results/rebin_x_fit_check/$run.txt" | tr '\n' ' ')"
  else
    echo "$run: comparison failed (see rebin_x_fit_check/$run.txt)"; status=1
  fi
done

echo
echo "rebinX(2) results:     $results"
echo "fit inputs:            $results/rebin_x_inputs/"
echo "fit comparison:        $results/rebin_x_fit_check/"
exit $status
