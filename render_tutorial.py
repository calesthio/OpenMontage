#!/usr/bin/env python3
"""Deterministic tutorial-video render executor (Workflow B core).

Given an authored tutorial (a *.tutorial.cy.js spec + *.tutorial.json recipe +
committed *.timings.json), this re-captures the app with Cypress and renders a
finished tutorial video — clean recording + AI voiceover + burned captions +
intro/outro cards + optional music — with NO LLM in the loop. It is the piece
that makes the k8s "worker jobs only" model work; it deliberately re-renders a
locked recipe (see the Rule Zero note in the plan).

Narration comes from the `ttsd` sidecar (reusing the circuit-bid narration
core) or, with --narration-backend elevenlabs, straight from the ElevenLabs API
(tools/audio/elevenlabs_narrator.py, cached per clip). Use --offline-narration
to assemble with silent placeholder audio (from the committed timings) for
testing without ttsd/ElevenLabs/the demo app.

Assembly reuses OpenMontage tools where they fit (subtitle_gen for captions,
audio_mixer for music ducking) and drives ffmpeg directly for the rest. A valid
edit_decisions artifact is persisted so the run is legible and the richer
Remotion "Explainer" path is a drop-in later.

Usage:
  python render_tutorial.py --tutorial sales-tour \
      --client-dir /path/to/circuitauction-backoffice/client \
      --base-url https://<demo-host> --project-id sales-tour-demo
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
# Repo-local virtualenv fallback: when this script runs under an interpreter that
# lacks the requirements (e.g. the system python3 that hosts the MCP server), use
# the packages installed in ./.venv (`uv venv .venv && uv pip install -r requirements.txt`).
try:
    import jsonschema  # noqa: F401
except ImportError:
    import sysconfig as _sc
    _venv_sp = REPO_ROOT / ".venv" / "lib" / f"python{_sc.get_python_version()}" / "site-packages"
    if _venv_sp.is_dir():
        sys.path.append(str(_venv_sp))

from lib import tutorial as T  # noqa: E402
from lib.envfile import parse_env_file  # noqa: E402
from lib.checkpoint import init_project  # noqa: E402
from lib.paths import PROJECTS_DIR  # noqa: E402
from tools.audio.narration_client import NarrationError  # noqa: E402
from tools.capture import cypress_bridge as bridge  # noqa: E402

FPS = 30
AR = 48000
BG_HEX = "0x0f1216"


# --- tutorial resolution ----------------------------------------------------

def resolve_tutorial(client_dir: Path, name: str) -> dict:
    root = client_dir / "cypress" / "e2e-tutorials"
    specs = list(root.rglob(f"{name}.tutorial.cy.js"))
    if not specs:
        raise FileNotFoundError(f"No tutorial spec {name}.tutorial.cy.js under {root}")
    spec = specs[0]
    recipe_path = spec.with_name(f"{name}.tutorial.json")
    timings_path = spec.with_name(f"{name}.timings.json")
    recipe = json.loads(recipe_path.read_text()) if recipe_path.exists() else {}
    if not recipe_path.exists():
        print(f"WARN: no recipe {recipe_path.name} — using defaults (title from name).", file=sys.stderr)
    # Never let intro/outro cards render an empty string (Explainer would fall back
    # to the literal cut id, e.g. "intro"). Default the title from the tutorial name.
    if not recipe.get("title"):
        recipe["title"] = name.replace("-", " ").replace("_", " ").title()
    timings = json.loads(timings_path.read_text()) if timings_path.exists() else {}
    spec_rel = spec.relative_to(client_dir).as_posix()
    return {
        "spec": spec,
        "spec_rel": spec_rel,
        "recipe": recipe,
        "timings": timings,
        "timings_path": timings_path,
    }


# --- ffmpeg helpers ---------------------------------------------------------

def _run(cmd: list[str], cwd: Optional[str] = None) -> None:
    subprocess.run(cmd, check=True, cwd=cwd)


def silent_wav(duration_s: float, out: Path, ar: int = AR) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"anullsrc=r={ar}:cl=mono",
        "-t", f"{max(0.1, duration_s):.3f}", "-c:a", "pcm_s16le", str(out),
    ])
    return out


def narration_bed(clips: list[tuple[float, Path]], total_s: float, out: Path, ar: int = AR) -> Path:
    """Place each (start_s, wav) onto a silent bed of length total_s -> one wav."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if not clips:
        return silent_wav(total_s, out, ar)
    cmd = ["ffmpeg", "-y", "-v", "error",
           "-f", "lavfi", "-i", f"anullsrc=r={ar}:cl=mono"]
    for _, wav in clips:
        cmd += ["-i", str(wav)]
    parts = []
    labels = ["0:a"]
    for idx, (start_s, _) in enumerate(clips, start=1):
        ms = max(0, int(round(start_s * 1000)))
        parts.append(f"[{idx}:a]adelay=delays={ms}:all=1[a{idx}]")
        labels.append(f"a{idx}")
    mix = "".join(f"[{l}]" for l in labels)
    fc = ";".join(parts) + f";{mix}amix=inputs={len(labels)}:normalize=0:duration=first[out]"
    cmd += ["-filter_complex", fc, "-map", "[out]",
            "-t", f"{total_s:.3f}", "-c:a", "pcm_s16le", str(out)]
    _run(cmd)
    return out


def loop_music(music: Path, duration_s: float, out: Path, base_vol: float = T.MUSIC_VOLUME, ar: int = AR) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    fade_out_start = max(0.0, duration_s - 1.5)
    af = f"volume={base_vol},afade=t=in:st=0:d=1.0,afade=t=out:st={fade_out_start:.3f}:d=1.5"
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-stream_loop", "-1", "-i", str(music),
        "-t", f"{duration_s:.3f}", "-af", af,
        "-ar", str(ar), "-ac", "1", "-c:a", "pcm_s16le", str(out),
    ])
    return out


def duck_music(narration: Path, music_bed: Path, out: Path) -> Path:
    """Duck music under narration via audio_mixer; fall back to ffmpeg sidechain.
    The fallback is LOGGED (never silent) so a swallowed import can't quietly
    change how the mix sounds; its attack/release (200/500ms) match audio_mixer's
    ducking defaults."""
    try:
        from tools.audio.audio_mixer import AudioMixer

        res = AudioMixer().execute({
            "operation": "duck",
            "primary_audio": str(narration),
            "secondary_audio": str(music_bed),
            "output_path": str(out),
            "duck_level": -14,
        })
        if getattr(res, "success", False) and out.exists():
            return out
        print(f"WARN audio_mixer duck did not succeed ({getattr(res, 'error', '?')}); "
              "using ffmpeg sidechain fallback", file=sys.stderr)
    except Exception as e:  # noqa: BLE001
        print(f"WARN audio_mixer unavailable ({e}); using ffmpeg sidechain fallback", file=sys.stderr)
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-i", str(narration), "-i", str(music_bed),
        "-filter_complex",
        "[1:a][0:a]sidechaincompress=threshold=0.03:ratio=8:attack=200:release=500[m];"
        "[0:a][m]amix=inputs=2:normalize=0:duration=first[out]",
        "-map", "[out]", "-c:a", "pcm_s16le", str(out),
    ])
    return out


def card_clip(png: Path, duration_s: float, out: Path, target: tuple[int, int]) -> Path:
    tw, th = target
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-loop", "1", "-i", str(png),
        "-f", "lavfi", "-i", f"anullsrc=r={AR}:cl=stereo",
        "-t", f"{duration_s:.3f}",
        "-vf", f"scale={tw}:{th},setsar=1,format=yuv420p",
        "-r", str(FPS),
        "-c:v", "libx264", "-crf", "20", "-preset", "medium",
        "-c:a", "aac", "-ar", str(AR), "-ac", "2",
        "-shortest", str(out),
    ])
    return out


def _srt_style(recipe: dict) -> str:
    return (
        "FontName=DejaVu Sans,FontSize=22,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,MarginV=48,Alignment=2"
    )


def burn_and_mux(video: Path, audio: Path, srt: Optional[Path], out: Path,
                 target: tuple[int, int], recipe: dict) -> Path:
    tw, th = target
    vf = f"scale={tw}:{th},setsar=1,format=yuv420p"
    cwd = None
    if srt and srt.exists():
        # Reference the SRT by basename from its own dir so the filtergraph never
        # embeds a path with special chars (':', apostrophes) that break ffmpeg's
        # lavfi quoting. Input/output stay absolute (passed as argv, not in-filter).
        cwd = str(srt.parent)
        vf += f",subtitles={srt.name}:force_style='{_srt_style(recipe)}'"
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-i", str(video), "-i", str(audio),
        "-vf", vf, "-r", str(FPS),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-crf", "20", "-preset", "medium",
        "-c:a", "aac", "-ar", str(AR), "-ac", "2",
        "-shortest", str(out),
    ], cwd=cwd)
    return out


def concat_av(clips: list[Path], out: Path) -> Path:
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for c in clips:
        cmd += ["-i", str(c)]
    streams = "".join(f"[{i}:v][{i}:a]" for i in range(len(clips)))
    fc = f"{streams}concat=n={len(clips)}:v=1:a=1[v][a]"
    cmd += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-crf", "20", "-preset", "medium",
            "-c:a", "aac", "-ar", str(AR), "-ac", "2",
            "-movflags", "faststart", str(out)]
    _run(cmd)
    return out


# --- narrators --------------------------------------------------------------

class OfflineNarrator:
    """Silent placeholder audio using durations from the committed timings."""

    def __init__(self, durations_ms: list[int]):
        self.durations_ms = durations_ms

    def render(self, lang: str, text: str, index: int, out_wav: Path) -> int:
        dur = self.durations_ms[index] if 0 <= index < len(self.durations_ms) else 1500
        silent_wav(dur / 1000.0, out_wav)
        return dur


class ClientNarrator:
    """Adapter from a narration client (ttsd or ElevenLabs) to the step narrator API."""

    def __init__(self, client):
        self.client = client

    def render(self, lang: str, text: str, index: int, out_wav: Path) -> int:
        return self.client.render(lang, text, str(out_wav))


def timings_voice_warning(timings: dict, backend: str, voice_id: str) -> Optional[str]:
    """Pacing guard: timings.json durations were measured with one voice; a
    different voice/backend speaks at a different pace, so the capture no
    longer lines up. Returns the warning text, or None when consistent/unknown."""
    rec = (timings or {}).get("narration") or {}
    if not rec:
        return None
    old_backend = rec.get("backend") or ""
    old_voice = rec.get("voice_id") or ""
    if old_backend == backend and old_voice == voice_id:
        return None
    return (
        f"WARN: timings.json was authored with backend={old_backend or '?'} "
        f"voice_id={old_voice or '(per-lang default)'} but this render uses "
        f"backend={backend} voice_id={voice_id or '(per-lang default)'}. Durations "
        "(and therefore capture pacing) may differ — re-run author_tutorial.py with "
        "the same backend/voice and re-capture."
    )


# --- main -------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Render a tutorial video from a Cypress spec.")
    ap.add_argument("--tutorial", required=True, help="tutorial name (e.g. sales-tour)")
    ap.add_argument("--client-dir", required=True, help="path to circuitauction-backoffice/client")
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--base-url", default=None, help="demo app URL to record against")
    ap.add_argument("--narration-url", default="http://127.0.0.1:5557")
    ap.add_argument("--narration-backend", choices=list(T.NARRATION_BACKENDS), default=None,
                    help="ttsd (sidecar at --narration-url) or elevenlabs (direct API; needs "
                         "ELEVENLABS_API_KEY and ELEVENLABS_VOICE_IDS or --voice-id). "
                         "Default: recipe.narration_backend, else $TUTORIAL_NARRATION_BACKEND, else ttsd.")
    ap.add_argument("--voice-id", default=None,
                    help="ElevenLabs voice id override. Default: recipe.voice_id, else "
                         "$TUTORIAL_VOICE_ID, else the per-language voice.")
    ap.add_argument("--offline-narration", action="store_true",
                    help="use silent placeholder audio from timings (no ttsd)")
    ap.add_argument("--music", default=None, help="music file (else recipe.music_track in music_library/)")
    ap.add_argument("--render-runtime", choices=["ffmpeg", "remotion"], default=None,
                    help="ffmpeg: self-contained assembly. remotion: render the Explainer "
                         "screencast_scene (animated callouts/zoom) — needs remotion-composer/"
                         "node_modules. Default: recipe.render_runtime, else ffmpeg.")
    ap.add_argument("--intro-seconds", type=float, default=3.0)
    ap.add_argument("--outro-seconds", type=float, default=3.0)
    ap.add_argument("--capture", default=None,
                    help="use an existing raw capture mp4 instead of running Cypress (testing)")
    ap.add_argument("--manifest", default=None,
                    help="manifest json to use with --capture (testing)")
    return ap


def main() -> int:
    args = build_arg_parser().parse_args()

    client_dir = Path(args.client_dir).resolve()
    tut = resolve_tutorial(client_dir, args.tutorial)
    recipe = tut["recipe"]
    lang = recipe.get("lang", "en")
    env = {**parse_env_file(REPO_ROOT / ".env"), **os.environ}  # shell wins over .env
    try:
        backend, voice_id = T.resolve_narration_choice(
            cli_backend=args.narration_backend, cli_voice_id=args.voice_id,
            recipe=recipe, env=env,
        )
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    target = (1920, 1080)
    # Runtime: explicit CLI wins, else the recipe can pin it (so the same tutorial
    # renders identically locally and on the cluster), else ffmpeg.
    runtime = args.render_runtime or recipe.get("render_runtime") or "ffmpeg"
    if runtime not in ("ffmpeg", "remotion"):
        print(f"ERROR: invalid render_runtime {runtime!r} (from recipe/CLI)", file=sys.stderr)
        return 2

    project_dir = init_project(
        args.project_id,
        title=recipe.get("title", args.tutorial),
        pipeline_type="screen-demo",
    )
    assets = project_dir / "assets"
    (assets / "audio").mkdir(parents=True, exist_ok=True)
    (assets / "video").mkdir(parents=True, exist_ok=True)

    # 1) Capture (or reuse a provided raw capture for testing).
    if args.capture:
        if not args.manifest:
            print("ERROR: --capture requires --manifest. Step timings, regions and drift "
                  "markers come from the capture manifest; timings.json alone places every "
                  "step at t=0.", file=sys.stderr)
            return 2
        manifest = json.loads(Path(args.manifest).read_text())
        raw_video = args.capture
    else:
        manifest = bridge.run_tutorial_spec(str(client_dir), tut["spec_rel"], base_url=args.base_url)
        raw_video = manifest.get("video")
        if not raw_video:
            print("ERROR: capture produced no video", file=sys.stderr)
            return 2

    # 2) Normalize: recover step times, crop marker strip, letterbox to 1080p.
    capture_mp4 = assets / "video" / "capture.mp4"
    norm = bridge.normalize_capture(raw_video, manifest, str(capture_mp4), target=target)
    body_duration = norm["body_duration_s"]

    # 3) Steps + timings.
    steps = T.steps_from_manifest(manifest)
    timings_steps = (tut["timings"] or {}).get("steps", [])
    durations_ms = [0] * (max([s.index for s in steps], default=-1) + 1)
    for ts in timings_steps:
        i = int(ts.get("index", -1))
        if 0 <= i < len(durations_ms):
            durations_ms[i] = int(ts.get("duration_ms", 0))

    # 4) Narration. Only go silent when EXPLICITLY offline — otherwise synthesize
    #    via ttsd (HttpNarrator needs no pre-existing durations), so a missing
    #    timings.json never silently ships a silent "successful" video.
    if args.offline_narration:
        narrator = OfflineNarrator(durations_ms if any(durations_ms) else [1500] * len(steps))
    else:
        if not any(durations_ms):
            print("WARN: no committed timings.json for this tutorial — the capture was not "
                  f"paced to the narration. Synthesizing fresh via {backend}; run author_tutorial.py "
                  "to commit timings and re-capture for correct pacing.", file=sys.stderr)
        warn = timings_voice_warning(tut["timings"], backend, voice_id)
        if warn:
            print(warn, file=sys.stderr)
        try:
            client = T.narration_client_for(
                backend, narration_url=args.narration_url, voice_id=voice_id, env=env,
            )
        except (ValueError, NarrationError) as e:
            print(f"ERROR: narration backend {backend!r} not ready: {e}", file=sys.stderr)
            return 2
        narrator = ClientNarrator(client)

    clips: list[tuple[float, Path]] = []
    for st in steps:
        if not st.narration:
            continue
        wav = assets / "audio" / f"step_{st.index}.wav"
        dur_ms = narrator.render(lang, st.narration, st.index, wav)
        if st.index < len(durations_ms):
            durations_ms[st.index] = dur_ms

    T.apply_durations(steps, durations_ms)
    # Primary: marker times (already relative to the trimmed start). Fallback:
    # manifest t_ms (imprecise for the preamble — see the drift note in the plan).
    T.assign_start_times(steps, norm.get("marker_times_s") or None, lead_offset_s=0.0)
    for st in steps:
        if st.narration and st.duration_s > 0:
            clips.append((st.video_start_s, assets / "audio" / f"step_{st.index}.wav"))

    music_path = _resolve_music(args.music, recipe)
    final = project_dir / "renders" / "final.mp4"
    final.parent.mkdir(parents=True, exist_ok=True)
    artifacts = project_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)

    # 5) Render via the chosen runtime. Build ONLY the audio that runtime needs
    #    (no double mix) and emit props/edit_decisions that match what shipped.
    srt_path: Optional[Path] = None
    if runtime == "remotion":
        # One full-timeline narration+music track drives the Remotion <Audio>.
        body_audio = build_full_audio(assets, clips, args.intro_seconds, body_duration,
                                      args.outro_seconds, music_path)
        props = T.build_remotion_props(
            steps, str(capture_mp4), body_duration, recipe,
            intro_s=args.intro_seconds, outro_s=args.outro_seconds,
            narration_audio_path=str(body_audio), music_path=None,
        )
        (artifacts / "remotion_props.json").write_text(json.dumps(props, indent=2))
        _run_remotion(artifacts / "remotion_props.json", final)
    else:
        body_audio, srt_path = render_ffmpeg_assembly(
            project_dir, assets, capture_mp4, steps, clips, body_duration, recipe,
            music_path, args.intro_seconds, args.outro_seconds, final, target)
        # Reference props for re-rendering via Remotion (the mp4 carries its own audio).
        props = T.build_remotion_props(
            steps, str(capture_mp4), body_duration, recipe,
            intro_s=args.intro_seconds, outro_s=args.outro_seconds,
            narration_audio_path=None, music_path=None,
        )
        (artifacts / "remotion_props.json").write_text(json.dumps(props, indent=2))

    # 6) edit_decisions + a best-effort completed `compose` checkpoint so the
    #    Backlot board reflects the run that actually produced final.mp4.
    ed = T.build_edit_decisions(
        steps, str(capture_mp4), body_duration,
        intro_s=args.intro_seconds, outro_s=args.outro_seconds, recipe=recipe,
        narration_audio_path=str(body_audio),
        subtitles_path=str(srt_path) if srt_path else None,
        music_path=str(music_path) if music_path else None,
        render_runtime=runtime,
    )
    (artifacts / "edit_decisions.json").write_text(json.dumps(ed, indent=2))
    _record_checkpoint(args.project_id, str(final),
                       args.intro_seconds + body_duration + args.outro_seconds, runtime, target)

    print(f"OK final render ({runtime}): {final}")
    return 0


def build_full_audio(assets: Path, clips, intro_s: float, body_duration: float,
                     outro_s: float, music_path: Optional[Path]) -> Path:
    """Narration placed on the FULL composition timeline (intro-offset), optionally
    ducked under music. This single track drives the Remotion <Audio> layer and is
    referenced by remotion_props.json."""
    total = intro_s + body_duration + outro_s
    full_clips = [(intro_s + start, wav) for (start, wav) in clips]
    narr = narration_bed(full_clips, total, assets / "audio" / "narration_full.wav")
    if music_path:
        bed = loop_music(music_path, total, assets / "music" / "music_bed.wav")
        return duck_music(narr, bed, assets / "audio" / "final_audio.wav")
    return narr


def render_ffmpeg_assembly(project_dir: Path, assets: Path, capture_mp4: Path, steps, clips,
                           body_duration: float, recipe: dict, music_path: Optional[Path],
                           intro_s: float, outro_s: float, final: Path,
                           target: tuple) -> tuple[Path, Optional[Path]]:
    """v1 self-contained ffmpeg render: narrated+captioned body between title cards.
    Returns (body_audio_path, srt_path) for the edit_decisions record."""
    narr = narration_bed(clips, body_duration, assets / "audio" / "narration.wav")
    if music_path:
        bed = loop_music(music_path, body_duration, assets / "music" / "music_bed_body.wav")
        body_audio = duck_music(narr, bed, assets / "audio" / "body_audio.wav")
    else:
        body_audio = narr
    srt = _build_srt(steps, project_dir)
    intro_png = T.make_title_card(str(assets / "images" / "intro.png"),
                                  recipe.get("intro_text", recipe.get("title", "")),
                                  recipe.get("intro_subtitle", ""))
    outro_png = T.make_title_card(str(assets / "images" / "outro.png"),
                                  recipe.get("outro_text", "Thanks for watching"),
                                  recipe.get("outro_subtitle", ""))
    intro_mp4 = card_clip(Path(intro_png), intro_s, assets / "video" / "intro.mp4", target)
    outro_mp4 = card_clip(Path(outro_png), outro_s, assets / "video" / "outro.mp4", target)
    body_final = burn_and_mux(capture_mp4, Path(body_audio), srt,
                              assets / "video" / "body_final.mp4", target, recipe)
    concat_av([intro_mp4, body_final, outro_mp4], final)
    return Path(body_audio), srt


def _record_checkpoint(project_id: str, final_path: str, duration_s: float,
                       runtime: str, target: tuple) -> None:
    """Best-effort completed `compose` checkpoint (an ungated stage) so the Backlot
    board shows the run that produced final.mp4. Writes the stage's canonical
    render_report artifact (schema-validated). Non-fatal — the render succeeded."""
    try:
        from lib.checkpoint import write_checkpoint

        render_report = {
            "version": "1.0",
            "outputs": [{
                "path": final_path,
                "format": "mp4",
                "resolution": f"{target[0]}x{target[1]}",
                "duration_seconds": round(duration_s, 3),
            }],
        }
        write_checkpoint(
            PROJECTS_DIR, project_id, "compose", "completed",
            {"render_report": render_report},
            pipeline_type="screen-demo",
            metadata={"origin": "cypress-tutorial", "render_runtime": runtime,
                      "note": "deterministic render_tutorial executor (not the agent pipeline)"},
        )
    except Exception as e:  # noqa: BLE001
        print(f"WARN could not write compose checkpoint: {e}", file=sys.stderr)


def _run_remotion(props_path: Path, out: Path) -> Path:
    """Render the Explainer composition (screencast_scene body + callouts) via Remotion."""
    composer = REPO_ROOT / "remotion-composer"
    if not (composer / "node_modules").exists():
        raise RuntimeError(
            f"remotion-composer/node_modules missing — run `npm install` in {composer}, "
            "or build the worker image with --build-arg INSTALL_REMOTION=true."
        )
    subprocess.run(
        ["npx", "remotion", "render", "src/index.tsx", "Explainer", str(out),
         f"--props={props_path}"],
        cwd=str(composer), check=True,
    )
    return out


def _resolve_music(cli_music: Optional[str], recipe: dict) -> Optional[Path]:
    """Resolve --music or recipe.music_track against a literal path first, then
    music_library/. Warns (never silently drops) when a requested track is missing."""
    track = cli_music or recipe.get("music_track")
    if not track:
        return None
    for cand in (Path(track), REPO_ROOT / "music_library" / track):
        if cand.exists():
            return cand
    print(f"WARN: music '{track}' not found (checked as a path and in music_library/) — "
          "rendering without music.", file=sys.stderr)
    return None


def _build_srt(steps, project_dir: Path) -> Optional[Path]:
    segments = T.build_subtitle_segments(steps)
    if not segments:
        return None
    try:
        from tools.subtitle.subtitle_gen import SubtitleGen

        srt = project_dir / "assets" / "subtitles.srt"
        SubtitleGen().execute({
            "segments": segments,
            "format": "srt",
            "output_path": str(srt),
            "highlight_style": "none",
        })
        return srt if srt.exists() else None
    except Exception as e:  # noqa: BLE001
        print(f"WARN subtitle_gen failed: {e}", file=sys.stderr)
        return None


if __name__ == "__main__":
    raise SystemExit(main())
