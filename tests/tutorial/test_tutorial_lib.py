"""Unit tests for lib.tutorial (Cypress → tutorial-video helpers)."""

import json
import struct
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lib import tutorial as T  # noqa: E402
from tools.audio.narration_client import wav_duration_ms  # noqa: E402


def test_subtitle_segments_timing():
    steps = [T.Step(index=i, narration="alpha beta gamma") for i in range(3)]
    T.apply_durations(steps, [3000, 3000, 3000])
    T.assign_start_times(steps, [0.0, 5.0, 10.0])
    segs = T.build_subtitle_segments(steps)
    assert [s["start"] for s in segs] == [0.0, 5.0, 10.0]
    assert [s["end"] for s in segs] == [3.0, 8.0, 13.0]
    w = segs[0]["words"]
    assert len(w) == 3
    assert w[0]["start"] == 0.0 and abs(w[0]["end"] - 1.0) < 1e-6
    assert abs(w[2]["end"] - 3.0) < 1e-6


def test_assign_start_prefers_markers_over_t_ms():
    steps = [T.Step(index=0, narration="x", t_ms=9999), T.Step(index=1, narration="y", t_ms=9999)]
    T.assign_start_times(steps, [1.5, 4.0])
    assert steps[0].video_start_s == 1.5 and steps[1].video_start_s == 4.0


def test_assign_start_fallback_uses_t_ms():
    steps = [T.Step(index=0, narration="x", t_ms=2500), T.Step(index=1, narration="y", t_ms=6000)]
    T.assign_start_times(steps, None)
    assert steps[0].video_start_s == 2.5 and steps[1].video_start_s == 6.0


def test_empty_narration_skipped():
    steps = [T.Step(index=0, narration=""), T.Step(index=1, narration="hi there")]
    T.apply_durations(steps, [1000, 1000])
    T.assign_start_times(steps, [0.0, 1.0])
    segs = T.build_subtitle_segments(steps)
    assert len(segs) == 1 and segs[0]["text"] == "hi there"


def test_edit_decisions_schema_valid():
    jsonschema = pytest.importorskip("jsonschema")
    steps = [T.Step(index=i, narration=f"Step {i}.") for i in range(3)]
    T.apply_durations(steps, [1200, 1200, 1200])
    T.assign_start_times(steps, [1.0, 3.0, 5.0])
    ed = T.build_edit_decisions(
        steps, "cap.mp4", 8.0, intro_s=3, outro_s=3,
        recipe={"subtitle_style": "word_by_word"},
        narration_audio_path="a.wav", subtitles_path="s.srt", music_path="m.mp3",
    )
    schema = json.loads((REPO / "schemas/artifacts/edit_decisions.schema.json").read_text())
    jsonschema.validate(ed, schema)
    assert ed["render_runtime"] == "ffmpeg" and ed["renderer_family"] == "screen-demo"


def test_title_card_png_is_1080p():
    from PIL import Image

    with tempfile.TemporaryDirectory() as d:
        p = T.make_title_card(str(Path(d) / "c.png"), "Title", "Subtitle")
        with Image.open(p) as im:
            assert im.size == (1920, 1080)


def test_screencast_scene_payload():
    steps = [
        T.Step(index=0, narration="Click here.", action="click",
               suggested_treatment="highlight", region={"x": 0.8, "y": 0.1, "w": 0.1, "h": 0.05}),
        T.Step(index=1, narration="Zoom in.", suggested_treatment="zoom",
               region={"x": 0.4, "y": 0.4, "w": 0.2, "h": 0.2}),
    ]
    T.apply_durations(steps, [1500, 2000])
    T.assign_start_times(steps, [1.0, 4.0])
    sc = T.build_screencast_scene(steps, "cap.mp4")
    assert sc["type"] == "screencast_scene" and sc["source"] == "cap.mp4"
    kinds = [o["kind"] for o in sc["screencastOverlays"]]
    assert kinds.count("highlight_box") == 2  # both steps highlighted
    assert "click_pulse" in kinds            # step0 is a click
    assert len(sc["screencastZoom"]) == 1     # only step1 zooms
    assert len(sc["screencastCursor"]) == 2
    assert sc["screencastCursor"][0]["to"] == [0.85, 0.125]  # region center
    hb0 = next(o for o in sc["screencastOverlays"] if o["kind"] == "highlight_box")
    assert hb0["atSeconds"] == 1.0  # body-relative time


def test_remotion_props_structure():
    steps = [
        T.Step(index=i, narration=f"Step {i} now.", suggested_treatment="highlight",
               region={"x": 0.5, "y": 0.5, "w": 0.1, "h": 0.1})
        for i in range(2)
    ]
    T.apply_durations(steps, [1000, 1000])
    T.assign_start_times(steps, [1.0, 3.0])
    props = T.build_remotion_props(
        steps, "cap.mp4", 6.0, {"intro_text": "Hi", "outro_text": "Bye"},
        intro_s=3, outro_s=3, narration_audio_path="a.wav", music_path="m.mp3",
    )
    assert [c["id"] for c in props["cuts"]] == ["intro", "body", "outro"]
    body = props["cuts"][1]
    assert body["type"] == "screencast_scene" and body["in_seconds"] == 3 and body["out_seconds"] == 9.0
    assert body["screencastOverlays"]
    assert props["cuts"][0]["out_seconds"] == 3 and props["cuts"][2]["out_seconds"] == 12.0
    assert props["captions"][0]["startMs"] == 4000  # body_offset(3) + step start(1)
    assert props["audio"]["narration"]["src"] == "a.wav" and "music" in props["audio"]


def test_wav_duration_ms_reads_header():
    pcm = b"\x00\x00" * 960  # 960 samples s16 mono @ 48k == 20ms
    hdr = (
        b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, 48000, 96000, 2, 16)
        + b"data" + struct.pack("<I", len(pcm))
    )
    assert wav_duration_ms(hdr + pcm) == 20
