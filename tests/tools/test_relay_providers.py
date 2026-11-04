"""Relay (中转站) provider system — registration, mapping, async safety, budget.

Everything runs against a loopback mock relay (tools/relay/mock_server.py); no
test can reach a real paid endpoint (tests/conftest.py blocks non-loopback
sockets, and the fixture strips proxy env vars so loopback isn't proxied).
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from tests.tools.relay_fixtures import (  # noqa: F401 — fixtures
    OTHER_KEY,
    TEST_KEY,
    mock_relay,
    relay_env,
    rewrite_config,
    write_png,
)
from tools.relay.config import RelayConfigError, parse_relay_config
from tools.relay.engine import load_job, render_template


# ---------------------------------------------------------------------------
# config validation
# ---------------------------------------------------------------------------


def _cfg(body: str):
    import yaml

    return parse_relay_config(yaml.safe_load(textwrap.dedent(body)))


class TestConfig:
    def test_literal_api_key_is_rejected(self):
        with pytest.raises(RelayConfigError, match="literal secrets"):
            _cfg("""
                relays:
                  r:
                    base_url: https://x.example.com
                    api_key: sk-abcdefghijklmnopqrstuvwxyz
                    api_key_env: R_KEY
            """)

    def test_key_looking_value_anywhere_is_rejected(self):
        with pytest.raises(RelayConfigError):
            _cfg("""
                relays:
                  r:
                    base_url: https://x.example.com
                    api_key_env: R_KEY
                    extra_headers: {X-Debug: sk-abcdefghijklmnopqrstuvwxyz}
            """)

    def test_api_key_env_must_be_a_variable_name(self):
        config = _cfg("""
            relays:
              r:
                base_url: https://x.example.com
                api_key_env: "my key value"
        """)
        assert not config.relays and "api_key_env" in config.errors[0]

    def test_bare_origin_gets_protocol_root(self):
        config = _cfg("""
            relays:
              r:
                base_url: https://relay.example.com/
                api_key_env: R_KEY
                models:
                  - {model: gpt-image-2, protocol: openai_images, capabilities: [text_to_image]}
                  - {model: seedance, protocol: ark_seedance, capabilities: [text_to_video]}
              s:
                base_url: https://relay.example.com/custom/v9
                api_key_env: S_KEY
                models:
                  - {model: gpt-image-2, protocol: openai_images, capabilities: [text_to_image]}
        """)
        endpoints = {m.tool_name: m.endpoint for m in config.models}
        assert endpoints["relay_r_gpt_image_2"] == "https://relay.example.com/v1"
        assert endpoints["relay_r_seedance"] == "https://relay.example.com/api/v3"
        assert endpoints["relay_s_gpt_image_2"] == "https://relay.example.com/custom/v9"

    def test_plain_http_refused_for_remote_relays(self):
        config = _cfg("""
            relays:
              r: {base_url: "http://relay.example.com", api_key_env: R_KEY}
        """)
        assert "plain http" in config.errors[0]

    def test_capabilities_must_be_explicit_and_protocol_compatible(self):
        config = _cfg("""
            relays:
              r:
                base_url: https://x.example.com
                api_key_env: R_KEY
                models:
                  - {model: a, protocol: openai_videos}
                  - {model: b, protocol: openai_videos, capabilities: [first_last_frame, image_to_video]}
        """)
        assert len(config.models) == 0
        assert any("capabilities must be declared" in e for e in config.errors)
        assert any("cannot express" in e for e in config.errors)

    def test_generic_capability_must_be_wired_into_request(self):
        config = _cfg("""
            relays:
              r:
                base_url: https://x.example.com
                api_key_env: R_KEY
                models:
                  - model: x
                    protocol: generic_async
                    kind: video
                    capabilities: [image_to_video]
                    request: {submit: {path: /s, body: {prompt: "{{prompt}}"}}}
        """)
        assert not config.models
        assert "silently dropped" in config.errors[0]

    def test_bad_entry_does_not_hide_good_ones(self):
        config = _cfg("""
            relays:
              r:
                base_url: https://x.example.com
                api_key_env: R_KEY
                models:
                  - {model: good, protocol: openai_images, capabilities: [text_to_image]}
                  - {model: bad, protocol: no_such_protocol, capabilities: [text_to_image]}
        """)
        assert [m.model for m in config.models] == ["good"]
        assert config.errors


# ---------------------------------------------------------------------------
# registry + selectors
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_one_tool_per_model_with_exact_metadata(self, relay_env):
        reg = relay_env["registry"]
        sora = reg.get("relay_mockrelay_sora_2")
        assert sora is not None and sora.capability == "video_generation"
        assert sora.hosting_provider == "mockrelay" and sora.provider == "mockrelay"
        assert sora.supports["image_to_video"] is True
        assert sora.supports["first_last_frame"] is False
        info = sora.get_info()
        assert "sora-2" in info["model_catalog"]
        assert "first_last_frame" in info["relay"]["unsupported_capabilities"]
        assert info["relay"]["api_key_env"] == "MOCKRELAY_API_KEY"
        assert TEST_KEY not in json.dumps(info, default=str)
        assert reg.get("relay_mockrelay_gpt_image_2").capability == "image_generation"
        assert reg.get("relay_mockrelay_tts").capability == "tts"
        # text models are listed in config but never become tools
        assert reg.get("relay_mockrelay_deepseek") is None

    def test_video_schema_has_no_image_url_to_avoid_fal_upload(self, relay_env):
        tool = relay_env["registry"].get("relay_mockrelay_sora_2")
        assert "image_url" not in tool.input_schema["properties"]
        assert "reference_image_path" in tool.input_schema["properties"]
        t2v = relay_env["registry"].get("relay_mockrelay_t2v_only")
        assert "reference_image_path" not in t2v.input_schema["properties"]

    def test_missing_key_marks_tool_unavailable(self, relay_env, monkeypatch):
        monkeypatch.delenv("ARKMOCK_API_KEY")
        tool = relay_env["registry"].get("relay_arkmock_seedance")
        assert tool.get_status().value == "unavailable"
        assert "ARKMOCK_API_KEY" in tool.get_info()["status_reason"]

    def test_provider_menu_lists_relay_tools(self, relay_env):
        menu = relay_env["registry"].provider_menu()
        names = {e["name"] for e in menu["video_generation"]["available"]}
        assert {"relay_mockrelay_sora_2", "relay_arkmock_seedance"} <= names

    def test_agent_skill_pointer_resolves(self, relay_env):
        root = Path(__file__).resolve().parents[2] / ".agents" / "skills"
        tool = relay_env["registry"].get("relay_arkmock_seedance")
        for skill in tool.agent_skills:
            assert (root / skill / "SKILL.md").exists(), skill


class TestSelectorRouting:
    def _rank(self, selector, **inputs):
        result = selector.execute({"prompt": "a lighthouse at dusk", "operation": "rank", **inputs})
        assert result.success, result.error
        return [r["tool_name"] for r in result.data["rankings"]]

    def test_preferred_tool_pins_exactly(self, relay_env, tmp_path):
        from tools.video.video_selector import VideoSelector

        result = VideoSelector().execute({
            "prompt": "slow dolly-in on a lighthouse",
            "preferred_tool": "relay_mockrelay_kling",
            "output_path": str(tmp_path / "k.mp4"),
        })
        assert result.success, result.error
        assert result.data["selected_tool"] == "relay_mockrelay_kling"

    def test_hosting_provider_and_model_select_exact_tool(self, relay_env):
        from tools.video.video_selector import VideoSelector

        names = self._rank(VideoSelector(), target_operation="text_to_video",
                           hosting_provider="arkmock", model="doubao-seedance-2-0-260128")
        assert names == ["relay_arkmock_seedance"]

    def test_image_to_video_excludes_t2v_only_models(self, relay_env):
        from tools.video.video_selector import VideoSelector

        names = self._rank(VideoSelector(), target_operation="image_to_video")
        assert "relay_mockrelay_t2v_only" not in names
        assert "relay_mockrelay_sora_2" in names and "relay_arkmock_custom_i2v" in names

    def test_text_to_video_excludes_i2v_only_models(self, relay_env):
        from tools.video.video_selector import VideoSelector

        names = self._rank(VideoSelector(), target_operation="text_to_video")
        assert "relay_arkmock_custom_i2v" not in names

    def test_generate_excludes_edit_only_image_models(self, relay_env):
        from tools.graphics.image_selector import ImageSelector

        names = self._rank(ImageSelector())
        assert "relay_mockrelay_edit_only" not in names
        assert "relay_mockrelay_gpt_image_2" in names

    def test_relay_only_policy_excludes_other_paid_vendors(self, relay_env, monkeypatch):
        from tools.video.video_selector import VideoSelector

        monkeypatch.setenv("FAL_KEY", "fal-test-key-not-real")
        names = self._rank(VideoSelector(), target_operation="text_to_video")
        non_relay = [n for n in names if not n.startswith("relay_")]
        reg = relay_env["registry"]
        for name in non_relay:  # only free/local tools may remain
            tool = reg.get(name)
            assert tool.runtime.value in {"local", "local_gpu"} or not tool.estimate_cost({"prompt": "x"})

    def test_policy_any_restores_original_behaviour(self, relay_env, monkeypatch):
        from tools.provider_routing import apply_paid_provider_policy

        tools = list(relay_env["registry"]._tools.values())
        assert len(apply_paid_provider_policy({}, tools)) < len(tools)
        monkeypatch.setenv("OPENMONTAGE_PAID_PROVIDER_POLICY", "any")
        assert len(apply_paid_provider_policy({}, tools)) == len(tools)
        monkeypatch.delenv("OPENMONTAGE_PAID_PROVIDER_POLICY")
        assert len(apply_paid_provider_policy({"allow_non_relay_paid": True}, tools)) == len(tools)

    def test_unavailable_preferred_tool_never_falls_back(self, relay_env, monkeypatch, tmp_path):
        from tools.video.video_selector import VideoSelector

        monkeypatch.delenv("ARKMOCK_API_KEY")
        result = VideoSelector().execute({
            "prompt": "x", "preferred_tool": "relay_arkmock_seedance",
            "output_path": str(tmp_path / "x.mp4"),
        })
        assert not result.success
        assert "ARKMOCK_API_KEY" in result.error and "No other provider was tried" in result.error
        assert not relay_env["relay"].state.submits()

    def test_tts_selector_routes_by_model(self, relay_env, tmp_path):
        from tools.audio.tts_selector import TTSSelector

        result = TTSSelector().execute({
            "text": "你好，欢迎观看。", "model": "tts-1", "hosting_provider": "mockrelay",
            "output_path": str(tmp_path / "vo.wav"),
        })
        assert result.success, result.error
        assert result.data["selected_tool"] == "relay_mockrelay_tts"
        assert Path(tmp_path / "vo.wav").read_bytes()[:4] == b"RIFF"


# ---------------------------------------------------------------------------
# parameter mapping, first frame, capability refusal
# ---------------------------------------------------------------------------


class TestMapping:
    def test_render_template_types_and_drops(self):
        body = render_template(
            {"model": "{{model}}", "d": "{{duration}}", "seed": "{{seed}}", "label": "v-{{model}}",
             "nested": {"img": "{{first_frame}}"}, "list": ["{{a}}", "{{missing}}"]},
            {"model": "m1", "duration": 5, "seed": None, "first_frame": "data:x", "a": 1},
        )
        assert body == {"model": "m1", "d": 5, "label": "v-m1", "nested": {"img": "data:x"}, "list": [1]}

    def test_request_override_merges_and_null_removes_preset_field(self):
        import yaml
        from tools.relay.engine import deep_merge, PRESETS

        override = yaml.safe_load('submit: {body: {image: "{{first_frame}}", input_reference: null}}')
        spec = deep_merge(PRESETS["openai_video_generations"], override)
        body = render_template(spec["submit"]["body"], {"model": "m", "prompt": "p", "first_frame": "data:x"})
        assert body == {"model": "m", "prompt": "p", "image": "data:x"}
        assert spec["submit"]["path"] == "/video/generations"

    def test_dry_run_shows_exact_request_without_sending(self, relay_env, tmp_path):
        tool = relay_env["registry"].get("relay_mockrelay_kling")
        frame = write_png(tmp_path / "frame.png")
        result = tool.execute({"prompt": "push in", "reference_image_path": str(frame),
                               "aspect_ratio": "9:16", "output_path": str(tmp_path / "o.mp4"), "dry_run": True})
        assert result.success, result.error
        body = result.data["body"]
        assert body["model"] == "kling-v2" and body["seconds"] == "5" and body["size"] == "720x1280"
        assert body["input_reference"].startswith("<data-uri image/png")
        assert result.data["estimated_cost_usd"] == pytest.approx(0.5)
        assert not relay_env["relay"].state.requests

    def test_local_first_frame_reaches_relay_as_data_uri(self, relay_env, tmp_path):
        tool = relay_env["registry"].get("relay_mockrelay_kling")
        frame = write_png(tmp_path / "frame.png")
        result = tool.execute({"prompt": "she turns around", "reference_image_path": str(frame),
                               "output_path": str(tmp_path / "clip.mp4")})
        assert result.success, result.error
        submit = relay_env["relay"].state.submits("/video/generations")[0]
        assert submit["body"]["input_reference"]["data_uri_mime"] == "image/png"
        assert submit["auth"] == f"Bearer {TEST_KEY}"
        assert result.data["operation"] == "image_to_video"

    def test_local_first_frame_uploaded_as_multipart_file(self, relay_env, tmp_path):
        tool = relay_env["registry"].get("relay_mockrelay_sora_2")
        frame = write_png(tmp_path / "frame.png")
        result = tool.execute({"prompt": "camera rises", "first_frame_path": str(frame),
                               "duration": 8, "output_path": str(tmp_path / "s.mp4")})
        assert result.success, result.error
        submit = relay_env["relay"].state.submits("/videos")[0]
        files = submit["multipart_files"]["input_reference"]
        assert files[0]["magic"] == "89504e47"  # PNG
        assert submit["body"]["seconds"] == "8" and submit["body"]["size"] == "1280x720"

    def test_multipart_protocol_stays_multipart_without_files(self, relay_env, tmp_path):
        tool = relay_env["registry"].get("relay_mockrelay_sora_2")
        assert tool.execute({"prompt": "pure text", "output_path": str(tmp_path / "t.mp4")}).success
        submit = relay_env["relay"].state.submits("/videos")[0]
        assert submit["body"] == {"model": "sora-2", "prompt": "pure text", "seconds": "4", "size": "1280x720"}

    def test_generic_protocol_base64_first_frame(self, relay_env, tmp_path):
        tool = relay_env["registry"].get("relay_arkmock_custom_i2v")
        frame = write_png(tmp_path / "f.png")
        result = tool.execute({"prompt": "waves", "reference_image_path": str(frame), "seed": 7,
                               "output_path": str(tmp_path / "g.mp4")})
        assert result.success, result.error
        body = relay_env["relay"].state.submits("/custom/api/submit")[0]["body"]
        assert body["parameters"] == {"duration": 5, "seed": 7}
        assert len(body["input"]["first_frame_image"]) > 100  # raw base64
        assert submit_auth(relay_env, "/custom/api/submit") == f"Bearer {OTHER_KEY}"

    def test_ark_relay_reuses_seedance_payload_with_first_and_last_frame(self, relay_env, tmp_path):
        tool = relay_env["registry"].get("relay_arkmock_seedance")
        first = write_png(tmp_path / "a.png", size=(640, 360))
        last = write_png(tmp_path / "b.png", color=(200, 10, 10), size=(640, 360))
        result = tool.execute({"prompt": "morph", "reference_image_path": str(first),
                               "last_frame_path": str(last), "output_path": str(tmp_path / "ark.mp4")})
        assert result.success, result.error
        body = relay_env["relay"].state.submits("/contents/generations/tasks")[0]["body"]
        roles = [c.get("role") for c in body["content"] if c.get("type") == "image_url"]
        assert roles == ["first_frame", "last_frame"]
        assert body["model"] == "doubao-seedance-2-0-260128"

    def test_unsupported_capability_is_refused_not_faked(self, relay_env, tmp_path):
        frame = write_png(tmp_path / "f.png")
        t2v = relay_env["registry"].get("relay_mockrelay_t2v_only")
        result = t2v.execute({"prompt": "x", "reference_image_path": str(frame),
                              "output_path": str(tmp_path / "x.mp4")})
        assert not result.success and result.data["error_code"] == "unsupported_capability"
        sora = relay_env["registry"].get("relay_mockrelay_sora_2")
        result = sora.execute({"prompt": "x", "reference_image_path": str(frame),
                               "last_frame_path": str(frame), "output_path": str(tmp_path / "y.mp4")})
        assert not result.success and "last frame" in result.error
        result = sora.execute({"prompt": "x", "operation": "text_to_video",
                               "reference_image_path": str(frame), "output_path": str(tmp_path / "z.mp4")})
        assert not result.success and "silently ignored" in result.error
        assert not relay_env["relay"].state.submits()

    def test_invalid_params_are_refused_before_sending(self, relay_env, tmp_path):
        sora = relay_env["registry"].get("relay_mockrelay_sora_2")
        result = sora.execute({"prompt": "x", "duration": 6, "output_path": str(tmp_path / "x.mp4")})
        assert not result.success and "allowed: [4, 8, 12]" in result.error
        result = sora.execute({"prompt": "x", "model": "sora-2-pro", "output_path": str(tmp_path / "x.mp4")})
        assert not result.success and result.data["error_code"] == "model_mismatch"
        assert not relay_env["relay"].state.submits()

    def test_oversized_first_frame_is_reencoded_for_upload_only(self, relay_env, tmp_path):
        import os

        from PIL import Image
        from tools.relay.tooling import _shrink_image
        from tools.relay.engine import load_image_input

        big = tmp_path / "noise.png"
        Image.frombytes("RGB", (900, 1600), os.urandom(900 * 1600 * 3)).save(big)
        original = big.read_bytes()
        shrunk = _shrink_image(load_image_input(big, max_mb=20), 300 * 1024)
        assert shrunk.mime == "image/jpeg" and len(shrunk.data) <= 300 * 1024
        assert big.read_bytes() == original  # the user's file is untouched

    def test_url_only_model_refuses_local_file(self, relay_env, tmp_path):
        from tools.relay.engine import RelayError, encode_image, load_image_input

        img = load_image_input(write_png(tmp_path / "f.png"))
        with pytest.raises(RelayError, match="will not upload"):
            encode_image(img, "url")

    def test_image_edit_multipart_and_text_to_image(self, relay_env, tmp_path):
        tool = relay_env["registry"].get("relay_mockrelay_gpt_image_2")
        out = tmp_path / "t2i.png"
        result = tool.execute({"prompt": "poster", "output_path": str(out)})
        assert result.success, result.error and out.read_bytes()[:4] == b"\x89PNG"
        src = write_png(tmp_path / "src.png")
        out2 = tmp_path / "i2i.png"
        result = tool.execute({"prompt": "make it night", "image_path": str(src), "output_path": str(out2)})
        assert result.success, result.error
        edit = relay_env["relay"].state.submits("/images/edits")[0]
        assert edit["multipart_files"]["image[]"][0]["magic"] == "89504e47"
        assert out2.read_bytes()[:4] == b"\x89PNG"


def submit_auth(env, fragment):
    return env["relay"].state.submits(fragment)[0]["auth"]


# ---------------------------------------------------------------------------
# async safety: submit once, resume, failure, local save, key scoping
# ---------------------------------------------------------------------------


class TestAsyncJobs:
    def test_poll_timeout_returns_pending_and_resume_never_resubmits(self, relay_env, tmp_path):
        tool = relay_env["registry"].get("relay_mockrelay_kling")
        out = tmp_path / "slow.mp4"
        first = tool.execute({"prompt": "[hold] long take", "output_path": str(out),
                              "poll_timeout_seconds": 0.05, "poll_interval_seconds": 0.01})
        assert not first.success
        assert first.data["status"] == "pending" and first.data["recovery_action"] == "resume"
        assert first.cost_usd == 0.0 and first.data["committed_cost_usd"] == pytest.approx(0.5)
        job = load_job(Path(first.data["job_path"]))
        assert job["state"] == "submitted" and job["task_id"]
        assert TEST_KEY not in Path(first.data["job_path"]).read_text(encoding="utf-8")

        # Same call again (e.g. the agent retries): resumes, does not pay again.
        relay_env["relay"].state.released = True
        second = tool.execute({"prompt": "[hold] long take", "output_path": str(out)})
        assert second.success, second.error
        assert len(relay_env["relay"].state.submits("/video/generations")) == 1
        assert second.cost_usd == pytest.approx(0.5)  # charged exactly once
        assert out.is_file() and out.stat().st_size > 0

        # A third call is served from the job record for free.
        third = tool.execute({"prompt": "[hold] long take", "output_path": str(out)})
        assert third.success and third.cost_usd == 0.0 and third.data["from_job_file"]
        assert len(relay_env["relay"].state.submits()) == 1

    def test_resume_from_job_path_only(self, relay_env, tmp_path):
        tool = relay_env["registry"].get("relay_mockrelay_sora_2")
        out = tmp_path / "r.mp4"
        pending = tool.execute({"prompt": "[hold] x", "output_path": str(out), "poll_timeout_seconds": 0.05})
        assert pending.data["status"] == "pending"
        relay_env["relay"].state.released = True
        resumed = tool.execute({"resume_job": pending.data["resume_job"]})
        assert resumed.success, resumed.error
        assert out.is_file()
        assert len(relay_env["relay"].state.submits("/videos")) == 1

    def test_cli_resume(self, relay_env, tmp_path, capsys):
        from tools.relay.__main__ import main

        tool = relay_env["registry"].get("relay_mockrelay_kling")
        out = tmp_path / "cli.mp4"
        pending = tool.execute({"prompt": "[hold] x", "output_path": str(out), "poll_timeout_seconds": 0.05})
        assert pending.data["status"] == "pending"
        relay_env["relay"].state.released = True
        assert main(["resume", pending.data["job_path"]]) == 0
        assert out.is_file()
        assert len(relay_env["relay"].state.submits()) == 1

    def test_task_failure_is_detected_and_not_auto_retried(self, relay_env, tmp_path):
        tool = relay_env["registry"].get("relay_mockrelay_kling")
        out = tmp_path / "f.mp4"
        failed = tool.execute({"prompt": "[fail] x", "output_path": str(out)})
        assert not failed.success and "content policy" in failed.error
        again = tool.execute({"prompt": "[fail] x", "output_path": str(out)})
        assert not again.success and again.data["error_code"] == "previous_failure"
        assert len(relay_env["relay"].state.submits()) == 1
        retried = tool.execute({"prompt": "[fail] x", "output_path": str(out), "confirm_resubmit": True})
        assert not retried.success
        assert len(relay_env["relay"].state.submits()) == 2  # only with explicit approval
        job = load_job(Path(retried.data["job_path"]))
        assert job["previous_attempts"][0]["task_id"] == failed.data["task_id"]

    def test_approved_resubmit_still_respects_live_switch(self, tmp_path, monkeypatch):
        import yaml
        from tools.relay.config import parse_relay_config
        from tools.relay.engine import save_job
        from tools.video.relay_video import RelayVideo

        config = parse_relay_config(yaml.safe_load("""
            relays:
              real:
                base_url: https://relay.example.com
                api_key_env: REAL_RELAY_KEY
                models:
                  - {model: kling, protocol: openai_video_generations, capabilities: [text_to_video], pricing: {per_request: 1}}
        """))
        monkeypatch.setenv("REAL_RELAY_KEY", "not-a-real-key-123456")
        tool = RelayVideo(config.models[0])
        out = tmp_path / "x.mp4"
        save_job(Path(str(out) + ".relay-job.json"), {"tool": tool.name, "state": "failed", "fingerprint": "old",
                                                       "output_path": str(out)})
        result = tool.execute({"prompt": "x", "output_path": str(out), "confirm_resubmit": True})
        assert not result.success and result.data["error_code"] == "live_disabled"

    def test_ambiguous_submit_is_never_repeated_silently(self, relay_env, tmp_path):
        tool = relay_env["registry"].get("relay_mockrelay_kling")
        out = tmp_path / "u.mp4"
        first = tool.execute({"prompt": "[504] x", "output_path": str(out)})
        assert not first.success and first.data["status"] == "submit_unknown"
        second = tool.execute({"prompt": "[504] x", "output_path": str(out)})
        assert not second.success and second.data["error_code"] == "submit_unknown"
        assert len(relay_env["relay"].state.submits()) == 1

    def test_rejected_submit_explains_model_not_found(self, relay_env, tmp_path):
        tool = relay_env["registry"].get("relay_mockrelay_kling")
        result = tool.execute({"prompt": "[400] x", "output_path": str(tmp_path / "m.mp4")})
        assert not result.success and "python -m tools.relay models" in result.error
        assert result.data["error_code"] == "model_not_found"

    def test_different_request_on_same_output_is_refused(self, relay_env, tmp_path):
        tool = relay_env["registry"].get("relay_mockrelay_kling")
        out = tmp_path / "c.mp4"
        assert tool.execute({"prompt": "one", "output_path": str(out)}).success
        other = tool.execute({"prompt": "two", "output_path": str(out)})
        assert not other.success and other.data["error_code"] == "job_conflict"
        assert len(relay_env["relay"].state.submits()) == 1

    def test_result_saved_locally_and_key_not_sent_to_file_host(self, relay_env, tmp_path):
        tool = relay_env["registry"].get("relay_arkmock_custom_i2v")
        out = tmp_path / "deep" / "dir" / "clip.mp4"
        frame = write_png(tmp_path / "f.png")
        result = tool.execute({"prompt": "x", "reference_image_path": str(frame), "output_path": str(out)})
        assert result.success, result.error
        assert out.is_file() and result.artifacts == [str(out)]
        assert result.data["remote_url"].startswith(relay_env["relay"].url + "/files/")
        downloads = [r for r in relay_env["relay"].state.requests if r["path"].startswith("/files/")]
        # Same host here, but the mock serves /files/ like a CDN: the engine only
        # sends auth to the relay endpoint origin, which this is — so assert the
        # stricter cross-origin rule directly:
        from tools.relay.engine import RelayHTTP

        http = RelayHTTP(tool.relay_model)
        assert http.same_origin(relay_env["relay"].url + "/x")
        assert not http.same_origin("https://cdn.example.com/x.mp4")
        assert downloads

    def test_openai_videos_content_download_uses_auth(self, relay_env, tmp_path):
        tool = relay_env["registry"].get("relay_mockrelay_sora_2")
        out = tmp_path / "s.mp4"
        assert tool.execute({"prompt": "x", "output_path": str(out)}).success
        content = [r for r in relay_env["relay"].state.requests if r["path"].endswith("/content")]
        assert content and content[0]["auth"] == f"Bearer {TEST_KEY}"

    def test_redownload_when_local_file_deleted_without_resubmit(self, relay_env, tmp_path):
        tool = relay_env["registry"].get("relay_mockrelay_kling")
        out = tmp_path / "d.mp4"
        assert tool.execute({"prompt": "x", "output_path": str(out)}).success
        out.unlink()
        again = tool.execute({"prompt": "x", "output_path": str(out)})
        assert again.success and out.is_file() and again.cost_usd == 0.0
        assert len(relay_env["relay"].state.submits()) == 1


# ---------------------------------------------------------------------------
# billing gates + budget
# ---------------------------------------------------------------------------


class TestBillingAndBudget:
    def test_live_false_blocks_real_relay_before_network(self, tmp_path, monkeypatch):
        import yaml
        from tools.relay.config import parse_relay_config
        from tools.video.relay_video import RelayVideo

        config = parse_relay_config(yaml.safe_load("""
            relays:
              real:
                base_url: https://relay.example.com
                api_key_env: REAL_RELAY_KEY
                live: false
                models:
                  - {model: kling, protocol: openai_video_generations, capabilities: [text_to_video], pricing: {per_request: 1}}
        """))
        monkeypatch.setenv("REAL_RELAY_KEY", "not-a-real-key-123456")
        tool = RelayVideo(config.models[0])
        result = tool.execute({"prompt": "x", "output_path": str(tmp_path / "x.mp4")})
        assert not result.success and result.data["error_code"] == "live_disabled"
        assert not (tmp_path / "x.mp4.relay-job.json").exists()
        dry = tool.execute({"prompt": "x", "output_path": str(tmp_path / "x.mp4"), "dry_run": True})
        assert dry.success and dry.data["billing_enabled"] is False

    def test_unpriced_model_needs_explicit_approval(self, relay_env, tmp_path):
        from tools.provider_pricing import PriceQuoteRequired

        tool = relay_env["registry"].get("relay_mockrelay_unpriced")
        with pytest.raises(PriceQuoteRequired):
            tool.estimate_cost({"prompt": "x"})
        result = tool.execute({"prompt": "x", "output_path": str(tmp_path / "u.mp4")})
        assert not result.success and result.data["error_code"] == "price_required"
        assert not relay_env["relay"].state.submits()
        ok = tool.execute({"prompt": "x", "output_path": str(tmp_path / "u.mp4"), "allow_unpriced": True})
        assert ok.success and ok.cost_usd is None and ok.data["cost_status"] == "unpriced"

    def test_cost_estimates_follow_config(self, relay_env):
        reg = relay_env["registry"]
        assert reg.get("relay_mockrelay_sora_2").estimate_cost({"duration": 12}) == pytest.approx(1.2)
        assert reg.get("relay_mockrelay_kling").estimate_cost({}) == pytest.approx(0.5)  # 3.6 CNY
        assert reg.get("relay_mockrelay_tts").estimate_cost({"text": "a" * 2000}) == pytest.approx(0.03)
        assert reg.get("relay_arkmock_seedance").estimate_cost({"duration": 10}) == pytest.approx(10 / 7.2, rel=1e-3)

    def test_cost_tracker_cap_mode_blocks_and_reconciles(self, relay_env, tmp_path):
        from lib.config_model import BudgetMode
        from tools.cost_tracker import BudgetExceededError, CostTracker

        tracker = CostTracker(budget_total_usd=1.0, reserve_pct=0.0, mode=BudgetMode.CAP,
                              single_action_approval_usd=5.0, require_approval_for_new_paid_tool=False,
                              cost_log_path=tmp_path / "cost_log.json")
        sora = relay_env["registry"].get("relay_mockrelay_sora_2")
        too_big = tracker.estimate(sora.name, "image_to_video", sora.estimate_cost({"duration": 12}))
        with pytest.raises(BudgetExceededError):
            tracker.reserve(too_big)
        ok = tracker.estimate(sora.name, "text_to_video", sora.estimate_cost({"duration": 4}))
        tracker.reserve(ok)
        result = sora.execute({"prompt": "x", "duration": 4, "output_path": str(tmp_path / "b.mp4")})
        assert result.success
        tracker.reconcile(ok, result.cost_usd, success=True)
        assert tracker.cost_snapshot()["total_spent_usd"] == pytest.approx(0.4)
