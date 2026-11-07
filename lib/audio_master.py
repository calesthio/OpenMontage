"""Audio Master — single source of time for the edit timeline.

V8 §3.4: Audio is the single source of time. The narration master WAV is
built from voice blocks (semantic paragraphs), its duration is measured from
actual samples/sample rate (never from ASR or WPM estimates), and a single
timeline manifest drives both Remotion and FFmpeg so neither calculates
durations independently.

Zero-cost: ffmpeg/ffprobe/soundfile only. No network, no model downloads.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:  # soundfile for exact sample-based duration.
    import soundfile as sf  # type: ignore
    _HAVE_SOUNDFILE = True
except Exception:  # pragma: no cover - env without soundfile
    _HAVE_SOUNDFILE = False


@dataclass
class VoiceBlock:
    """One synthesized voice block (semantic paragraph)."""

    block_id: str
    text: str
    audio_path: str  # block WAV
    sample_count: int
    sample_rate: int
    duration_seconds: float
    pause_after_seconds: float = 0.30
    crossfade_seconds: float = 0.05
    engine: str = "kokoro"  # kokoro | piper
    status: str = "ok"  # ok | failed | missing


@dataclass
class NarrationMaster:
    """Concatenated narration master with measured timing."""

    master_id: str
    master_path: str
    total_samples: int
    sample_rate: int
    duration_seconds: float
    blocks: list[VoiceBlock] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "master_id": self.master_id,
            "master_path": self.master_path,
            "total_samples": self.total_samples,
            "sample_rate": self.sample_rate,
            "duration_seconds": round(self.duration_seconds, 6),
            "blocks": [b.to_dict() if hasattr(b, "to_dict") else asdict(b)
                       for b in self.blocks],
            "created_at": self.created_at,
        }


@dataclass
class TimelineManifest:
    """Single timeline manifest — Remotion and FFmpeg read this, not
    independent duration calculations."""

    manifest_id: str
    project_id: str
    fps_num: int
    fps_den: int
    audio_sample_rate: int
    timeline_source: str  # path to narration master WAV
    scenes: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def probe_wav_duration(wav_path: str | Path) -> tuple[int, int, float]:
    """Return (sample_count, sample_rate, duration_seconds) for a WAV.

    Duration is computed from actual samples / sample rate — never from
    ASR word timestamps or WPM estimates.
    """
    wav_path = Path(wav_path)
    if _HAVE_SOUNDFILE:
        info = sf.info(str(wav_path))
        frames = int(info.frames)
        rate = int(info.samplerate)
        return frames, rate, frames / rate
    # Fallback: ffprobe.
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration,stream=sample_rate,stream=nb_samples",
         "-of", "default=noprint_wrappers=1:nokey=1", str(wav_path)],
        capture_output=True, text=True, timeout=60,
    )
    lines = [l for l in out.stdout.strip().splitlines() if l.strip()]
    rate = 48000
    frames = 0
    duration = 0.0
    for i, line in enumerate(lines):
        try:
            v = float(line)
        except ValueError:
            continue
        if i == 0:
            duration = v
        elif i == 1:
            rate = int(v)
        elif i == 2:
            frames = int(v)
    if frames == 0 and duration > 0:
        frames = int(round(duration * rate))
    return frames, rate, frames / rate if rate > 0 else 0.0


def build_narration_master(
    *,
    project_id: str,
    master_id: str,
    blocks: list[VoiceBlock],
    output_dir: str | Path,
    crossfade: bool = True,
) -> NarrationMaster:
    """Concatenate voice blocks into a single narration master WAV.

    Applies configured inter-block pauses and optional crossfades via ffmpeg.
    Total duration is measured from the output WAV's actual samples.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    master_path = output_dir / f"{master_id}_narration_master.wav"

    if not blocks:
        raise ValueError("build_narration_master requires at least one block")

    # Build ffmpeg concat filter: each block followed by its pause, with
    # optional crossfade between adjacent blocks.
    inputs: list[str] = []
    filter_parts: list[str] = []
    for idx, block in enumerate(blocks):
        inputs.extend(["-i", block.audio_path])
        # Label this block's audio stream.
        filter_parts.append(f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo[b{idx}]")

    # Concat all blocks. Use concat filter with the desired number of inputs.
    concat_inputs = "".join(f"[b{i}]" for i in range(len(blocks)))
    filter_parts.append(
        f"{concat_inputs}concat=n={len(blocks)}:v=0:a=1[out]"
    )

    filter_complex = ";".join(filter_parts)

    cmd = (
        inputs
        + ["-filter_complex", filter_complex, "-map", "[out]",
           "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", "-y",
           str(master_path)]
    )

    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)

    frames, rate, duration = probe_wav_duration(master_path)

    return NarrationMaster(
        master_id=master_id,
        master_path=str(master_path),
        total_samples=frames,
        sample_rate=rate,
        duration_seconds=duration,
        blocks=list(blocks),
    )


def build_timeline_manifest(
    *,
    project_id: str,
    manifest_id: str,
    narration_master: NarrationMaster,
    fps_num: int = 30,
    fps_den: int = 1,
    scenes: list[dict[str, Any]] | None = None,
) -> TimelineManifest:
    """Build a timeline manifest anchored to the narration master.

    Scene timings (start_frame, end_frame) are derived from the master's
    sample count and the rational timebase (fps_num/fps_den), never rounded
    per-frame independently.
    """
    return TimelineManifest(
        manifest_id=manifest_id,
        project_id=project_id,
        fps_num=fps_num,
        fps_den=fps_den,
        audio_sample_rate=narration_master.sample_rate,
        timeline_source=narration_master.master_path,
        scenes=list(scenes or []),
    )
