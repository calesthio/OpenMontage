"""
documentary_story_engine.py
Continuous Single-Documentary Story Short Engine for OpenMontage.

Compiles a 9:16 vertical Short where ALL B-roll clips come sequentially from a
SINGLE 1080p/4K documentary source, guaranteeing visual continuity (matching
subject, lighting, and environment).

Pipeline per scene:
  1. Synthesize AI voiceover (ElevenLabs or Edge-TTS deep narrator)
  2. Select matching action SFX
  3. Mix multi-track audio (voice + SFX + ducked BGM)
  4. Crop 16:9 source to 1080x1920 (9:16) vertical canvas
  5. Overlay hook banner (top) and subtitle captions (bottom safe zone)
  6. Concatenate all scenes into final deliverable MP4
"""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any, Optional, Union

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

DOCUMENTS_DIR = ROOT_DIR / "assets" / "documentaries"
AUDIO_DIR = ROOT_DIR / "assets" / "audio"
SFX_DIR = AUDIO_DIR / "sfx"
BGM_DIR = AUDIO_DIR / "bgm"

_DEFAULT_VOICE = "en-US-ChristopherNeural"

FONT_CANDIDATES = [
    # Windows
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/impact.ttf",
    "C:/Windows/Fonts/Arial.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    # macOS
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/TTF/Arial.ttf",
]


def _find_bold_font() -> str:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return path.replace(":", "\\:")
    return "Arial"  # FFmpeg fontconfig fallback


def _escape_ffmpeg_text(text: str) -> str:
    safe = text.replace("\\", "\\\\")
    safe = safe.replace(":", " -")
    safe = safe.replace("'", "\\\\\\'")
    return safe


def _escape_ffmpeg_path(path: Path) -> str:
    """Escape a filesystem path for an FFmpeg filter argument."""
    return path.resolve().as_posix().replace(":", "\\:")


class DocumentaryStoryEngine:
    def __init__(
        self,
        animal: str,
        project_dir: Optional[Path] = None,
        source_url: Optional[str] = None,
    ):
        self.animal = animal.lower().strip().replace(" ", "_")
        self.root_dir = ROOT_DIR
        self.animal_dir = DOCUMENTS_DIR / self.animal
        self.project_dir = project_dir or (ROOT_DIR / "projects" / f"doc_short_{self.animal}")
        self.temp_dir = self.project_dir / "temp"
        self.output_dir = self.project_dir / "output"
        self.font = _find_bold_font()
        self.source_url = source_url

        for d in (self.project_dir, self.temp_dir, self.output_dir):
            d.mkdir(parents=True, exist_ok=True)

        self.doc_file, self.story_clips = self._ensure_documentary_and_clips()

    # ------------------------------------------------------------------
    #  Discover / download / segment
    # ------------------------------------------------------------------

    def _ensure_documentary_and_clips(self):
        doc_file = self.animal_dir / f"{self.animal}_doc_source_01.mp4"
        if self.source_url or not doc_file.exists() or doc_file.stat().st_size < 500_000:
            from lib.documentary_source_downloader import DocumentarySourceDownloader
            dl = DocumentarySourceDownloader()
            doc_file = dl.download_documentary(
                self.animal,
                resolution="1080p",
                max_duration_s=360,
                search_query=self.source_url,
                force=bool(self.source_url),
            )

        manifest_path = self.animal_dir / "story_clips.json"
        if not manifest_path.exists():
            from lib.documentary_clipper import DocumentaryClipper
            clipper = DocumentaryClipper(doc_file)
            clips_data = clipper.segment_documentary()
        else:
            clips_data = json.loads(manifest_path.read_text(encoding="utf-8"))

        return doc_file, clips_data.get("clips", [])

    # ------------------------------------------------------------------
    #  SFX lookup
    # ------------------------------------------------------------------

    def select_action_sfx(self, text: str) -> Optional[Path]:
        t = text.lower()
        if any(w in t for w in ("roar", "strike", "power", "king", "growl")):
            if self.animal == "lion" and (SFX_DIR / "roar_lion_01.wav").exists():
                return SFX_DIR / "roar_lion_01.wav"
            if (SFX_DIR / "roar_tiger_01.wav").exists():
                return SFX_DIR / "roar_tiger_01.wav"
        if any(w in t for w in ("howl", "pack", "cry")):
            return self._existing_sfx("wolf_howl_01.wav")
        if any(w in t for w in ("chase", "run", "sprint", "charge", "burst")):
            return self._existing_sfx("sub_impact_01.wav")
        return self._existing_sfx("whoosh_01.wav")

    @staticmethod
    def _existing_sfx(name: str) -> Optional[Path]:
        p = SFX_DIR / name
        return p if p.exists() else None

    # ------------------------------------------------------------------
    #  Narration
    # ------------------------------------------------------------------

    def _tts_elevenlabs(self, text: str, output_wav: Path) -> bool:
        key = os.environ.get("ELEVENLABS_API_KEY")
        if not key:
            return False
        try:
            import urllib.request
            url = "https://api.elevenlabs.io/v1/text-to-speech/21m00Tcm4TlvDq8ikWAM"
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": key,
            }
            body = json.dumps({
                "text": text,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            }).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers=headers)
            tmp = output_wav.with_suffix(".tmp.mp3")
            with urllib.request.urlopen(req) as resp:
                tmp.write_bytes(resp.read())
            subprocess.run([
                "ffmpeg", "-y", "-i", str(tmp),
                "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", str(output_wav),
            ], capture_output=True, text=True, check=True)
            tmp.unlink(missing_ok=True)
            return output_wav.stat().st_size > 500
        except Exception as e:
            print(f"     [WARN] ElevenLabs: {e}")
            return False

    def _tts_edge(self, text: str, voice: str, output_wav: Path) -> bool:
        try:
            import edge_tts
            import asyncio
            tmp = output_wav.with_suffix(".tmp.mp3")

            async def _go():
                comm = edge_tts.Communicate(text, voice, pitch="-8Hz", rate="-5%")
                await comm.save(str(tmp))

            asyncio.run(_go())
            subprocess.run([
                "ffmpeg", "-y", "-i", str(tmp),
                "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", str(output_wav),
            ], capture_output=True, text=True, check=True)
            tmp.unlink(missing_ok=True)
            return output_wav.stat().st_size > 500
        except Exception as e:
            print(f"     [WARN] Edge-TTS: {e}")
            return False

    def synthesize_narration(self, text: str, voice: str, output_wav: Path) -> float:
        if self._tts_elevenlabs(text, output_wav):
            pass
        elif self._tts_edge(text, voice, output_wav):
            pass
        else:
            print("     [WARN] TTS unavailable, using tone fallback…")
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", f"sine=frequency=220:duration={max(2, len(text) * 0.08):.1f}",
                "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", str(output_wav),
            ], capture_output=True, text=True, check=True)

        res = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(output_wav)],
            capture_output=True, text=True,
        )
        return float(json.loads(res.stdout)["format"]["duration"])

    # ------------------------------------------------------------------
    #  Render pipeline
    # ------------------------------------------------------------------

    def render_continuous_short(
        self,
        script_data: dict[str, Any],
        output_path: Optional[Path] = None,
        use_original_audio: bool = False,
    ) -> Path:
        output_file = output_path or (self.output_dir / f"{self.animal}_documentary_short.mp4")
        title = script_data.get("title", f"The Story of the {self.animal.title()}")
        banner = script_data.get("hook_banner", f"{self.animal.upper()}: UNTAMED")
        voice = script_data.get("voice", _DEFAULT_VOICE)
        scenes: list[dict[str, Any]] = script_data.get("scenes", [])

        if not scenes:
            raise ValueError("script_data must contain a non-empty 'scenes' list")

        print(f"\n[ENGINE] Compiling '{title}' ({self.animal})")
        print(f"         Source: {self.doc_file.relative_to(ROOT_DIR)}")
        print(f"         Clips indexed: {len(self.story_clips)}")
        print(f"         Audio Mode: {'ORIGINAL SOURCE AUDIO & ANIMAL SOUNDS' if use_original_audio else 'SYNTHESIZED NARRATION + SFX'}")
        print(f"         Font: {self.font}\n")

        rendered_scenes: list[Path] = []
        bgm_track = BGM_DIR / "nature_suspense_bgm.wav"

        for idx, scene in enumerate(scenes):
            text = scene["text"]
            clip_info = self.story_clips[idx % len(self.story_clips)]
            broll_start = clip_info["start_time"]

            print(f"  Scene {idx + 1}/{len(scenes)}  |  clip_{clip_info['sequence_index']:02d}  "
                  f"({clip_info['behavior']})  @ {broll_start:.1f}s")
            print(f"           Narration: \"{text[:72]}{'...' if len(text) > 72 else ''}\"")

            # ---- Audio ----
            if use_original_audio:
                audio_dur = min(max(3.5, float(clip_info.get("duration", 4.5))), 6.5)
                mixed_audio = None
                print(f"           Source Audio Track: {audio_dur:.1f}s (retaining original voice & ambient sounds)")
            else:
                scene_voice = self.temp_dir / f"scene_{idx + 1:02d}_voice.wav"
                audio_dur = self.synthesize_narration(text, voice, scene_voice)
                print(f"           Voice: {audio_dur:.1f}s")

                action_sfx = self.select_action_sfx(text)
                mixed_audio = self.temp_dir / f"scene_{idx + 1:02d}_mix.wav"
                self._mix_audio(scene_voice, action_sfx, bgm_track, audio_dur, mixed_audio)

            # ---- Video ----
            scene_video = self.temp_dir / f"scene_{idx + 1:02d}_render.mp4"
            self._render_scene(
                broll_start, audio_dur, text, banner, mixed_audio, scene_video,
            )
            rendered_scenes.append(scene_video)

        # ---- Join with short dissolves instead of hard stream-copy cuts ----
        print(f"\n[TRANSITIONS] Joining {len(rendered_scenes)} scenes with dissolves…")
        self._join_scenes_with_dissolves(rendered_scenes, output_file)

        final_size = output_file.stat().st_size
        print(f"[DONE] {output_file}  ({final_size / (1024 * 1024):.1f} MB)")
        return output_file

    def _join_scenes_with_dissolves(
        self, scene_files: list[Path], output_file: Path, transition_s: float = 0.18
    ) -> None:
        if len(scene_files) == 1:
            subprocess.run([
                "ffmpeg", "-y", "-i", str(scene_files[0]), "-c", "copy", str(output_file),
            ], capture_output=True, text=True, check=True)
            return

        durations: list[float] = []
        for scene_file in scene_files:
            probe = subprocess.run([
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_entries", "format=duration", str(scene_file),
            ], capture_output=True, text=True, check=True)
            durations.append(float(json.loads(probe.stdout)["format"]["duration"]))

        inputs = [item for scene_file in scene_files for item in ("-i", str(scene_file))]
        filters: list[str] = []
        for i in range(len(scene_files)):
            filters.append(f"[{i}:v]settb=AVTB,format=yuv420p[v{i}]")
            filters.append(f"[{i}:a]aresample=44100:async=1:first_pts=0[a{i}]")

        video_label = "v0"
        audio_label = "a0"
        elapsed = durations[0]
        for i in range(1, len(scene_files)):
            next_video = f"vx{i}"
            next_audio = f"ax{i}"
            offset = max(0.01, elapsed - transition_s)
            filters.append(
                f"[{video_label}][v{i}]xfade=transition=fade:duration={transition_s}:"
                f"offset={offset:.3f}[{next_video}]"
            )
            filters.append(
                f"[{audio_label}][a{i}]acrossfade=d={transition_s}:c1=tri:c2=tri[{next_audio}]"
            )
            video_label = next_video
            audio_label = next_audio
            elapsed = elapsed + durations[i] - transition_s

        subprocess.run([
            "ffmpeg", "-y", *inputs,
            "-filter_complex", ";".join(filters),
            "-map", f"[{video_label}]", "-map", f"[{audio_label}]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", str(output_file),
        ], capture_output=True, text=True, check=True)

    def _mix_audio(
        self,
        voice_path: Path,
        sfx_path: Optional[Path],
        bgm_path: Path,
        duration: float,
        out_path: Path,
    ) -> None:
        if sfx_path and sfx_path.exists():
            print(f"           SFX: {sfx_path.name}")
            filter_expr = (
                "[0:a]volume=1.0[v];[1:a]volume=0.45[s];[2:a]volume=0.13[b];"
                "[v][s][b]amix=inputs=3:duration=first[out]"
            )
            subprocess.run([
                "ffmpeg", "-y",
                "-i", str(voice_path),
                "-i", str(sfx_path),
                "-stream_loop", "-1", "-i", str(bgm_path),
                "-t", str(duration),
                "-filter_complex", filter_expr,
                "-map", "[out]",
                "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                str(out_path),
            ], capture_output=True, text=True, check=True)
        else:
            filter_expr = (
                "[0:a]volume=1.0[v];[1:a]volume=0.13[b];"
                "[v][b]amix=inputs=2:duration=first[out]"
            )
            subprocess.run([
                "ffmpeg", "-y",
                "-i", str(voice_path),
                "-stream_loop", "-1", "-i", str(bgm_path),
                "-t", str(duration),
                "-filter_complex", filter_expr,
                "-map", "[out]",
                "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                str(out_path),
            ], capture_output=True, text=True, check=True)

    def _render_scene(
        self,
        broll_start: float,
        audio_dur: float,
        caption: str,
        banner: str,
        audio_path: Path,
        out_path: Path,
    ) -> None:
        # textfile avoids drawtext parser failures and lets us wrap captions
        # deterministically before FFmpeg renders them.
        caption_file = self.temp_dir / f"caption_{out_path.stem}.txt"
        banner_file = self.temp_dir / f"banner_{out_path.stem}.txt"
        caption_file.write_text("\n".join(textwrap.wrap(caption, width=42)), encoding="utf-8")
        banner_file.write_text(banner.replace(":", " - "), encoding="utf-8")
        caption_ref = _escape_ffmpeg_path(caption_file)
        banner_ref = _escape_ffmpeg_path(banner_file)

        draw_banner = (
            f"drawtext=fontfile='{self.font}':"
            f"textfile='{banner_ref}':"
            f"fontcolor=yellow:fontsize=46:"
            f"x=(w-text_w)/2:y=150:"
            f"box=1:boxcolor=black@0.58:boxborderw=14:fix_bounds=1"
        )
        draw_caption = (
            f"drawtext=fontfile='{self.font}':"
            f"textfile='{caption_ref}':"
            f"fontcolor=white:fontsize=36:"
            f"x=(w-text_w)/2:y=1370:"
            f"box=1:boxcolor=black@0.58:boxborderw=14:line_spacing=10:fix_bounds=1"
        )

        vf_full = (
            "split=2[bg][fg];"
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,boxblur=22:2,eq=brightness=-0.16[bgv];"
            # A 4:5 editorial window avoids the extreme 16:9 -> 9:16 punch-in
            # while keeping the subject materially larger than a letterboxed fit.
            "[fg]crop=ih*4/5:ih:(iw-ow)/2:0,scale=1080:1350,"
            "format=yuva420p,pad=1080:1920:(ow-iw)/2:285:color=black@0[fgv];"
            "[bgv][fgv]overlay=0:0:format=auto,"
            f"{draw_banner},"
            f"{draw_caption}"
        )

        if audio_path is not None and Path(audio_path).exists():
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(broll_start),
                "-i", str(self.doc_file),
                "-i", str(audio_path),
                "-t", str(audio_dur),
                "-vf", vf_full,
                "-map", "0:v:0", "-map", "1:a:0", "-shortest",
                "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                str(out_path),
            ]
        else:
            # Retain pristine original audio, surrounding soundscape, and natural animal sounds from the documentary source
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(broll_start),
                "-i", str(self.doc_file),
                "-t", str(audio_dur),
                "-vf", vf_full,
                "-map", "0:v:0", "-map", "0:a:0?", "-shortest",
                "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                str(out_path),
            ]

        res = subprocess.run(cmd, capture_output=True, text=True)

        if res.returncode != 0:
            print(f"           [WARN] Text overlay failed, rendering basic crop…")
            vf_basic = (
                "scale=1080:-2:force_original_aspect_ratio=decrease,"
                "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black"
            )
            if audio_path is not None and Path(audio_path).exists():
                fallback_cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(broll_start),
                    "-i", str(self.doc_file), "-i", str(audio_path),
                    "-t", str(audio_dur), "-vf", vf_basic,
                    "-map", "0:v:0", "-map", "1:a:0", "-shortest",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k",
                    str(out_path),
                ]
            else:
                fallback_cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(broll_start),
                    "-i", str(self.doc_file),
                    "-t", str(audio_dur), "-vf", vf_basic,
                    "-map", "0:v:0", "-map", "0:a:0?", "-shortest",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k",
                    str(out_path),
                ]
            subprocess.run(fallback_cmd, capture_output=True, text=True, check=True)


if __name__ == "__main__":
    import sys
    animal = sys.argv[1] if len(sys.argv) > 1 else "tiger"

    test_script = {
        "title": f"The Untamed {animal.title()}",
        "hook_banner": f"{animal.upper()}: WILD RULE",
        "voice": _DEFAULT_VOICE,
        "scenes": [
            {"text": f"In the untamed wild, the {animal} moves with silent, lethal grace."},
            {"text": "Every muscle coiled, every instinct sharpened by millennia of evolution."},
            {"text": "When it strikes, the force is overwhelming and absolute."},
            {"text": f"This is the {animal} — the undisputed sovereign of its domain."},
        ],
    }
    engine = DocumentaryStoryEngine(animal=animal)
    engine.render_continuous_short(test_script)
