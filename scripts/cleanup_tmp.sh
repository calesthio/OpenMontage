#!/usr/bin/env bash
#
# scripts/cleanup_tmp.sh — reclaim /tmp scratch space used by OpenMontage runs.
#
# Disk rotation policy: /workspaces is small and must hold only deliverables
# (projects/<id>/artifacts, assets, renders). All throwaway scratch — smoke
# runs, Kaggle bridge round-trips, decoded frames, TTS segments — lives in /tmp
# and is cleaned from here.
#
# WHAT IT CLEANS (matched directly under /tmp, nothing deeper):
#   /tmp/p0_smoke                    P0 smoke-test workspace
#   /tmp/*_smoke                     other smoke workspaces (e.g. atlas_media_smoke)
#   /tmp/kilo/s<N>_out               Kaggle bridge outputs (s1..s15)
#   /tmp/kilo/s<N>_jobs              Kaggle bridge job scratch
#   /tmp/kaggle*                     `kaggle kernels output -p /tmp/kaggle_*` downloads
#   /tmp/*_frames, /tmp/frames_*     decoded frame sequences
#   /tmp/tts_output, /tmp/tts_jobs   TTS segment scratch
#
# WHAT IT NEVER TOUCHES:
#   docs/, projects/ (deliverables), anything outside /tmp, any git-tracked
#   file, any symlink, /tmp/kilo itself, /tmp/kilo/z1_venv (venv),
#   /tmp/kilo/kokoro_onnx_weights (model weights), and all other /tmp entries.
#
# Dry-run by default. Nothing is deleted without --force.
#
#   ./scripts/cleanup_tmp.sh                     # report only
#   ./scripts/cleanup_tmp.sh --age-days 1        # report only, skip entries < 1 day old
#   ./scripts/cleanup_tmp.sh --force             # actually delete
#   ./scripts/cleanup_tmp.sh --age-days 1 --force
#
# Exit codes: 0 = ok (dry run or deleted); 2 = bad usage; 3 = unsafe state.

set -euo pipefail

TMP_ROOT="${TMP_ROOT:-/tmp}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORCE=0
AGE_DAYS=0

usage () { sed -n '2,33p' "$0" | sed 's/^# \?//'; }

while [ "$#" -gt 0 ]; do
    case "$1" in
        --force)      FORCE=1; shift ;;
        --dry-run)    FORCE=0; shift ;;
        --age-days)   AGE_DAYS="${2:-}"; shift 2 ;;
        --age-days=*) AGE_DAYS="${1#*=}"; shift ;;
        -h|--help)    usage; exit 0 ;;
        *) echo "Unknown option: $1 (try --help)" >&2; exit 2 ;;
    esac
done

case "$AGE_DAYS" in
    ''|*[!0-9]*) echo "--age-days needs a non-negative integer" >&2; exit 2 ;;
esac

[ -d "$TMP_ROOT" ] || { echo "TMP_ROOT does not exist: $TMP_ROOT" >&2; exit 3; }
TMP_REAL="$(cd "$TMP_ROOT" && pwd -P)"
[ "$TMP_REAL" = "/" ] && { echo "Refusing to run with TMP_ROOT=/" >&2; exit 3; }

# Scratch globs, relative to TMP_ROOT. Keep this list short and explicit —
# anything not listed here is left alone.
PATTERNS=(
    "p0_smoke"
    "*_smoke"
    "kilo/s[0-9]*_out"
    "kilo/s[0-9]*_jobs"
    "kaggle*"
    "*_frames"
    "frames_*"
    "tts_output"
    "tts_jobs"
)

# Names that are never deleted even if a glob matches them.
DENY_NAMES=(docs projects .git node_modules z1_venv kilo)

human () { du -sh "$1" 2>/dev/null | cut -f1 || echo "?"; }
size_kb () { du -sk "$1" 2>/dev/null | cut -f1 || echo 0; }

# Return 0 (true) when the candidate is safe to delete.
is_safe () {
    local path="$1" real base rel depth

    [ -n "$path" ] || return 1
    [ -e "$path" ] || return 1
    [ -L "$path" ] && return 1                      # never follow/delete symlinks
    [ -d "$path" ] || return 1                      # directories only

    real="$(cd "$path" 2>/dev/null && pwd -P)" || return 1

    # Must live strictly inside TMP_ROOT.
    case "$real" in
        "$TMP_REAL"/*) ;;
        *) return 1 ;;
    esac

    # Must be at most two levels deep (e.g. /tmp/p0_smoke, /tmp/kilo/s7_out).
    rel="${real#"$TMP_REAL"/}"
    depth="$(awk -F/ '{print NF}' <<<"$rel")"
    [ "$depth" -le 2 ] || return 1

    base="$(basename "$real")"
    local denied
    for denied in "${DENY_NAMES[@]}"; do
        [ "$base" = "$denied" ] && return 1
    done

    # Model weights and venvs are expensive to rebuild — never scratch.
    case "$base" in
        *.onnx|*.safetensors|*.pt|*.pth|*.bin) return 1 ;;
    esac

    # Never touch the repository, its deliverables, or any tracked file.
    case "$real" in
        "$REPO_ROOT"|"$REPO_ROOT"/*) return 1 ;;
    esac
    if git -C "$REPO_ROOT" ls-files --error-unmatch -- "$real" >/dev/null 2>&1; then
        return 1
    fi

    return 0
}

# Expand patterns into a deduplicated candidate list.
declare -A SEEN=()
CANDIDATES=()
for pattern in "${PATTERNS[@]}"; do
    shopt -s nullglob
    for path in "$TMP_ROOT"/$pattern; do
        is_safe "$path" || continue
        real="$(cd "$path" 2>/dev/null && pwd -P)" || continue
        [ -n "${SEEN[$real]:-}" ] && continue
        # Staleness filter applies to the report and to deletion alike.
        if [ "$AGE_DAYS" -gt 0 ] && \
           [ -z "$(find "$real" -maxdepth 0 -mmin +$((AGE_DAYS * 1440)) 2>/dev/null)" ]; then
            continue
        fi
        SEEN[$real]=1
        CANDIDATES+=("$real")
    done
    shopt -u nullglob
done

echo "=== /tmp cleanup: ${TMP_ROOT} (dry-run unless --force) ==="
if [ "${#CANDIDATES[@]}" -eq 0 ]; then
    echo "  (no matching scratch directories)"
else
    printf '  %-8s %-8s %s\n' "SIZE" "AGE" "PATH"
    total_kb=0
    for path in "${CANDIDATES[@]}"; do
        age_days=$(( ( $(date +%s) - $(stat -c %Y "$path") ) / 86400 ))
        printf '  %-8s %-8s %s\n' "$(human "$path")" "${age_days}d" "$path"
        total_kb=$(( total_kb + $(size_kb "$path") ))
    done
    printf '  %-8s %-8s %s\n' "$(awk -v k="$total_kb" 'BEGIN{printf "%.1fM", k/1024}')" "" "total reclaimable"
fi
echo

if [ "${#CANDIDATES[@]}" -eq 0 ]; then
    echo "Nothing to do."
    exit 0
fi

if [ "$FORCE" -ne 1 ]; then
    echo "Dry run. Re-run with --force to delete the entries above."
    exit 0
fi

deleted=0
for path in "${CANDIDATES[@]}"; do
    echo "removing $path"
    rm -rf --one-file-system -- "$path"
    deleted=$(( deleted + 1 ))
done

echo
echo "Deleted $deleted entr(y|ies). Free space now:"
df -h "$TMP_ROOT" | tail -1
