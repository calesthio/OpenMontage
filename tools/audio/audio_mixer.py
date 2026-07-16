"""Audio mixer tool wrapping FFmpeg and pydub.

Mixes speech, music, and SFX tracks with support for ducking, fades,
and volume normalization. Falls back to FFmpeg-only mode if pydub is
not installed.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class AudioMixer(BaseTool):
    name = "audio_mixer"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "audio_processing"
    provider = "ffmpeg"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg"]
    install_instructions = (
        "FFmpeg is required. pydub is optional for advanced mixing:\n"
        "pip install pydub"
    )
    agent_skills = ["ffmpeg", "video-toolkit"]

    capabilities = ["mix", "duck", "fade", "normalize", "extract_audio", "segmented_music"]

    input_schema = {
        "type": "object",
        "required": ["operation"],
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["mix", "duck", "extract", "full_mix", "segmented_music"],
                "description": (
                    "mix: layer multiple tracks with volume/delay/fades. "
                    "duck: lower music volume when speech is present. "
                    "extract: extract audio from video file. "
                    "full_mix: combine narration tracks + music with ducking + normalize "
                    "in a single call (preferred for compose-director). "
                    "segmented_music: mix music into a video only during specified "
                    "time segments (e.g. music during talking head, silence during "
                    "showcase clips)."
                ),
            },
            "tracks": {
                "type": "array",
                "description": (
                    "Audio tracks for mix/duck operations (advanced format). "
                    "For duck, each track needs a 'role' of 'speech' or 'music'. "
                    "For the simple duck API, use primary_audio/secondary_audio instead."
                ),
                "items": {
                    "type": "object",
                    "required": ["path", "role"],
                    "properties": {
                        "path": {"type": "string"},
                        "role": {
                            "type": "string",
                            "enum": ["speech", "music", "sfx", "primary", "secondary"],
                        },
                        "volume": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1.0,
                            "default": 1.0,
                        },
                        "start_seconds": {"type": "number", "minimum": 0},
                        "fade_in_seconds": {"type": "number", "minimum": 0},
                        "fade_out_seconds": {"type": "number", "minimum": 0},
                    },
                },
            },
            "primary_audio": {
                "type": "string",
                "description": (
                    "Path to primary/speech audio track (duck operation, simple format). "
                    "This is the track that stays at full volume (e.g. narration/dialogue). "
                    "Use with secondary_audio as an alternative to the tracks array."
                ),
            },
            "secondary_audio": {
                "type": "string",
                "description": (
                    "Path to secondary/music audio track (duck operation, simple format). "
                    "This track gets ducked (volume lowered) when primary audio is present. "
                    "Use with primary_audio as an alternative to the tracks array."
                ),
            },
            "duck_level": {
                "type": "number",
                "description": (
                    "Ducking attenuation in dB for the secondary track (duck operation, "
                    "simple format). Negative values reduce volume, e.g. -12 means duck "
                    "by 12dB. Converted to a linear ratio internally. Default: -12."
                ),
                "default": -12,
            },
            "input_path": {"type": "string", "description": "Input for extract operation"},
            "output_path": {"type": "string"},
            "ducking": {
                "type": "object",
                "description": (
                    "Advanced ducking parameters. Works with both the simple "
                    "(primary_audio/secondary_audio) and advanced (tracks) formats."
                ),
                "properties": {
                    "enabled": {"type": "boolean", "default": True},
                    "music_volume_during_speech": {
                        "type": "number", "minimum": 0, "maximum": 1.0, "default": 0.15,
                    },
                    "attack_ms": {"type": "number", "default": 200},
                    "release_ms": {"type": "number", "default": 800},
                },
            },
            "normalize": {
                "type": "boolean",
                "default": True,
                "description": (
                    "Two-pass EBU R128 normalization to -14 LUFS / -1.5 dBTP "
                    "(YouTube target; see tools/audio/loudness.py)."
                ),
            },
            "video_path": {
                "type": "string",
                "description": (
                    "Path to the assembled video (segmented_music operation). "
                    "Music is mixed into this video's audio at specified segments."
                ),
            },
            "music_path": {
                "type": "string",
                "description": "Path to background music file (segmented_music operation).",
            },
            "music_volume": {
                "type": "number",
                "minimum": 0,
                "maximum": 1.0,
                "default": 0.20,
                "description": "Volume level for music during active segments.",
            },
            "segments": {
                "type": "array",
                "description": (
                    "Time segments where music should play (segmented_music operation). "
                    "Each segment: {start: seconds, end: seconds}. Music fades in/out "
                    "at segment boundaries. Outside these segments, music is silent."
                ),
                "items": {
                    "type": "object",
                    "required": ["start", "end"],
                    "properties": {
                        "start": {"type": "number", "minimum": 0},
                        "end": {"type": "number", "minimum": 0},
                    },
                },
            },
            "fade_duration": {
                "type": "number",
                "default": 0.5,
                "description": "Duration of fade in/out at segment boundaries (seconds).",
            },
        },
    }

    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=500)
    idempotency_key_fields = ["operation", "tracks", "ducking"]
    side_effects = ["writes mixed audio file to output_path"]
    user_visible_verification = [
        "Listen to mixed output and verify speech clarity and music ducking",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        # "full_mix" is explicitly documented as "the preferred operation for
        # the compose-director skill" (see _full_mix's own docstring) — the
        # only one of five operations with a stated default use case. Same
        # defect class as video_compose/video_stitch, confirmed live: an
        # agent driving compose called this tool with mix-shaped params but no
        # "operation", raising a bare KeyError and burning the stage's entire
        # turn budget instead of failing on ITS OWN precondition.
        operation = inputs.get("operation", "full_mix")
        start = time.time()

        try:
            if operation == "mix":
                result = self._mix(inputs)
            elif operation == "duck":
                result = self._duck(inputs)
            elif operation == "extract":
                result = self._extract(inputs)
            elif operation == "full_mix":
                result = self._full_mix(inputs)
            elif operation == "segmented_music":
                result = self._segmented_music(inputs)
            else:
                return ToolResult(success=False, error=f"Unknown operation: {operation}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

        result.duration_seconds = round(time.time() - start, 2)
        return result

    # ------------------------------------------------------------------
    # Shared helpers (audit 2026-07-16, Wave 1 ① — audio chain quality)
    # ------------------------------------------------------------------

    def _probe_duration(self, path: str) -> float | None:
        """Duration of an audio file in seconds, or None if unprobeable."""
        try:
            proc = self.run_command([
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "csv=p=0", str(path),
            ], timeout=60)
            return float(proc.stdout.strip().splitlines()[0])
        except Exception:
            return None

    @staticmethod
    def _duck_envelope_expr(
        intervals: list[tuple[float, float]],
        duck_gain: float,
        attack_s: float,
        release_s: float,
    ) -> str:
        """Volume expression that ducks music DURING speech intervals and
        returns it to full bed level in the gaps.

        This replaces the old sidechaincompress + static `volume=x*3`
        compensation, which applied a constant post-gain to the whole track —
        the music never recovered between narration segments and the
        advertised music_volume_during_speech semantics were fiction. With
        known speech intervals (we schedule narration ourselves via
        start_seconds), a deterministic gain envelope is both more accurate
        and reproducible than a compressor: gain ramps from 1.0 down to
        `duck_gain` over `attack_s` at speech start and back up over
        `release_s` after speech end — the Premiere/Descript ducking model.
        """
        attack = max(attack_s, 0.01)
        release = max(release_s, 0.01)
        envs = []
        for start, end in intervals:
            s, e = round(start, 3), round(end, 3)
            envs.append(
                f"if(lt(t,{s}),0,"
                f"if(lt(t,{s + attack}),(t-{s})/{attack},"
                f"if(lt(t,{e}),1,"
                f"if(lt(t,{e + release}),1-(t-{e})/{release},0))))"
            )
        env_sum = "+".join(f"({e})" for e in envs) if envs else "0"
        return f"1-{1 - duck_gain}*min(1,{env_sum})"

    def _normalize_output(self, premix_path: Path, output_path: Path) -> bool:
        """Two-pass -14 LUFS normalization from a premix file. Best-effort:
        on failure the premix is promoted to the output unchanged."""
        from tools.audio.loudness import normalize_media_loudness

        if normalize_media_loudness(premix_path, output_path):
            premix_path.unlink(missing_ok=True)
            return True
        premix_path.replace(output_path)
        return False

    def _mix(self, inputs: dict[str, Any]) -> ToolResult:
        """Mix multiple audio tracks into one output."""
        tracks = inputs.get("tracks", [])
        if not tracks:
            return ToolResult(success=False, error="No tracks provided")

        output_path = Path(inputs.get("output_path", "mixed_audio.wav"))
        normalize = inputs.get("normalize", True)

        # Validate all inputs exist
        for t in tracks:
            if not Path(t["path"]).exists():
                return ToolResult(success=False, error=f"Track not found: {t['path']}")

        # Build FFmpeg complex filter for mixing
        filter_parts = []
        input_args = []

        for i, track in enumerate(tracks):
            input_args.extend(["-i", track["path"]])
            volume = track.get("volume", 1.0)
            delay_ms = int(track.get("start_seconds", 0) * 1000)
            fade_in = track.get("fade_in_seconds", 0)
            fade_out = track.get("fade_out_seconds", 0)

            filters = []
            if volume != 1.0:
                filters.append(f"volume={volume}")
            if delay_ms > 0:
                filters.append(f"adelay={delay_ms}|{delay_ms}")
            if fade_in > 0:
                filters.append(f"afade=t=in:d={fade_in}")
            if fade_out > 0:
                filters.append(f"afade=t=out:d={fade_out}")

            if filters:
                filter_chain = ",".join(filters)
                filter_parts.append(f"[{i}:a]{filter_chain}[a{i}]")
            else:
                filter_parts.append(f"[{i}:a]acopy[a{i}]")

        # Amix all processed streams. normalize=0: ffmpeg's amix default
        # scales every input by 1/n, so a narration+music mix used to arrive
        # ~6 dB down before loudnorm dragged it back up — audible pumping.
        # Track gains are OUR job (the per-track volume filters above);
        # amix must just sum.
        mix_inputs = "".join(f"[a{i}]" for i in range(len(tracks)))
        filter_parts.append(
            f"{mix_inputs}amix=inputs={len(tracks)}:duration=longest:"
            f"dropout_transition=2:normalize=0[mixed]"
        )

        filter_complex = ";".join(filter_parts)

        # Render the premix at 48 kHz, then two-pass normalize to -14 LUFS.
        # The old in-graph single-pass loudnorm ran in dynamic mode (audible
        # gain pumping) at -16, and silently resampled the output to 192 kHz.
        premix_path = output_path.with_name(output_path.stem + ".premix.wav") if normalize else output_path
        cmd = ["ffmpeg", "-y"]
        cmd.extend(input_args)
        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[mixed]", "-ar", "48000", str(premix_path)])

        self.run_command(cmd)

        normalized = False
        if normalize:
            normalized = self._normalize_output(premix_path, output_path)

        return ToolResult(
            success=True,
            data={
                "operation": "mix",
                "track_count": len(tracks),
                "output": str(output_path),
                "normalized": normalized,
                "loudness_target_lufs": -14 if normalized else None,
            },
            artifacts=[str(output_path)],
        )

    def _duck(self, inputs: dict[str, Any]) -> ToolResult:
        """Apply ducking: lower music volume when speech is present.

        Accepts two input formats:

        Simple format (preferred for agents):
            {
                "operation": "duck",
                "primary_audio": "speech.mp3",
                "secondary_audio": "music.mp3",
                "duck_level": -12,
                "output_path": "out.wav"
            }

        Advanced format (tracks array):
            {
                "operation": "duck",
                "tracks": [
                    {"path": "speech.mp3", "role": "primary"},  # or "speech"
                    {"path": "music.mp3", "role": "secondary"}  # or "music"
                ],
                "output_path": "out.wav"
            }
        """
        ducking = inputs.get("ducking", {})
        output_path = Path(inputs.get("output_path", "ducked_audio.wav"))

        # --- Resolve speech/music paths from either input format ---
        speech_path = None
        music_path = None

        # Simple format: primary_audio / secondary_audio
        if "primary_audio" in inputs or "secondary_audio" in inputs:
            speech_path = inputs.get("primary_audio")
            music_path = inputs.get("secondary_audio")
            # If duck_level (dB) is provided, convert to linear ratio for
            # music_volume_during_speech.  e.g. -12 dB -> 10^(-12/20) ~ 0.25
            if "duck_level" in inputs and "ducking" not in inputs:
                import math
                db = inputs["duck_level"]
                ducking = dict(ducking)  # copy so we don't mutate caller
                ducking.setdefault(
                    "music_volume_during_speech",
                    round(math.pow(10, db / 20), 4),
                )

        # Advanced format: tracks array with role field
        tracks = inputs.get("tracks", [])
        if tracks and speech_path is None and music_path is None:
            # Support both naming conventions: speech/music and primary/secondary
            speech_tracks = [
                t for t in tracks if t.get("role") in ("speech", "primary")
            ]
            music_tracks = [
                t for t in tracks if t.get("role") in ("music", "secondary")
            ]
            if speech_tracks:
                speech_path = speech_tracks[0]["path"]
            if music_tracks:
                music_path = music_tracks[0]["path"]

        if not speech_path or not music_path:
            return ToolResult(
                success=False,
                error=(
                    "Ducking requires a primary (speech) and secondary (music) track. "
                    "Provide either primary_audio/secondary_audio params, or a tracks "
                    "array with role='speech'/'primary' and role='music'/'secondary'."
                ),
            )

        music_vol = ducking.get("music_volume_during_speech", 0.15)
        attack = ducking.get("attack_ms", 200) / 1000
        release = ducking.get("release_ms", 800) / 1000

        # Deterministic envelope duck (see _duck_envelope_expr): music dips to
        # music_vol for the speech track's duration and recovers afterward.
        # Falls back to sidechaincompress only when the speech file can't be
        # probed — WITHOUT the old static `volume=x*3` "compensation", which
        # was a constant post-gain that defeated the duck's recovery.
        speech_dur = self._probe_duration(speech_path)
        if speech_dur is not None:
            expr = self._duck_envelope_expr([(0.0, speech_dur)], music_vol, attack, release)
            music_chain = f"[1:a]volume='{expr}':eval=frame[music_out]"
        else:
            music_chain = (
                f"[1:a]sidechaincompress="
                f"threshold=0.02:ratio=9:attack={attack}:release={release}:"
                f"level_sc=1[music_out]"
            )
        # A label can only be consumed once — the sidechain fallback needs the
        # speech twice (key + mix), so fork it explicitly.
        if speech_dur is not None:
            filter_complex = (
                f"{music_chain};"
                f"[0:a][music_out]amix=inputs=2:duration=longest:normalize=0[out]"
            )
        else:
            filter_complex = (
                f"[0:a]asplit=2[speech_key][speech_mix];"
                f"{music_chain.replace('[1:a]', '[1:a][speech_key]')};"
                f"[speech_mix][music_out]amix=inputs=2:duration=longest:normalize=0[out]"
            )

        cmd = [
            "ffmpeg", "-y",
            "-i", speech_path,
            "-i", music_path,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-ar", "48000",
            str(output_path),
        ]

        self.run_command(cmd)

        return ToolResult(
            success=True,
            data={
                "operation": "duck",
                "speech_track": speech_path,
                "music_track": music_path,
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
        )

    def _extract(self, inputs: dict[str, Any]) -> ToolResult:
        """Extract audio from a video file."""
        input_path = Path(inputs["input_path"])
        if not input_path.exists():
            return ToolResult(success=False, error=f"Input not found: {input_path}")

        output_path = Path(
            inputs.get("output_path", str(input_path.with_suffix(".wav")))
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(output_path),
        ]

        self.run_command(cmd)

        return ToolResult(
            success=True,
            data={
                "operation": "extract",
                "input": str(input_path),
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
        )

    def _full_mix(self, inputs: dict[str, Any]) -> ToolResult:
        """One-call mix: layer narration tracks, add music with ducking, normalize.

        This is the preferred operation for the compose-director skill.
        It combines mix + duck + normalize in a single FFmpeg filter graph.

        Input format:
            {
                "operation": "full_mix",
                "tracks": [
                    {"path": "narration_s1.mp3", "role": "speech", "start_seconds": 0},
                    {"path": "narration_s2.mp3", "role": "speech", "start_seconds": 10.5},
                    {"path": "music.mp3", "role": "music", "volume": 0.3}
                ],
                "ducking": {
                    "enabled": true,
                    "music_volume_during_speech": 0.15,
                    "attack_ms": 200,
                    "release_ms": 500
                },
                "normalize": true,
                "output_path": "mixed_audio.wav"
            }
        """
        tracks = inputs.get("tracks", [])
        if not tracks:
            return ToolResult(success=False, error="No tracks provided for full_mix")

        output_path = Path(inputs.get("output_path", "full_mix_output.wav"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        normalize = inputs.get("normalize", True)
        ducking = inputs.get("ducking", {"enabled": True})

        speech_tracks = [t for t in tracks if t.get("role") in ("speech", "primary")]
        music_tracks = [t for t in tracks if t.get("role") in ("music", "secondary")]
        sfx_tracks = [t for t in tracks if t.get("role") == "sfx"]
        all_tracks = speech_tracks + music_tracks + sfx_tracks

        if not all_tracks:
            return ToolResult(success=False, error="No valid tracks (need speech/music/sfx roles)")

        # Validate all files exist
        for t in all_tracks:
            if not Path(t["path"]).exists():
                return ToolResult(success=False, error=f"Track not found: {t['path']}")

        # Build FFmpeg inputs and filter graph
        input_args = []
        filter_parts = []

        for i, track in enumerate(all_tracks):
            input_args.extend(["-i", track["path"]])
            volume = track.get("volume", 1.0)
            delay_ms = int(track.get("start_seconds", 0) * 1000)
            fade_in = track.get("fade_in_seconds", 0)
            fade_out = track.get("fade_out_seconds", 0)

            filters = []
            if volume != 1.0:
                filters.append(f"volume={volume}")
            if delay_ms > 0:
                filters.append(f"adelay={delay_ms}|{delay_ms}")
            if fade_in > 0:
                filters.append(f"afade=t=in:d={fade_in}")
            if fade_out > 0:
                filters.append(f"afade=t=out:d={fade_out}")

            if filters:
                filter_chain = ",".join(filters)
                filter_parts.append(f"[{i}:a]{filter_chain}[a{i}]")
            else:
                filter_parts.append(f"[{i}:a]acopy[a{i}]")

        # If ducking is enabled and we have both speech and music, apply sidechain
        duck_enabled = ducking.get("enabled", True) if isinstance(ducking, dict) else bool(ducking)

        duck_mode = "none"
        if duck_enabled and speech_tracks and music_tracks:
            # Combine speech tracks (they're time-offset narration segments —
            # normalize=0 so amix doesn't scale each by 1/n).
            speech_indices = list(range(len(speech_tracks)))
            speech_labels = "".join(f"[a{i}]" for i in speech_indices)

            if len(speech_tracks) > 1:
                filter_parts.append(
                    f"{speech_labels}amix=inputs={len(speech_tracks)}:"
                    f"duration=longest:normalize=0[speech_out]"
                )
            else:
                filter_parts.append(f"[a{speech_indices[0]}]acopy[speech_out]")

            # Mix music tracks together
            music_start = len(speech_tracks)
            music_indices = list(range(music_start, music_start + len(music_tracks)))
            music_labels = "".join(f"[a{i}]" for i in music_indices)

            if len(music_tracks) > 1:
                filter_parts.append(
                    f"{music_labels}amix=inputs={len(music_tracks)}:"
                    f"duration=longest:normalize=0[music_mix]"
                )
                music_in = "[music_mix]"
            else:
                music_in = f"[a{music_indices[0]}]"

            duck_params = ducking if isinstance(ducking, dict) else {}
            attack = duck_params.get("attack_ms", 200) / 1000
            release = duck_params.get("release_ms", 800) / 1000
            music_vol = duck_params.get("music_volume_during_speech", 0.15)

            # Deterministic envelope duck: we SCHEDULE the narration segments
            # ourselves (start_seconds + probed duration), so the exact speech
            # intervals are known — a gain envelope dips music to music_vol
            # during them and lets it genuinely recover in the gaps. The old
            # sidechaincompress chain ended in a static `volume=x*3`
            # compensation gain, so the music level never came back up between
            # segments and music_volume_during_speech was a constant scaler,
            # not a duck depth (audit 2026-07-16, Wave 1 ①).
            intervals: list[tuple[float, float]] = []
            for t in speech_tracks:
                dur = self._probe_duration(t["path"])
                if dur is None:
                    intervals = []
                    break
                start = float(t.get("start_seconds", 0))
                intervals.append((start, start + dur))

            if intervals:
                duck_mode = "envelope"
                expr = self._duck_envelope_expr(intervals, music_vol, attack, release)
                filter_parts.append(f"{music_in}volume='{expr}':eval=frame[music_out]")
            else:
                # Probe failed → compressor fallback, without the old static
                # post-gain. Needs the speech twice (key + mix): fork it.
                duck_mode = "sidechain"
                filter_parts[-1] = filter_parts[-1].replace("[speech_out]", "[speech_all]")
                filter_parts.append("[speech_all]asplit=2[speech_key][speech_out]")
                filter_parts.append(
                    f"{music_in}[speech_key]sidechaincompress="
                    f"threshold=0.02:ratio=9:attack={attack}:release={release}:"
                    f"level_sc=1[music_out]"
                )

            # Final mix: speech + ducked music
            mix_label = "[speech_out][music_out]amix=inputs=2:duration=longest:normalize=0[premix]"

            # Add SFX if present
            sfx_start = len(speech_tracks) + len(music_tracks)
            if sfx_tracks:
                sfx_labels = "".join(f"[a{i}]" for i in range(sfx_start, sfx_start + len(sfx_tracks)))
                filter_parts.append(mix_label.replace("[premix]", "[pressfx]"))
                filter_parts.append(
                    f"[pressfx]{sfx_labels}amix=inputs={1 + len(sfx_tracks)}:"
                    f"duration=longest:normalize=0[premix]"
                )
            else:
                filter_parts.append(mix_label)

        else:
            # No ducking: simple amix of all tracks
            all_labels = "".join(f"[a{i}]" for i in range(len(all_tracks)))
            filter_parts.append(
                f"{all_labels}amix=inputs={len(all_tracks)}:duration=longest:"
                f"dropout_transition=2:normalize=0[premix]"
            )

        filter_complex = ";".join(p for p in filter_parts if p)

        # Render the premix at 48 kHz, then two-pass normalize to -14 LUFS
        # (see _mix for why the old in-graph single-pass loudnorm was wrong).
        premix_path = output_path.with_name(output_path.stem + ".premix.wav") if normalize else output_path
        cmd = ["ffmpeg", "-y"]
        cmd.extend(input_args)
        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", "[premix]", "-ar", "48000", str(premix_path)])

        self.run_command(cmd)

        normalized = False
        if normalize:
            normalized = self._normalize_output(premix_path, output_path)

        return ToolResult(
            success=True,
            data={
                "operation": "full_mix",
                "speech_tracks": len(speech_tracks),
                "music_tracks": len(music_tracks),
                "sfx_tracks": len(sfx_tracks),
                "ducking_enabled": duck_enabled,
                "duck_mode": duck_mode,
                "normalized": normalized,
                "loudness_target_lufs": -14 if normalized else None,
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
        )

    def _segmented_music(self, inputs: dict[str, Any]) -> ToolResult:
        """Mix background music into a video only during specified time segments.

        Uses FFmpeg volume expressions with smooth fades at segment boundaries.
        Music is silent outside the specified segments.

        Input format:
            {
                "operation": "segmented_music",
                "video_path": "assembled.mp4",
                "music_path": "bg_music.mp3",
                "music_volume": 0.20,
                "segments": [
                    {"start": 0, "end": 17.0},
                    {"start": 167.0, "end": 175.0}
                ],
                "fade_duration": 0.5,
                "output_path": "final_with_music.mp4"
            }
        """
        video_path = inputs.get("video_path")
        music_path = inputs.get("music_path")
        output_path = Path(inputs.get("output_path", "segmented_music_output.mp4"))
        segments = inputs.get("segments", [])
        music_volume = inputs.get("music_volume", 0.20)
        fade_dur = inputs.get("fade_duration", 0.5)

        if not video_path or not Path(video_path).exists():
            return ToolResult(success=False, error=f"Video not found: {video_path}")
        if not music_path or not Path(music_path).exists():
            return ToolResult(success=False, error=f"Music not found: {music_path}")
        if not segments:
            return ToolResult(success=False, error="No segments specified")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Get video duration
        dur_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            video_path,
        ]
        total_dur = float(self.run_command(dur_cmd).stdout.strip().split("\n")[0])

        # Build volume expression for each segment with smooth fades
        parts = []
        for seg in sorted(segments, key=lambda s: s["start"]):
            s = seg["start"]
            e = seg["end"]
            fade_in_end = s + fade_dur
            fade_out_start = e - fade_dur
            parts.append(
                f"if(lt(t,{s}),0,"
                f"if(lt(t,{fade_in_end}),{music_volume}*(t-{s})/{fade_dur},"
                f"if(lt(t,{fade_out_start}),{music_volume},"
                f"if(lt(t,{e}),{music_volume}*({e}-t)/{fade_dur},"
                f"0))))"
            )

        vol_expr = "+".join(f"({p})" for p in parts) if len(parts) > 1 else parts[0]

        filter_complex = (
            f"[1:a]atrim=0:{total_dur},asetpts=PTS-STARTPTS,"
            f"volume='{vol_expr}':eval=frame[music_shaped];"
            f"[0:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[speech];"
            f"[music_shaped]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[music_fmt];"
            # normalize=0 — amix's default 1/n scaling would drop the video's
            # own speech 6 dB the moment music is mixed in.
            f"[speech][music_fmt]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[aout]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-stream_loop", "-1",
            "-i", music_path,
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path),
        ]

        self.run_command(cmd)

        if not output_path.exists():
            return ToolResult(success=False, error="No output produced")

        return ToolResult(
            success=True,
            data={
                "operation": "segmented_music",
                "video": video_path,
                "music": music_path,
                "segments": segments,
                "music_volume": music_volume,
                "fade_duration": fade_dur,
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
        )
