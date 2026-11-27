# Shared helpers for the optical stage scripts (sourced, not run).
#
#   decode.sh  raw .tpx3 (once, on import) -> decoded_data/<dataset>/optical/<run>/
#   fit.sh     decoded HDF5         -> <results>[/before]/optical/<run>/   (spark cut + fits)
#   plot.sh    one fit folder       -> <that folder>/plots/
#   pair.sh    before/ + top level  -> <results>/plots/optical_per_run/   (before/after pairs)

REPO=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
BUILD="${WARTPC_BUILD:-$REPO/build}"
BLACKBOX="${WARTPC_BLACKBOX:-$REPO/blackbox}"
PYTHON="${WARTPC_PYTHON:-python3}"

die() { echo "$(basename -- "$0"): $*" >&2; exit 1; }

# Load the Hammer modules once (no-op on a machine without environment modules).
load_environment() {
  [[ -n "${WARTPC_ENV_LOADED:-}" || -n "${WARTPC_NO_SETUP:-}" ]] && return 0
  local setup="${BLACKBOX_SETUP:-$BLACKBOX/setup_blackbox.sh}"
  if ! type module >/dev/null 2>&1 && [[ -n "${MODULESHOME:-}${LMOD_CMD:-}" && -f /etc/profile ]]; then
    set +u; source /etc/profile; set -u
  fi
  if type module >/dev/null 2>&1 && [[ -f "$setup" ]]; then
    echo "# environment: $setup"
    set +u; source "$setup" || die "cannot load $setup"; set -u
  fi
  export WARTPC_ENV_LOADED=1
}

# Run folders (excluding results/) directly inside $1, sorted.
list_run_dirs() {
  [[ -d "$1" ]] || return 0
  find "$1" -mindepth 1 -maxdepth 1 \( -type d -o -type l \) ! -name results ! -name '.*' \
    -exec basename {} \; | sort
}

# select_runs <available...> -- sets SELECTED from $RUN_SELECTION (comma list
# of names or quoted patterns such as 'vr22-1*'; empty or "all" = every run).
select_runs() {
  local available=("$@") tok r found
  SELECTED=()
  if [[ -z "${RUN_SELECTION:-}" || "$RUN_SELECTION" == all ]]; then
    SELECTED=("${available[@]+"${available[@]}"}")
    return 0
  fi
  for tok in ${RUN_SELECTION//,/ }; do
    found=0
    for r in "${available[@]+"${available[@]}"}"; do
      # shellcheck disable=SC2053  # pattern match on purpose
      if [[ "$r" == $tok ]]; then
        [[ " ${SELECTED[*]+"${SELECTED[*]}"} " == *" $r "* ]] || SELECTED+=("$r")
        found=1
      fi
    done
    [[ $found -eq 1 ]] || die "no run matches '$tok'"
  done
}

# Dataset name used in plot legends: <stem> from <stem>_results[-NN].
dataset_name() {
  local base
  base=$(basename -- "$1")
  base=${base%_results*}
  printf '%s' "$base"
}
