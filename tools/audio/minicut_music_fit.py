"""Music written to a finished cut, played locally by the MiniCut CLI.

The tool takes the assembled timeline (edit_decisions cuts, or cut times
and a length), writes a song file whose chords change and whose drum hits
land on every cut, and has ``minicut music check`` and ``minicut music
render`` play it on this computer with recorded instrument samples. The
result is a WAV exactly as long as the cut. No model generates it, no
media leaves the computer and it uses no credits. It needs a free
``minicut login`` first, like every MiniCut command.

A song file is plain data (format ``minicut-song/1``): instruments by id,
notes as ``[pitch, start_s, length_s, velocity]``. An agent can also write
its own song (``song`` input) and this tool only checks and plays it.
The same cuts always give the same song. Trimming a shot changes only that
shot's notes; the later shots keep theirs, moved in time.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any

from tools import minicut_cli
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

SONG_FORMAT = "minicut-song/1"
PITCH_CLASS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
# Scale steps of a four-chord loop: minor i VI III VII, major I V vi IV.
PROGRESSIONS = {
    "minor": [(0, "minor"), (8, "major"), (3, "major"), (10, "major")],
    "major": [(0, "major"), (7, "major"), (9, "minor"), (5, "major")],
}
TRIADS = {"major": [0, 4, 7], "minor": [0, 3, 7]}
DURATION_TOLERANCE_S = 0.001


def timeline(inputs: dict[str, Any]) -> tuple[float, list[float]]:
    """(length in seconds, cut times) from edit_decisions cuts or from cut_times + duration_seconds."""
    cuts = inputs.get("cuts")
    if cuts:
        t, times = 0.0, []
        for cut in cuts:
            if cut.get("layer", "primary") != "primary":
                continue
            speed = max(float(cut.get("speed", 1.0)), 0.1)
            seconds = (float(cut["out_seconds"]) - float(cut.get("in_seconds", 0))) / speed
            if seconds <= 0:
                continue
            if t > 0:
                times.append(round(t, 6))
            t += seconds
        length = round(t, 6)
    else:
        if inputs.get("duration_seconds") is None:
            raise ValueError("give cuts (edit_decisions cuts) or duration_seconds with cut_times")
        length = round(float(inputs["duration_seconds"]), 6)
        times = sorted({round(float(x), 6) for x in inputs.get("cut_times") or []})
    if length < 0.5:
        raise ValueError(f"the cut is {length} s long; the shortest song is 0.5 s")
    return length, [x for x in times if 0 < x < length]


def write_song(length: float, cut_times: list[float], key: str = "D", mode: str = "minor",
               bpm: float = 90.0, title: str = "OpenMontage cut") -> dict[str, Any]:
    """A song whose chord changes and drum hits sit exactly on the cut times."""
    if mode not in PROGRESSIONS:
        raise ValueError(f"mode must be one of {sorted(PROGRESSIONS)}")
    name = key.strip()
    if not name or name[0].upper() not in PITCH_CLASS or name[1:] not in ("", "#", "b"):
        raise ValueError(f"key must be a note letter like D, F# or Bb, got {key!r}")
    root = PITCH_CLASS[name[0].upper()] + {"": 0, "#": 1, "b": -1}[name[1:]]
    beat = 60.0 / float(bpm)
    edges = [0.0, *cut_times, length]
    strings, cello, piano, drums = [], [], [], []
    for i, (start, end) in enumerate(zip(edges, edges[1:])):
        step, quality = PROGRESSIONS[mode][i % 4]
        chord = [60 + (root + step) % 12 + x for x in TRIADS[quality]]  # octave 4
        held = round(end - start, 6)
        strings += [[p, start, held, 58] for p in chord]
        cello.append([chord[0] - 24, start, held, 72])
        # Beats count from each cut, so every shot starts on a beat.
        n = 0
        while start + n * beat < end - 0.05:
            at = round(start + n * beat, 6)
            piano.append([chord[n % 3] + 12, at, round(min(beat * 0.9, end - at), 6), 62 if n % 4 == 0 else 46])
            n += 1
        if i > 0:
            drums.append(["low", start, 1.5, 104])
    return {
        "format": SONG_FORMAT,
        "title": title[:200],
        "length_s": length,
        "tempo_map": [[0, float(bpm)]],
        "meter": 4,
        "markers": [{"t": t, "name": f"cut {i + 1}"} for i, t in enumerate(cut_times)],
        "tracks": [
            {"name": "strings", "instrument": "violins", "volume_db": -14, "pan": -0.2, "notes": strings},
            {"name": "cello", "instrument": "cello", "volume_db": -10, "pan": 0.2, "notes": cello},
            {"name": "piano", "instrument": "piano", "volume_db": -14, "notes": piano},
            {"name": "cut hits", "instrument": "timpani", "volume_db": 6, "notes": drums},
        ],
        "master": {"fade_out_s": round(min(1.5, length / 4), 3)},
        "made_by": "openmontage minicut_music_fit",
    }


class MiniCutMusicFit(BaseTool):
    name = "minicut_music_fit"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "music_generation"
    provider = "minicut"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["cmd:minicut"]
    install_instructions = (
        minicut_cli.INSTALL_INSTRUCTIONS
        + "\n  Then add the music tools once (instrument samples, about 396 MB): minicut setup"
    )
    agent_skills = []

    capabilities = ["generate_background_music", "score_to_cuts"]
    supports = {
        "exact_duration": True,
        "cut_aligned": True,
        "custom_song": True,
        "offline": True,
    }
    best_for = [
        "music that changes on every cut of a finished edit",
        "a track exactly as long as the cut, made locally with no credits",
        "short-form edits that are re-cut often (same cuts in, same song out)",
    ]
    not_good_for = ["vocals or lyrics", "a specific genre or a known song's sound"]
    fallback_tools = ["music_gen", "pixabay_music"]

    input_schema = {
        "type": "object",
        "properties": {
            "cuts": {
                "type": "array",
                "items": {"type": "object"},
                "description": "edit_decisions cuts (in_seconds, out_seconds, speed, layer), in play order",
            },
            "cut_times": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Seconds where the picture cuts, e.g. scene_detect start_seconds. Needs duration_seconds.",
            },
            "duration_seconds": {"type": "number", "description": "Length of the cut when cut_times is used"},
            "key": {"type": "string", "default": "D", "description": "Note letter: C, D, F#, Bb ..."},
            "mode": {"type": "string", "enum": ["minor", "major"], "default": "minor"},
            "bpm": {"type": "number", "minimum": 40, "maximum": 200, "default": 90},
            "song": {
                "type": "object",
                "description": "A minicut-song/1 file the agent wrote itself. Checked and played as given.",
            },
            "output_path": {"type": "string", "description": "Where to save the WAV"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=2, ram_mb=2048, vram_mb=0, disk_mb=200, network_required=False)
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = ["cuts", "cut_times", "duration_seconds", "key", "mode", "bpm", "song"]
    side_effects = ["writes a WAV to output_path", "keeps the song file and its render in the MiniCut cache folder"]
    user_visible_verification = ["Listen across each cut: the chord change and hit should land on it"]

    def _song(self, inputs: dict[str, Any]) -> dict[str, Any]:
        if inputs.get("song"):
            return inputs["song"]
        length, cut_times = timeline(inputs)
        return write_song(length, cut_times, inputs.get("key", "D"), inputs.get("mode", "minor"),
                          float(inputs.get("bpm", 90)))

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if minicut_cli.find_cli() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 60.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        output_path = Path(inputs.get("output_path", "minicut_music_fit.wav"))
        if output_path.suffix.lower() != ".wav":
            return ToolResult(success=False, error="output_path must end in .wav", cost_usd=0.0)
        try:
            song = self._song(inputs)
            text = json.dumps(song, ensure_ascii=True)
            # The CLI reads and writes only inside its own folders, so the song goes in its cache.
            folder = minicut_cli.minicut_home() / "cache" / "openmontage" / "music"
            folder.mkdir(parents=True, exist_ok=True)
            song_path = folder / f"{hashlib.sha256(text.encode()).hexdigest()[:16]}.song.json"
            song_path.write_text(text, encoding="utf-8")

            for words, timeout in ((["music", "check", str(song_path)], 120),
                                   (["music", "render", str(song_path), "--no-mp3"], 1800)):
                code, data = minicut_cli.run(words, timeout=timeout)
                if code != 0:
                    raise RuntimeError(f"minicut {' '.join(words[:2])}: {minicut_cli.message(data, code)}")

            wav = song_path.with_name(song_path.name.replace(".song.json", ".wav"))
            if not wav.is_file():
                raise RuntimeError(f"minicut music render wrote no {wav.name}")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(wav, output_path)
        except Exception as exc:
            return ToolResult(success=False, error=f"MiniCut music failed: {exc}", cost_usd=0.0)

        from tools.analysis.audio_probe import probe_duration

        target = float(song["length_s"])
        seconds = probe_duration(output_path)
        if seconds is not None and abs(seconds - target) > DURATION_TOLERANCE_S:
            return ToolResult(
                success=False, cost_usd=0.0,
                error=f"Rendered {seconds:.3f} s, the cut is {target:.3f} s",
                data={"output_path": str(output_path)},
            )
        report_path = song_path.with_name(song_path.name.replace(".song.json", ".report.json"))
        report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
        return ToolResult(
            success=True,
            data={
                "provider": "minicut",
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "wav",
                "target_seconds": target,
                "duration_seconds": seconds,
                "cut_times": [m["t"] for m in song.get("markers", [])],
                "song_path": str(song_path),
                "notes": report.get("notes"),
                "integrated_lufs": report.get("integrated_lufs"),
                "true_peak_dbtp": report.get("true_peak_dbtp"),
            },
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            model="minicut-song/1",
        )
