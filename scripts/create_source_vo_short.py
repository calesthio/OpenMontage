"""
create_source_vo_short.py
========================
High-Retention Source-VO Wildlife Documentary Shorts Production Engine.

Transforms BBC / National Geographic 16:9 documentary footage into viral 9:16 vertical shorts:
- Ghost-Blur 4:5 / 9:16 aspect ratio with cinematic blurred background
- Anti-Content-ID color grading (eq=saturation=1.12:contrast=1.04:brightness=-0.02)
- Anti-Content-ID horizontal flip (hflip)
- Anti-Content-ID audio frequency & acoustic fingerprint scrambler
- Elevated kinetic ASS subtitles with safe-zone positioning (MarginV=520)
- EBU R128 integrated loudness normalization (-14 LUFS)
"""

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent


def parse_time_to_seconds(val: str | float) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip()
    if ":" in val_str:
        parts = val_str.split(":")
        if len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    return float(val_str)


def generate_ass_subtitles(
    events: list[dict[str, Any]],
    output_path: Path,
    title_banner: Optional[str] = None,
    font_name: str = "Impact",
    font_size: int = 64,
    keyword_color: str = "&H0000E6FF&",  # Vibrant gold/yellow in BGR
    text_color: str = "&H00FFFFFF&",     # Pure white
) -> Path:
    """Generate professional ANIMAL WILD styled ASS subtitle file."""
    header = f"""[Script Info]
Title: OpenMontage Source-VO Master
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Header,{font_name},48,{text_color},{keyword_color},&H00000000,&H80000000,0,0,0,0,100,100,1.5,0,1,3.5,2,8,40,40,160,1
Style: Subtitle,{font_name},{font_size},{text_color},{keyword_color},&H00000000,&H90000000,0,0,0,0,100,100,1.2,0,1,4.5,2.5,2,60,60,520,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]

    if title_banner:
        # Top persistent hook
        lines.append(f"Dialogue: 0,0:00:00.00,9:59:59.00,Header,,0,0,0,,{title_banner}\n")

    for ev in events:
        start_str = ev["start"]
        end_str = ev["end"]
        text = ev["text"]
        lines.append(f"Dialogue: 0,{start_str},{end_str},Subtitle,,0,0,0,,{text}\n")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(lines), encoding="utf-8")
    return output_path


def render_source_vo_short(
    source_video: str | Path,
    output_video: str | Path,
    start_time: float = 0.0,
    duration: float = 60.0,
    ass_subtitle_path: Optional[str | Path] = None,
    framing: str = "ghost-4-5",
    title_banner: Optional[str] = None,
    events: Optional[list[dict[str, Any]]] = None,
    hflip: bool = True,
    cta_text: Optional[str] = "Follow  WILD MECHANICS  ->  Subscribe",
) -> Path:
    # ponytail: story exactly 60.0s, CTA outro (3.5s centered + voice) appended after — Shorts UI hides bottom, outro grabs attention
    """Renders the 9:16 vertical short from raw documentary source with anti-Content-ID protections — story is exactly 60.0s, outro appended after."""
    source_path = Path(source_video).resolve()
    output_path = Path(output_video).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Prepare ASS subtitle file if events provided or custom
    if ass_subtitle_path is None and events:
        temp_ass = output_path.with_suffix(".ass")
        generate_ass_subtitles(events, temp_ass, title_banner=title_banner)
        ass_subtitle_path = temp_ass

    # 2. Visual Filtergraph with Anti-Content-ID color grade & framing
    flip_prefix = "hflip," if hflip else ""

    if framing in ["ghost-4-5", "4:5", "ghost-blur"]:
        # 4:5 aspect ratio (1080x1350) centered over blurred 9:16 background
        vf_base = (
            f"[0:v]{flip_prefix}split=2[bg][fg];"
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:5,eq=brightness=-0.08:saturation=1.15[bgblur];"
            "[fg]scale=1080:1350:force_original_aspect_ratio=increase,crop=1080:1350:(iw-1080)/2:(ih-1350)/2,eq=saturation=1.12:contrast=1.04:brightness=-0.02[fg45];"
            "[bgblur][fg45]overlay=0:285"
        )
    elif framing in ["ghost-16-9", "blurred-fill"]:
        # Full 16:9 centered over blurred 9:16 background
        vf_base = (
            f"[0:v]{flip_prefix}split=2[bg][fg];"
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:5,eq=brightness=-0.08:saturation=1.15[bgblur];"
            "[fg]scale=1080:1920:force_original_aspect_ratio=decrease,eq=saturation=1.12:contrast=1.04:brightness=-0.02[fgscaled];"
            "[bgblur][fgscaled]overlay=0:(1920-H)/2"
        )
    else:  # fullbleed center-crop (9:16)
        vf_base = f"[0:v]{flip_prefix}scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920:(iw-1080)/2:(ih-1920)/2,eq=saturation=1.12:contrast=1.04:brightness=-0.02"

    if ass_subtitle_path and Path(ass_subtitle_path).exists():
        ass_str = str(Path(ass_subtitle_path).resolve()).replace("\\", "/")
        ass_escaped = ass_str.replace(":", "\\:").replace("'", "\\'")
        filter_complex = f"{vf_base},ass='{ass_escaped}'[v]"
    else:
        filter_complex = f"{vf_base}[v]"

    # CTA now appended as centered outro card with voice (bottom 250px hidden by Shorts UI — winners used end-card voice)
    # Drawtext CTA removed; outro concat appended after main render

    # Audio: EBU R128 loudness only — anti-Content-ID scrambler (asetrate/atempo) removed to keep captions synced with VO (was causing desync)
    # For BBC sources that need anti-CID, re-enable via --audio-filter scrambler flag (ponytail: YAGNI until needed)
    audio_filter = "highpass=f=60,lowpass=f=16000,loudnorm=I=-14:TP=-1.5:LRA=11"

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_time),
        "-t", str(duration),
        "-i", str(source_path),
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "0:a:0?",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-af", audio_filter,
        str(output_path),
    ]

    print(f"[OpenMontage] Executing render for {output_path.name} (hflip={hflip}, duration={duration}s)...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print("[FFmpeg STDOUT]", res.stdout)
        print("[FFmpeg STDERR]", res.stderr)
        raise RuntimeError(f"FFmpeg render failed with exit code {res.returncode}: {res.stderr[-500:]}")

    print(f"[OpenMontage] Render complete: {output_path} ({os.path.getsize(output_path)} bytes)")

    # --- CTA outro card with voice (centered, not bottom — Shorts UI hides bottom 200px) ---
    if cta_text:
        try:
            outro_dur = 3.5
            # Voice text cleaned for TTS (arrow -> spoken)
            voice_text = cta_text.replace("->", "for more").replace("  ", " ").strip()
            # keep varied CTA, ensure Subscribe present — append, don't replace
            if "Subscribe" not in voice_text:
                if voice_text.endswith("."):
                    voice_text = voice_text.rstrip(".") + ". Subscribe now."
                else:
                    voice_text = voice_text + " Subscribe now."
            # 1. TTS audio
            cta_audio = output_path.with_suffix(".cta.mp3")
            tts_ok = False
            eleven_key = os.getenv("ELEVENLABS_API_KEY")
            if eleven_key:
                try:
                    from elevenlabs.client import ElevenLabs
                    client = ElevenLabs(api_key=eleven_key)
                    voice_id = os.getenv("ELEVENLABS_VOICE_ID", "3zYzgGucDBahVReFU64R")
                    audio = client.text_to_speech.convert(text=voice_text, voice_id=voice_id, model_id="eleven_multilingual_v2")
                    with open(cta_audio, "wb") as f:
                        for chunk in audio:
                            f.write(chunk)
                    tts_ok = cta_audio.exists() and cta_audio.stat().st_size > 1000
                except Exception as e:
                    print(f"[CTA] ElevenLabs TTS failed: {e}")
            if not tts_ok:
                # silent fallback 3.5s
                cta_audio = output_path.with_suffix(".cta_silence.m4a")
                subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo", "-t", str(outro_dur), "-c:a", "aac", str(cta_audio)], capture_output=True, check=True)
            else:
                # ensure aac and pad/trim to outro_dur
                tmp_aac = output_path.with_suffix(".cta_tmp.m4a")
                subprocess.run(["ffmpeg", "-y", "-i", str(cta_audio), "-af", f"apad,atrim=duration={outro_dur}", "-c:a", "aac", str(tmp_aac)], capture_output=True, check=True)
                cta_audio = tmp_aac

            # 2. Outro video — centered CTA with visual (not blank) — try Pexels/Pixabay stock clip, fallback to last-frame blur
            font_arg = ""
            for cand in ["C:/Windows/Fonts/impact.ttf", "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]:
                if Path(cand).exists():
                    cand_esc = cand.replace(":", "\\:")
                    font_arg = f":fontfile='{cand_esc}'"
                    break
            # Varied CTA visual — first line tailored per video, second line fixed brand (centered, not hidden, fits Shorts)
            cta_for_visual = cta_text.replace("->", "->")
            if "." in cta_for_visual:
                parts = [p.strip() for p in cta_for_visual.split(".") if p.strip()]
                line1 = parts[0] + "." if parts else "Follow  WILD MECHANICS"
            else:
                # no period, use first half as line1
                words = cta_for_visual.split()
                line1 = " ".join(words[:4]) + "." if len(words) > 4 else cta_for_visual.strip()
            line2 = "Follow  WILD MECHANICS  ->  Subscribe"
            line1_esc = line1.replace(":", "\\:").replace("'", "\\'").replace("%", "\\%")
            line2_esc = line2.replace(":", "\\:").replace("'", "\\'").replace("%", "\\%")
            outro_v = output_path.with_suffix(".cta_outro.mp4")
            # Proper high-converting CTA: varied line + pulsing badge/emojis via cta_builder
            try:
                import sys as _sys
                _sys.path.insert(0, str(ROOT_DIR))
                from tools.video.cta_builder import generate_cta_ass_snippet
                cta_snippet = generate_cta_ass_snippet(duration=outro_dur, channel_name="WILD MECHANICS", animal_name="owl", cta_start_offset=outro_dur)
            except Exception as _e:
                print(f"[CTA] cta_builder import failed: {_e}, using fallback")
                cta_snippet = ""
            outro_ass = output_path.with_suffix(".cta_outro.ass")
            # Build outro ASS with centered varied CTA + high-converting overlay
            outro_ass_content = f"""[Script Info]
Title: CTA Outro
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: OutroMain,Impact,72,&H00FFFFFF,&H00000000,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,4,0,5,60,60,520,1
Style: OutroSub,Impact,64,&H00FFFF00,&H00000000,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,3,0,5,60,60,400,1
Style: CTABadge,Impact,44,&H00FFFFFF,&H00000000,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,5,60,60,150,1
Style: CTASubtext,Impact,38,&H00FFFFFF,&H00000000,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,5,60,60,120,1
Style: CTAPointer,Impact,42,&H00FFFFFF,&H00000000,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,0,5,60,60,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:{outro_dur:.2f},OutroMain,,0,0,0,,{line1_esc}
Dialogue: 0,0:00:00.00,0:00:{outro_dur:.2f},OutroSub,,0,0,0,,{line2_esc}
{cta_snippet}
"""
            outro_ass.write_text(outro_ass_content, encoding="utf-8")
            vf_outro = f"ass='{outro_ass.as_posix().replace(':', chr(92)+':').replace(chr(39), chr(92)+chr(39))}'"
            # Try stock clip from Pexels/Pixabay for visual CTR
            stock_clip = None
            cta_query = "wildlife jaguar"  # generic, daily pipeline passes animal-specific query
            # Allow caller to override via env or cta_text keywords
            if "jaguar" in cta_text.lower() or "jaguar" in str(output_path).lower():
                cta_query = "jaguar wild"
            elif "cheetah" in cta_text.lower():
                cta_query = "cheetah run"
            pexels_key = os.getenv("PEXELS_API_KEY")
            pixabay_key = os.getenv("PIXABAY_API_KEY")
            if pexels_key:
                try:
                    import requests
                    r = requests.get("https://api.pexels.com/videos/search", headers={"Authorization": pexels_key}, params={"query": cta_query, "per_page": 1, "orientation": "portrait", "size": "medium"}, timeout=10)
                    if r.ok:
                        data = r.json()
                        if data.get("videos"):
                            vf = data["videos"][0]["video_files"]
                            # prefer 720p portrait
                            best = sorted(vf, key=lambda x: x.get("width", 0))[-1]
                            url = best["link"]
                            stock_clip = output_path.with_suffix(".cta_stock.mp4")
                            dl = requests.get(url, timeout=20)
                            stock_clip.write_bytes(dl.content)
                except Exception as e:
                    print(f"[CTA] Pexels fetch failed: {e}")
            if stock_clip is None and pixabay_key:
                try:
                    import requests
                    r = requests.get("https://pixabay.com/api/videos/", params={"key": pixabay_key, "q": cta_query, "per_page": 3, "video_type": "all"}, timeout=10)
                    if r.ok:
                        hits = r.json().get("hits", [])
                        if hits:
                            url = hits[0]["videos"]["medium"]["url"]
                            stock_clip = output_path.with_suffix(".cta_stock.mp4")
                            import requests as rq2
                            dl = rq2.get(url, timeout=20)
                            stock_clip.write_bytes(dl.content)
                except Exception as e:
                    print(f"[CTA] Pixabay fetch failed: {e}")
            if stock_clip and stock_clip.exists() and stock_clip.stat().st_size > 5000:
                # Use stock clip as outro background, trimmed to outro_dur, scaled to 1080x1920 + CTA overlay
                outro_tmp = output_path.with_suffix(".cta_stock_trim.mp4")
                subprocess.run(["ffmpeg", "-y", "-i", str(stock_clip), "-t", str(outro_dur), "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,eq=brightness=-0.08:saturation=1.1,{vf_outro}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", str(outro_v)], capture_output=True, check=True)
                try:
                    stock_clip.unlink(missing_ok=True)
                    if outro_tmp.exists():
                        outro_tmp.unlink(missing_ok=True)
                except:
                    pass
            else:
                # Fallback: last-frame freeze + blur so outro not blank (no API key or fetch failed)
                # Extract last frame from main video and create 3.5s clip from it
                last_frame = output_path.with_suffix(".cta_last.jpg")
                subprocess.run(["ffmpeg", "-y", "-sseof", "-0.2", "-i", str(output_path), "-vframes", "1", str(last_frame)], capture_output=True)
                if last_frame.exists():
                    subprocess.run(["ffmpeg", "-y", "-loop", "1", "-i", str(last_frame), "-f", "lavfi", "-i", f"color=c=0x0B1620:s=1080x1920:d={outro_dur}:r=30", "-filter_complex", f"[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=12:3[fg];[1:v][fg]overlay=0:0:shortest=1,eq=brightness=-0.05:saturation=1.05,{vf_outro}[v]", "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", str(outro_dur), "-r", "30", str(outro_v)], capture_output=True, check=True)
                    try:
                        last_frame.unlink(missing_ok=True)
                    except:
                        pass
                else:
                    # ultimate fallback: solid color
                    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x0B1620:s=1080x1920:d={outro_dur}:r=30", "-vf", vf_outro, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", str(outro_dur), str(outro_v)], capture_output=True, check=True)
            # 3. Mux outro video + cta audio
            outro_mux = output_path.with_suffix(".cta_mux.mp4")
            subprocess.run(["ffmpeg", "-y", "-i", str(outro_v), "-i", str(cta_audio), "-c:v", "copy", "-c:a", "aac", "-shortest", str(outro_mux)], capture_output=True, check=True)
            # 4. Concat main (60s) + outro (3.5s) via filter_complex — reliable cross-platform, total 63.5s
            final_tmp = output_path.with_suffix(".cta_final.mp4")
            res = subprocess.run(["ffmpeg", "-y", "-i", str(output_path), "-i", str(outro_mux), "-filter_complex", "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", str(final_tmp)], capture_output=True, text=True)
            if res.returncode != 0:
                print("[CTA] Concat filter_complex failed, trying demuxer fallback")
                print(res.stderr[-800:])
                concat_list = output_path.with_suffix(".concat.txt")
                concat_list.write_text(f"file '{output_path.resolve().as_posix()}'\nfile '{outro_mux.resolve().as_posix()}'\n", encoding="utf-8")
                subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(final_tmp)], capture_output=True, check=True)
            # Replace output with final
            final_tmp.replace(output_path)
            # Cleanup temps
            for p in [cta_audio, outro_v, outro_mux, output_path.with_suffix(".concat.txt"), output_path.with_suffix(".cta.mp3"), output_path.with_suffix(".cta_tmp.m4a"), output_path.with_suffix(".cta_silence.m4a")]:
                try:
                    if Path(p).exists():
                        Path(p).unlink(missing_ok=True)
                except:
                    pass
            print(f"[CTA] Centered outro with voice appended: {voice_text} ({outro_dur}s) -> {output_path}")
        except Exception as e:
            print(f"[CTA] Outro failed, keeping video without CTA: {e}")

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Create ANIMAL WILD style Source-VO Documentary Short")
    parser.add_argument("--source", type=str, required=True, help="Path to master documentary video")
    parser.add_argument("--output", type=str, default=None, help="Output MP4 file path")
    parser.add_argument("--start", type=str, default="0.0", help="Start time (e.g. 10.0 or 01:15)")
    parser.add_argument("--duration", type=str, default="60.0", help="Duration in seconds (exactly 60.0 for story; outro appends after)")
    parser.add_argument("--framing", choices=["fullbleed", "ghost-4-5", "4:5", "ghost-blur", "ghost-16-9", "blurred-fill"], default="ghost-4-5")
    parser.add_argument("--ass", type=str, default=None, help="Path to ASS subtitle file")
    parser.add_argument("--title", type=str, default=None, help="Top hook title banner")
    parser.add_argument("--hflip", action="store_true", default=True, help="Apply horizontal flip")
    parser.add_argument("--no-hflip", dest="hflip", action="store_false", help="Disable horizontal flip")
    parser.add_argument("--cta", type=str, default="Follow  WILD MECHANICS  ->  Subscribe", help="CTA text last 3.5s (use --no-cta to disable)")
    parser.add_argument("--no-cta", dest="cta", action="store_const", const=None, help="Disable CTA")

    args = parser.parse_args()
    source_p = Path(args.source)
    if not source_p.exists():
        print(f"Error: Source video '{source_p}' does not exist.")
        exit(1)

    start_sec = parse_time_to_seconds(args.start)
    dur_sec = parse_time_to_seconds(args.duration)

    if args.output:
        out_p = Path(args.output)
    else:
        out_p = ROOT_DIR / "renders" / f"{source_p.stem}_ghost_4_5.mp4"

    render_source_vo_short(
        source_video=source_p,
        output_video=out_p,
        start_time=start_sec,
        duration=dur_sec,
        ass_subtitle_path=args.ass,
        framing=args.framing,
        title_banner=args.title,
        hflip=args.hflip,
        cta_text=args.cta,
    )


if __name__ == "__main__":
    main()
