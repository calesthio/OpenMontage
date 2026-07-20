"""Remotion local-asset staging (verified live 2026-07-17).

The templated Remotion path converted absolute asset paths to file:// URIs.
That NEVER worked — proven by rendering real project assets:
  <Img>            → Chrome "Not allowed to load local resource"
  <OffthreadVideo> → its /proxy calls @remotion/renderer's readFile(), which
                     throws "Can only download URLs starting with http://"
Remotion has no file:// support at any slash count; local assets must be
served over http from the public dir via staticFile(). These tests pin the
staging contract so the file:// premise cannot creep back.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.video.video_compose import VideoCompose  # noqa: E402

COMPOSER_PUBLIC = PROJECT_ROOT / "remotion-composer" / "public" / "om-staged"


@pytest.fixture
def asset(tmp_path):
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"fake-video-bytes")
    return p


def _cleanup(rewritten: str) -> None:
    if rewritten.startswith("om-staged/"):
        (COMPOSER_PUBLIC / rewritten.split("/", 1)[1]).unlink(missing_ok=True)


class TestStagePublicAssets:
    def test_absolute_path_becomes_public_relative(self, asset):
        props = {"cuts": [{"id": "c1", "source": str(asset)}]}
        _, staged, missing = VideoCompose()._stage_public_assets(props)
        assert missing == []
        src = props["cuts"][0]["source"]
        try:
            assert staged == 1
            # The whole point: NOT a file:// URI.
            assert not src.startswith("file://")
            assert src.startswith("om-staged/")
            # staticFile() resolves this against the public dir, and the
            # staged entry must really exist there.
            assert (COMPOSER_PUBLIC / src.split("/", 1)[1]).exists()
        finally:
            _cleanup(src)

    def test_staged_entry_is_readable_by_a_plain_copy(self, asset):
        # Remotion BUNDLES public/ by copying it; symlinks did not survive
        # that copy (the staged names 404'd from inside the bundle), so the
        # entry must read as a real file — i.e. a hard link or a copy.
        props = {"cuts": [{"id": "c1", "source": str(asset)}]}
        VideoCompose()._stage_public_assets(props)
        src = props["cuts"][0]["source"]
        try:
            staged_path = COMPOSER_PUBLIC / src.split("/", 1)[1]
            assert staged_path.read_bytes() == b"fake-video-bytes"
            assert not staged_path.is_symlink(), (
                "symlinked staging does not survive Remotion's public-dir copy"
            )
        finally:
            _cleanup(src)

    def test_file_uri_input_is_also_staged(self, asset):
        props = {"cuts": [{"id": "c1", "source": f"file://{asset}"}]}
        VideoCompose()._stage_public_assets(props)
        src = props["cuts"][0]["source"]
        try:
            assert src.startswith("om-staged/")
        finally:
            _cleanup(src)

    def test_remote_and_data_urls_untouched(self):
        props = {"cuts": [
            {"id": "a", "source": "https://cdn.example/x.mp4"},
            {"id": "b", "source": "data:image/png;base64,AAAA"},
        ]}
        _, staged, missing = VideoCompose()._stage_public_assets(props)
        assert staged == 0
        assert missing == []
        assert props["cuts"][0]["source"] == "https://cdn.example/x.mp4"
        assert props["cuts"][1]["source"] == "data:image/png;base64,AAAA"

    def test_public_relative_paths_untouched(self):
        # The convention the one working Remotion project already used.
        props = {"cuts": [{"id": "a", "source": "projects/xiaotuzi/video/a.mp4"}]}
        _, staged, missing = VideoCompose()._stage_public_assets(props)
        assert staged == 0
        assert missing == []
        assert props["cuts"][0]["source"] == "projects/xiaotuzi/video/a.mp4"

    def test_missing_file_left_alone_but_reported(self, tmp_path):
        # Not this function's job to raise — but it must report the missing
        # path so the caller (_remotion_render) can fail loud with the real
        # cause instead of letting a bogus absolute path reach Remotion,
        # where it can only ever surface as an opaque "file:// not
        # supported" proxy error (observed live 2026-07-19: a
        # never-generated / corrupted-in-transit asset path silently rode
        # all the way to the Remotion subprocess before failing).
        missing_path = tmp_path / "nope.mp4"
        props = {"cuts": [{"id": "a", "source": str(missing_path)}]}
        _, staged, missing = VideoCompose()._stage_public_assets(props)
        assert staged == 0
        assert missing == [str(missing_path)]
        # Left untouched in props — the caller decides what to do with it.
        assert props["cuts"][0]["source"] == str(missing_path)

    def test_stages_a_redacted_path_recovered_from_directory(self, tmp_path):
        # Atelier props are hand-authored by the agent directly — they never
        # pass through _resolve_manifest_asset_path, so its recovery alone
        # doesn't cover this case. Observed live 2026-07-19: the source
        # asset_manifest.json on disk was already correct, but the agent
        # re-typed the path into its own _cinematic_props.json and got the
        # same live redaction applied to that fresh transcription. Staging
        # must recover here too, since this is the one choke point both the
        # templated and atelier render paths share.
        video_dir = tmp_path / "video"
        video_dir.mkdir()
        real = video_dir / "maas_video_ltx-2-3_de2cd78360806541.mp4"
        real.write_bytes(b"fake-video-bytes")
        redacted = str(video_dir / "maas_video_ltx-2-3_de2cd[PHONE_REDACTED]1.mp4")

        props = {"scenes": [{"id": "sc01", "kind": "video", "src": redacted}]}
        _, staged, missing = VideoCompose()._stage_public_assets(props)
        src = props["scenes"][0]["src"]
        try:
            assert missing == []
            assert staged == 1
            assert src.startswith("om-staged/")
        finally:
            _cleanup(src)

    def test_every_asset_bearing_field_is_staged(self, asset, tmp_path):
        img = tmp_path / "bg.png"
        img.write_bytes(b"png")
        audio = tmp_path / "vo.mp3"
        audio.write_bytes(b"mp3")
        props = {
            "cuts": [{
                "id": "c1",
                "source": str(asset),
                "backgroundImage": str(img),
                "backgroundVideo": str(asset),
                "images": [str(img)],
            }],
            "scenes": [{"id": "s1", "src": str(asset), "backgroundSrc": str(img)}],
            "audio": {"narration": {"src": str(audio)}, "music": {"src": str(audio)}},
            "music": {"src": str(audio)},
            "videoSrc": str(asset),
        }
        VideoCompose()._stage_public_assets(props)
        cut = props["cuts"][0]
        rewritten = [
            cut["source"], cut["backgroundImage"], cut["backgroundVideo"],
            cut["images"][0], props["scenes"][0]["src"],
            props["scenes"][0]["backgroundSrc"],
            props["audio"]["narration"]["src"], props["audio"]["music"]["src"],
            props["music"]["src"], props["videoSrc"],
        ]
        try:
            for value in rewritten:
                assert value.startswith("om-staged/"), value
        finally:
            for value in rewritten:
                _cleanup(value)

    def test_same_source_reuses_one_staged_entry(self, asset):
        # Content-addressed by path → stable across cuts AND re-renders.
        props = {"cuts": [
            {"id": "a", "source": str(asset)},
            {"id": "b", "source": str(asset)},
        ]}
        VideoCompose()._stage_public_assets(props)
        try:
            assert props["cuts"][0]["source"] == props["cuts"][1]["source"]
        finally:
            _cleanup(props["cuts"][0]["source"])

    def test_relative_manifest_path_now_gets_staged_end_to_end(self, tmp_path):
        # Regression: asset_manifest paths are project-relative by convention
        # (e.g. "assets/video/sc-01.mp4"). _resolve_manifest_asset_path must
        # make that absolute BEFORE it reaches _stage_public_assets — feeding
        # it the raw relative string hits the
        # test_public_relative_paths_untouched contract above and the clip
        # never gets staged (confirmed live: a full paid run rendered only
        # the background, no clips/images/overlays composited).
        project_dir = tmp_path / "projects" / "some-job"
        clip = project_dir / "assets" / "video" / "sc-01.mp4"
        clip.parent.mkdir(parents=True)
        clip.write_bytes(b"fake-video-bytes")
        output_path = project_dir / "renders" / "final.mp4"

        resolved = VideoCompose._resolve_manifest_asset_path(
            "assets/video/sc-01.mp4", output_path,
        )
        assert Path(resolved).is_absolute()
        assert Path(resolved) == clip

        props = {"cuts": [{"id": "c1", "source": resolved}]}
        _, staged, missing = VideoCompose()._stage_public_assets(props)
        src = props["cuts"][0]["source"]
        try:
            assert staged == 1
            assert missing == []
            assert src.startswith("om-staged/")
        finally:
            _cleanup(src)

    def test_resolve_manifest_asset_path_recovers_redacted_filename(self, tmp_path):
        # Observed live 2026-07-19: an upstream LLM-provider content filter
        # redacted a digit run inside a hex asset hash mid-conversation —
        # not a one-time file corruption, since re-reading the correct file
        # from disk and having the agent re-echo it reproduced the SAME
        # redaction on a later turn. The recovery is a wildcard match on
        # the bracketed placeholder against the real directory listing.
        project_dir = tmp_path / "projects" / "some-job"
        video_dir = project_dir / "assets" / "video_generation"
        video_dir.mkdir(parents=True)
        real = video_dir / "maas_video_ltx-2-3_de2cd78360806541.mp4"
        real.write_bytes(b"fake-video-bytes")
        output_path = project_dir / "renders" / "final.mp4"

        raw = "assets/video_generation/maas_video_ltx-2-3_de2cd[PHONE_REDACTED]1.mp4"
        resolved = VideoCompose._resolve_manifest_asset_path(raw, output_path)
        assert Path(resolved) == real

    def test_resolve_manifest_asset_path_no_recovery_when_ambiguous(self, tmp_path):
        # More than one file matches the wildcard — refuse to guess.
        project_dir = tmp_path / "projects" / "some-job"
        video_dir = project_dir / "assets" / "video_generation"
        video_dir.mkdir(parents=True)
        (video_dir / "maas_video_ltx-2-3_de2cd78360806541.mp4").write_bytes(b"a")
        (video_dir / "maas_video_ltx-2-3_de2cd00000000001.mp4").write_bytes(b"b")
        output_path = project_dir / "renders" / "final.mp4"

        raw = "assets/video_generation/maas_video_ltx-2-3_de2cd[PHONE_REDACTED]1.mp4"
        resolved = VideoCompose._resolve_manifest_asset_path(raw, output_path)
        # Falls back to the (nonexistent) literal candidate — caller's
        # missing-asset handling takes over from here.
        assert not Path(resolved).exists()

    def test_resolve_manifest_asset_path_absolute_passthrough(self, asset):
        assert VideoCompose._resolve_manifest_asset_path(
            str(asset), Path("/anywhere/renders/final.mp4"),
        ) == str(asset)

    def test_resolve_manifest_asset_path_unknown_output_shape_passthrough(self):
        # output_path not under a renders/ dir — no safe anchor, leave as-is
        # rather than guessing wrong.
        raw = "assets/video/sc-01.mp4"
        assert VideoCompose._resolve_manifest_asset_path(
            raw, Path("/tmp/output.mp4"),
        ) == raw

    def test_resolve_audio_music_sets_src_from_asset_id(self, tmp_path):
        # Regression: edit_decisions.schema.json's audio.music ALWAYS
        # references its asset via asset_id (never a raw path) — confirmed
        # live that nothing converted that to the `src` field Explainer.tsx's
        # AudioConfig.music and _stage_public_assets both require, so a
        # templated render's music track was silently never staged. The
        # compose agent tried ~20 tool calls chasing "Remotion can't find the
        # music asset" before concluding (wrongly) it was an environment bug.
        project_dir = tmp_path / "projects" / "some-job"
        track = project_dir / "assets" / "music" / "bg.mp3"
        track.parent.mkdir(parents=True)
        track.write_bytes(b"fake-mp3-bytes")
        output_path = project_dir / "renders" / "final.mp4"
        asset_lookup = {"music_primary": {"path": "assets/music/bg.mp3"}}
        edit_decisions = {
            "audio": {"music": {"asset_id": "music_primary", "volume": 0.35}},
        }
        resolved = VideoCompose._resolve_audio_music(edit_decisions, asset_lookup, output_path)
        music = resolved["audio"]["music"]
        assert music["src"] == str(track)
        assert Path(music["src"]).is_file()
        assert music["volume"] == 0.35  # other fields preserved
        assert music["asset_id"] == "music_primary"  # not stripped, just enriched

    def test_resolve_audio_music_missing_asset_id_leaves_edit_decisions_unchanged(self):
        edit_decisions = {"audio": {"music": {"asset_id": "not_in_manifest"}}}
        resolved = VideoCompose._resolve_audio_music(
            edit_decisions, {}, Path("/repo/projects/job/renders/final.mp4"),
        )
        assert resolved is edit_decisions
        assert "src" not in resolved["audio"]["music"]

    def test_resolve_audio_music_no_music_block_is_a_no_op(self):
        edit_decisions = {"cuts": []}
        resolved = VideoCompose._resolve_audio_music(
            edit_decisions, {}, Path("/repo/projects/job/renders/final.mp4"),
        )
        assert resolved is edit_decisions

    def test_resolve_audio_music_ignores_narration_segments(self):
        # Deliberately unresolved — Explainer's AudioConfig models narration
        # as ONE track (audio.narration.src), not multiple independently-
        # timed segments, so bridging segments[] would silently drop all but
        # one. Confirm this function doesn't touch narration at all.
        edit_decisions = {
            "audio": {
                "narration": {"segments": [{"asset_id": "vo1", "start_seconds": 0}]},
                "music": {"asset_id": "not_in_manifest"},
            },
        }
        resolved = VideoCompose._resolve_audio_music(
            edit_decisions, {}, Path("/repo/projects/job/renders/final.mp4"),
        )
        assert resolved["audio"]["narration"] == edit_decisions["audio"]["narration"]

    def test_captions_and_text_are_never_mangled(self, asset):
        # Traversal is an explicit key list, not "anything that looks like a
        # path" — a caption word must survive untouched.
        props = {
            "cuts": [{"id": "c1", "source": str(asset), "text": "/not/a/real/path"}],
            "captions": [{"word": "/usr/bin", "startMs": 0, "endMs": 100}],
        }
        VideoCompose()._stage_public_assets(props)
        try:
            assert props["cuts"][0]["text"] == "/not/a/real/path"
            assert props["captions"][0]["word"] == "/usr/bin"
        finally:
            _cleanup(props["cuts"][0]["source"])


class TestMissingAssetFailsLoud:
    """_remotion_render must refuse to invoke npx at all when a referenced
    local asset doesn't exist — the old behavior let the bogus absolute path
    ride all the way into the Remotion subprocess, where it surfaced as an
    opaque "file:// not supported" proxy error with no link back to the
    actual missing/corrupted manifest path (observed live 2026-07-19)."""

    def test_missing_asset_blocks_before_npx_runs(self, tmp_path, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/npx")
        tool = VideoCompose()
        called = []
        monkeypatch.setattr(tool, "run_command", lambda *a, **k: called.append(a))

        missing_path = tmp_path / "vid" / "sc01.mp4"
        result = tool._remotion_render({
            "composition_data": {
                "cuts": [{"id": "c1", "source": str(missing_path)}],
            },
            "output_path": str(tmp_path / "renders" / "out.mp4"),
        })

        assert result.success is False
        assert str(missing_path) in result.error
        assert called == [], "npx must never be invoked once a missing asset is found"

    def test_existing_assets_are_unaffected(self, asset, tmp_path, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/npx")
        tool = VideoCompose()

        def fake_run_command(cmd, **k):
            # Emulate a successful Remotion render by producing the output
            # file. cmd = ["npx", "remotion", "render", entry, comp_id,
            # output_path, "--color-space=bt709"].
            out = Path(cmd[5])
            out.write_bytes(b"fake-mp4")

        monkeypatch.setattr(tool, "run_command", fake_run_command)
        monkeypatch.setattr(tool, "_normalize_deliverable_loudness", lambda *_: False)
        monkeypatch.setattr(
            "tools.video.aigc_label.embed_aigc_metadata", lambda *a, **k: {}
        )

        result = tool._remotion_render({
            "composition_data": {"cuts": [{"id": "c1", "source": str(asset)}]},
            "output_path": str(tmp_path / "renders" / "out.mp4"),
        })

        assert result.success is True


class TestAnchorAtelierProps:
    """Atelier props are hand-authored by the agent with no anchoring
    guarantee — unlike cuts[] (anchored via _resolve_manifest_asset_path
    before staging). Observed live 2026-07-19: an agent wrote
    "projects/<slug>/assets/video/x.mp4" (relative to the repo root) into
    scenes[].src — neither absolute nor a real public/-relative path, so
    staging's own "leave relative paths alone" contract correctly but
    unhelpfully passed it straight through and it 404'd downstream."""

    def test_anchors_repo_root_relative_path(self, tmp_path):
        repo_root = tmp_path / "repo"
        project_dir = repo_root / "projects" / "some-job"
        video_dir = project_dir / "assets" / "video"
        video_dir.mkdir(parents=True)
        real = video_dir / "x.mp4"
        real.write_bytes(b"fake")

        props = {"scenes": [{
            "id": "sc01", "kind": "video",
            "src": "projects/some-job/assets/video/x.mp4",
        }]}
        VideoCompose._anchor_atelier_props(props, project_dir=project_dir, repo_root=repo_root)
        assert props["scenes"][0]["src"] == str(real)

    def test_anchors_project_relative_path(self, tmp_path):
        repo_root = tmp_path / "repo"
        project_dir = repo_root / "projects" / "some-job"
        video_dir = project_dir / "assets" / "video"
        video_dir.mkdir(parents=True)
        real = video_dir / "x.mp4"
        real.write_bytes(b"fake")

        props = {"scenes": [{"id": "sc01", "kind": "video", "src": "assets/video/x.mp4"}]}
        VideoCompose._anchor_atelier_props(props, project_dir=project_dir, repo_root=repo_root)
        assert props["scenes"][0]["src"] == str(real)

    def test_leaves_already_staged_path_untouched(self, tmp_path):
        props = {"scenes": [{"id": "sc01", "kind": "video", "src": "om-staged/abc123.mp4"}]}
        VideoCompose._anchor_atelier_props(
            props, project_dir=tmp_path / "p", repo_root=tmp_path / "r",
        )
        assert props["scenes"][0]["src"] == "om-staged/abc123.mp4"

    def test_leaves_unresolvable_relative_path_for_staging_to_report(self, tmp_path):
        props = {"scenes": [{"id": "sc01", "kind": "video", "src": "assets/video/nope.mp4"}]}
        VideoCompose._anchor_atelier_props(
            props, project_dir=tmp_path / "p", repo_root=tmp_path / "r",
        )
        assert props["scenes"][0]["src"] == "assets/video/nope.mp4"

    def test_anchor_then_stage_recovers_repo_root_relative_src(self, tmp_path):
        # Composed pipeline: anchor (repo-root-relative -> absolute) then
        # stage (absolute -> om-staged/ public-relative) — the exact two
        # steps _render_via_atelier now runs before invoking npx.
        repo_root = tmp_path / "repo"
        project_dir = repo_root / "projects" / "some-job"
        video_dir = project_dir / "assets" / "video"
        video_dir.mkdir(parents=True)
        real = video_dir / "x.mp4"
        real.write_bytes(b"fake")

        props = {"scenes": [{
            "id": "sc01", "kind": "video",
            "src": "projects/some-job/assets/video/x.mp4",
        }]}
        VideoCompose._anchor_atelier_props(props, project_dir=project_dir, repo_root=repo_root)
        _, staged, missing = VideoCompose()._stage_public_assets(props)
        src = props["scenes"][0]["src"]
        try:
            assert missing == []
            assert staged == 1
            assert src.startswith("om-staged/")
        finally:
            _cleanup(src)
