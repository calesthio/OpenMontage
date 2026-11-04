"""End-to-end: a vague brief → relay assets → OpenMontage compose → final.mp4.

Plays the agent's part for "here are two photos and a song — make a cinematic
short, you decide": it plans two shots, stylises a user photo (image_to_image),
animates it from a LOCAL first frame (image_to_video, first poll times out and
is resumed without a second paid submit), animates the second raw photo through
a different relay with a non-OpenAI protocol, narrates with relay TTS, mixes
with the user's music via audio_mixer, and renders via video_compose. Budget
runs through CostTracker (estimate → reserve → reconcile) and the
asset_manifest validates against the canonical schema.

All traffic goes to the loopback mock relay. Requires ffmpeg.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.tools.relay_fixtures import mock_relay, relay_env, write_png  # noqa: F401

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg required for e2e compose")


def _probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def _user_song(path: Path, seconds: int = 12) -> Path:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds}",
         "-ac", "2", str(path)],
        check=True,
    )
    return path


def test_vague_brief_to_final_video_through_relays(relay_env, tmp_path):
    from jsonschema import Draft202012Validator

    from lib.checkpoint import init_project, write_checkpoint
    from lib.config_model import BudgetMode
    from tools.audio.audio_mixer import AudioMixer
    from tools.audio.tts_selector import TTSSelector
    from tools.cost_tracker import CostTracker
    from tools.graphics.image_selector import ImageSelector
    from tools.video.video_compose import VideoCompose
    from tools.video.video_selector import VideoSelector

    registry = relay_env["registry"]
    mock = relay_env["relay"]

    # --- user inputs: two photos and a song ---------------------------------
    inbox = tmp_path / "inbox"
    photo_a = write_png(inbox / "harbor.png", color=(30, 60, 110), size=(640, 360))
    photo_b = write_png(inbox / "street.png", color=(150, 90, 40), size=(640, 360))
    song = _user_song(inbox / "song.wav")

    # --- workspace + preflight ----------------------------------------------
    projects = tmp_path / "projects"
    pid = "harbor-nights"
    project = init_project(pid, title="Harbor Nights", pipeline_type="cinematic", pipeline_dir=projects)
    summary = registry.provider_menu_summary()
    video_cap = next(c for c in summary["capabilities"] if c["capability"] == "video_generation")
    assert "mockrelay" in video_cap["available_providers"]

    tracker = CostTracker(budget_total_usd=5.0, reserve_pct=0.1, mode=BudgetMode.CAP,
                          single_action_approval_usd=5.0, require_approval_for_new_paid_tool=False,
                          cost_log_path=project / "cost_log.json")

    def paid(tool_name: str, selector, inputs: dict):
        tool = registry.get(tool_name)
        entry = tracker.estimate(tool_name, inputs.get("operation", "generate"), tool.estimate_cost(inputs))
        tracker.reserve(entry)
        result = selector.execute(inputs)
        if result.success or result.data.get("status") != "pending":
            tracker.reconcile(entry, result.cost_usd or 0.0, success=result.success)
        return result, entry

    assets = []

    # --- shot 1: stylise photo A, then animate it from that local first frame
    frame_a = project / "assets" / "images" / "shot01_frame.png"
    img, _ = paid("relay_mockrelay_gpt_image_2", ImageSelector(), {
        "prompt": "cinematic night grade, teal and amber, anamorphic flare",
        "preferred_tool": "relay_mockrelay_gpt_image_2",
        "image_path": str(photo_a), "output_path": str(frame_a), "scene_id": "shot01",
    })
    assert img.success, img.error
    assets.append({"id": "shot01_frame", "type": "image", "path": str(frame_a), "scene_id": "shot01",
                   "source_tool": img.data["selected_tool"], "provider": "mockrelay", "model": "gpt-image-2",
                   "cost_usd": img.cost_usd})

    clip_a = project / "assets" / "video" / "shot01.mp4"
    shot1_inputs = {
        "prompt": "[hold] slow push-in across the harbor, lights flicker on",
        "preferred_tool": "relay_mockrelay_sora_2", "operation": "image_to_video",
        "reference_image_path": str(frame_a), "duration": 4, "aspect_ratio": "16:9",
        "output_path": str(clip_a), "scene_id": "shot01",
        "poll_timeout_seconds": 0.02,  # force the "agent's poll window" to expire
    }
    pending, entry = paid("relay_mockrelay_sora_2", VideoSelector(), shot1_inputs)
    assert not pending.success and pending.data["status"] == "pending"
    mock.state.released = True  # the relay finishes rendering later
    resumed = VideoSelector().execute({**shot1_inputs, "poll_timeout_seconds": 10})
    assert resumed.success, resumed.error
    tracker.reconcile(entry, resumed.cost_usd, success=True)
    assert len(mock.state.submits("/videos")) == 1, "resume must not resubmit the paid task"
    assets.append({"id": "shot01", "type": "video", "path": str(clip_a), "scene_id": "shot01",
                   "source_tool": resumed.data["selected_tool"], "provider": "mockrelay", "model": "sora-2",
                   "cost_usd": resumed.cost_usd, "duration_seconds": resumed.data.get("duration_seconds")})

    # --- shot 2: raw photo B through another relay + non-OpenAI protocol ----
    clip_b = project / "assets" / "video" / "shot02.mp4"
    shot2, _ = paid("relay_arkmock_custom_i2v", VideoSelector(), {
        "prompt": "handheld drift down a rain-soaked street",
        "hosting_provider": "arkmock", "model": "wan-i2v", "operation": "image_to_video",
        "reference_image_path": str(photo_b), "duration": 5,
        "output_path": str(clip_b), "scene_id": "shot02",
    })
    assert shot2.success, shot2.error
    assert shot2.data["selected_tool"] == "relay_arkmock_custom_i2v"
    assets.append({"id": "shot02", "type": "video", "path": str(clip_b), "scene_id": "shot02",
                   "source_tool": shot2.data["selected_tool"], "provider": "arkmock", "model": "wan-i2v",
                   "cost_usd": shot2.cost_usd})

    # --- narration via relay TTS ---------------------------------------------
    vo = project / "assets" / "audio" / "narration.wav"
    tts, _ = paid("relay_mockrelay_tts", TTSSelector(), {
        "text": "有些港口，只在夜里醒来。", "preferred_tool": "relay_mockrelay_tts",
        "voice": "nova", "output_format": "wav", "output_path": str(vo),
    })
    assert tts.success, tts.error
    assets.append({"id": "narration", "type": "narration", "path": str(vo), "scene_id": "global",
                   "source_tool": "relay_mockrelay_tts", "provider": "mockrelay", "cost_usd": tts.cost_usd})

    # --- canonical asset manifest + checkpoint --------------------------------
    manifest = {"version": "1.0", "assets": assets,
                "total_cost_usd": round(sum(a.get("cost_usd") or 0 for a in assets), 4)}
    schema = json.loads((Path(__file__).resolve().parents[2] / "schemas/artifacts/asset_manifest.schema.json").read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(manifest), key=str)
    assert not errors, [e.message for e in errors]
    (project / "artifacts" / "asset_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_checkpoint(projects, pid, "assets", "in_progress", {"asset_manifest": manifest},
                     pipeline_type="cinematic", cost_snapshot=tracker.cost_snapshot(),
                     metadata={"partial_progress": {"completed": 4, "total": 4}})

    # --- edit + compose with the existing OpenMontage tools ------------------
    mix = project / "assets" / "audio" / "mix.wav"
    mixed = AudioMixer().execute({"operation": "mix", "output_path": str(mix), "tracks": [
        {"path": str(vo), "role": "speech", "volume": 1.0},
        {"path": str(song), "role": "music", "volume": 0.3, "fade_out_seconds": 1.0},
    ]})
    assert mixed.success, mixed.error

    final = project / "renders" / "final.mp4"
    composed = VideoCompose().execute({
        "operation": "compose",
        "edit_decisions": {"render_runtime": "ffmpeg", "cuts": [
            {"source": str(clip_a), "in_seconds": 0, "out_seconds": 2},
            {"source": str(clip_b), "in_seconds": 0, "out_seconds": 2},
        ]},
        "audio_path": str(mix), "output_path": str(final),
    })
    assert composed.success, composed.error
    probe = _probe(final)
    kinds = {s["codec_type"] for s in probe["streams"]}
    assert {"video", "audio"} <= kinds
    assert float(probe["format"]["duration"]) == pytest.approx(4.0, abs=0.6)

    # --- budget and provenance -------------------------------------------------
    snapshot = tracker.cost_snapshot()
    expected = 0.04 + 0.4 + 0.25 + round(len("有些港口，只在夜里醒来。") * 0.015 / 1000, 4)
    assert snapshot["total_spent_usd"] == pytest.approx(expected, abs=1e-3)
    assert snapshot["total_reserved_usd"] == 0
    for job in (project / "assets").rglob("*.relay-job.json"):
        data = json.loads(job.read_text(encoding="utf-8"))
        assert data["state"] == "downloaded"
        assert "mock-relay-key" not in job.read_text(encoding="utf-8")
    paid_submits = [r for r in mock.state.requests if r["method"] == "POST"]
    assert len(paid_submits) == 4  # i2i + 2 videos + tts — nothing paid twice
