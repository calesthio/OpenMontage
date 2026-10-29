#!/usr/bin/env python3
"""Failing tests first (TDD) for tools/audio/finish_audio.py.

Uses the repo QC module (tools/qa/qc.py) to measure ebur128 integrated LUFS +
true peak after finishing. Fixtures generated with ffmpeg lavfi into tmp dirs;
no media committed. Stdlib + ffmpeg/ffprobe only; no network, no model downloads.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.audio.finish_audio import FinishAudioTool  # noqa: E402
from tools.qa.qc import QCTool  # noqa: E402

FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"


def _run(cmd, timeout=180):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _gen_tone(path, duration=8, freq=440, level_db=-30, rate=44100, channels=1):
    """Generate a sine tone at level_db (peak near 0 dBFS if level_db=0)."""
    ch = "stereo" if channels == 2 else "mono"
    src = f"sine=frequency={freq}:duration={duration}:sample_rate={rate}"
    cmd = [
        FFMPEG, "-y", "-f", "lavfi", "-i", src,
        "-af", f"volume={level_db}dB",
        "-ar", str(rate), "-ac", str(channels),
        "-c:a", "pcm_f32le", path,
    ]
    _run(cmd)
    assert os.path.exists(path) and os.path.getsize(path) > 0


def _gen_voice_plus_silence(path, duration=10, rate=44100, channels=1):
    """Voice tone 0-5s, silence 5-10s (for ducking segment measurement)."""
    ch = "stereo" if channels == 2 else "mono"
    cmd = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration=5:sample_rate={rate}",
        "-f", "lavfi", "-i", f"anullsrc=duration=5:sample_rate={rate}:channel_layout={ch}",
        "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[a]",
        "-map", "[a]", "-ar", str(rate), "-ac", str(channels),
        "-c:a", "pcm_f32le", path,
    ]
    _run(cmd)
    assert os.path.exists(path) and os.path.getsize(path) > 0


def _gen_noise_bed(path, duration=10, rate=44100, channels=1):
    """Pink noise music bed."""
    ch = "stereo" if channels == 2 else "mono"
    cmd = [
        FFMPEG, "-y", "-f", "lavfi", "-i", f"anoisesrc=d={duration}:c=pink:sample_rate={rate}",
        "-ar", str(rate), "-ac", str(channels),
        "-c:a", "pcm_f32le", path,
    ]
    _run(cmd)
    assert os.path.exists(path) and os.path.getsize(path) > 0


def _ebur128(path):
    """Return (integrated_lufs, true_peak) via QC tool's ebur128 check."""
    tmp = Path(path).with_suffix(".qa_report.json")
    qc = QCTool()
    res = qc.execute({
        "input_path": str(path),
        "output_path": str(tmp),
    })
    assert res.success, f"qc.execute failed: {res.error}"
    report = json.loads(tmp.read_text())
    entry = next(e for e in report if e["check_id"] == "ebur128")
    # measured_value like "I=-17.1, TP=-0.0"
    mv = entry["measured_value"] or ""
    i_lufs = None
    tp = None
    mi = re.search(r"I=([-\d.]+)", mv)
    mtp = re.search(r"TP=([-\d.]+)", mv)
    if mi:
        i_lufs = float(mi.group(1))
    if mtp:
        tp = float(mtp.group(1))
    return i_lufs, tp, entry


def _volume(path):
    """Return mean_volume (dB) via ffmpeg volumedetect."""
    r = _run([FFMPEG, "-i", path, "-af", "volumedetect", "-f", "null", "-"])
    mv = None
    m = re.search(r"mean_volume:\s*([-\d.]+) dB", r.stderr)
    if m:
        mv = float(m.group(1))
    return mv


def _extract_segment(path, start, end, out):
    _run([FFMPEG, "-y", "-i", path, "-ss", str(start), "-t", str(end - start),
          "-c:a", "pcm_f32le", out])
    assert os.path.exists(out)


def test_voice_tone_loudness_and_true_peak(tmp_path):
    """(a) Low-level voice tone + peak near 0 dBFS -> I within -14 +/- 2, TP <= -1.5."""
    in_wav = tmp_path / "voice_in.wav"
    out_wav = tmp_path / "voice_out.wav"
    _gen_tone(in_wav, duration=8, freq=440, level_db=-40, rate=44100, channels=1)

    tool = FinishAudioTool()
    res = tool.execute({
        "input_path": str(in_wav),
        "output_path": str(out_wav),
    })
    assert res.success, f"finish failed: {res.error}"
    assert os.path.exists(out_wav)

    i_lufs, tp, entry = _ebur128(out_wav)
    assert entry["status"] == "PASS", entry
    assert i_lufs is not None
    assert abs(i_lufs - (-14.0)) <= 2.0, f"I={i_lufs} not within -14 +/- 2"
    assert tp is not None
    assert tp <= -1.5, f"TP={tp} > -1.5"


def test_music_ducking(tmp_path):
    """(b) With music bed: music ducked under voice (voiced segment quieter than music-only)."""
    voice = tmp_path / "voice.wav"
    music = tmp_path / "music.wav"
    out = tmp_path / "mixed.wav"
    _gen_voice_plus_silence(voice, duration=10, rate=44100, channels=1)
    _gen_noise_bed(music, duration=10, rate=44100, channels=1)

    tool = FinishAudioTool()
    res = tool.execute({
        "input_path": str(voice),
        "output_path": str(out),
        "music_path": str(music),
        "ducking": {"enabled": True, "reduction_db": 12, "attack_ms": 50, "release_ms": 100},
    })
    assert res.success, f"finish failed: {res.error}"
    assert os.path.exists(out)

    # voiced segment (0-5s) vs music-only segment (5-10s)
    vseg = tmp_path / "vseg.wav"
    mseg = tmp_path / "mseg.wav"
    _extract_segment(out, 0, 5, vseg)
    _extract_segment(out, 5, 10, mseg)
    v_db = _volume(vseg)
    m_db = _volume(mseg)
    assert v_db is not None and m_db is not None
    # music under voice should be lower than music-only segment
    assert m_db - v_db >= 5.0, f"music not ducked: voiced={v_db:.1f} music-only={m_db:.1f}"


def test_no_music_still_works(tmp_path):
    """(c) No music: finishing still works."""
    in_wav = tmp_path / "in.wav"
    out_wav = tmp_path / "out.wav"
    _gen_tone(in_wav, duration=6, freq=440, level_db=-40, rate=44100, channels=1)
    tool = FinishAudioTool()
    res = tool.execute({"input_path": str(in_wav), "output_path": str(out_wav)})
    assert res.success, f"finish failed: {res.error}"
    assert os.path.exists(out_wav)
    i_lufs, tp, entry = _ebur128(out_wav)
    assert entry["status"] == "PASS", entry
    assert abs(i_lufs - (-14.0)) <= 2.0


def test_mono_stereo_and_rates(tmp_path):
    """(d) mono/stereo and 22050/44100 Hz inputs all finish to PASS."""
    for rate in (22050, 44100):
        for ch in (1, 2):
            in_wav = tmp_path / f"in_{rate}_{ch}.wav"
            out_wav = tmp_path / f"out_{rate}_{ch}.wav"
            _gen_tone(in_wav, duration=5, freq=440, level_db=-40, rate=rate, channels=ch)
            tool = FinishAudioTool()
            res = tool.execute({"input_path": str(in_wav), "output_path": str(out_wav)})
            assert res.success, f"finish failed rate={rate} ch={ch}: {res.error}"
            assert os.path.exists(out_wav)
            i_lufs, tp, entry = _ebur128(out_wav)
            assert entry["status"] == "PASS", entry
            assert abs(i_lufs - (-14.0)) <= 2.0


def test_failure_path_blocked(tmp_path, monkeypatch):
    """(e) ffmpeg filter missing or measurement unparsable -> BLOCKED, never silent success."""
    import tools.audio.finish_audio as famod

    in_wav = tmp_path / "in.wav"
    out_wav = tmp_path / "out.wav"
    _gen_tone(in_wav, duration=5, freq=440, level_db=-40, rate=44100, channels=1)

    # Force loudnorm filter to be unavailable by monkeypatching shutil.which? 
    # Instead simulate by making _run raise for loudnorm. Simpler: monkeypatch
    # the module's subprocess runner to raise for loudnorm-containing cmds.
    orig_run = famod.subprocess.run

    def fake_run(cmd, *args, **kwargs):
        cmd_str = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        if "loudnorm" in cmd_str:
            raise subprocess.CalledProcessError(1, cmd, output="", stderr="No such filter: loudnorm")
        return orig_run(cmd, *args, **kwargs)

    monkeypatch.setattr(famod.subprocess, "run", fake_run)
    tool = FinishAudioTool()
    res = tool.execute({"input_path": str(in_wav), "output_path": str(out_wav)})
    assert not res.success, "should fail when loudnorm missing"
    assert "BLOCKED" in (res.error or "") or res.error is not None, res.error
