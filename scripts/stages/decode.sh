#!/usr/bin/env bash
# Decode a dataset's optical runs once, when the data is imported.
#
#   decode.sh -i <dataset.zip | raw_dataset_dir> -o <decoded_root> [--runs LIST] [--force]
#             [--timeout MIN] [--tmp DIR]
#
# -i is an uploaded ZIP (a bare name such as voltage-run-18-11-26.zip is looked
# up in /storage/phsccs_grp/transfer/) or an already unzipped dataset folder.
# A ZIP is unzipped into a temporary folder (--tmp, default <decoded_root>),
# decoded, and the temporary copy deleted; if every run in it is already
# decoded, it is not unzipped at all. <dataset> is the ZIP's name without .zip.
#
# For every run in <dataset>/optical/<run>/, runs tpx3dump on
# rawdata_000000.tpx3 and writes
#   <decoded_root>/<dataset>/optical/<run>/output.hdf5
#   <decoded_root>/<dataset>/optical/<run>/settings.csv
# These are the only per-run files the optical fits and plots read; point
# workflow.sh -i at <decoded_root>/<dataset>. Runs already decoded are skipped
# unless --force is given (settings.csv is still refreshed if it changed). A run
# whose tpx3dump takes longer than --timeout minutes (default 10, 0 = no limit)
# is stopped, marked failed, and the next run starts. The raw dataset is never written.
# Logs: <decoded_root>/<dataset>/logs/decode/<run>.log
# Summary of the last pass: <decoded_root>/<dataset>/decode_status.txt
#
# Examples:
#   bash scripts/stages/decode.sh -i voltage-run-18-11-26.zip -o ~/warTPC/decoded_data
#   bash scripts/stages/decode.sh -i ~/warTPC/data/voltage-run-22-11-26 -o ~/warTPC/decoded_data

set -uo pipefail
source "$(dirname -- "$0")/common.sh"

usage() { sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; }

dataset="" out_root="" tmp_root="" force=0 timeout_min=10 RUN_SELECTION=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    -i|--input) [[ $# -ge 2 ]] || die "$1 needs a value"; dataset="$2"; shift 2 ;;
    -o|--output) [[ $# -ge 2 ]] || die "$1 needs a value"; out_root="$2"; shift 2 ;;
    --runs) [[ $# -ge 2 ]] || die "--runs needs a list"; RUN_SELECTION="$2"; shift 2 ;;
    --force) force=1; shift ;;
    --tmp) [[ $# -ge 2 ]] || die "--tmp needs a folder"; tmp_root="$2"; shift 2 ;;
    --timeout)
      [[ $# -ge 2 && "$2" =~ ^[0-9]+$ ]] || die "--timeout needs whole minutes (0 = no limit)"
      timeout_min="$2"; shift 2 ;;
    *) usage >&2; die "unknown argument: $1" ;;
  esac
done
[[ -n "$dataset" && -n "$out_root" ]] || { usage >&2; exit 2; }
mkdir -p "$out_root" || die "cannot create $out_root"
out_root=$(cd "$out_root" && pwd)

# A ZIP: work out which file, skip it if everything in it is decoded, else
# unzip it into a temporary folder that is removed when this script ends.
zip=""
if [[ ! -d "$dataset" ]]; then
  zip="$dataset"
  [[ "$zip" == */* ]] || zip="${WARTPC_TRANSFER:-${WARTPC_STORAGE:-/storage/phsccs_grp}/transfer}/$zip"
  [[ -f "$zip" || "$zip" == *.zip ]] || zip="$zip.zip"
  [[ -f "$zip" ]] || die "$dataset: no such folder or ZIP (looked for $zip)"
  command -v unzip >/dev/null || die "unzip is not installed"
  zip_stem=$(basename -- "$zip" .zip)
  if [[ $force -eq 0 && -z "$RUN_SELECTION" ]]; then
    zip_runs=$(unzip -Z1 "$zip" | awk -F/ '$NF == "rawdata_000000.tpx3" && $(NF-2) == "optical" {print $(NF-1)}' | sort -u)
    todo=0
    for r in $zip_runs; do [[ -s "$out_root/$zip_stem/optical/$r/output.hdf5" ]] || todo=$((todo + 1)); done
    if [[ -n "$zip_runs" && $todo -eq 0 ]]; then
      echo "# decode: $(basename -- "$zip"): all $(wc -w <<< "$zip_runs" | tr -d ' ') optical runs already decoded in $out_root/$zip_stem (use --force to redo)"
      exit 0
    fi
  fi
  tmp_root="${tmp_root:-$out_root}"
  mkdir -p "$tmp_root" || die "cannot create $tmp_root"
  unzip_dir=$(mktemp -d "$tmp_root/.unzip-$zip_stem.XXXXXX") || die "cannot write to $tmp_root"
  trap 'rm -rf -- "$unzip_dir"' EXIT
  echo "# decode: unzipping $zip (temporary copy in $unzip_dir, removed afterwards)"
  bash "$REPO/scripts/unzip.sh" "$zip" "$unzip_dir" >/dev/null || die "cannot unzip $zip"
  dataset="$unzip_dir/$zip_stem"
fi
[[ -d "$dataset/optical" ]] || die "$dataset has no optical/ folder"
dataset=$(cd "$dataset" && pwd)
stem=$(basename -- "$dataset")
mkdir -p "$out_root/$stem/optical" "$out_root/$stem/logs/decode" || die "cannot create $out_root/$stem"
target=$(cd "$out_root/$stem" && pwd -P)
[[ "$target/" != "$dataset/"* ]] || die "the output must be outside the raw dataset"
[[ -x "$BLACKBOX/tpx3dump" ]] || die "$BLACKBOX/tpx3dump not found or not executable"
store="$target/optical"

available=()
while IFS= read -r r; do available+=("$r"); done < <(list_run_dirs "$dataset/optical")
select_runs "${available[@]+"${available[@]}"}"
(( ${#SELECTED[@]} > 0 )) || die "no runs in $dataset/optical"
load_environment

# Time limit per run, in seconds (WARTPC_DECODE_TIMEOUT_S overrides, for testing).
limit_s=${WARTPC_DECODE_TIMEOUT_S:-$((timeout_min * 60))}
if (( limit_s == 0 )); then limit_text="none"
elif [[ -n "${WARTPC_DECODE_TIMEOUT_S:-}" ]]; then limit_text="${limit_s} s"
else limit_text="${timeout_min} min"; fi

# Run "$@" with that limit; on timeout stop it and anything it started, return 124.
# Uses coreutils timeout (Linux/Hammer), or a small perl watchdog where it is missing.
run_limited() {
  (( limit_s > 0 )) || { "$@"; return; }
  if command -v timeout >/dev/null 2>&1; then
    timeout -k 30 "$limit_s" "$@"
    local rc=$?
    (( rc == 137 )) && rc=124  # ignored the TERM and was killed
    return $rc
  fi
  perl -e '
    my $limit = shift;
    my $pid = fork() // die "fork: $!\n";
    if (!$pid) { setpgrp(0, 0); exec @ARGV or die "cannot run $ARGV[0]: $!\n"; }
    local $SIG{ALRM} = sub { kill "TERM", -$pid; sleep 5; kill "KILL", -$pid; waitpid($pid, 0); exit 124 };
    alarm $limit;
    waitpid($pid, 0);
    exit($? & 127 ? 128 + ($? & 127) : $? >> 8);
  ' "$limit_s" "$@"
}

ok=0 skipped=0 failed=() reasons=()
echo "# decode: $dataset"
echo "# into:   $store"
echo "# decode: time limit per run $limit_text"
for run in "${SELECTED[@]}"; do
  src="$dataset/optical/$run"
  dst="$store/$run"
  raw="$src/rawdata_000000.tpx3"
  log="$target/logs/decode/$run.log"
  if [[ ! -f "$raw" ]]; then
    echo "$run: FAILED (no rawdata_000000.tpx3)"; failed+=("$run"); reasons+=("no rawdata_000000.tpx3"); continue
  fi
  mkdir -p "$dst"
  # settings.csv is the only other file the analysis reads.
  if [[ -f "$src/settings.csv" ]]; then
    if [[ -f "$dst/settings.csv" ]] && ! cmp -s "$src/settings.csv" "$dst/settings.csv"; then
      echo "$run: settings.csv differs from the stored copy; updating it"
    fi
    cmp -s "$src/settings.csv" "$dst/settings.csv" 2>/dev/null || cp -p -- "$src/settings.csv" "$dst/" \
      || die "cannot copy $src/settings.csv"
  else
    echo "$run: warning: no settings.csv in the dataset"
  fi
  if [[ $force -eq 0 && -s "$dst/output.hdf5" ]]; then
    echo "$run: already decoded (use --force to redo)"; skipped=$((skipped + 1)); continue
  fi
  echo "$run: decoding ..."
  partial="$dst/output.partial.$$.hdf5"
  rm -f -- "$partial"
  echo "# decode $run started $(date '+%Y-%m-%d %H:%M:%S'), limit $limit_text" > "$log"
  start=$SECONDS
  run_limited "$BLACKBOX/tpx3dump" -i "$raw" -o "$partial" >>"$log" 2>&1
  rc=$?
  took=$(( SECONDS - start ))
  if (( rc == 0 )) && [[ -s "$partial" ]]; then
    mv -f -- "$partial" "$dst/output.hdf5"
    echo "# result: OK (${took} s)" >> "$log"
    echo "$run: OK (${took} s)"; ok=$((ok + 1))
  else
    rm -f -- "$partial"  # an earlier good output.hdf5 (with --force) is left alone
    if (( rc == 124 )); then
      reason="timed out after $limit_text"
    elif (( rc == 0 )); then
      reason="tpx3dump wrote no output"
    else
      reason="tpx3dump exit $rc"
    fi
    echo "# result: FAILED ($reason)" >> "$log"
    echo "$run: FAILED ($reason; see $log)"; failed+=("$run"); reasons+=("$reason")
  fi
done

{
  echo "# decode (this pass: ${SELECTED[*]}): $ok decoded, $skipped already done, ${#failed[@]} failed ($(date '+%Y-%m-%d %H:%M:%S'))"
  for i in "${!failed[@]}"; do
    echo "# FAILED ${failed[$i]}: ${reasons[$i]} (log: logs/decode/${failed[$i]}.log)"
  done
} | tee "$target/decode_status.txt"
(( ${#failed[@]} == 0 ))
