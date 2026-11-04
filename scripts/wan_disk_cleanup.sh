#!/usr/bin/env bash
#
# Reclaim disk used by local Wan video generation.
#
# Local generation is free of API cost but not of disk: the Wan 2.2 TI2V-5B
# checkpoint alone is ~32GB, the CUDA-enabled virtualenv is ~7GB, and uv keeps
# every wheel it has ever downloaded.
#
# Nothing is deleted unless you pass a target. Without --yes it only reports.
#
#   ./scripts/wan_disk_cleanup.sh                  # show what is on disk
#   ./scripts/wan_disk_cleanup.sh --models --yes   # delete Wan model weights
#   ./scripts/wan_disk_cleanup.sh --all --yes      # weights + venv + uv cache
#
# Deleted weights are re-downloaded automatically on the next run, so this is
# safe to run whenever you need the space back.

set -euo pipefail

HF_HOME_DIR="${HF_HOME:-$HOME/.cache/huggingface}"
HUB_DIR="$HF_HOME_DIR/hub"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv-wan"
UV_CACHE_DIR="${UV_CACHE_DIR:-$HOME/.cache/uv}"

# Only these are touched by --models. Other repos in the shared HF cache
# (OCR models, LLMs, anything another project put there) are left alone.
WAN_PATTERNS=(
    "models--Wan-AI--*"
    "models--FastVideo--FastWan*"
    "models--lightx2v--Wan*"
    "models--Comfy-Org--Wan*"
    "models--QuantStack--Wan*"
)

DO_MODELS=0; DO_VENV=0; DO_UV=0; CONFIRM=0

for arg in "$@"; do
    case "$arg" in
        --models) DO_MODELS=1 ;;
        --venv)   DO_VENV=1 ;;
        --uv-cache) DO_UV=1 ;;
        --all)    DO_MODELS=1; DO_VENV=1; DO_UV=1 ;;
        --yes|-y) CONFIRM=1 ;;
        -h|--help) sed -n '2,20p' "$0" | sed 's/^# \?//'; exit 0 ;;
        *) echo "Unknown option: $arg (try --help)" >&2; exit 2 ;;
    esac
done

human () { du -sh "$1" 2>/dev/null | cut -f1; }

# Expand the Wan patterns into real paths.
wan_paths () {
    local pattern path
    for pattern in "${WAN_PATTERNS[@]}"; do
        for path in "$HUB_DIR"/$pattern; do
            [ -e "$path" ] && printf '%s\n' "$path"
        done
    done
}

echo "=== Current usage ==="
if [ -d "$HUB_DIR" ]; then
    total_wan=0
    while IFS= read -r path; do
        printf '  %-8s %s\n' "$(human "$path")" "$(basename "$path")"
        total_wan=$(( total_wan + $(du -sk "$path" 2>/dev/null | cut -f1) ))
    done < <(wan_paths)
    [ "$total_wan" -gt 0 ] \
        && printf '  %-8s Wan model weights (total)\n' "$(( total_wan / 1024 / 1024 ))G" \
        || echo "  (no Wan weights cached)"
    printf '  %-8s entire HF cache at %s\n' "$(human "$HF_HOME_DIR")" "$HF_HOME_DIR"
fi
[ -d "$VENV_DIR" ]     && printf '  %-8s %s\n' "$(human "$VENV_DIR")" "$VENV_DIR"
[ -d "$UV_CACHE_DIR" ] && printf '  %-8s %s\n' "$(human "$UV_CACHE_DIR")" "$UV_CACHE_DIR"
echo

if [ $((DO_MODELS + DO_VENV + DO_UV)) -eq 0 ]; then
    echo "Nothing selected. Pass --models, --venv, --uv-cache or --all (add --yes to delete)."
    exit 0
fi

targets=()
[ "$DO_MODELS" -eq 1 ] && while IFS= read -r path; do targets+=("$path"); done < <(wan_paths)
[ "$DO_VENV" -eq 1 ] && [ -d "$VENV_DIR" ] && targets+=("$VENV_DIR")
[ "$DO_UV" -eq 1 ] && [ -d "$UV_CACHE_DIR" ] && targets+=("$UV_CACHE_DIR")

if [ "${#targets[@]}" -eq 0 ]; then
    echo "Nothing to delete."
    exit 0
fi

echo "=== Would delete ==="
for path in "${targets[@]}"; do printf '  %-8s %s\n' "$(human "$path")" "$path"; done
echo

if [ "$CONFIRM" -ne 1 ]; then
    echo "Dry run. Re-run with --yes to actually delete."
    exit 0
fi

for path in "${targets[@]}"; do
    echo "removing $path"
    rm -rf -- "$path"
done

echo
echo "Done. Free space now:"
df -h "$HOME" | tail -1
echo
echo "To rebuild: model weights re-download on the next wan_video run;"
echo "recreate the venv with"
echo "  uv venv --python 3.12 .venv-wan"
echo "  uv pip install --python .venv-wan/bin/python torch torchvision --index-url https://download.pytorch.org/whl/cu128"
echo "  uv pip install --python .venv-wan/bin/python 'diffusers>=0.36' transformers accelerate safetensors sentencepiece imageio imageio-ffmpeg ftfy protobuf"
