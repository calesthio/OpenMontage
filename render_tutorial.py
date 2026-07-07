#!/usr/bin/env python3
"""Deterministic tutorial-video render executor (Workflow B core).

Given an authored tutorial (a *.tutorial.cy.js spec + *.tutorial.json recipe +
committed *.timings.json), this re-captures the app with Cypress and renders a
finished tutorial video — clean recording + AI voiceover + burned captions +
intro/outro cards + optional music — with NO LLM in the loop. It is the piece
that makes the k8s "worker jobs only" model work; it deliberately re-renders a
locked recipe (see the Rule Zero note in the plan).

Narration is fetched from the `ttsd` sidecar (reusing the circuit-bid narration
core). Use --offline-narration to assemble with silent placeholder audio (from
the committed timings) for testing without ttsd/ElevenLabs/the demo app.

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
import subprocess
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from lib import tutorial as T  # noqa: E402
from lib.checkpoint import init_project  # noqa: E402
from lib.paths import PROJECTS_DIR  # noqa: E402
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

def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


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


def loop_music(music: Path, duration_s: float, out: Path, base_vol: float = 0.22, ar: int = AR) -> Path:
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
    """Reuse audio_mixer to duck music under narration; fall back to ffmpeg."""
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
    except Exception:
        pass
    # ffmpeg sidechain fallback
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
    if srt and srt.exists():
        srt_esc = str(srt).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
        vf += f",subtitles='{srt_esc}':force_style='{_srt_style(recipe)}'"
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-i", str(video), "-i", str(audio),
        "-vf", vf, "-r", str(FPS),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-crf", "20", "-preset", "medium",
        "-c:a", "aac", "-ar", str(AR), "-ac", "2",
        "-shortest", str(out),
    ])
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


class HttpNarrator:
    def __init__(self, base_url: str):
        from tools.audio.narration_client import NarrationClient

        self.client = NarrationClient(base_url)

    def render(self, lang: str, text: str, index: int, out_wav: Path) -> int:
        return self.client.render(lang, text, str(out_wav))


# --- main -------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Render a tutorial video from a Cypress spec.")
    ap.add_argument("--tutorial", required=True, help="tutorial name (e.g. sales-tour)")
    ap.add_argument("--client-dir", required=True, help="path to circuitauction-backoffice/client")
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--base-url", default=None, help="demo app URL to record against")
    ap.add_argument("--narration-url", default="http://127.0.0.1:5557")
    ap.add_argument("--offline-narration", action="store_true",
                    help="use silent placeholder audio from timings (no ttsd)")
    ap.add_argument("--music", default=None, help="music file (else recipe.music_track in music_library/)")
    ap.add_argument("--render-runtime", choices=["ffmpeg", "remotion"], default="ffmpeg",
                    help="ffmpeg: self-contained assembly (default). remotion: render the "
                         "Explainer screencast_scene (animated callouts/zoom) — needs "
                         "remotion-composer/node_modules.")
    ap.add_argument("--intro-seconds", type=float, default=3.0)
    ap.add_argument("--outro-seconds", type=float, default=3.0)
    ap.add_argument("--capture", default=None,
                    help="use an existing raw capture mp4 instead of running Cypress (testing)")
    ap.add_argument("--manifest", default=None,
                    help="manifest json to use with --capture (testing)")
    args = ap.parse_args()

    client_dir = Path(args.client_dir).resolve()
    tut = resolve_tutorial(client_dir, args.tutorial)
    recipe = tut["recipe"]
    lang = recipe.get("lang", "en")
    target = (1920, 1080)

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
        manifest = json.loads(Path(args.manifest).read_text()) if args.manifest else tut["timings"]
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

    # 4) Narration.
    if args.offline_narration or not durations_ms or all(d == 0 for d in durations_ms):
        narrator = OfflineNarrator(durations_ms if any(durations_ms) else [1500] * len(steps))
    else:
        narrator = HttpNarrator(args.narration_url)

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

    # 5) Full-timeline narration track + Remotion props. Emitted for both runtimes:
    #    the remotion runtime renders straight from these, and they document the v2
    #    screencast scene (animated callouts/zoom) for the ffmpeg runtime too.
    full_audio = build_full_audio(assets, clips, args.intro_seconds, body_duration,
                                  args.outro_seconds, music_path)
    props = T.build_remotion_props(
        steps, str(capture_mp4), body_duration, recipe,
        intro_s=args.intro_seconds, outro_s=args.outro_seconds,
        narration_audio_path=str(full_audio), music_path=None,
    )
    props_path = project_dir / "artifacts" / "remotion_props.json"
    props_path.parent.mkdir(parents=True, exist_ok=True)
    props_path.write_text(json.dumps(props, indent=2))

    # 6) Render via the chosen runtime.
    if args.render_runtime == "remotion":
        _run_remotion(props_path, final)
    else:
        render_ffmpeg_assembly(project_dir, assets, capture_mp4, steps, clips,
                               body_duration, recipe, music_path,
                               args.intro_seconds, args.outro_seconds, final, target)

    # 7) Persist edit_decisions (render_runtime reflects the chosen path).
    ed = T.build_edit_decisions(
        steps, str(capture_mp4), body_duration,
        intro_s=args.intro_seconds, outro_s=args.outro_seconds, recipe=recipe,
        narration_audio_path=str(full_audio),
        music_path=str(music_path) if music_path else None,
        render_runtime=args.render_runtime,
    )
    (project_dir / "artifacts" / "edit_decisions.json").write_text(json.dumps(ed, indent=2))

    print(f"OK final render ({args.render_runtime}): {final}")
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
                           target: tuple) -> Path:
    """v1 self-contained ffmpeg render: narrated+captioned body between title cards."""
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
    return final


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
    if cli_music:
        p = Path(cli_music)
        return p if p.exists() else None
    track = recipe.get("music_track")
    if not track:
        return None
    p = REPO_ROOT / "music_library" / track
    return p if p.exists() else None


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
