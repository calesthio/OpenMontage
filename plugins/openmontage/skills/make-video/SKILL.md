---
name: make-video
description: Make videos with OpenMontage, an agentic video production system. Use when the user asks to make, create, produce, edit or render a video, trailer, explainer, short, reel, clip, animation or montage, asks for a video like one they link, or mentions OpenMontage.
argument-hint: [what to make]
---

# OpenMontage

OpenMontage runs from a local checkout of https://github.com/calesthio/OpenMontage. This skill finds that checkout and hands the request to its own agent guide.

## 1. Find the checkout

Use the first of these that contains both `AGENT_GUIDE.md` and `pipeline_defs/`:

1. The current project directory
2. `$OPENMONTAGE_HOME`
3. `~/OpenMontage`

## 2. No checkout yet

Ask the user before installing: it clones the repository and installs its Python and Node dependencies. Check the prerequisites first: git, Python 3.10+, Node.js 18+ and FFmpeg. Then run:

```bash
git clone https://github.com/calesthio/OpenMontage.git "${OPENMONTAGE_HOME:-$HOME/OpenMontage}"
cd "${OPENMONTAGE_HOME:-$HOME/OpenMontage}" && make setup
```

Without `make`, use the "No `make`?" commands under Quick Start in the checkout's `README.md`.

## 3. Hand over

- Read `AGENT_GUIDE.md` in the checkout and follow it before acting on the request. It decides the first step and is the contract for everything after.
- Every path in OpenMontage's guides and skills is relative to the checkout. Run commands from the checkout (`cd <checkout> && ...`) with its `.venv`.
- Projects and renders go under `<checkout>/projects/`. Tell the user where the finished video is saved.
- If the checkout is outside the session's working directories, suggest `/add-dir <checkout>` so reading and writing its files doesn't prompt.

Request: $ARGUMENTS
