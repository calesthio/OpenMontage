"""AIGC labeling E2E (roadmap 0.1 — 《人工智能生成合成内容标识办法》).

Real ffmpeg renders, verified by ffprobe (implicit metadata label) and raw
frame extraction (explicit opening-frame label) — unit-level assertions on
command strings alone have repeatedly missed real defects in this codebase.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.video.aigc_label import (
    EXPLICIT_LABEL_SECONDS,
    burn_explicit_label,
    embed_aigc_metadata,
    find_cjk_font,
    new_content_id,
    opening_label_filter,
    render_label_png,
)

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe required",
)

W, H = 640, 360
FIXTURE_SECONDS = 8


@pytest.fixture
def red_video(tmp_path: Path) -> Path:
    """A solid-red H.264 fixture — gray-luma ~54, far from both the label's
    white text (>200) and its black box (<40), so corner-pixel extrema are an
    unambiguous machine check for the burned label."""
    out = tmp_path / "fixture.mp4"
    subprocess.run(
        ["ffmpeg", "-y",
         "-f", "lavfi", "-t", str(FIXTURE_SECONDS), "-i", f"color=c=red:s={W}x{H}:r=30",
         "-f", "lavfi", "-t", str(FIXTURE_SECONDS), "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out)],
        check=True, capture_output=True,
    )
    return out


def _corner_pixels(video: Path, t: float) -> bytes:
    """Raw gray bytes of the top-right corner region at time t."""
    crop_w, crop_h = int(W * 0.35), int(H * 0.2)
    crop_x = W - crop_w - 2
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(video),
         "-frames:v", "1", "-vf", f"crop={crop_w}:{crop_h}:{crop_x}:2",
         "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        check=True, capture_output=True,
    )
    assert proc.stdout, "no frame extracted"
    return proc.stdout


def _format_tags(video: Path) -> dict:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format_tags",
         "-of", "json", str(video)],
        check=True, capture_output=True, text=True,
    )
    return (json.loads(probe.stdout).get("format") or {}).get("tags") or {}


def _assert_aigc_tags(video: Path) -> dict:
    tags = {k.lower(): v for k, v in _format_tags(video).items()}
    assert "comment" in tags, f"no comment tag in {tags}"
    payload = json.loads(tags["comment"])
    aigc = payload["AIGC"]
    assert aigc["Label"] == "AI-Generated"
    assert aigc["ContentProducer"]
    assert aigc["ProducerCode"]
    assert aigc["ProduceID"]
    return aigc


def _assert_label_visible_then_gone(video: Path) -> None:
    labeled = _corner_pixels(video, 1.0)
    assert max(labeled) > 200, "no bright (text) pixels in the label corner at t=1"
    assert min(labeled) < 60, "no dark (box) pixels in the label corner at t=1"
    after = _corner_pixels(video, EXPLICIT_LABEL_SECONDS + 1.5)
    assert max(after) < 160, "label corner still altered after the label window"


# ── implicit metadata label ──────────────────────────────────────────────────

def test_embed_metadata_and_survives_export_copy(red_video, tmp_path):
    info = embed_aigc_metadata(red_video)
    assert info and info["embedded"]
    aigc = _assert_aigc_tags(red_video)
    assert aigc["ProduceID"] == info["content_id"]

    # The regulation requires the label to SURVIVE export/download.
    # export_bundle copies byte-for-byte (shutil.copy2) — prove it.
    from tools.publishers.export_bundle import ExportBundle
    result = ExportBundle().execute({
        "video_path": str(red_video),
        "title": "aigc survival",
        "export_dir": str(tmp_path / "bundle"),
    })
    assert result.success, result.error
    exported = tmp_path / "bundle" / "video" / "output.mp4"
    assert _assert_aigc_tags(exported)["ProduceID"] == info["content_id"]


def test_content_id_carries_project_name(tmp_path):
    p = tmp_path / "projects" / "demo-film" / "renders" / "final.mp4"
    cid = new_content_id(p)
    assert cid.startswith("demo-film-final-")


# ── explicit opening-frame label ─────────────────────────────────────────────

@pytest.mark.skipif(find_cjk_font() is None, reason="no CJK font on this machine")
def test_burn_explicit_label_visible_on_opening_frames_only(red_video):
    assert burn_explicit_label(red_video)
    _assert_label_visible_then_gone(red_video)


@pytest.mark.skipif(find_cjk_font() is None, reason="no CJK font on this machine")
def test_ffmpeg_compose_burns_label_and_embeds_metadata(red_video, tmp_path):
    # The REAL _compose path: segment encode → concat → mux → loudness →
    # metadata. The label must be burned into the opening segment and the
    # metadata must be present in the final deliverable.
    from tools.video.video_compose import VideoCompose
    out = tmp_path / "renders" / "final.mp4"
    result = VideoCompose().execute({
        "operation": "compose",
        "edit_decisions": {
            "cuts": [
                {"source": str(red_video), "in_seconds": 0, "out_seconds": 6},
                {"source": str(red_video), "in_seconds": 0, "out_seconds": 3},
            ],
            "metadata": {"compose_target": {"width": W, "height": H}},
        },
        "output_path": str(out),
    })
    assert result.success, result.error
    assert result.data["aigc_label"]["explicit_burned"] is True
    assert result.data["aigc_label"]["metadata"]["embedded"] is True
    _assert_aigc_tags(out)
    _assert_label_visible_then_gone(out)


def test_opening_label_filter_shape(tmp_path):
    if find_cjk_font() is None:
        assert opening_label_filter(1920, 1080, tmp_path) is None
        return
    suffix = opening_label_filter(1920, 1080, tmp_path)
    # A labeled filtergraph SUFFIX for direct concatenation onto a chain.
    assert suffix.startswith("[aigc_base];movie=")
    assert "overlay=" in suffix
    assert f"lt(t,{EXPLICIT_LABEL_SECONDS})" in suffix
    png = tmp_path / "aigc_label.png"
    assert png.is_file()
    # Label height ≥ 5% of the shorter edge (1080 → ≥54px incl. padding).
    from PIL import Image
    assert Image.open(png).height >= 54


def test_render_label_png_none_without_font(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.video.aigc_label.find_cjk_font", lambda: None)
    assert render_label_png(1920, 1080, tmp_path / "x.png") is None


# ── HyperFrames composition injection ────────────────────────────────────────

def test_hyperframes_index_html_includes_label_clip(tmp_path):
    from tools.video.hyperframes_compose import HyperFramesCompose
    html = HyperFramesCompose()._generate_index_html(
        cuts=[{"type": "text_card", "text": "hello", "in_seconds": 0, "out_seconds": 5}],
        audio_refs={},
        width=1920,
        height=1080,
        total_duration=5.0,
        css_vars={"--color-bg": "#000", "--color-fg": "#fff",
                  "--color-accent": "#0ff", "--font-body": "sans-serif",
                  "--font-heading": "sans-serif"},
        title="t",
    )
    assert 'id="aigc-label"' in html
    assert "AI生成" in html
    # Reserved top track, opening window.
    assert 'data-start="0"' in html


# ── Remotion real-render E2E ─────────────────────────────────────────────────

COMPOSER_DIR = Path(__file__).resolve().parent.parent.parent / "remotion-composer"


@pytest.mark.skipif(
    shutil.which("npx") is None or not (COMPOSER_DIR / "node_modules").exists(),
    reason="npx + remotion-composer/node_modules required",
)
def test_remotion_badge_renders_on_opening_frames(tmp_path):
    # REAL Remotion render of a registered (withAigcLabel-wrapped)
    # composition with the aigcLabel prop video_compose injects — then frame
    # extraction proves the badge is actually visible on the opening frames
    # and gone afterwards. EndTag: 5.5s, black background, centered text —
    # the top-right corner stays empty except for the badge.
    props = tmp_path / "props.json"
    props.write_text(json.dumps({
        "text": "AIGC E2E",
        "palette": "cool_offwhite_on_black",
        "fadeInSeconds": 0.6, "holdSeconds": 4.3, "fadeOutSeconds": 0.6,
        "aigcLabel": {"text": "AI生成", "seconds": 3},
    }))
    out = tmp_path / "endtag.mp4"
    cmd = ["npx", "remotion", "render", "src/index.tsx", "EndTag", str(out),
           f"--props={props}", "--color-space=bt709", "--scale=0.5"]
    for attempt in (1, 2):   # Google Fonts CDN flakes — retry once
        proc = subprocess.run(cmd, cwd=COMPOSER_DIR, capture_output=True,
                              text=True, timeout=900)
        if proc.returncode == 0:
            break
        if attempt == 2 or "fonts.gstatic" not in (proc.stderr + proc.stdout):
            pytest.fail(f"remotion render failed:\n{(proc.stderr or proc.stdout)[-2000:]}")
    assert out.is_file()

    w, h = 960, 540   # 1920x1080 at --scale=0.5
    def corner(t: float) -> bytes:
        cw, ch = int(w * 0.3), int(h * 0.18)
        p = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(out),
             "-frames:v", "1", "-vf", f"crop={cw}:{ch}:{w - cw - 2}:2",
             "-f", "rawvideo", "-pix_fmt", "gray", "-"],
            check=True, capture_output=True)
        assert p.stdout
        return p.stdout

    assert max(corner(1.0)) > 180, "badge text not visible in the corner at t=1"
    assert max(corner(4.5)) < 100, "corner not clean after the 3s badge window"


# ── Remotion props injection ─────────────────────────────────────────────────

def test_remotion_render_injects_aigc_label_prop(tmp_path, monkeypatch):
    # Captures the props file the CLI would receive — the badge itself is
    # rendered by withAigcLabel (Root.tsx); this pins the injection so the
    # prop can't silently vanish (house failure pattern: mechanism built,
    # call site missing).
    from tools.video.video_compose import VideoCompose
    vc = VideoCompose()
    captured = {}

    def fake_run(cmd, **kwargs):
        props_arg = next(a for a in cmd if str(a).startswith("--props="))
        props_path = Path(str(props_arg).split("=", 1)[1])
        captured.update(json.loads(props_path.read_text()))
        out_i = cmd.index("render") + 3  # npx remotion render <entry> <comp> <out>
        Path(cmd[out_i]).write_bytes(b"fake")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(vc, "run_command", fake_run)
    monkeypatch.setattr(vc, "_normalize_deliverable_loudness", lambda p: False)
    monkeypatch.setattr(
        "tools.video.aigc_label.embed_aigc_metadata",
        lambda *a, **k: {"content_id": "x", "embedded": True},
    )
    out = tmp_path / "r.mp4"
    result = vc._remotion_render({
        "edit_decisions": {"cuts": [], "renderer_family": "explainer-data"},
        "output_path": str(out),
    })
    assert result.success, result.error
    assert captured.get("aigcLabel", {}).get("text") == "AI生成"
