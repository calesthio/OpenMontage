"""
wild_mechanics_engine.py
Core engine helpers for the Wild Mechanics Master Production Pipeline.
Includes:
- 4:5 Ghost Blur Filtergraph with Zero Watermarks & OLED color punch
- Smart Trimming with Whisper Sentence Boundaries & 0.8s Black Fade
- Word-Level Kinetic Karaoke Subtitles (ASS \\k tags, #FFFF00 active yellow)
- YouTube Shorts Safe-Zone Subtitle Alignment (MarginV=460)
- Top Header Branding & Curiosity Hook Titles (Y=105 / Y=165)
- Dynamic Outro CTA Generator with ElevenLabs Voice & Mixed Background Music Bed (volume=0.35)
"""

import os
import re
import json
import asyncio
import requests
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT_DIR = Path(__file__).resolve().parent.parent

def is_bbc_source(file_path: Path | str) -> bool:
    """Detects if a media file is from BBC based on filename prefix/tag."""
    name = Path(file_path).name.lower()
    return "bbc" in name or name.startswith("bbc_")

def get_target_durations(file_path: Path | str, requested_target: Optional[float] = None) -> tuple[float, float, float]:
    """
    Returns (hook_target_s, story_target_s, cta_target_s) matching channel benchmarks:
    - BBC Source: Hook = 3.0s, Story = 55.5s, CTA = 2.5s (Total = 61.0s, exactly 1:01 on YouTube)
    - Non-BBC Source: Hook = 3.0s, Story = 70.0s+ (requested duration > 60s), CTA = 2.5s (Total = 75.5s+)
    """
    hook_s = 3.0
    cta_s = 2.5
    if is_bbc_source(file_path):
        story_s = 55.5 if requested_target is None or requested_target > 58.0 else requested_target
    else:
        story_s = requested_target if requested_target and requested_target >= 58.0 else 70.0
    return hook_s, story_s, cta_s


def master_stitch_filter(num_inputs: int = 3, total_duration: float = 61.0, progress_bar: bool = True) -> str:
    """
    Generates the master concat filtergraph with standardized SAR=1:1, FPS=30, Stereo 48kHz audio,
    and a 100% time-synchronized, fluid animated yellow progress bar.
    """
    prep_v = ";".join(f"[{i}:v]setsar=1,fps=30[v{i}]" for i in range(num_inputs))
    prep_a = ";".join(f"[{i}:a]aformat=sample_rates=48000:channel_layouts=stereo,aresample=48000[a{i}]" for i in range(num_inputs))
    inputs_str = "".join(f"[v{i}][a{i}]" for i in range(num_inputs))
    
    concat_part = f"{prep_v};{prep_a};{inputs_str}concat=n={num_inputs}:v=1:a=1[v_raw][a]"
    if progress_bar:
        return (
            f"{concat_part};"
            f"color=c=black@0.4:s=1080x16:d={total_duration:.2f}[pbg];"
            f"color=c=yellow:s=1080x16:d={total_duration:.2f}[pbar];"
            f"[v_raw][pbg]overlay=0:0[v_bg];"
            f"[v_bg][pbar]overlay=x='min(0,-1080+1080*(t/{total_duration:.2f}))':y=0[v]"
        )
    else:
        return f"{concat_part};[v_raw]copy[v]"


def generate_cold_hook_clip(
    doc_source: Path,
    hook_title_text: str,
    output_clip_path: Path,
    hook_cut_start: float = 35.0,
    hook_cut_duration: float = 3.00,
    pitch_factor: float = 0.91
) -> Path:
    """
    Renders Act 1: Cold Action Teaser Hook (0.0s - 3.0s):
    - High-intensity clash / strike action shot extracted from footage
    - Authentic documentary roaring / river audio with pitch modulation (NO AI TTS on hook!)
    - Top branding header + Electric Yellow curiosity hook title
    - 4:5 Ghost Blur framing
    """
    temp_dir = output_clip_path.parent / "temp_hook"
    temp_dir.mkdir(parents=True, exist_ok=True)
    hook_raw = temp_dir / "hook_raw.mp4"
    hook_ass = temp_dir / "hook.ass"
    
    # 1. Cut Climax Action Snippet with Authentic Audio & Pitch Modulation
    cmd_cut = [
        "ffmpeg", "-y",
        "-ss", str(hook_cut_start),
        "-t", str(hook_cut_duration),
        "-i", str(doc_source),
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-filter:a", f"asetrate=48000*{pitch_factor},atempo=1/{pitch_factor},loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:a", "aac", "-b:a", "320k",
        str(hook_raw)
    ]
    subprocess.run(cmd_cut, check=True)
    
    # 2. Subtitles / Top Header (Jaguar Standard)
    ass_content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TopBrand,Impact,32,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,2,2,8,40,40,130,1
Style: TopTitle,Impact,48,&H0000D7FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,3,2,8,40,40,180,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 1,0:00:00.00,0:00:03.00,TopBrand,,0,0,0,,{{\\fad(100,100)}}WILD MECHANICS
Dialogue: 1,0:00:00.00,0:00:03.00,TopTitle,,0,0,0,,{{\\fad(100,100)}}{hook_title_text.upper()}
"""
    hook_ass.write_text(ass_content, encoding="utf-8")
    
    hook_filter = ghost_blur_filter(ass_file=str(hook_ass), hflip=True, progress_bar=True, duration=hook_cut_duration)
    cmd_render = [
        "ffmpeg", "-y",
        "-i", str(hook_raw),
        "-filter_complex", hook_filter,
        "-map", "[v]", "-map", "0:a",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-c:a", "aac", "-b:a", "320k",
        str(output_clip_path)
    ]
    subprocess.run(cmd_render, check=True)
    return output_clip_path


def extract_high_ctr_thumbnail(video_path: Path, output_thumb_path: Path, timestamp_s: float = 1.5) -> Path:
    """
    Extracts a high-CTR 1080x1920 thumbnail from the Cold Hook frame:
    - High contrast (+12%) & saturation (+28%) boost for vivid colors
    - Unsharp mask filter for crisp detail on mobile feeds
    - High JPEG quality
    """
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(timestamp_s),
        "-i", str(video_path),
        "-vf", "scale=1080:1920,eq=contrast=1.12:saturation=1.28:brightness=-0.02,unsharp=5:5:1.0:5:5:0.0",
        "-vframes", "1",
        "-q:v", "2",
        str(output_thumb_path)
    ]
    subprocess.run(cmd, check=True)
    return output_thumb_path

def ghost_blur_filter(
    ass_file: Optional[str] = None,
    fade_out_start: Optional[float] = None,
    fade_duration: float = 0.8,
    hflip: bool = True,
    progress_bar: bool = True,
    duration: Optional[float] = None,
    time_offset: float = 0.0,
    total_duration: Optional[float] = None,
    crop_mode: str = "subject_4_5",
    x_align: str = "center"
) -> str:
    """
    Generates the official Wild Mechanics 4:5 Ghost Blur FFmpeg filtergraph:
    - hflip: Horizontal flip on footage for 100% visual Content-ID evasion.
    - crop_mode:
        * 'subject_4_5' (Default / Standard): Preserves 100% vertical height (1080px from top to bottom),
          extracts the true 4:5 window (864x1080) directly centered on the animal subject, and scales to 1080x1350.
          Corner watermarks (e.g. Nat Geo WILD on bottom right) are naturally discarded outside the 864px window!
        * 'broadcast_crop': Strips bottom 16% specifically for broadcasts with full-width lower-third text tickers.
    - x_align: 'center' (default), 'left', 'right', or horizontal ratio expression.
    - Background: 1080x1920 ambient blur (boxblur=30:5, brightness=-0.08, saturation=1.15).
    - Foreground: 1080x1350 (4:5) centered at Y=285 (saturation=1.12, contrast=1.04).
    """
    flip_chain = "hflip," if hflip else ""
    
    if crop_mode == "broadcast_crop":
        filter_chain = (
            f"[0:v]{flip_chain}crop=in_w*0.92:in_h*0.84:(in_w-out_w)/2:0,split=2[bg][fg];"
            "[bg]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:5,eq=brightness=-0.08:saturation=1.15[bgblur];"
            "[fg]scale=1080:1350:force_original_aspect_ratio=increase,crop=1080:1350:(iw-1080)/2:(ih-1350)/2,eq=saturation=1.12:contrast=1.04:brightness=-0.02[fg45];"
            "[bgblur][fg45]overlay=0:285[base]"
        )
    else:
        if x_align == "left":
            x_expr = "(in_w-out_w)*0.15"
        elif x_align == "right":
            x_expr = "(in_w-out_w)*0.85"
        else:
            x_expr = "(in_w-out_w)/2"
            
        filter_chain = (
            f"[0:v]{flip_chain}split=2[bg_raw][fg_raw];"
            "[bg_raw]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=30:5,eq=brightness=-0.08:saturation=1.15[bgblur];"
            f"[fg_raw]crop=in_h*4/5:in_h:{x_expr}:0,scale=1080:1350,eq=saturation=1.12:contrast=1.04:brightness=-0.02[fg45];"
            "[bgblur][fg45]overlay=0:285[base]"
        )
    
    post_filters = []
    if progress_bar:
        tot_dur = total_duration if (total_duration is not None and total_duration > 0) else (duration if (duration is not None and duration > 0) else 60.0)
        post_filters.append(f"drawbox=x=0:y=0:w='min(iw,iw*(({time_offset:.2f}+t)/{tot_dur:.2f}))':h=16:color=yellow@1:t=fill")
        
    if ass_file:
        escaped_ass = Path(ass_file).resolve().as_posix().replace(":", "\\:")
        post_filters.append(f"ass='{escaped_ass}'")
        
    if fade_out_start is not None and fade_out_start > 0:
        post_filters.append(f"fade=t=out:st={fade_out_start:.2f}:d={fade_duration:.2f}")
        
    if post_filters:
        filter_chain += f";[base]{','.join(post_filters)}[v]"
    else:
        filter_chain += ";[base]copy[v]"
        
    return filter_chain


# -------------------------------------------------------------
# 2. AUDIO PITCH & FADE FILTER (DEEPER PITCH FOR ANTI-CONTENT-ID)
# -------------------------------------------------------------
def audio_pitch_and_fade_filter(fade_out_start: Optional[float] = None, fade_duration: float = 0.8, pitch_factor: float = 0.91) -> str:
    """
    Applies strong pitch modulation (anti-Content-ID voice alteration) and optional audio fade out.
    pitch_factor=0.91 gives a deep, distinct resonant documentary tone while preserving speech clarity.
    """
    atempo = 1.0 / pitch_factor
    f = f"asetrate=48000*{pitch_factor:.3f},atempo={atempo:.3f},highpass=f=65,lowpass=f=14500,bass=g=3:f=110"
    if fade_out_start is not None and fade_out_start > 0:
        f += f",afade=t=out:st={fade_out_start:.2f}:d={fade_duration:.2f}"
    f += ",loudnorm=I=-14:TP=-1.5:LRA=11"
    return f


# -------------------------------------------------------------
# 3. ASS KINETIC KARAOKE & HEADER GENERATOR (JAGUAR STANDARD)
# -------------------------------------------------------------
def build_ass_subtitles(
    segments: List[Any],
    output_path: Optional[Path] = None,
    title_hook: str = "WILD MECHANICS",
    animal_name: str = "",
    action_badges: Optional[List[Dict[str, Any]]] = None,
    max_duration: Optional[float] = None,
    output_ass_path: Optional[Path] = None,
) -> Path:
    r"""
    Builds the official Wild Mechanics ASS subtitle file matching the exact Jaguar video standard:
    - TopBrand: WILD MECHANICS (Impact 32, Diamond White &H00FFFFFF, MarginV=130, Outline=2, Shadow=2)
    - TopTitle: Curiosity Hook (Impact 48, Vivid Gold/Yellow &H0000D7FF, MarginV=180, Outline=3, Shadow=2)
    - BottomKaraoke: Word-level kinetic karaoke (\k tags, #FFFF00 active) (Impact 52, MarginV=420)
    - MidBadge: Action badges timed to peak moments (Impact 46, Vivid Gold)
    """
    out_file = output_ass_path or output_path
    if not out_file:
        raise ValueError("output_path or output_ass_path must be provided")
    ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TopBrand,Impact,32,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,2,2,8,40,40,130,1
Style: TopTitle,Impact,48,&H0000D7FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,3,2,8,40,40,180,1
Style: MidBadge,Impact,46,&H0000FFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,3,2,5,40,40,900,1
Style: BottomKaraoke,Impact,52,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,3,2,2,40,40,420,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    
    # End time for persistent headers
    end_s = max_duration if max_duration else 95.0
    end_h = int(end_s // 3600)
    end_m = int((end_s % 3600) // 60)
    end_sec = int(end_s % 60)
    end_cs = int((end_s - int(end_s)) * 100)
    end_time_str = f"{end_h}:{end_m:02d}:{end_sec:02d}.{end_cs:02d}"
    
    events.append(f"Dialogue: 1,0:00:00.00,{end_time_str},TopBrand,,0,0,0,,{{\\fad(200,400)}}WILD MECHANICS")
    events.append(f"Dialogue: 1,0:00:00.00,{end_time_str},TopTitle,,0,0,0,,{{\\fad(200,400)}}{title_hook}")
    
    # Action Badges
    if action_badges:
        for badge in action_badges:
            b_text = badge["text"]
            b_st = badge["start"]
            b_en = badge["end"]
            st_str = format_ass_time(b_st)
            en_str = format_ass_time(b_en)
            events.append(f"Dialogue: 2,{st_str},{en_str},MidBadge,,0,0,0,,{{\\fad(300,300)}}{b_text}")
            
    # Word-level karaoke chunks
    for seg in segments:
        words = seg.words if hasattr(seg, "words") and seg.words else []
        if not words:
            continue
        chunk_size = 5
        for i in range(0, len(words), chunk_size):
            chunk = words[i:i+chunk_size]
            if not chunk:
                continue
            c_start = chunk[0].start
            c_end = chunk[-1].end
            if max_duration and c_start >= max_duration - 0.5:
                continue
            if max_duration:
                c_end = min(max_duration - 0.5, c_end)
                
            k_text = ""
            for w in chunk:
                dur_cs = max(1, int(round((w.end - w.start) * 100)))
                clean_w = w.word.strip().upper()
                k_text += f"{{\\k{dur_cs}}}{clean_w} "
                
            start_str = format_ass_time(c_start)
            end_str = format_ass_time(c_end)
            events.append(f"Dialogue: 0,{start_str},{end_str},BottomKaraoke,,0,0,0,,{k_text.strip()}")
            
    out_file.write_text(ass_header + "\n".join(events) + "\n", encoding="utf-8")
    return out_file


def format_ass_time(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int((sec - int(sec)) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


# -------------------------------------------------------------
# 4. DYNAMIC OUTRO CTA SYNTHESIS (ELEVENLABS + BOOSTED BGM)
# -------------------------------------------------------------
def generate_dynamic_cta_clip(
    animal_name: str,
    output_clip_path: Path,
    stock_bg_video: Optional[Path] = None,
    bgm_track: Optional[Path] = None,
    whisper_model: Any = None,
    bgm_volume: float = 0.35,
    duration_s: float = 2.5,
    clean_stock_bg: Optional[str] = None
) -> Path:
    """
    Renders the official dynamic Outro CTA (Snappy 2.5s or full):
    - ElevenLabs channel voice (FOLLOW -> WILD MECHANICS -> FOR MORE)
    - Mixed background music bed (volume=0.35 / -13dB with smooth fade-in/out)
    - Centered bold Electric Yellow kinetic text bursts
    """
    temp_dir = output_clip_path.parent / "temp_cta"
    temp_dir.mkdir(parents=True, exist_ok=True)
    clean_slug = re.sub(r'[^a-zA-Z0-9_]', '_', animal_name)
    voice_audio = temp_dir / f"cta_voice_{clean_slug}.wav"
    
    # 1. Voice Synthesis (Snappy 2.5s CTA)
    cta_script = "Follow Wild Mechanics for more."
    eleven_key = os.environ.get("ELEVENLABS_API_KEY")
    eleven_voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "3zYzgGucDBahVReFU64R")
    
    voice_ready = False
    if eleven_key:
        headers = {"xi-api-key": eleven_key, "Content-Type": "application/json"}
        data = {
            "text": cta_script,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}
        }
        try:
            res = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{eleven_voice_id}", json=data, headers=headers, timeout=10)
            if res.status_code == 200 and len(res.content) > 1000:
                raw_mp3 = temp_dir / f"cta_raw_{clean_slug}.mp3"
                raw_mp3.write_bytes(res.content)
                subprocess.run(["ffmpeg", "-y", "-i", str(raw_mp3), "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(voice_audio)], check=True)
                voice_ready = True
        except Exception:
            pass

    if not voice_ready:
        stock_cta = ROOT_DIR / "assets" / "audio" / "cta" / "short_cta_voice.wav"
        cached_cta = ROOT_DIR / "projects" / "grizzly_bear" / "assets" / "short_cta_voice.mp3"
        
        if stock_cta.exists() and stock_cta.stat().st_size > 1000:
            subprocess.run(["ffmpeg", "-y", "-i", str(stock_cta), "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(voice_audio)], check=True)
            voice_ready = True
        elif cached_cta.exists() and cached_cta.stat().st_size > 1000:
            subprocess.run(["ffmpeg", "-y", "-i", str(cached_cta), "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(voice_audio)], check=True)
            voice_ready = True
        else:
            # Fallback to pure silent/ambient stereo bed
            cmd_null_vo = ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", str(duration_s), "-c:a", "pcm_s16le", str(voice_audio)]
            subprocess.run(cmd_null_vo, check=True)
            voice_ready = True
            
    # 2. Build Centered ASS Kinetic Bursts (FOLLOW -> WILD MECHANICS -> FOR MORE)
    cta_ass = temp_dir / "short_cta.ass"
    cta_ass_content = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CenterWord,Impact,76,&H0000FFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,6,3,5,40,40,0,1
Style: WhiteWord,Impact,76,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,6,3,5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:00.75,WhiteWord,,0,0,0,,FOLLOW
Dialogue: 0,0:00:00.75,0:00:01.60,CenterWord,,0,0,0,,WILD MECHANICS
Dialogue: 0,0:00:01.60,0:00:02.50,CenterWord,,0,0,0,,FOR MORE.
"""
    cta_ass.write_text(cta_ass_content, encoding="utf-8")
    
    # 3. Background Video Selection
    bg_video = None
    if stock_bg_video and Path(stock_bg_video).exists():
        bg_video = Path(stock_bg_video)
    elif clean_stock_bg and (ROOT_DIR / clean_stock_bg).exists():
        bg_video = ROOT_DIR / clean_stock_bg
    else:
        # Default to bear CTA bg or generate a clean ambient background
        fallback_bg = ROOT_DIR / "projects" / "grizzly_bear" / "assets" / "clean_bear_cta_bg.mp4"
        if fallback_bg.exists():
            bg_video = fallback_bg
        else:
            bg_video = temp_dir / "cta_ambient_bg.mp4"
            cmd_gen = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:d={duration_s:.2f}", "-c:v", "libx264", "-t", str(duration_s), str(bg_video)]
            subprocess.run(cmd_gen, check=True)

    if bgm_track is None or not Path(bgm_track).exists():
        stock_bgm = ROOT_DIR / "assets" / "audio" / "bgm" / "nature_suspense_bgm.wav"
        if stock_bgm.exists():
            bgm_track = stock_bgm
        else:
            bgm_fallback = temp_dir / "cta_bgm_fallback.wav"
            cmd_null_bgm = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo", "-t", str(duration_s), str(bgm_fallback)]
            subprocess.run(cmd_null_bgm, check=True)
            bgm_track = bgm_fallback

    # 4. Render CTA Video
    escaped_ass = cta_ass.resolve().as_posix().replace(":", "\\:")
    filter_complex = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fade=t=in:st=0.0:d=0.2,eq=brightness=-0.10:contrast=1.05:saturation=1.12[bg];"
        f"[bg]ass='{escaped_ass}'[v];"
        "[1:a]volume=1.4,aformat=sample_rates=48000:channel_layouts=stereo[vo];"
        f"[2:a]volume={bgm_volume:.2f},aformat=sample_rates=48000:channel_layouts=stereo,afade=t=in:st=0.0:d=0.2,afade=t=out:st={duration_s-0.5:.2f}:d=0.5[bgm];"
        f"[vo][bgm]amix=inputs=2:duration=longest:dropout_transition=0,atrim=0:{duration_s:.2f},apad=whole_dur={duration_s:.2f}[a]"
    )
    
    cmd = [
        "ffmpeg", "-y",
        "-ss", "0.5",
        "-t", str(duration_s),
        "-i", str(Path(bg_video).resolve()),
        "-i", str(Path(voice_audio).resolve()),
        "-i", str(Path(bgm_track).resolve()),
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-c:a", "aac", "-b:a", "320k",
        str(Path(output_clip_path).resolve())
    ]
    subprocess.run(cmd, check=True)
    return output_clip_path
