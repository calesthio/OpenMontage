"""
auto_short_engine.py
Automated Wildlife Short Video Production Engine for OpenMontage.

Takes a documentary script / narration beat list, automatically matches narration to
analyzed B-roll moments from `assets/source_clips/`, trims and crops video into 9:16 format,
synthesizes natural AI narration (ElevenLabs / Edge-TTS with deep narrator pitch tuning),
mixes multi-track audio (Voice + Action SFX + Ducked BGM), and renders a final Short video.
"""

import os
import sys
import json
import asyncio
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

# Ensure UTF-8 output
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

ROOT_DIR = Path(__file__).resolve().parent.parent
SOURCE_CLIPS_DIR = ROOT_DIR / "assets" / "source_clips"
BROLL_INDEX_PATH = SOURCE_CLIPS_DIR / "broll_index.json"
AUDIO_DIR = ROOT_DIR / "assets" / "audio"
SFX_DIR = AUDIO_DIR / "sfx"
BGM_DIR = AUDIO_DIR / "bgm"
FONT_PATH = "C:/Windows/Fonts/arialbd.ttf"


class AutoShortEngine:
    def __init__(self, project_dir: Optional[Path] = None):
        self.root_dir = ROOT_DIR
        self.source_clips_dir = SOURCE_CLIPS_DIR
        self.broll_index_path = BROLL_INDEX_PATH
        self.project_dir = project_dir or (ROOT_DIR / "projects" / "auto_short_production")
        self.temp_dir = self.project_dir / "temp"
        self.output_dir = self.project_dir / "output"

        for d in (self.project_dir, self.temp_dir, self.output_dir):
            d.mkdir(parents=True, exist_ok=True)

        self.broll_index = self._load_broll_index()
        self._ensure_audio_assets()

    def _ensure_audio_assets(self):
        """Ensures SFX and BGM audio assets exist."""
        if not (SFX_DIR / "whoosh_01.wav").exists() or not (BGM_DIR / "nature_suspense_bgm.wav").exists():
            print("🔊 Initializing SFX & BGM audio library...")
            from scripts.download_wildlife_audio import main as download_audio
            download_audio()

    def _load_broll_index(self) -> Dict[str, Any]:
        """Loads analyzed B-roll index."""
        if not self.broll_index_path.exists():
            print(f"⚠️ B-roll index missing at {self.broll_index_path}. Running analyzer first...")
            from lib.wildlife_broll_analyzer import WildlifeBrollAnalyzer
            analyzer = WildlifeBrollAnalyzer(self.source_clips_dir)
            return analyzer.analyze_all()

        with open(self.broll_index_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def match_narration_to_broll(self, text: str, target_animal: Optional[str] = None) -> Dict[str, Any]:
        """Matches a narration sentence to the best B-roll moment in the library."""
        text_lower = text.lower()
        moments = self.broll_index.get("broll_moments", [])

        # 1. Determine animal
        detected_animal = target_animal
        if not detected_animal:
            for animal in ["tiger", "lion", "elephant", "wolf", "bear", "snow_leopard", "crocodile", "eagle", "leopard", "cheetah"]:
                if animal.replace("_", " ") in text_lower or animal in text_lower:
                    detected_animal = animal
                    break
        if not detected_animal:
            detected_animal = "tiger"  # default fallback

        # 2. Determine behavior intent keywords
        behavior_keywords = {
            "hunting": ["hunt", "stalk", "chase", "strike", "prey", "prowl", "apex"],
            "running": ["run", "sprint", "speed", "fast", "flee", "charge"],
            "attacking": ["attack", "fight", "clash", "strike", "bite", "claw"],
            "eating": ["eat", "devour", "feed", "feast", "meat", "prey"],
            "drinking": ["drink", "water", "river", "thirst", "lake", "trunk"],
            "sleeping/resting": ["rest", "sleep", "lay", "laze", "shade", "sun", "quiet"],
            "social behavior": ["pride", "pack", "herd", "together", "bond", "cub", "play", "family"],
            "babies/cubs": ["baby", "cub", "young", "puppy", "calves", "infant"],
            "close-up": ["eyes", "roar", "gaze", "face", "power", "king", "jaw"],
            "natural habitat": ["savanna", "forest", "jungle", "snow", "mountain", "plain", "wild"]
        }

        matched_behavior = None
        for beh, kw_list in behavior_keywords.items():
            if any(kw in text_lower for kw in kw_list):
                matched_behavior = beh
                break

        # 3. Filter candidates
        candidates = [m for m in moments if m["animal"] == detected_animal]
        if not candidates:
            candidates = moments  # fallback

        scored_candidates = []
        for cand in candidates:
            score = 0.0
            if cand["animal"] == detected_animal:
                score += 5.0
            if matched_behavior and cand["behavior"] == matched_behavior:
                score += 4.0
            score += cand.get("motion_score", 0.5) * 2.0
            scored_candidates.append((score, cand))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        best_moment = scored_candidates[0][1] if scored_candidates else moments[0]
        return best_moment

    def select_action_sfx(self, text: str, animal: str) -> Optional[Path]:
        """Selects a matching action SFX based on text intent and animal."""
        t = text.lower()
        if "roar" in t or "strike" in t or "power" in t:
            if animal == "lion" and (SFX_DIR / "roar_lion_01.wav").exists():
                return SFX_DIR / "roar_lion_01.wav"
            elif (SFX_DIR / "roar_tiger_01.wav").exists():
                return SFX_DIR / "roar_tiger_01.wav"
        elif "howl" in t or "pack" in t:
            if (SFX_DIR / "wolf_howl_01.wav").exists():
                return SFX_DIR / "wolf_howl_01.wav"
        elif "chase" in t or "run" in t or "sprint" in t:
            if (SFX_DIR / "sub_impact_01.wav").exists():
                return SFX_DIR / "sub_impact_01.wav"

        # Default transition whoosh
        if (SFX_DIR / "whoosh_01.wav").exists():
            return SFX_DIR / "whoosh_01.wav"
        return None

    async def generate_narration_audio(self, text: str, voice: str, output_wav: Path) -> float:
        """Synthesizes natural AI narration using ElevenLabs API or tuned Edge-TTS deep narrator."""
        elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY")
        temp_mp3 = output_wav.with_suffix(".mp3")

        # 1. Try ElevenLabs API if key configured
        if elevenlabs_key:
            try:
                import urllib.request
                voice_id = "21m00Tcm4TlvDq8ikWAM"  # Default Rachel/Adam voice
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
                headers = {
                    "Accept": "audio/mpeg",
                    "Content-Type": "application/json",
                    "xi-api-key": elevenlabs_key
                }
                data = json.dumps({"text": text, "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}).encode("utf-8")
                req = urllib.request.Request(url, data=data, headers=headers)
                with urllib.request.urlopen(req) as resp:
                    with open(temp_mp3, "wb") as out:
                        out.write(resp.read())
                
                cmd = ["ffmpeg", "-y", "-i", str(temp_mp3), "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", str(output_wav)]
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                if temp_mp3.exists():
                    temp_mp3.unlink()
                print("     🎙️ Synthesized ElevenLabs AI Narration!")
            except Exception as e:
                print(f"⚠️ ElevenLabs TTS note ({e}). Falling back to tuned Edge-TTS deep narrator...")

        # 2. Edge-TTS with deep narrator pitch tuning
        if not output_wav.exists() or output_wav.stat().st_size < 1000:
            try:
                import edge_tts
                # Pitch tuning for deep documentary tone: pitch="-8Hz", rate="-5%"
                communicator = edge_tts.Communicate(text, voice, pitch="-8Hz", rate="-5%")
                await communicator.save(str(temp_mp3))
                cmd = ["ffmpeg", "-y", "-i", str(temp_mp3), "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", str(output_wav)]
                subprocess.run(cmd, capture_output=True, text=True, check=True)
                if temp_mp3.exists():
                    temp_mp3.unlink()
            except Exception as e:
                print(f"⚠️ Edge-TTS fallback ({e}). Generating tone fallback...")
                cmd = [
                    "ffmpeg", "-y",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
                    "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                    str(output_wav)
                ]
                subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Probe exact audio duration
        probe_cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(output_wav)]
        res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        dur = float(json.loads(res.stdout)["format"]["duration"])
        return round(dur, 2)

    def generate_short(self, script_data: Dict[str, Any], output_path: Optional[Path] = None) -> Path:
        """Assembles a full 9:16 vertical wildlife short video with multi-track audio mix."""
        output_file = output_path or (self.output_dir / "wildlife_autoshort.mp4")
        title = script_data.get("title", "Wildlife Short")
        banner = script_data.get("hook_banner", "WILDLIFE UNTAMED")
        voice = script_data.get("voice", "en-US-ChristopherNeural")
        scenes = script_data.get("scenes", [])

        print(f"\n🎬 [AutoShortEngine] Processing Short: '{title}'...")

        rendered_scene_files = []

        for idx, scene in enumerate(scenes, 1):
            text = scene["text"]
            target_animal = scene.get("animal")
            print(f"  📌 [Scene {idx}/{len(scenes)}] Matching narration: '{text[:40]}...'")

            # 1. Match narration to B-roll moment
            broll_moment = self.match_narration_to_broll(text, target_animal)
            rel_video_file = broll_moment["parent_video"]
            abs_video_file = self.source_clips_dir / rel_video_file
            broll_start = broll_moment["start_time"]
            print(f"     ✅ Matched B-roll: {broll_moment['animal']} ({broll_moment['behavior']}) -> {rel_video_file} @ {broll_start}s")

            # 2. Synthesize voice narration
            scene_voice = self.temp_dir / f"scene_{idx:02d}_voice.wav"
            audio_duration = asyncio.run(self.generate_narration_audio(text, voice, scene_voice))
            print(f"     🎙️ Narration Duration: {audio_duration}s")

            # 3. Select action SFX
            action_sfx = self.select_action_sfx(text, broll_moment["animal"])

            # 4. Multi-track Audio Mixing (Voice + Action SFX + Ducked BGM)
            mixed_audio = self.temp_dir / f"scene_{idx:02d}_mix.wav"
            bgm_track = BGM_DIR / "nature_suspense_bgm.wav"

            if action_sfx and action_sfx.exists():
                print(f"     🔊 Adding Action SFX: {action_sfx.name}")
                audio_filter = (
                    "[0:a]volume=1.0[v_voice];"
                    "[1:a]volume=0.4[v_sfx];"
                    "[2:a]volume=0.12[v_bgm];"
                    "[v_voice][v_sfx][v_bgm]amix=inputs=3:duration=first[aout]"
                )
                mix_cmd = [
                    "ffmpeg", "-y",
                    "-i", str(scene_voice),
                    "-i", str(action_sfx),
                    "-stream_loop", "-1", "-i", str(bgm_track),
                    "-t", str(audio_duration),
                    "-filter_complex", audio_filter,
                    "-map", "[aout]",
                    "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                    str(mixed_audio)
                ]
            else:
                audio_filter = (
                    "[0:a]volume=1.0[v_voice];"
                    "[1:a]volume=0.12[v_bgm];"
                    "[v_voice][v_bgm]amix=inputs=2:duration=first[aout]"
                )
                mix_cmd = [
                    "ffmpeg", "-y",
                    "-i", str(scene_voice),
                    "-stream_loop", "-1", "-i", str(bgm_track),
                    "-t", str(audio_duration),
                    "-filter_complex", audio_filter,
                    "-map", "[aout]",
                    "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                    str(mixed_audio)
                ]

            subprocess.run(mix_cmd, capture_output=True, text=True, check=True)

            # 5. Crop video to 9:16 (1080x1920) and burn safe-zone captions
            scene_video = self.temp_dir / f"scene_{idx:02d}_render.mp4"
            safe_text = text.replace("'", "'\\''").replace(":", "\\:")
            banner_text = banner.replace("'", "'\\''").replace(":", "\\:")

            vf_filter = (
                f"crop=ih*9/16:ih:(iw-ow)/2:0,scale=1080:1920,"
                f"drawtext=fontfile='{FONT_PATH}':text='{banner_text}':fontcolor=yellow:fontsize=56:x=(w-text_w)/2:y=180:box=1:boxcolor=black@0.7:boxborderw=16,"
                f"drawtext=fontfile='{FONT_PATH}':text='{safe_text}':fontcolor=white:fontsize=42:x=(w-text_w)/2:y=h-360:w=900:box=1:boxcolor=black@0.7:boxborderw=20:line_spacing=12"
            )

            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-ss", str(broll_start),
                "-i", str(abs_video_file),
                "-i", str(mixed_audio),
                "-t", str(audio_duration),
                "-vf", vf_filter,
                "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                str(scene_video)
            ]

            res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
            if res.returncode != 0:
                print(f"⚠️ FFmpeg render error on Scene {idx}: {res.stderr}")
                vf_filter_basic = f"crop=ih*9/16:ih:(iw-ow)/2:0,scale=1080:1920"
                ffmpeg_cmd_basic = [
                    "ffmpeg", "-y",
                    "-ss", str(broll_start),
                    "-i", str(abs_video_file),
                    "-i", str(mixed_audio),
                    "-t", str(audio_duration),
                    "-vf", vf_filter_basic,
                    "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k",
                    str(scene_video)
                ]
                subprocess.run(ffmpeg_cmd_basic, capture_output=True, text=True, check=True)

            rendered_scene_files.append(scene_video)

        # 6. Concatenate scenes into final video
        concat_list = self.temp_dir / "concat_list.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for sf in rendered_scene_files:
                f.write(f"file '{sf.as_posix()}'\n")

        print("🎞️ Concatenating scenes into final short video with multi-track audio...")
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(output_file)
        ]
        subprocess.run(concat_cmd, capture_output=True, text=True, check=True)

        print(f"✨ [Success] Rendered final Wildlife AutoShort with upgraded Audio Engine: {output_file}")
        return output_file
