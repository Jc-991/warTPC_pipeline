#!/usr/bin/env bash
# Spark cut and optical fits, from the decoded HDF5 made by decode.sh (no tpx3dump).
#
#   fit.sh -r <results_dir> -d <decoded_dataset_dir> --spark off|remove
#          [--veto BEFORE,AFTER] [--runs LIST] [--into DIR] [--rebin-x off|N] [--analysis FILE]
#
#   -d DIR           decoded dataset from decode.sh, e.g. ~/warTPC/decoded_data/<dataset>
#                    (read only; nothing from it is copied or linked into the results)
#   --spark off      no cut; writes <results_dir>/before/optical/<run>/
#   --spark remove   5 ms grouped spark cut; writes <results_dir>/optical/<run>/
#   --veto 1,20      also remove hits 1 s before to 20 s after each flagged window
#   --into DIR       write to <results_dir>/DIR instead ("." = the top level)
#   --analysis FILE  use another analysis script (default blackbox/optical-analysis.py)
#
# Reads <decoded_dataset_dir>/optical/<run>/{output.hdf5,settings.csv}. Each selected run's
# folder is replaced (without output.hdf5); other runs are kept. Afterwards the folder's
# optical/results/signals.csv, optical_status.txt and spark_counts.csv are
# rebuilt from every run in it. Per-run logs: <dest>/logs/fit/<run>.log

set -uo pipefail
source "$(dirname -- "$0")/common.sh"

usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; }

results="" decoded_in="" spark="" veto="" into="" rebin_x=off analysis="" RUN_SELECTION=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    -r|--results) [[ $# -ge 2 ]] || die "$1 needs a value"; results="$2"; shift 2 ;;
    -d|--decoded) [[ $# -ge 2 ]] || die "$1 needs a folder"; decoded_in="$2"; shift 2 ;;
    --spark)
      [[ $# -ge 2 && ( "$2" == off || "$2" == remove ) ]] || die "--spark must be off or remove"
      spark="$2"; shift 2 ;;
    --veto)
      [[ $# -ge 2 && "$2" =~ ^[0-9.]+,[0-9.]+$ ]] || die "--veto needs BEFORE,AFTER in seconds, e.g. 1,20"
      veto="$2"; shift 2 ;;
    --into) [[ $# -ge 2 ]] || die "--into needs a folder"; into="$2"; shift 2 ;;
    --runs) [[ $# -ge 2 ]] || die "--runs needs a list"; RUN_SELECTION="$2"; shift 2 ;;
    --rebin-x)
      [[ $# -ge 2 && "$2" =~ ^(off|2|4|8|16)$ ]] || die "--rebin-x must be off, 2, 4, 8 or 16"
      rebin_x="$2"; shift 2 ;;
    --analysis) [[ $# -ge 2 ]] || die "--analysis needs a file"; analysis="$2"; shift 2 ;;
    *) usage >&2; die "unknown argument: $1" ;;
  esac
done
[[ -n "$results" && -n "$spark" ]] || { usage >&2; exit 2; }
[[ -z "$veto" || "$spark" == remove ]] || die "--veto needs --spark remove"
mkdir -p "$results" || die "cannot create $results"
results=$(cd "$results" && pwd)
[[ -n "$decoded_in" ]] || die "pass -d <decoded_dataset_dir>, e.g. ~/warTPC/decoded_data/<dataset>"
[[ -d "$decoded_in/optical" ]] || die "$decoded_in has no optical/ folder; decode it first with decode.sh"
decoded=$(cd "$decoded_in/optical" && pwd -P)
[[ -L "$results/decoded" ]] && rm -f -- "$results/decoded"  # link left by older versions
[[ -n "$into" ]] || { [[ "$spark" == off ]] && into=before || into=.; }
[[ "$into" != /* && "$into" != *..* ]] || die "--into must be a folder inside the results directory"
dest="$results/$into"; dest=${dest%/.}
analysis="${analysis:-$BLACKBOX/optical-analysis.py}"
[[ -f "$analysis" ]] || die "$analysis not found"
analysis="$(cd "$(dirname -- "$analysis")" && pwd)/$(basename -- "$analysis")"

available=()
while IFS= read -r r; do available+=("$r"); done < <(list_run_dirs "$decoded")
select_runs "${available[@]+"${available[@]}"}"
(( ${#SELECTED[@]} > 0 )) || die "no decoded runs in $decoded"
load_environment

export WARTPC_SPARK_METHOD=grouped WARTPC_SPARK_MODE="$spark" WARTPC_REBIN=1 WARTPC_REBIN_X="$rebin_x"
if [[ -n "$veto" ]]; then
  export WARTPC_SPARK_VETO_BEFORE_S="${veto%,*}" WARTPC_SPARK_VETO_AFTER_S="${veto#*,}"
else
  unset WARTPC_SPARK_VETO_BEFORE_S WARTPC_SPARK_VETO_AFTER_S
fi

echo "# fit: spark $spark${veto:+, veto -${veto%,*} s / +${veto#*,} s}, rebin-x $rebin_x"
echo "# into: $dest"
echo "# analysis: $analysis"
mkdir -p "$dest/optical/results" "$dest/logs/fit" || die "cannot create $dest"
failed=()
for run in "${SELECTED[@]}"; do
  src="$decoded/$run"
  dst="$dest/optical/$run"
  log="$dest/logs/fit/$run.log"
  if [[ ! -s "$src/output.hdf5" ]]; then
    echo "$run: FAILED (not decoded)"; failed+=("$run"); continue
  fi
  # Fresh run folder, so a failed fit cannot leave an old integral.csv behind.
  rm -rf -- "$dst"
  mkdir -p "$dst"
  for f in "$src"/*; do
    case "$(basename -- "$f")" in output.hdf5|output.partial.*) continue ;; esac
    [[ -f "$f" ]] || continue
    cp -p -- "$f" "$dst/"
  done
  ln -s -- "$src/output.hdf5" "$dst/output.hdf5"
  echo "$run: fitting ..."
  {
    echo "# fit $run started $(date '+%Y-%m-%d %H:%M:%S') on $(hostname)"
    echo "# spark $spark${veto:+, veto $veto}; rebin-x $rebin_x; analysis $analysis"
  } > "$log"
  (cd "$BLACKBOX" && PYTHONPATH="$BLACKBOX${PYTHONPATH:+:$PYTHONPATH}" \
     "$PYTHON" "$analysis" "$dest/optical" "$run" output.hdf5) >>"$log" 2>&1
  rc=$?
  rm -f -- "$dst/output.hdf5"  # only a link to the decoded data; not kept in the results
  if [[ -s "$dst/integral.csv" ]]; then
    echo "# result: OK" >> "$log"; echo "$run: OK"
  else
    echo "# result: FAILED (exit $rc, no integral.csv)" >> "$log"
    echo "$run: FAILED (see $log)"; failed+=("$run")
  fi
done

# Rebuild the folder's combined tables from every run's own files.
: > "$dest/optical/results/signals.csv"
: > "$dest/optical/results/signals_inspect.csv"
done_n=0 total_n=0 missing=()
while IFS= read -r run; do
  total_n=$((total_n + 1))
  d="$dest/optical/$run"
  if [[ -s "$d/integral.csv" ]]; then
    done_n=$((done_n + 1))
    cat "$d/integral.csv" >> "$dest/optical/results/signals.csv"
    [[ -f "$d/integral-inspect.csv" ]] && cat "$d/integral-inspect.csv" >> "$dest/optical/results/signals_inspect.csv"
  else
    missing+=("$run")
  fi
done < <({ printf '%s\n' "${SELECTED[@]}"; list_run_dirs "$dest/optical"; } | sort -u)
{
  echo "# completed $done_n/$total_n runs (fit.sh, $(date '+%Y-%m-%d %H:%M:%S'))"
  for run in "${missing[@]+"${missing[@]}"}"; do
    if [[ -s "$decoded/$run/output.hdf5" ]]; then
      echo "# FAILED $run: no optical/$run/integral.csv (log: logs/fit/$run.log)"
    else
      echo "# FAILED $run: not decoded (see decode_status.txt and logs/decode/$run.log in $(dirname -- "$decoded"))"
    fi
  done
} > "$dest/optical_status.txt"
bash "$REPO/scripts/write-spark-counts.sh" "$dest" || failed+=("(spark counts)")

echo "# fit: ${#SELECTED[@]} runs, ${#failed[@]} failed; folder now $done_n/$total_n complete"
(( ${#failed[@]} == 0 ))
