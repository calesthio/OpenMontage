#!/bin/bash
# MOSS-TTS MLX Setup for Apple Silicon
# Downloads MOSS-TTS-Nano-100M + MOSS-Audio-Tokenizer-Nano via aria2c (fast, resumable)
# Layout required by tools/audio/moss_tts.py and mlx_audio:
#   moss-tts-mlx/moss-tts-nano/                     <- LLM + config
#   moss-tts-mlx/moss-tts-nano/audio_tokenizer/     <- codec (found locally, no HF fetch at runtime)

set -e

# Resolve repo root from this script's location (scripts/ -> repo root)
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MOSS_DIR="$REPO_ROOT/moss-tts-mlx"
MODEL_DIR="$MOSS_DIR/moss-tts-nano"
TOK_DIR="$MODEL_DIR/audio_tokenizer"
ARIA2C="${ARIA2C:-$(command -v aria2c || echo /opt/homebrew/bin/aria2c)}"

AUTH_ARGS=()
if [ -n "$HF_TOKEN" ]; then
    AUTH_ARGS=(--header="Authorization: Bearer $HF_TOKEN")
    echo "Using HF_TOKEN for authenticated downloads"
fi

echo "=== MOSS-TTS MLX Setup ==="
mkdir -p "$MODEL_DIR" "$TOK_DIR"

# --- Python deps (system python; mlx-audio already installed there) ---
if ! python3 -c "import mlx_audio" >/dev/null 2>&1; then
    echo "Installing mlx-audio..."
    python3 -m pip install "mlx-audio[tts]" soundfile librosa sounddevice huggingface_hub
fi

fetch() { # fetch <url> <dest_dir>
    local fname="${1##*/}"
    ( cd "$2" && "$ARIA2C" -x 16 -s 16 -k 4M --continue=true --file-allocation=none \
        --max-tries=0 --retry-wait=3 -o "$fname" "${AUTH_ARGS[@]}" "$1" )
}

# --- Nano LLM (default; fits 16GB unified memory, ~0.4GiB total) ---
if ! ls "$MODEL_DIR"/model.safetensors >/dev/null 2>&1; then
    echo "Downloading MOSS-TTS-Nano-100M (LLM ~272MB)..."
    for f in config.json model.safetensors special_tokens_map.json tokenizer.model tokenizer_config.json ; do
        fetch "https://huggingface.co/mlx-community/MOSS-TTS-Nano-100M/resolve/main/$f" "$MODEL_DIR"
    done
else
    echo "Nano LLM already present."
fi

# --- Nano codec (inside model dir; ~84MB) ---
if ! ls "$TOK_DIR"/model-*.safetensors >/dev/null 2>&1; then
    echo "Downloading MOSS-Audio-Tokenizer-Nano (codec ~84MB)..."
    for f in config.json model.safetensors.index.json model-00001-of-00001.safetensors ; do
        fetch "https://huggingface.co/OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano/resolve/main/$f" "$TOK_DIR"
    done
else
    echo "Nano codec already present."
fi

echo ""
echo "=== Setup Complete ==="
echo "Model:      $MODEL_DIR"
echo "Codec:      $TOK_DIR"
echo "Verify:     python3 -c \"from tools.audio.moss_tts import MossTTS; print(MossTTS().get_status())\""
