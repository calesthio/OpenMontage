import json
from pathlib import Path

import pytest

from tools.video.video_compose import VideoCompose


def test_cinematic_cut_adapter_builds_a_sequential_timeline() -> None:
    scenes = VideoCompose._cuts_to_cinematic_scenes([
        {
            "id": "v1",
            "source": "clip.mp4",
            "in_seconds": 2,
            "out_seconds": 6,
            "transition_in": "cut",
            "transition_out": "none",
        },
        {
            "id": "title",
            "source": "",
            "type": "hero_title",
            "text": "The signal arrives",
            "in_seconds": 0,
            "out_seconds": 3,
        },
    ])

    assert scenes[0] == {
        "id": "v1",
        "startSeconds": 0.0,
        "durationSeconds": 4.0,
        "kind": "video",
        "src": "clip.mp4",
        "trimBeforeSeconds": 2.0,
        "trimAfterSeconds": 6.0,
        "playbackRate": 1.0,
        "fadeInFrames": 0,
        "fadeOutFrames": 0,
    }
    assert scenes[1]["kind"] == "title"
    assert scenes[1]["startSeconds"] == 4.0
    assert scenes[1]["text"] == "The signal arrives"


def test_cinematic_cut_adapter_preserves_playback_speed() -> None:
    scenes = VideoCompose._cuts_to_cinematic_scenes([
        {
            "id": "fast",
            "source": "clip.mp4",
            "in_seconds": 2,
            "out_seconds": 6,
            "speed": 2,
        }
    ])

    assert scenes[0]["durationSeconds"] == 2
    assert scenes[0]["playbackRate"] == 2


@pytest.mark.parametrize("uri_style", ["standard", "legacy_windows"])
def test_remotion_media_staging_decodes_file_uris(tmp_path, uri_style) -> None:
    source = tmp_path / "clip with space.mp4"
    source.write_bytes(b"video")
    public_dir = tmp_path / "public"
    uri = source.as_uri()
    if uri_style == "legacy_windows" and len(source.drive) == 2:
        uri = f"file://{source.drive}{source.as_posix()[2:]}".replace(" ", "%20")
    props = {"scenes": [{"src": uri}]}

    staged_count = VideoCompose._stage_remotion_media(props, public_dir)

    assert staged_count == 1
    assert props["scenes"][0]["src"] != uri
    assert (public_dir / props["scenes"][0]["src"]).read_bytes() == b"video"


def test_remotion_render_adapts_cuts_and_stages_local_video(monkeypatch, tmp_path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"not-a-real-video")
    output = tmp_path / "render.mp4"
    captured = {}

    def fake_run_command(self, command, **kwargs):
        captured["command"] = command
        captured["timeout"] = kwargs["timeout"]
        props_arg = next(arg for arg in command if arg.startswith("--props="))
        captured["props"] = json.loads(Path(props_arg.split("=", 1)[1]).read_text())
        public_arg = next(arg for arg in command if arg.startswith("--public-dir="))
        public_dir = Path(public_arg.split("=", 1)[1])
        captured["staged_exists_during_render"] = (
            public_dir / captured["props"]["scenes"][0]["src"]
        ).exists()
        output.write_bytes(b"rendered")

    monkeypatch.setattr(VideoCompose, "run_command", fake_run_command)

    result = VideoCompose()._remotion_render({
        "edit_decisions": {
            "renderer_family": "cinematic-trailer",
            "cuts": [
                {
                    "id": "v1",
                    "source": str(source),
                    "in_seconds": 0,
                    "out_seconds": 2,
                }
            ],
        },
        "output_path": str(output),
    })

    assert result.success, result.error
    assert "cuts" not in captured["props"]
    assert captured["props"]["scenes"][0]["kind"] == "video"
    assert captured["staged_exists_during_render"] is True
    assert result.data["staged_media_count"] == 1


def test_remotion_timeout_scales_with_scene_count(monkeypatch, tmp_path) -> None:
    output = tmp_path / "render.mp4"
    captured = {}

    def fake_run_command(self, command, **kwargs):
        captured["timeout"] = kwargs["timeout"]
        output.write_bytes(b"rendered")

    monkeypatch.setattr(VideoCompose, "run_command", fake_run_command)
    cuts = [
        {
            "id": f"title-{index}",
            "source": "",
            "type": "hero_title",
            "text": str(index),
            "in_seconds": 0,
            "out_seconds": 1,
        }
        for index in range(50)
    ]

    result = VideoCompose()._remotion_render({
        "edit_decisions": {"renderer_family": "cinematic-trailer", "cuts": cuts},
        "output_path": str(output),
    })

    assert result.success, result.error
    assert captured["timeout"] == 750


def test_remotion_render_preserves_direct_cinematic_scenes(monkeypatch, tmp_path) -> None:
    output = tmp_path / "render.mp4"
    captured = {}

    def fake_run_command(self, command, **kwargs):
        props_arg = next(arg for arg in command if arg.startswith("--props="))
        captured["props"] = json.loads(Path(props_arg.split("=", 1)[1]).read_text())
        output.write_bytes(b"rendered")

    monkeypatch.setattr(VideoCompose, "run_command", fake_run_command)
    scene = {
        "id": "authored",
        "kind": "title",
        "text": "Keep me",
        "startSeconds": 0,
        "durationSeconds": 1,
    }

    result = VideoCompose()._remotion_render({
        "composition_data": {
            "renderer_family": "cinematic-trailer",
            "scenes": [scene],
        },
        "output_path": str(output),
    })

    assert result.success, result.error
    assert captured["props"]["scenes"] == [scene]


@pytest.mark.parametrize("renderer_family", ["cinematic-trailer", "documentary-montage"])
def test_remotion_render_rejects_cinematic_overlays_before_rendering(
    monkeypatch, tmp_path, renderer_family
) -> None:
    monkeypatch.setattr("tools.video.video_compose.shutil.which", lambda _name: None)
    result = VideoCompose()._remotion_render(
        {
            "edit_decisions": {
                "renderer_family": renderer_family,
                "scenes": [
                    {
                        "id": "scene-1",
                        "kind": "video",
                        "src": "clip.mp4",
                        "startSeconds": 0,
                        "durationSeconds": 1,
                    }
                ],
                "overlays": [
                    {
                        "type": "section_title",
                        "text": "Chapter 1",
                        "startSeconds": 0,
                        "durationSeconds": 1,
                    }
                ],
            },
            "output_path": str(tmp_path / "render.mp4"),
        }
    )

    assert not result.success
    assert result.error == (
        "CinematicRenderer does not support non-empty overlays; remove overlays "
        "or use a composition that supports them."
    )


def test_resolve_music_canonical_and_legacy() -> None:
    asset_lookup = {
        "asset_music_bed": {"id": "asset_music_bed", "path": "path/to/bed.mp3"},
        "asset_legacy": {"id": "asset_legacy", "path": "path/to/legacy.mp3"},
    }

    # Canonical audio.music
    canonical_ed = {
        "audio": {
            "music": {
                "asset_id": "asset_music_bed",
                "volume": 0.6,
                "fade_in_seconds": 1.0,
                "fade_out_seconds": 4.0,
                "ducking": False,
            }
        }
    }
    resolved, err = VideoCompose._resolve_music(canonical_ed, asset_lookup)
    assert err is None
    assert resolved is not None
    assert resolved["src"] == "path/to/bed.mp3"
    assert resolved["volume"] == 0.6
    assert resolved["fadeInSeconds"] == 1.0
    assert resolved["fadeOutSeconds"] == 4.0
    assert resolved["ducking"] is False

    # Legacy music
    legacy_ed = {
        "music": {
            "asset_id": "asset_legacy",
            "volume": 0.3,
            "fade_in_seconds": 0.5,
            "fade_out_seconds": 2.0,
        }
    }
    resolved, err = VideoCompose._resolve_music(legacy_ed, asset_lookup)
    assert err is None
    assert resolved is not None
    assert resolved["src"] == "path/to/legacy.mp3"
    assert resolved["volume"] == 0.3
    assert resolved["fadeInSeconds"] == 0.5
    assert resolved["fadeOutSeconds"] == 2.0


def test_resolve_music_missing_asset_id_fails_loudly() -> None:
    ed = {
        "audio": {
            "music": {
                "asset_id": "asset_nonexistent_bed",
            }
        }
    }
    resolved, err = VideoCompose._resolve_music(ed, {})
    assert resolved is None
    assert err == "Music asset_id 'asset_nonexistent_bed' not found in asset_manifest."


def test_render_resolves_and_stages_music_into_remotion_props(monkeypatch, tmp_path) -> None:
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"dummy-clip")
    music = tmp_path / "music_bed.mp3"
    music.write_bytes(b"dummy-audio-content")
    output = tmp_path / "out.mp4"
    captured = {}

    def fake_run_command(self, command, **kwargs):
        captured["command"] = command
        props_arg = next(arg for arg in command if arg.startswith("--props="))
        captured["props"] = json.loads(Path(props_arg.split("=", 1)[1]).read_text())
        public_arg = next(arg for arg in command if arg.startswith("--public-dir="))
        public_dir = Path(public_arg.split("=", 1)[1])
        captured["staged_music_exists"] = (
            public_dir / captured["props"]["music"]["src"]
        ).exists()
        output.write_bytes(b"rendered-mp4")

    monkeypatch.setattr(VideoCompose, "run_command", fake_run_command)
    monkeypatch.setattr(
        VideoCompose,
        "_run_final_review",
        lambda self, *args, **kwargs: {"status": "pass", "issues": []},
    )

    result = VideoCompose().execute({
        "operation": "render",
        "output_path": str(output),
        "edit_decisions": {
            "renderer_family": "documentary-montage",
            "render_runtime": "remotion",
            "cuts": [
                {
                    "id": "c1",
                    "source": "asset_clip",
                    "in_seconds": 0,
                    "out_seconds": 4,
                }
            ],
            "audio": {
                "music": {
                    "asset_id": "asset_music_bed",
                    "volume": 0.6,
                    "fade_in_seconds": 1.0,
                    "fade_out_seconds": 4.0,
                    "ducking": False,
                }
            },
        },
        "asset_manifest": {
            "version": "1.0",
            "assets": [
                {"id": "asset_clip", "path": str(clip)},
                {"id": "asset_music_bed", "path": str(music)},
            ],
        },
    })

    assert result.success, result.error
    assert captured["staged_music_exists"] is True
    # Verify top-level music prop for CinematicRenderer
    music_prop = captured["props"]["music"]
    assert music_prop["volume"] == 0.6
    assert music_prop["fadeInSeconds"] == 1.0
    assert music_prop["fadeOutSeconds"] == 4.0
    assert music_prop["src"] != str(music)  # Staged filename
    # Verify audio.music prop for Explainer
    assert captured["props"]["audio"]["music"]["src"] == music_prop["src"]
    # 1 video clip + 1 music file = 2 staged media
    assert result.data["staged_media_count"] == 2


def test_render_missing_music_asset_id_returns_error(tmp_path) -> None:
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"dummy-clip")
    result = VideoCompose().execute({
        "operation": "render",
        "output_path": str(tmp_path / "out.mp4"),
        "edit_decisions": {
            "renderer_family": "documentary-montage",
            "render_runtime": "remotion",
            "cuts": [{"id": "c1", "source": "asset_clip", "in_seconds": 0, "out_seconds": 4}],
            "audio": {
                "music": {
                    "asset_id": "asset_missing_music",
                }
            },
        },
        "asset_manifest": {
            "version": "1.0",
            "assets": [{"id": "asset_clip", "path": str(clip)}],
        },
    })
    assert not result.success
    assert "Music asset_id 'asset_missing_music' not found in asset_manifest." in result.error

