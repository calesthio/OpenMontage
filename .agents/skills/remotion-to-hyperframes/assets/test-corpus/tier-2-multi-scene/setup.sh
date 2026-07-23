#!/usr/bin/env bash
# setup.sh — generate the binary assets this fixture needs.
#
# Both Remotion and HyperFrames variants need a 200x200 blue PNG and a
# 6-second silent WAV. Generating them via ffmpeg keeps binaries out of
# the repo while still letting the fixture render reproducibly.
#
# Run from the fixture root: ./setup.sh

set -euo pipefail

THIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "error: ffmpeg not on PATH" >&2
  exit 2
fi

mkdir -p "$THIS_DIR/remotion-src/public" "$THIS_DIR/hf-src/assets"

# 200x200 solid blue PNG, ~200 bytes.
ffmpeg -y -hide_banner -loglevel error \
  -f lavfi -i "color=color=#3066be:size=200x200" -frames:v 1 \
  "$THIS_DIR/remotion-src/public/square.png"
cp "$THIS_DIR/remotion-src/public/square.png" "$THIS_DIR/hf-src/assets/square.png"

# 6-second silent WAV at 8 kHz mono. ~96 KB if checked in, but it is generated.
ffmpeg -y -hide_banner -loglevel error \
  -f lavfi -i "anullsrc=cl=mono:r=8000" -t 6 -acodec pcm_s16le \
  "$THIS_DIR/remotion-src/public/music.wav"
cp "$THIS_DIR/remotion-src/public/music.wav" "$THIS_DIR/hf-src/assets/music.wav"

echo "generated:"
ls -la "$THIS_DIR/remotion-src/public/" "$THIS_DIR/hf-src/assets/"
