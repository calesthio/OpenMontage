"""Tests for Remotion local-asset staging in video_compose (issue #237, PR #238).

Remotion's renderer only serves http(s) URLs or files under a public/ directory
— file:// is rejected at render time. `_remotion_render` must therefore stage
local assets and rewrite the props to staticFile-relative paths, for BOTH the
Explainer shape (cuts[].source, audio.narration/music.src) and the Cinematic
shape (scenes[].src, top-level soundtrack.src / music.src).

Two containment properties matter as much as the rewrite itself:

* Staging goes to a render-scoped directory beside the output, handed to
  Remotion via --public-dir, and is removed when the call ends. Staging into
  the shared `remotion-composer/public/` checkout instead left user media
  readable by later projects and renders, growing without bound.
* file:// URIs are parsed as URIs. `Path.as_uri()` on Windows produces
  `file:///C:/dir/clip.mp4`; stripping only the scheme leaves `/C:/dir/...`,
  which resolves to nothing, so the asset silently went unstaged and Remotion
  received the very file:// source this staging exists to eliminate.
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.video.video_compose import VideoCompose  # noqa: E402

REPO_STAGING_DIR = PROJECT_ROOT / "remotion-composer" / "public" / "_om_assets"


def _capture_props(tool):
    """Patch run_command so a render 'succeeds', capturing props and public dir.

    The staging directory is deleted once `_remotion_render` returns, so its
    contents are snapshotted here — mid-render is the only point they exist.
    Returns a dict populated after execute(): props, public_dir, staged (name
    -> bytes), and the raw cmd.
    """
    captured = {}

    def _arg_value(cmd, flag):
        for i, arg in enumerate(cmd):
            s = str(arg)
            if s == flag:
                return cmd[i + 1]
            if s.startswith(f"{flag}="):
                return s.split("=", 1)[1]
        raise AssertionError(f"no {flag} argument in cmd: {cmd}")

    def fake_run_command(cmd, *a, **k):
        captured["cmd"] = list(cmd)
        captured["props"] = json.loads(Path(_arg_value(cmd, "--props")).read_text())
        public_dir = Path(_arg_value(cmd, "--public-dir"))
        captured["public_dir"] = public_dir
        captured["staged"] = {
            p.name: p.read_bytes() for p in public_dir.rglob("*") if p.is_file()
        }
        Path(cmd[5]).write_bytes(b"\x00")  # create output so exists() -> True
        return None

    tool.run_command = fake_run_command  # type: ignore[assignment]
    return captured


@pytest.fixture
def tool(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/npx")
    return VideoCompose()


def test_cinematic_audio_and_scenes_are_staged(tool, tmp_path):
    soundtrack = tmp_path / "narration.wav"
    soundtrack.write_bytes(b"narration-bytes")
    music = tmp_path / "bed.mp3"
    music.write_bytes(b"music-bytes")
    scene_clip = tmp_path / "broll.mp4"
    scene_clip.write_bytes(b"broll-bytes")

    captured = _capture_props(tool)
    out = tmp_path / "renders" / "out.mp4"
    result = tool._remotion_render(
        {
            "composition_data": {
                "renderer_family": "cinematic-trailer",
                "scenes": [{"src": str(scene_clip)}],
                "soundtrack": {"src": str(soundtrack)},
                "music": {"src": music.as_uri()},
            },
            "output_path": str(out),
        }
    )

    assert result.success is True, result.error
    props = captured["props"]
    assert props["soundtrack"]["src"].startswith("_om_assets/")
    assert props["music"]["src"].startswith("_om_assets/")
    assert props["scenes"][0]["src"].startswith("_om_assets/")

    for key, original in (
        (props["soundtrack"]["src"], b"narration-bytes"),
        (props["music"]["src"], b"music-bytes"),
        (props["scenes"][0]["src"], b"broll-bytes"),
    ):
        assert captured["staged"][Path(key).name] == original


def test_explainer_cuts_and_nested_audio_are_staged(tool, tmp_path):
    cut = tmp_path / "shot.mp4"
    cut.write_bytes(b"cut-bytes")
    narration = tmp_path / "vo.wav"
    narration.write_bytes(b"vo-bytes")

    captured = _capture_props(tool)
    out = tmp_path / "renders" / "out.mp4"
    result = tool._remotion_render(
        {
            "composition_data": {
                "renderer_family": "explainer-data",
                "cuts": [{"source": str(cut)}],
                "audio": {"narration": {"src": str(narration)}},
            },
            "output_path": str(out),
        }
    )

    assert result.success is True, result.error
    props = captured["props"]
    assert props["cuts"][0]["source"].startswith("_om_assets/")
    assert props["audio"]["narration"]["src"].startswith("_om_assets/")
    assert captured["staged"][Path(props["cuts"][0]["source"]).name] == b"cut-bytes"


def test_remote_and_data_sources_are_left_alone(tool, tmp_path):
    captured = _capture_props(tool)
    out = tmp_path / "renders" / "out.mp4"
    result = tool._remotion_render(
        {
            "composition_data": {
                "renderer_family": "cinematic-trailer",
                "scenes": [{"src": "https://cdn.example.com/a.mp4"}],
                "soundtrack": {"src": "data:audio/wav;base64,AAA"},
            },
            "output_path": str(out),
        }
    )

    assert result.success is True, result.error
    props = captured["props"]
    assert props["scenes"][0]["src"] == "https://cdn.example.com/a.mp4"
    assert props["soundtrack"]["src"] == "data:audio/wav;base64,AAA"


# ---------------------------------------------------------------------------
# Containment: render-scoped public dir, cleaned up, never the repo checkout
# ---------------------------------------------------------------------------


def test_public_dir_is_render_scoped_and_passed_to_remotion(tool, tmp_path):
    src = tmp_path / "narration.wav"
    src.write_bytes(b"bytes")

    captured = _capture_props(tool)
    out = tmp_path / "renders" / "out.mp4"
    result = tool._remotion_render(
        {
            "composition_data": {
                "renderer_family": "cinematic-trailer",
                "scenes": [],
                "soundtrack": {"src": str(src)},
            },
            "output_path": str(out),
        }
    )

    assert result.success is True, result.error
    public_dir = captured["public_dir"]
    # Handed to Remotion, and located in the project workspace beside the
    # output — not inside the shared composer checkout.
    assert any(str(a).startswith("--public-dir=") for a in captured["cmd"])
    assert public_dir.parent == out.parent.resolve()
    assert (PROJECT_ROOT / "remotion-composer") not in public_dir.parents


def test_staging_dir_is_removed_after_render(tool, tmp_path):
    src = tmp_path / "narration.wav"
    src.write_bytes(b"bytes")

    captured = _capture_props(tool)
    out = tmp_path / "renders" / "out.mp4"
    tool._remotion_render(
        {
            "composition_data": {
                "renderer_family": "cinematic-trailer",
                "scenes": [],
                "soundtrack": {"src": str(src)},
            },
            "output_path": str(out),
        }
    )

    # It existed during the render...
    assert captured["staged"]
    # ...and no user media outlives the call that staged it.
    assert not captured["public_dir"].exists()
    assert not list(out.parent.glob(".om_public_*"))


def test_staging_dir_is_removed_when_render_fails(tool, tmp_path):
    src = tmp_path / "narration.wav"
    src.write_bytes(b"bytes")

    holder = {}

    def exploding_run_command(cmd, *a, **k):
        for arg in cmd:
            if str(arg).startswith("--public-dir="):
                holder["public_dir"] = Path(str(arg).split("=", 1)[1])
        raise RuntimeError("render blew up")

    tool.run_command = exploding_run_command  # type: ignore[assignment]
    out = tmp_path / "renders" / "out.mp4"
    result = tool._remotion_render(
        {
            "composition_data": {
                "renderer_family": "cinematic-trailer",
                "scenes": [],
                "soundtrack": {"src": str(src)},
            },
            "output_path": str(out),
        }
    )

    assert result.success is False
    assert not holder["public_dir"].exists()
    assert not list(out.parent.glob(".om_public_*"))


def test_staging_dir_is_removed_when_setup_raises_before_render(tool, tmp_path, monkeypatch):
    """A failure during staging/setup — before run_command — must still clean up.

    The staging directory is created lazily by the first asset copy, so an
    exception in a later copy or in props/theme construction happens after the
    directory exists but before the render call. The cleanup guard must cover
    that whole window, not just the subprocess.
    """
    a = tmp_path / "a.mp4"
    a.write_bytes(b"a")
    b = tmp_path / "b.mp4"
    b.write_bytes(b"b")

    # run_command must never be reached; if setup cleanup is scoped correctly the
    # exception surfaces before it.
    def unreached(*a, **k):  # pragma: no cover
        raise AssertionError("run_command should not run when setup fails")

    tool.run_command = unreached  # type: ignore[assignment]

    # Blow up on the SECOND staged copy: the first has already created the dir.
    real_copy = __import__("shutil").copy2
    calls = {"n": 0}

    def flaky_copy(src, dst, *a, **k):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise OSError("disk full mid-stage")
        return real_copy(src, dst, *a, **k)

    monkeypatch.setattr("shutil.copy2", flaky_copy)

    out = tmp_path / "renders" / "out.mp4"
    result = tool._remotion_render(
        {
            "composition_data": {
                "renderer_family": "cinematic-trailer",
                "scenes": [{"src": str(a)}],
                "soundtrack": {"src": str(b)},
            },
            "output_path": str(out),
        }
    )

    assert result.success is False
    assert "disk full" in (result.error or "")
    # The half-populated staging dir must not survive the failure.
    assert not list(out.parent.glob(".om_public_*"))


def test_repo_composer_public_is_never_written(tool, tmp_path):
    before = (
        sorted(p.name for p in REPO_STAGING_DIR.iterdir())
        if REPO_STAGING_DIR.exists()
        else None
    )

    src = tmp_path / "narration.wav"
    src.write_bytes(b"bytes")
    _capture_props(tool)
    out = tmp_path / "renders" / "out.mp4"
    tool._remotion_render(
        {
            "composition_data": {
                "renderer_family": "cinematic-trailer",
                "scenes": [],
                "soundtrack": {"src": str(src)},
            },
            "output_path": str(out),
        }
    )

    after = (
        sorted(p.name for p in REPO_STAGING_DIR.iterdir())
        if REPO_STAGING_DIR.exists()
        else None
    )
    assert after == before, "render wrote media into the shared composer checkout"


def test_staged_bytes_match_current_source_on_each_render(tool, tmp_path):
    src = tmp_path / "narration.wav"
    src.write_bytes(b"first-render")

    captured = _capture_props(tool)
    comp = {
        "renderer_family": "cinematic-trailer",
        "scenes": [],
        "soundtrack": {"src": str(src)},
    }
    out = tmp_path / "renders" / "out.mp4"

    r1 = tool._remotion_render({"composition_data": dict(comp), "output_path": str(out)})
    assert r1.success is True, r1.error
    name = Path(captured["props"]["soundtrack"]["src"]).name
    assert captured["staged"][name] == b"first-render"

    # Regenerate the asset at the same path with new bytes.
    src.write_bytes(b"second-render-longer-bytes")
    r2 = tool._remotion_render({"composition_data": dict(comp), "output_path": str(out)})
    assert r2.success is True, r2.error
    name = Path(captured["props"]["soundtrack"]["src"]).name
    assert captured["staged"][name] == b"second-render-longer-bytes"


# ---------------------------------------------------------------------------
# file:// URI parsing — canonical Windows forms, asserted on every platform
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "uri,expected",
    [
        ("file:///C:/media/clip.mp4", "C:/media/clip.mp4"),
        ("file:///D:/a b/clip%20two.mp4", "D:/a b/clip two.mp4"),
        ("file:///home/user/clip.mp4", "/home/user/clip.mp4"),
        ("file:///home/user/a%20b.mp4", "/home/user/a b.mp4"),
        ("file://server/share/clip.mp4", "//server/share/clip.mp4"),
        ("/plain/path/clip.mp4", "/plain/path/clip.mp4"),
    ],
)
def test_file_uri_to_local_path(uri, expected):
    # as_posix() keeps the assertion identical on POSIX and Windows.
    assert VideoCompose._local_path_from_uri(uri).as_posix() == expected


def test_windows_drive_uri_is_staged_not_passed_through(tool, tmp_path, monkeypatch):
    """A canonical Windows file URI must resolve to the real file and stage.

    The bug: stripping "file://" from `file:///C:/...` leaves `/C:/...`, which
    never exists, so `_stage_asset` returned the URI unchanged and Remotion got
    a file:// source. Simulated cross-platform by mapping a fake `/C:/`-rooted
    URI onto a real temp file through the same parser the tool uses.
    """
    real = tmp_path / "clip.mp4"
    real.write_bytes(b"windows-bytes")

    original = VideoCompose._local_path_from_uri.__func__

    def fake_parser(cls, value):
        parsed = original(cls, value)
        # Stand in for the Windows filesystem: C:/media/clip.mp4 -> real file.
        if parsed.as_posix() == "C:/media/clip.mp4":
            return real
        return parsed

    monkeypatch.setattr(VideoCompose, "_local_path_from_uri", classmethod(fake_parser))

    captured = _capture_props(tool)
    out = tmp_path / "renders" / "out.mp4"
    result = tool._remotion_render(
        {
            "composition_data": {
                "renderer_family": "cinematic-trailer",
                "scenes": [{"src": "file:///C:/media/clip.mp4"}],
            },
            "output_path": str(out),
        }
    )

    assert result.success is True, result.error
    staged_src = captured["props"]["scenes"][0]["src"]
    assert not staged_src.startswith("file://"), "Windows URI reached Remotion unstaged"
    assert staged_src.startswith("_om_assets/")
    assert captured["staged"][Path(staged_src).name] == b"windows-bytes"


def test_percent_encoded_path_is_staged(tool, tmp_path):
    src = tmp_path / "my clip.mp4"
    src.write_bytes(b"spaced-bytes")

    captured = _capture_props(tool)
    out = tmp_path / "renders" / "out.mp4"
    result = tool._remotion_render(
        {
            "composition_data": {
                "renderer_family": "cinematic-trailer",
                "scenes": [{"src": src.as_uri()}],  # percent-encodes the space
            },
            "output_path": str(out),
        }
    )

    assert result.success is True, result.error
    staged_src = captured["props"]["scenes"][0]["src"]
    assert staged_src.startswith("_om_assets/")
    assert captured["staged"][Path(staged_src).name] == b"spaced-bytes"
