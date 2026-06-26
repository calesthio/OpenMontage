---
name: synthetic-screen-recording
description: Synthetic terminal-style screen recording guidance for Remotion `TerminalScene`.
license: MIT
---

# Synthetic Screen Recording (Remotion TerminalScene)

**Decision this skill answers:** When the user wants a screen-recording-looking demo of a terminal, CLI tool, or coding workflow — do I **capture the real desktop** (OS screen recording via `screen_recorder`, Windows-MCP, Cap, or Playwright), or do I **synthesize it in Remotion** with the `TerminalScene` component?

> **Heuristic:** If the agent can author the exact command/output sequence in advance, synthesize. Only capture live when the real behavior is unpredictable, needs a real app UI, or the user explicitly asked for a real recording.

## Why this exists

v3 of the OpenMontage showcase tried to use Windows-MCP + `screen_recorder` to drive a Git-Bash window for the install walkthrough. It stalled on window positioning, focus races, and taskbar privacy concerns. We pivoted to **pure Remotion rendering** — a React component named `TerminalScene` that draws a fake terminal and types commands character-by-character. The output is visually indistinguishable from a real screen recording (same traffic-light window chrome, blinking cursor, scrolling output) but deterministic, privacy-safe, pixel-perfect at 1080p, and pace-controllable to the frame.

That component + pattern is the capability this skill makes discoverable.

## When to use synthetic (TerminalScene)

**YES, synthesize when:**
- The demo is a **terminal / CLI / coding session** where commands and outputs are predictable
- The user wants a polished tutorial feel (clean typography, floating pills, cursor blink)
- Install walkthroughs, setup demos, API key config, `make` targets, `git clone` flows
- You need tight sync with narration — every command must land on a specific beat
- You want the result reproducible (re-render gets identical pixels)
- The user's actual desktop has private apps/windows visible you'd otherwise have to crop

**NO, capture a real screen when:**
- The demo is **a real app UI** that can't be faked (Figma, Photoshop, a web app with live state, a browser flow)
- The user explicitly asked for a recording of *their* actual screen
- The behavior depends on timing you can't script (streaming LLM output, real network latency)
- There's a visual quirk (a cursor effect, a plugin pop-up) that only appears in the live environment

**For a browser demo** → `playwright-recording` skill, not this one.
**For a real desktop** → `screen_recorder` tool or Cap via `cap_recorder`.

## The component — `TerminalScene`

Located at: `remotion-composer/src/components/TerminalScene.tsx`
Exported from: `remotion-composer/src/components/index.ts`
Wired in dispatch: `remotion-composer/src/Explainer.tsx` (`if (cut.type === "terminal_scene")`)

**Props:**
```ts
interface TerminalSceneProps {
  title?: string;           // shown in the window title bar
  steps: TerminalStep[];    // the timeline
  prompt?: string;          // "$", ">", etc.
  accentColor?: string;     // pill + prompt glow
  backgroundColor?: string;
}
```

**Step kinds:**
```ts
{ kind: "cmd",   text: string, typeSpeed?: number, holdSeconds?: number }
{ kind: "out",   text: string, holdSeconds?: number }
{ kind: "pause", seconds: number }
{ kind: "pill",  text: string, color?: string, durationSeconds?: number }
```

- `cmd` — prints the prompt, types the text character-by-character (`typeSpeed` is seconds per character, default 0.035), then holds for `holdSeconds` (default 0.3)
- `out` — a line of program output, reveals instantly with a short fade-in
- `pause` — dead time. Terminal holds on last visible state. USE THIS TO SYNC WITH NARRATION.
- `pill` — non-blocking floating badge (top-right). Spring-in, hold, spring-out. Does NOT advance the cursor — the next step runs in parallel.

## Authoring pattern

Author a new scene by adding a cut to `build_composition.py` (or your equivalent props builder):

```python
install_steps = [
    {"kind": "pause", "seconds": 7.0},                 # wait for intro narration
    {"kind": "cmd", "text": "git clone https://github.com/calesthio/OpenMontage.git",
     "typeSpeed": 0.045, "holdSeconds": 0.3},
    {"kind": "out", "text": "Cloning into 'OpenMontage'..."},
    {"kind": "out", "text": "remote: Enumerating objects: 2847, done."},
    {"kind": "pill", "text": "repo cloned", "color": "#34D399", "durationSeconds": 2.6},
    {"kind": "pause", "seconds": 3.8},                 # bridge to next narration cue
    # ...
]

cuts.append({
    "id": "install-terminal",
    "type": "terminal_scene",
    "terminalTitle": "bash — OpenMontage setup",
    "prompt": "$",
    "accentColor": "#22D3EE",
    "steps": install_steps,
    "in_seconds": 50.0,
    "out_seconds": 110.0,
})
```

## THE RULE: pace with narration, never ahead

**The #1 failure mode:** steps run continuously and burn through all content in the first 40% of the scene, leaving the terminal frozen for the remaining 60%. This is what killed the v3 first pass — the capability menu rendered at t=80s but narration didn't announce it until t=92s.

**Do this instead:**

1. **Know your narration cues** — for each scene, write down the exact video-time each narration segment starts.
2. **Start with a pause** that reaches the first narration cue before any command types.
3. **Time each command to land with its narration line** — `cmd` should start typing the moment narration says its line, not before.
4. **Put pauses between command groups** that bridge to the next narration cue.
5. **End with a closer hold** — a pause long enough that the final state is readable after narration ends.

**Sanity-check your steps before rendering** — every minute of Remotion render is precious. Sum the step durations and verify they equal scene duration:

```python
import math
def trace(steps, scene_start, fps=30):
    t = 0.0
    for s in steps:
        k = s["kind"]
        if k == "cmd":
            tf = math.ceil(len(s["text"]) * s.get("typeSpeed", 0.035) * fps)
            t += tf / fps + s.get("holdSeconds", 0.3)
        elif k == "out":
            t += max(2, math.ceil(0.08 * fps)) / fps + s.get("holdSeconds", 0.15)
        elif k == "pause":
            t += s["seconds"]
        # "pill" is non-blocking — does NOT advance cursor
        print(f"  {t + scene_start:6.2f}s  {k}: {s.get('text', '')[:40]}")
trace(install_steps, 50)
```

Look at the output column. Each narration cue's video-time must appear adjacent to the command/output it announces. If a command lands 10s before or after its cue, adjust pauses.

See `lib/verify_scene_pacing.py` for a reusable version of this script.

## Design rules (inherited from the v3 retune)

- **Intro pause** — every terminal scene opens with at least 2s of empty-terminal-with-blinking-cursor before anything types. The viewer needs to register the window.
- **Pill timing** — a pill should fire at the exact moment its named event completes on screen (e.g., `repo cloned` immediately after the last `Receiving objects` line). Pills are your substitute for real-world UI notifications.
- **Command hold after typing** — keep `holdSeconds` ≥ 0.3 on every `cmd` so viewers register the completed command before the first output scrolls in.
- **Output cadence** — space `holdSeconds` on output lines between 0.4 and 1.0. Output that flies too fast feels like a bug; output that crawls feels boring.
- **Auto-scroll works** — the terminal holds the most recent 18 lines. Don't worry about off-screen content.
- **Cursor blinks only on the latest command line while typing + a ~0.2s tail** after typing completes.

## `ProviderChip` (companion component)

The `.agents/skills/synthetic-screen-recording` pattern also owns `ProviderChip` — a rotating badge overlay that cycles through a list of provider names at a fixed cadence. Used in the v3 showcase to cycle through all 11 AI video-gen providers during the "generated motion" section.

```python
overlays.append({
    "type": "provider_chip",
    "providers": ["Veo 3.1", "Seedance 2.0", "Kling 2.5", ...],
    "cycleSeconds": 2.5,
    "position": "bottom-right",
    "accentColor": "#22D3EE",
    "label": "generated with",
    "in_seconds": 195.0,
    "out_seconds": 222.5,
})
```

Wired in dispatch at: `remotion-composer/src/Explainer.tsx` overlay renderer (`overlay.type === "provider_chip"`).

## Adding new synthetic-UI components

The pattern generalizes. When you need to fake another UI surface (Claude Code chat bubbles, a Jira ticket view, a GitHub PR diff, a Slack message, a VS Code status bar):

1. Copy `TerminalScene.tsx` as a template.
2. Define a `steps` interface for the relevant timeline primitives.
3. Render each step by interpolating `frame` against cumulative start/end times.
4. Wire it into `Explainer.tsx`'s `SceneRenderer` dispatch with a new `cut.type`.
5. Add the type to the `Cut` interface in `Explainer.tsx` and to `components/index.ts`.
6. Add a section to this skill documenting it.
7. Update `remotion-composer/SCENE_TYPES.md` with the new cut type.

## Related skills

- `.agents/skills/remotion` — general Remotion authoring (hooks, springs, sequences)
- `.agents/skills/playwright-recording` — real browser-flow capture for web apps
- `tools/capture/screen_recorder` — ffmpeg-based desktop capture
- `tools/capture/cap_recorder` — Cap.so polished desktop capture
- `skills/pipelines/screen-demo/asset-director.md` — chooses between synthetic and real for a screen-demo project

## Provenance

Introduced: OpenMontage showcase v3 render (2026-04-16). Original motivation: the v3 setup walkthrough section needed a 60-second install demo where every command aligned to Chirp 3 HD narration cues, and Windows-MCP-driven real capture was too flaky in practice. See `projects/openmontage-showcase/build_composition.py` for the reference implementation.
