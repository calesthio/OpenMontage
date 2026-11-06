"""Audio Mixing — combine narration, music and SFX into a master track.

Layers (mixed with FFmpeg `amix` + `loudnorm`):
  1. Narration (priority, intelligible — music ducks beneath it).
  2. Optional background music (commercial-cleared or original only).
  3. Optional SFX.

Uses ffmpeg `-af` filter graph: per-input volume normalization, music
ducking sidechain via `sidechaincompress`, fade in/out, and a final
`loudnorm` pass to hit YouTube-safe loudness (−14 LUFS integrated, −1 dBTP).

Zero-cost: FFmpeg only.  No music/SFX files are sourced by this module —
callers must supply asset paths with confirmed rights; missing files are
silently skipped so narration always renders alone.

Never modifies the original narration files — writes a new master WAV/AAC.
"""

from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AudioMix:
    """One mixed audio master."""

    project_id: str
    output_path: str
    duration_seconds: float
    sample_rate: int
    channels: int
    loudness_lufs: float | None
    true_peak_db: float | None
    narration_path: str
    music_path: str | None
    sfx_paths: list[str]
    fade_in_seconds: float
    fade_out_seconds: float
    music_volume: float
    status: str  # planned | mixed | failed
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AudioMixing:
    """Mix narration (+ optional music/SFX) into a master audio track."""

    def __init__(
        self,
        *,
        ffmpeg_bin: str = "ffmpeg",
        ffprobe_bin: str = "ffprobe",
        sample_rate: int = 48000,
        channels: int = 2,
        narration_lufs: float = -14.0,
        true_peak_db: float = -1.0,
        music_volume: float = 0.15,
        sfx_volume: float = 1.0,
        fade_in_seconds: float = 1.0,
        fade_out_seconds: float = 1.5,
        ducking_threshold_db: float = -20.0,
        ducking_reduction_db: float = -12.0,
    ) -> None:
        self.ffmpeg_bin = ffmpeg_bin
        self.ffprobe_bin = ffprobe_bin
        self.sample_rate = sample_rate
        self.channels = channels
        self.narration_lufs = narration_lufs
        self.true_peak_db = true_peak_db
        self.music_volume = music_volume
        self.sfx_volume = sfx_volume
        self.fade_in_seconds = fade_in_seconds
        self.fade_out_seconds = fade_out_seconds
        self.ducking_threshold_db = ducking_threshold_db
        self.ducking_reduction_db = ducking_reduction_db

    # ------------------------------------------------------------------
    # Mix
    # ------------------------------------------------------------------

    def mix(
        self,
        *,
        project_id: str,
        narration_path: str | Path,
        output_path: str | Path,
        music_path: str | Path | None = None,
        sfx_paths: list[str | Path] | None = None,
        music_volume: float | None = None,
        fade_in_seconds: float | None = None,
        fade_out_seconds: float | None = None,
    ) -> AudioMix:
        """Produce a master audio track.

        Narration is always present and prioritized.  Music/SFX are mixed
        underneath with ducking; missing/optional files are skipped so the
        narration still renders.
        """
        narration_path = Path(narration_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        music_volume = self.music_volume if music_volume is None else music_volume
        fade_in = self.fade_in_seconds if fade_in_seconds is None else fade_in_seconds
        fade_out = (
            self.fade_out_seconds if fade_out_seconds is None else fade_out_seconds
        )

        mv = music_volume if music_volume is not None else self.music_volume
        fi = fade_in if fade_in is not None else self.fade_in_seconds
        fo = fade_out if fade_out is not None else self.fade_out_seconds

        music_path = Path(music_path) if music_path else None
        sfx_paths = [Path(p) for p in (sfx_paths or [])]

        # Validate narration exists.
        if not narration_path.exists():
            return AudioMix(
                project_id=project_id,
                output_path=str(output_path),
                duration_seconds=0.0,
                sample_rate=self.sample_rate,
                channels=self.channels,
                loudness_lufs=None,
                true_peak_db=None,
                narration_path=str(narration_path),
                music_path=str(music_path) if music_path else "",
                sfx_paths=[str(p) for p in sfx_paths],
                fade_in_seconds=fi,
                fade_out_seconds=fo,
                music_volume=mv,
                status="failed",
                error=f"narration not found: {narration_path}",
            )

        # Duration of narration (master length).
        narration_dur = self._probe_duration(narration_path)
        if narration_dur <= 0:
            return AudioMix(
                project_id=project_id,
                output_path=str(output_path),
                duration_seconds=0.0,
                sample_rate=self.sample_rate,
                channels=self.channels,
                loudness_lufs=None,
                true_peak_db=None,
                narration_path=str(narration_path),
                music_path=str(music_path) if music_path else "",
                sfx_paths=[str(p) for p in sfx_paths],
                fade_in_seconds=fi,
                fade_out_seconds=fo,
                music_volume=mv,
                status="failed",
                error="narration duration could not be probed",
            )

        # Build inputs: narration first (index 0), then music, then SFX.
        inputs: list[str] = [str(narration_path)]
        labels: list[str] = ["0:a"]
        if music_path and music_path.exists():
            inputs.append(str(music_path))
            labels.append(f"{len(inputs)-1}:a")
        for p in sfx_paths:
            if p.exists():
                inputs.append(str(p))
                labels.append(f"{len(inputs)-1}:a")

        # Filter graph:
        #   1. each input -> aformat=sample_rates={SR}:channel_layouts={ch}
        #   2. narration: loudnorm (measure only, to log)
        #   3. music: volume=mv + sidechain ducking under narration
        #   4. amix all inputs -> master
        #   5. afade in/out + loudnorm to target
        filter_parts: list[str] = []

        # aformat each input.
        for idx in range(len(inputs)):
            filter_parts.append(
                f"[{idx}:a]aformat=sample_rates={self.sample_rate}:"
                f"channel_layouts=stereo[a{idx}];"
            )

        # Narration volume (unity).
        filter_parts.append("[a0]volume=1.0[nar];")

        # Music: ducked under narration via sidechaincompress.
        # sidechaincompress threshold is linear amplitude 0..1 (-20dBFS ~ 0.1).
        music_idx = 1 if (music_path and music_path.exists()) else None
        sfx_start = (music_idx + 1) if music_idx is not None else 1
        musd_label = "[nar]"  # default: narration alone when no music
        if music_idx is not None:
            filter_parts.append(
                f"[a{music_idx}]volume={mv}[mus];"
                f"[nar][mus]sidechaincompress="
                f"threshold=0.1:ratio=10:attack=20:release=500:"
                f"makeup=0:detection=0[musd];"
            )
            musd_label = "[musd]"

        # SFX (unity-ish, no ducking).
        sfx_labels: list[str] = []
        for j, p in enumerate(sfx_paths):
            if p.exists():
                label = f"[a{sfx_start + j}]"
                sfx_labels.append(label)
                filter_parts.append(
                    f"{label}volume={self.sfx_volume}[sfx{j}];"
                )

        # Amix: narration (+ ducked music) + sfx -> master.
        amix_inputs = f"{musd_label}"
        for sl in sfx_labels:
            amix_inputs += f"[sfx{sfx_labels.index(sl)}]"
        num_inputs = 1 + len(sfx_labels)
        filter_parts.append(
            f"{amix_inputs}amix=inputs={num_inputs}:"
            f"duration=longest:normalize=0[mix];"
        )

        # Fade + loudnorm master.
        filter_parts.append(
            f"[mix]afade=t=in:st=0:d={fi},"
            f"afade=t=out:st={max(0.0,narration_dur-fo)}:d={fo},"
            f"loudnorm=I={self.narration_lufs}:TP={self.true_peak_db}:"
            f"linear=true:print_format=json[master];"
        )

        filter_complex = "".join(filter_parts)

        cmd = [
            self.ffmpeg_bin, "-y",
        ]
        for inp in inputs:
            cmd += ["-i", str(inp)]
        cmd += [
            "-filter_complex", filter_complex,
            "-map", "[master]",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", str(self.sample_rate),
            "-ac", str(self.channels),
            "-shortest",
            str(output_path),
        ]

        try:
            proc = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, timeout=600,
            )
        except subprocess.TimeoutExpired as exc:
            return AudioMix(
                project_id=project_id,
                output_path=str(output_path),
                duration_seconds=narration_dur,
                sample_rate=self.sample_rate,
                channels=self.channels,
                loudness_lufs=None,
                true_peak_db=None,
                narration_path=str(narration_path),
                music_path=str(music_path) if music_path else "",
                sfx_paths=[str(p) for p in sfx_paths],
                fade_in_seconds=fi,
                fade_out_seconds=fo,
                music_volume=mv,
                status="failed",
                error=f"mix timed out: {(exc.stdout or '') + (exc.stderr or '')}",
            )
        except FileNotFoundError:
            return AudioMix(
                project_id=project_id,
                output_path=str(output_path),
                duration_seconds=narration_dur,
                sample_rate=self.sample_rate,
                channels=self.channels,
                loudness_lufs=None,
                true_peak_db=None,
                narration_path=str(narration_path),
                music_path=str(music_path) if music_path else "",
                sfx_paths=[str(p) for p in sfx_paths],
                fade_in_seconds=fi,
                fade_out_seconds=fo,
                music_volume=mv,
                status="failed",
                error="ffmpeg not found",
            )

        if proc.returncode != 0:
            return AudioMix(
                project_id=project_id,
                output_path=str(output_path),
                duration_seconds=narration_dur,
                sample_rate=self.sample_rate,
                channels=self.channels,
                loudness_lufs=None,
                true_peak_db=None,
                narration_path=str(narration_path),
                music_path=str(music_path) if music_path else "",
                sfx_paths=[str(p) for p in sfx_paths],
                fade_in_seconds=fi,
                fade_out_seconds=fo,
                music_volume=mv,
                status="failed",
                error=proc.stderr or f"ffmpeg exit {proc.returncode}",
            )

        actual_dur = self._probe_duration(output_path)
        loudness, true_peak = self._probe_loudness(output_path)

        return AudioMix(
            project_id=project_id,
            output_path=str(output_path),
            duration_seconds=round(actual_dur, 3),
            sample_rate=self.sample_rate,
            channels=self.channels,
            loudness_lufs=loudness,
            true_peak_db=true_peak,
            narration_path=str(narration_path),
            music_path=str(music_path) if music_path else "",
            sfx_paths=[str(p) for p in sfx_paths],
            fade_in_seconds=fi,
            fade_out_seconds=fo,
            music_volume=mv,
            status="mixed",
            error=None,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _probe_duration(self, path: Path) -> float:
        try:
            out = subprocess.check_output(
                [
                    self.ffprobe_bin, "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "csv=p=0", str(path),
                ],
                stderr=subprocess.STDOUT, text=True, timeout=30,
            )
            return float(out.strip())
        except Exception:  # noqa: BLE001
            return 0.0

    def _probe_loudness(self, path: Path) -> tuple[float | None, float | None]:
        """Return (integrated_lufs, true_peak_db) via ffmpeg ebur128 or loudnorm stats."""
        try:
            out = subprocess.check_output(
                [
                    self.ffmpeg_bin, "-hide_banner", "-nostats",
                    "-i", str(path),
                    "-af", "loudnorm=I=-14:TP=-1:linear=true:print_format=json",
                    "-f", "null", "-",
                ],
                stderr=subprocess.STDOUT, text=True, timeout=60,
            )
            # ffmpeg prints a JSON object on stderr; find it.
            import json
            start = out.find("{")
            end = out.rfind("}")
            if start >= 0 and end > start:
                data = json.loads(out[start:end+1])
                return (
                    float(data.get("input_i", data.get("I", 0.0))),
                    float(data.get("input_tp", data.get("TP", 0.0))),
                )
        except Exception:  # noqa: BLE001
            pass
        return None, None
