#!/usr/bin/env bash
# Unzip one uploaded dataset, nothing else.
#
#   ./unzip.sh example.zip output/path/to/directory
#
# -> output/path/to/directory/example/   (with optical/ and/or charge/)
#
# Then analyse it with:
#   ./workflow.sh output/path/to/directory/example <output_dir> [options]
set -uo pipefail

STORAGE="${WARTPC_STORAGE:-/storage/phsccs_grp}"
TRANSFER="${WARTPC_TRANSFER:-$STORAGE/transfer}"

usage() {
  cat <<EOF
Usage: $(basename "$0") <file.zip> <output_dir> [--force]

  <file.zip>      ZIP name in $TRANSFER (or a path to a ZIP)
  <output_dir>    the dataset is unzipped to <output_dir>/<name>/
  --force         unzip again even if <output_dir>/<name>/ already exists
                  (the old folder is replaced)
  -h, --help      show this help
EOF
}
die() { echo "$*" >&2; exit 1; }

name="" outdir="" force=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --force) force=1; shift ;;
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

# 1. Find the ZIP. A bare name is looked up in the transfer folder, which
#    needs access to the group storage; a path is used as given.
if [[ "$name" == */* ]]; then
  zip="$name"
else
  if [[ ! -d "$STORAGE" || ! -r "$STORAGE" || ! -x "$STORAGE" ]]; then
    die "no access to the data"
  fi
  if [[ ! -d "$TRANSFER" || ! -r "$TRANSFER" || ! -x "$TRANSFER" ]]; then
    die "no access to the data ($TRANSFER is not readable)"
  fi
  zip="$TRANSFER/$name"
fi
[[ -f "$zip" || "$zip" == *.zip || ! -f "$zip.zip" ]] || zip="$zip.zip"
[[ -f "$zip" ]] || die "$(basename "$zip") does not exist"
[[ -r "$zip" ]] || die "no access to the data ($(basename "$zip") is not readable)"
command -v unzip >/dev/null || die "unzip is not installed"

# 2. Where it goes
mkdir -p "$outdir" || die "cannot create $outdir"
outdir=$(cd "$outdir" && pwd)
stem=$(basename "$zip" .zip)
dataset="$outdir/$stem"

if [[ -e "$dataset" && $force -eq 0 ]]; then
  if [[ -d "$dataset/optical" || -d "$dataset/charge" ]]; then
    echo "Already unzipped: $dataset"
    echo "(use --force to unzip again)"
    echo "$dataset"
    exit 0
  fi
  die "$dataset exists but has no optical/ or charge/ folder; move or delete it first"
fi

# 3. Check the ZIP and the free space
echo "Checking $zip"
unzip -tq "$zip" >/dev/null || die "$(basename "$zip") is damaged or not a ZIP file"
need=$(unzip -Zt "$zip" | awk '{print $3}')
avail=$(df -Pk "$outdir" | awk 'NR==2 {print $4 * 1024}')
if [[ -n "$need" && -n "$avail" ]] && (( need > avail )); then
  die "not enough space in $outdir: need $((need / 1048576)) MiB, have $((avail / 1048576)) MiB"
fi

# 4. Unzip into a temporary folder first, so a failure leaves nothing behind
tmp=$(mktemp -d "$outdir/.unzip_${stem}.XXXXXX") || die "cannot write to $outdir"
trap 'rm -rf "$tmp"' EXIT
echo "Unzipping $(basename "$zip") ($((need / 1048576)) MiB)"
unzip -q "$zip" -d "$tmp" || die "unzipping $(basename "$zip") failed"
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

# Only now replace an old folder (--force), so a failed unzip keeps it.
if [[ -e "$dataset" ]]; then
  rm -rf "$dataset" || die "cannot remove the old $dataset"
fi
mv "$root" "$dataset" || die "cannot move the unzipped data to $dataset"
rm -rf "$tmp"
trap - EXIT

n_opt=$(find "$dataset/optical" -mindepth 1 -maxdepth 1 -type d ! -name results 2>/dev/null | wc -l)
n_chg=$(find "$dataset/charge" -mindepth 1 -maxdepth 1 -type d ! -name results 2>/dev/null | wc -l)
echo "Done: $((n_opt)) optical runs, $((n_chg)) charge runs"
echo "$dataset"
