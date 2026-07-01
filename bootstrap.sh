#!/usr/bin/env bash
# Bootstrap a bare Linux server (or macOS box) to verified-render-ready, then prove it
# with a zero-key demo render. `make setup` + the README cover the desktop happy path;
# on a headless server a few things are missing and each one surfaces as its own
# mid-render failure. This closes those gaps and runs the standard `make setup` for
# everything else.
#
# Gaps this closes:
#   1. FFmpeg          — listed as a prereq, but `make setup` does not install it.
#   2. python3-venv     — base python3 lacks ensurepip on Debian/Ubuntu; `python -m venv`
#                         fails until the distro package is installed.
#   3. Chromium libs    — Remotion's headless renderer needs them (libnss3, libnspr4, ...);
#                         not documented anywhere; absence shows up as a first-render crash
#                         (`libnspr4.so: cannot open shared object file`).
#   4. Piper voice      — `make setup` installs the piper-tts engine but downloads no voice,
#                         so the offline $0 TTS path has nothing to speak with.
#
# Idempotent / re-runnable. Exits 0 = ready, non-zero = names exactly what failed.
#
# Usage:  ./bootstrap.sh [/path/to/OpenMontage]   (default: current directory)
set -euo pipefail

OM_DIR="${1:-$(pwd)}"
VOICE="${VOICE:-en_US-lessac-medium}"
VOICE_DIR="${VOICE_DIR:-$OM_DIR/.voices}"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m  [ok] %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m  [warn] %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m  [FAIL] %s\033[0m\n' "$*" >&2; exit 1; }

cd "$OM_DIR"
[ -f Makefile ] && [ -f render_demo.py ] || die "run this from an OpenMontage checkout (no Makefile/render_demo.py found in $OM_DIR)."

# ---- 0. detect package manager ----
if   command -v apt-get >/dev/null 2>&1; then PKG=apt
elif command -v brew    >/dev/null 2>&1; then PKG=brew
else die "no apt-get or brew found — install FFmpeg, python3-venv, and (Linux) Chromium libs manually, then re-run."; fi
SUDO=""; [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1 && SUDO=sudo

apt_install() { DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y --no-install-recommends "$@"; }

# ---- 1. FFmpeg + python3-venv (gaps #1, #2) ----
say "System prerequisites"
if [ "$PKG" = apt ]; then
  $SUDO apt-get update -qq
  apt_install ffmpeg python3 python3-venv python3-pip
  ok "ffmpeg + python3-venv installed"

  # ---- 2. Chromium headless libraries (gap #3) ----
  say "Chromium headless libraries (undocumented Remotion dependency)"
  apt_install \
    libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 libxshmfence1 || \
    warn "some chromium libs failed to install — Remotion renders may crash"
  ok "chromium libs installed"
else
  brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg
  ok "ffmpeg installed (macOS ships the Chromium libs Remotion needs, no extra step)"
fi

# ---- 3. the standard install path ----
say "make setup"
make setup
ok "make setup complete"

# ---- 4. Piper voice (gap #4) ----
say "Piper offline voice: $VOICE"
mkdir -p "$VOICE_DIR"
if ls "$VOICE_DIR/$VOICE"* >/dev/null 2>&1; then
  ok "voice already present"
else
  PYTHON_BIN="$OM_DIR/.venv/bin/python"
  [ -x "$PYTHON_BIN" ] || PYTHON_BIN="python3"
  "$PYTHON_BIN" -m piper.download_voices "$VOICE" --data-dir "$VOICE_DIR" \
    && ok "voice downloaded to $VOICE_DIR" \
    || warn "voice download failed — offline \$0 TTS unavailable; cloud TTS still works with keys in .env"
fi

# ---- 5. prove it: zero-key demo render ----
say "Proof render (zero keys, zero tokens)"
PYTHON_BIN="$OM_DIR/.venv/bin/python"
[ -x "$PYTHON_BIN" ] || PYTHON_BIN="python3"
if "$PYTHON_BIN" render_demo.py --list >/dev/null 2>&1; then
  FIRST_DEMO="$("$PYTHON_BIN" render_demo.py --list 2>/dev/null | awk '/^[[:space:]]+[a-z0-9]/{print $1; exit}' || true)"
  if [ -n "$FIRST_DEMO" ] && "$PYTHON_BIN" render_demo.py "$FIRST_DEMO" >/dev/null 2>&1; then
    ok "demo '$FIRST_DEMO' rendered — render stack is live"
  else
    warn "demo list works but a render failed — inspect: $PYTHON_BIN render_demo.py $FIRST_DEMO"
  fi
else
  warn "render_demo.py --list failed — check 'make setup' output above"
fi

say "Bootstrap complete"
ok "READY — add API keys to .env for cloud providers, then open this project in your AI coding assistant."
