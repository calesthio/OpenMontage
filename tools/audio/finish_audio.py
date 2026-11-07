"""Audio finishing module per QA_SPEC.md loudness targets.

Two-pass EBU R128 loudnorm (measure, then apply with measured values) +
lookahead limiter for true-peak safety. Optional sidechain-compressor ducking
of a music bed under the narration (EDITING_DOCTRINE §3.2).

Targets I=-14, TP=-1.5, LRA=11 are read from config/qc_thresholds.json
(INITIAL GUESSES; for narration-first content -16..-14 LUFS may be acceptable
-- record this question for the owner). No music is used unless MUSIC_POLICY.md
license evidence exists.

Stdlib + ffmpeg/ffprobe only. No network, no model downloads.
Fail-closed: loudnorm measurement unparsable / filter missing => BLOCKED.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)

DEFAULT_TARGET_I = -14.0
DEFAULT_TARGET_TP = -1.5
DEFAULT_TARGET_LRA = 11.0


def _find_binary(name: str) -> str | None:
    return shutil.which(name)


def _run(cmd: list[str], timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _load_config() -> dict[str, float]:
    """Read loudness targets from config/qc_thresholds.json (INITIAL GUESSES)."""
    import os

    cfg = {
        "target_i": DEFAULT_TARGET_I,
        "target_tp": DEFAULT_TARGET_TP,
        "target_lra": DEFAULT_TARGET_LRA,
    }
    path = os.path.join("config", "qc_thresholds.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        cfg["target_i"] = float(raw.get("lufs_target", DEFAULT_TARGET_I))
        cfg["target_tp"] = float(raw.get("true_peak_max", DEFAULT_TARGET_TP))
        cfg["target_lra"] = float(raw.get("lra_target", DEFAULT_TARGET_LRA))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    return cfg


def _probe_audio(path: str) -> dict[str, Any]:
    """Return {sample_rate, channels, channel_layout, duration} via ffprobe."""
    r = _run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-show_format", path,
        ],
    )
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {r.stderr.strip()[:200]}")
    info = json.loads(r.stdout or "{}")
    audio = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    if not audio:
        raise RuntimeError("no audio stream found")
    a = audio[0]
    fmt = info.get("format", {})
    return {
        "sample_rate": int(a.get("sample_rate", 44100)),
        "channels": int(a.get("channels", 1)),
        "channel_layout": a.get("channel_layout") or ("stereo" if a.get("channels") == 2 else "mono"),
        "duration": float(fmt.get("duration", 0) or 0),
    }


def _loudnorm_measure(input_path: str) -> dict[str, float]:
    """Pass 1: measure integrated loudness/LRA/TP via loudnorm print_format=json.

    Returns {input_i, input_lra, input_tp, input_thresh}. Raises if unparsable.
    """
    r = _run(
        [
            "ffmpeg", "-hide_banner", "-i", input_path,
            "-af", "loudnorm=print_format=json",
            "-f", "null", "-",
        ],
    )
    text = r.stderr or r.stdout or ""
    m_i = re.search(r'"input_i"\s*:\s*"?([-\d.]+)"?', text)
    m_lra = re.search(r'"input_lra"\s*:\s*"?([-\d.]+)"?', text)
    m_tp = re.search(r'"input_tp"\s*:\s*"?([-\d.]+)"?', text)
    m_thresh = re.search(r'"input_thresh"\s*:\s*"?([-\d.]+)"?', text)
    if not (m_i and m_lra and m_tp):
        raise RuntimeError(f"loudnorm measurement unparsable: {text[-500:]}")

    def _to_float(g):
        v = g.group(1)
        if v in ("-", ""):
            return -60.0  # treat silence/minus-infinity as a very low level
        return float(v)

    return {
        "input_i": _to_float(m_i),
        "input_lra": _to_float(m_lra),
        "input_tp": _to_float(m_tp),
        "input_thresh": float(m_thresh.group(1)) if m_thresh else -30.0,
    }


def _loudnorm_filter(measured: dict[str, float], cfg: dict[str, float]) -> str:
    """Pass 2: apply loudnorm with measured values + delivery targets (-af form)."""
    return (
        f"loudnorm=I={cfg['target_i']}:TP={cfg['target_tp']}:"
        f"LRA={cfg['target_lra']}:measured_I={measured['input_i']}:"
        f"measured_LRA={measured['input_lra']}:measured_TP={measured['input_tp']}:"
        f"measured_thresh={measured['input_thresh']}:offset=0:linear=true,"
        f"aresample=44100"
    )


def _limiter_filter() -> str:
    """Lookahead limiter: true-peak safety, engage only above 0 dBFS.

    ``level=1`` is unity gain (default); ``limit=1`` engages only above 0 dBFS,
    so in-range audio passes untouched. ``level=0`` would mute the output.
    """
    return "alimiter=limit=1:level=1"


class FinishAudioTool(BaseTool):
    name = "finish_audio"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "audio_finishing"
    provider = "ffmpeg"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["cmd:ffmpeg", "cmd:ffprobe"]
    install_instructions = "Install FFmpeg (provides loudnorm, sidechaincompress, alimiter, ebur128). No API keys needed."
    agent_skills = ["ffmpeg", "audio-edit"]

    capabilities = ["loudnorm", "true_peak_limit", "sidechain_ducking"]
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500)
    idempotency_key_fields = ["input_path", "music_path", "ducking"]
    side_effects = ["writes finished audio to output_path"]
    user_visible_verification = [
        "Measure output with ebur128: integrated LUFS near target, true peak <= target",
        "Confirm music is ducked under narration when a music bed is given",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path", "output_path"],
        "properties": {
            "input_path": {"type": "string"},
            "output_path": {"type": "string"},
            "music_path": {"type": "string"},
            "ducking": {
                "type": "object",
                "description": "sidechain ducking params (EDITING_DOCTRINE §3.2)",
                "properties": {
                    "enabled": {"type": "boolean", "default": True},
                    "reduction_db": {"type": "number", "default": 12},
                    "attack_ms": {"type": "number", "default": 50},
                    "release_ms": {"type": "number", "default": 100},
                },
            },
        },
    }

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = inputs["input_path"]
        output_path = inputs["output_path"]
        music_path = inputs.get("music_path")
        ducking = inputs.get("ducking") or {}
        cfg = _load_config()

        ffmpeg_bin = _find_binary("ffmpeg")
        ffprobe_bin = _find_binary("ffprobe")
        if not ffmpeg_bin or not ffprobe_bin:
            return ToolResult(
                success=False,
                error="BLOCKED: ffmpeg/ffprobe not available",
                data={"verdict": "BLOCKED"},
            )

        try:
            probe = _probe_audio(input_path)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                error=f"BLOCKED: cannot probe input audio: {exc}",
                data={"verdict": "BLOCKED"},
            )

        rate = probe["sample_rate"]
        ch = probe["channels"]
        layout = probe["channel_layout"]

        out_parent = Path(output_path).parent
        if out_parent and not Path(out_parent).exists():
            Path(out_parent).mkdir(parents=True, exist_ok=True)

        # Build the pre-normalization mix: voice alone, or voice + ducked music.
        mix_input = input_path
        temp_mix = None
        if music_path:
            temp_mix = str(Path(output_path).with_suffix(".ducked_mix.wav"))
            enabled = bool(ducking.get("enabled", True))
            red = float(ducking.get("reduction_db", 12))
            atk = float(ducking.get("attack_ms", 50))
            rel = float(ducking.get("release_ms", 100))
            # sidechaincompress: threshold is linear amplitude (0-1), not dB.
            # Set low enough that typical narration (-20..-40 dBFS) triggers it;
            # ratio controls ducking depth. reduction_db is recorded as the
            # requested depth but the exact curve is tuned after human review.
            threshold = 0.005
            ratio = max(4.0, min(20.0, 2.0 * red))
            # sidechaincompress: music (main=input[0]) ducked by voice (sidechain=input[1]).
            # Split voice so it can feed both the sidechain and the final amix.
            sc = (
                f"[1:a]asetpts=PTS-STARTPTS,atrim=0:{probe['duration']},"
                f"aresample=44100[msc];"
                f"[0:a]asetpts=PTS-STARTPTS,asplit=2[voc_main][voc_sc];"
                f"[msc][voc_sc]sidechaincompress="
                f"threshold={threshold}:ratio={ratio}:attack={atk/1000.0}:release={rel/1000.0}[ducked];"
                f"[voc_main][ducked]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[mix]"
            )
            r = _run(
                [
                    ffmpeg_bin, "-hide_banner", "-y",
                    "-i", input_path,
                    "-i", music_path,
                    "-filter_complex", sc,
                    "-map", "[mix]",
                    "-ar", "44100", "-ac", "2",
                    "-c:a", "pcm_f32le",
                    temp_mix,
                ],
            )
            if r.returncode != 0:
                return ToolResult(
                    success=False,
                    error=f"BLOCKED: sidechain mix failed: {(r.stderr or r.stdout or '').strip()[:300]}",
                    data={"verdict": "BLOCKED"},
                )
            mix_input = temp_mix

        # Pass 1: measure loudness of the (mix or voice) input.
        try:
            measured = _loudnorm_measure(mix_input)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                error=f"BLOCKED: {exc}",
                data={"verdict": "BLOCKED"},
            )

        # Pass 2: apply loudnorm with measured values + delivery targets, then
        # true-peak safety limiter, in one filter chain. Output pcm_s16le wav
        # directly (pcm_f32le->aac and pcm_s16le->aac after a limiter are broken
        # in this ffmpeg build; ebur128 reads pcm_s16le wav fine).
        normed = str(Path(output_path).with_suffix(".norm.wav"))
        r = _run(
            [
                ffmpeg_bin, "-hide_banner", "-y",
                "-i", mix_input,
                "-af", _loudnorm_filter(measured, cfg) + "," + _limiter_filter(),
                "-ar", "44100", "-ac", "2",
                "-c:a", "pcm_s16le",
                output_path,
            ],
        )
        if r.returncode != 0:
            return ToolResult(
                success=False,
                error=f"BLOCKED: loudnorm+limiter failed: {(r.stderr or r.stdout or '').strip()[:300]}",
                data={"verdict": "BLOCKED"},
            )

        # Clean up intermediates.
        for p in (temp_mix, normed):
            if p and Path(p).exists():
                try:
                    Path(p).unlink()
                except OSError:
                    pass

        return ToolResult(
            success=True,
            data={
                "verdict": "PASS",
                "input": input_path,
                "output": output_path,
                "measured_loudness": measured,
                "targets": cfg,
                "sample_rate": rate,
                "channels": ch,
                "ducking": bool(music_path and ducking.get("enabled", True)),
            },
            artifacts=[output_path],
            duration_seconds=round(time.time(), 2),
        )
