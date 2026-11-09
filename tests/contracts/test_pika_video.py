"""Contract tests for the Pika H3 Flex video provider (Pika API).

Every HTTP call is faked; the suite's network guard would block a real one.

Run: pytest tests/contracts/test_pika_video.py -v
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import pytest
from requests.exceptions import ConnectionError, Timeout

from tools.base_tool import (
    BaseTool,
    ResumeSupport,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)
from tools.provider_pricing import PriceQuoteRequired
from tools.video import pika_video as module
from tools.video.pika_video import MODEL, PikaVideo

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE = "https://api.dev.pika.art"
JOB_ID = "media_8f3a2c91-5b7d-4e0a-9c26-31d4f2a8e6b0"
VIDEO_URL = "https://api.dev.pika.art/v1/files/video_8f3a2c91.mp4"


# ------------------------------------------------------------------
# Fake HTTP
# ------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status_code=200, json_data=None, headers=None, text="", content=b"", reason="OK"):
        self.status_code = status_code
        self._json = json_data
        self.headers = headers or {}
        self.text = text or (json.dumps(json_data) if json_data is not None else "")
        self.content = content
        self.reason = reason

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeRequests:
    """Routes (method, url-substring) to queued responses and records every call."""

    def __init__(self):
        self.calls: list[dict] = []
        self._routes: list[tuple[str, str, deque]] = []

    def add(self, method: str, contains: str, *responses) -> None:
        wrapped = [r if isinstance(r, FakeResponse) else FakeResponse(200, r) for r in responses]
        self._routes.append((method.upper(), contains, deque(wrapped)))

    def _respond(self, method, url, **kwargs):
        self.calls.append({"method": method.upper(), "url": url, **kwargs})
        for route_method, contains, queue in self._routes:
            if route_method == method.upper() and contains in url:
                if not queue:
                    raise AssertionError(f"No more fake responses for {method} {url}")
                return queue.popleft() if len(queue) > 1 else queue[0]
        raise AssertionError(f"Unexpected request {method} {url}")

    def request(self, method, url, headers=None, timeout=None, json=None, data=None, params=None):
        return self._respond(method, url, headers=headers, json=json, data=data, timeout=timeout)

    def get(self, url, headers=None, timeout=None, params=None):
        return self._respond("GET", url, headers=headers, json=None, data=None, timeout=timeout)

    def by(self, method: str, contains: str) -> list[dict]:
        return [c for c in self.calls if c["method"] == method.upper() and contains in c["url"]]


def job(status, *, error=None, billing=None, usage=None, output=True):
    body = {"id": JOB_ID, "status": status, "model_id": f"pika/{MODEL}/text-to-video"}
    if status == "completed":
        body["usage"] = usage or {"video_output_tokens": 50638}
        body["billing"] = billing if billing is not None else {"state": "settled", "charge_micro_usd": 372189}
        if output:
            body["output"] = {"media_type": "video", "video": {"url": VIDEO_URL, "content_type": "video/mp4"}}
    if status == "failed":
        body["error"] = error or {"code": "provider_error", "message": "boom"}
        body["billing"] = None
    return body


@pytest.fixture()
def fake_http(monkeypatch):
    fake = FakeRequests()
    monkeypatch.setattr(module, "requests", fake)
    monkeypatch.setattr("tools.provider_jobs.requests", fake)
    monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    monkeypatch.setattr("tools.provider_jobs.time.sleep", lambda *_: None)
    return fake


@pytest.fixture()
def pika_env(monkeypatch):
    monkeypatch.setenv("PIKA_API_KEY", "pk-test-key")
    monkeypatch.delenv("PIKA_API_BASE_URL", raising=False)


@pytest.fixture()
def no_pika_env(monkeypatch):
    monkeypatch.delenv("PIKA_API_KEY", raising=False)


def happy_path(fake: FakeRequests, *, polls=None, video=b"\x00\x00\x00\x18ftypmp42"):
    fake.add("POST", f"/v1/media/pika/{MODEL}/", FakeResponse(200, {"id": JOB_ID, "status": "queued"}))
    fake.add("GET", f"/v1/media/jobs/{JOB_ID}", *(polls or [job("queued"), job("running"), job("completed")]))
    fake.add("GET", VIDEO_URL, FakeResponse(200, content=video))


# ------------------------------------------------------------------
# Contract
# ------------------------------------------------------------------

class TestContract:
    def test_inherits_base_tool(self):
        assert issubclass(PikaVideo, BaseTool)

    def test_identity(self):
        tool = PikaVideo()
        assert tool.name == "pika_video"
        assert tool.provider == "pika"
        assert tool.capability == "video_generation"
        assert tool.tier == ToolTier.GENERATE
        assert tool.stability == ToolStability.BETA
        assert tool.runtime == ToolRuntime.API
        assert tool.resume_support == ResumeSupport.FROM_CHECKPOINT
        assert tool.dependencies == ["env:PIKA_API_KEY"]
        assert tool.retry_policy.max_retries == 0

    def test_input_schema(self):
        schema = PikaVideo().input_schema
        assert schema["type"] == "object"
        assert schema["required"] == ["prompt"]
        props = schema["properties"]
        for name in ("prompt", "operation", "model", "duration", "resolution", "aspect_ratio", "seed",
                     "rewrite", "reference_image_path", "reference_image_url", "reference_image_urls",
                     "references", "output_path", "job_path", "resume_job", "dry_run"):
            assert name in props, name
        assert props["model"]["enum"] == [MODEL]
        assert set(props["resolution"]["enum"]) == {"480p", "768p", "1080p", "2k", "4k"}

    def test_capabilities_and_supports(self):
        tool = PikaVideo()
        for op in ("text_to_video", "image_to_video", "first_last_frame_to_video", "reference_to_video"):
            assert op in tool.capabilities
            assert tool.supports[op] is True
        assert tool.supports["native_audio"] is True
        assert tool.models == {MODEL: {
            "text_to_video": "text-to-video",
            "image_to_video": "image-to-video",
            "first_last_frame_to_video": "image-to-video",
            "reference_to_video": "reference-to-video",
        }}

    def test_agent_skill_pointers_resolve(self):
        for skill in PikaVideo().agent_skills:
            assert (REPO_ROOT / ".agents" / "skills" / skill / "SKILL.md").exists(), skill

    def test_get_info_serializes_with_billing_and_catalog(self, pika_env):
        info = PikaVideo().get_info()
        json.dumps(info)
        assert info["hosting_provider"] == "pika"
        assert info["billing"]["prepaid"] is True and info["billing"]["free_tier"] is False
        assert info["model_catalog"][MODEL]["usd_per_output_second"]["480p"] == pytest.approx(0.01)
        assert info["quality_score"] == pytest.approx(0.9)

    def test_schema_does_not_advertise_image_url(self):
        """video_selector uploads reference_image_path to fal for tools that expose image_url;
        pika_video uploads to Pika itself, so it must not advertise that name."""
        props = PikaVideo().input_schema["properties"]
        assert "image_url" not in props and "image_path" not in props
        assert "reference_image_path" in props and "reference_image_url" in props

    def test_contract_file_is_pinned_from_public_catalog(self):
        contract = json.loads(
            (REPO_ROOT / "tools" / "provider_contracts" / "pika_h3_flex.json").read_text(encoding="utf-8")
        )
        for fn in ("text-to-video", "image-to-video", "reference-to-video"):
            assert contract[fn]["source"].startswith("https://api.dev.pika.art/catalog/apis/")
            assert contract[fn]["verified_on"]
            assert contract[fn]["call"]["path"] == f"/v1/media/pika/{MODEL}/{fn}"


# ------------------------------------------------------------------
# Discovery and status
# ------------------------------------------------------------------

class TestDiscoveryAndStatus:
    def test_registry_discovers_tool(self, isolated_tool_registry):
        isolated_tool_registry.discover()
        tool = isolated_tool_registry.get("pika_video")
        assert tool is not None
        assert tool.provider == "pika"
        assert tool in isolated_tool_registry.get_by_capability("video_generation")

    def test_unavailable_without_key(self, no_pika_env):
        assert PikaVideo().get_status() == ToolStatus.UNAVAILABLE

    def test_available_with_key_and_no_network(self, pika_env, monkeypatch):
        def explode(*_a, **_k):
            raise AssertionError("get_status must not touch the network")

        monkeypatch.setattr(module.requests, "request", explode)
        assert PikaVideo().get_status() == ToolStatus.AVAILABLE

    def test_execute_without_key_fails_with_setup_hint(self, no_pika_env):
        result = PikaVideo().execute({"prompt": "a harbor at dawn"})
        assert result.success is False
        assert "PIKA_API_KEY" in result.error and "dev.pika.art" in result.error


# ------------------------------------------------------------------
# Estimates
# ------------------------------------------------------------------

class TestEstimates:
    def test_provider_overrides_are_priced_in_preflight_and_submission(self, pika_env, fake_http, tmp_path):
        inputs = {"prompt": "x", "duration": 3, "resolution": "480p",
                  "provider_params": {"duration": 15, "resolution": "4k"},
                  "output_path": str(tmp_path / "override.mp4")}
        tool = PikaVideo()
        assert tool.estimate_cost(inputs) == pytest.approx(1.28)
        assert fake_http.calls == []
        happy_path(fake_http)
        result = tool.execute(inputs)
        assert result.success, result.error
        assert result.data["estimated_cost_usd"] == pytest.approx(1.28)
        assert result.data["resume_job"]["estimated_cost_usd"] == pytest.approx(1.28)
        sent = fake_http.by("POST", "/v1/media/pika/")[0]["json"]
        assert sent["duration"] == 15 and sent["resolution"] == "4k"

    def test_overridden_references_include_input_video_cost(self):
        inputs = {"prompt": "x", "reference_image_urls": ["https://a/original.png"],
                  "resolution": "4k", "duration": 15,
                  "provider_params": {"references": [{"type": "video", "url": "https://a/final.mp4"}]}}
        with pytest.raises(PriceQuoteRequired):
            PikaVideo().estimate_cost(inputs)
        assert PikaVideo().estimate_cost({**inputs, "reference_video_seconds": 6}) == pytest.approx(2.20)

    def test_only_effective_references_are_billed(self):
        inputs = {"prompt": "x", "reference_video_urls": ["https://a/unused.mp4"],
                  "provider_params": {"references": [{"type": "image", "url": "https://a/final.png"}]}}
        assert PikaVideo().estimate_cost(inputs) == pytest.approx(0.36)

    def test_resume_estimate_is_the_saved_preflight_estimate(self, fake_http):
        # A resume carries no prompt and submits nothing; preflight must not fail
        # on validation or price a job that was already reserved.
        tool = PikaVideo()
        saved = {"id": JOB_ID, "tool": "pika_video", "operation": "text_to_video", "estimated_cost_usd": 0.48}
        assert tool.estimate_cost({"resume_job": saved, "poll_timeout": 600}) == pytest.approx(0.48)
        assert tool.estimate_cost({"resume_job": {"id": JOB_ID, "tool": "pika_video"}}) == 0.0
        assert tool.dry_run({"resume_job": saved})["estimated_cost_usd"] == pytest.approx(0.48)
        assert fake_http.calls == []

    def test_estimate_of_local_media_never_uploads(self, fake_http, tmp_path):
        # This need not exist: preflight must not upload or read the reference.
        inputs = {"prompt": "x", "reference_video_paths": [str(tmp_path / "input.mp4")],
                  "reference_video_seconds": 6}
        assert PikaVideo().estimate_cost(inputs) == pytest.approx(0.72)
        assert fake_http.calls == []

    @pytest.mark.parametrize(
        ("inputs", "expected"),
        [
            ({"prompt": "x"}, 0.02 * 6),                                        # 768p default, 5s + 1s allowance
            ({"prompt": "x", "resolution": "480p", "duration": 3}, 0.01 * 4),
            ({"prompt": "x", "resolution": "4k", "duration": 15}, 0.08 * 16),
            ({"prompt": "x", "resolution": "1080p", "duration": "10s", "image_url": "https://a/b.png"}, 0.035 * 11),
            ({"prompt": "x", "resolution": "480p", "reference_image_urls": ["https://a/1.png"]}, 0.03 * 6),
            ({"prompt": "x", "resolution": "768p", "reference_video_urls": ["https://a/1.mp4"],
              "reference_video_seconds": 6}, 0.06 * 6 + 0.06 * 6),
        ],
    )
    def test_estimate_from_published_rates(self, inputs, expected):
        assert PikaVideo().estimate_cost(inputs) == pytest.approx(expected)

    def test_reference_video_without_seconds_requires_quote(self):
        with pytest.raises(PriceQuoteRequired):
            PikaVideo().estimate_cost({"prompt": "x", "reference_video_urls": ["https://a/1.mp4"]})

    def test_reference_upscale_uses_published_rate(self):
        cost = PikaVideo().estimate_cost({"prompt": "x", "resolution": "4k", "reference_image_urls": ["https://a/1.png"]})
        assert cost == pytest.approx(0.10 * 6)

    def test_runtime_grows_with_duration_and_upscale(self):
        tool = PikaVideo()
        assert tool.estimate_runtime({"prompt": "x", "duration": 5}) < tool.estimate_runtime({"prompt": "x", "duration": 15})
        assert tool.estimate_runtime({"prompt": "x", "resolution": "4k"}) > tool.estimate_runtime({"prompt": "x"})


# ------------------------------------------------------------------
# Payload building
# ------------------------------------------------------------------

class TestPayload:
    def build(self, inputs):
        return PikaVideo()._build_request(inputs, {"X-API-Key": "k"})

    def test_text_to_video_defaults(self):
        op, fn, payload = self.build({"prompt": "A calm harbor at dawn"})
        assert (op, fn) == ("text_to_video", "text-to-video")
        assert payload == {"prompt": "A calm harbor at dawn", "duration": 5, "resolution": "768p", "rewrite": True}

    def test_aliases_and_normalization(self):
        _, _, payload = self.build({
            "prompt": "x", "seconds": "8s", "resolution": "2K", "ratio": "9:16",
            "prompt_optimizer": False, "seed": 42, "operation": "generate",
        })
        assert payload == {"prompt": "x", "duration": 8, "resolution": "2k", "rewrite": False,
                           "aspect_ratio": "9:16", "seed": 42}

    def test_first_frame_infers_image_to_video(self):
        op, fn, payload = self.build({"prompt": "x", "reference_image_url": "https://a/first.png"})
        assert (op, fn) == ("image_to_video", "image-to-video")
        assert payload["image"] == "https://a/first.png"
        assert "last_frame_image" not in payload

    def test_last_frame_alone_is_valid(self):
        op, _, payload = self.build({"prompt": "x", "end_image_url": "https://a/last.png"})
        assert op == "image_to_video"
        assert payload["last_frame_image"] == "https://a/last.png" and "image" not in payload

    def test_both_frames_infer_first_last(self):
        op, fn, payload = self.build({"prompt": "x", "image_url": "https://a/f.png", "last_frame_image": "https://a/l.png"})
        assert (op, fn) == ("first_last_frame_to_video", "image-to-video")
        assert payload["image"] == "https://a/f.png" and payload["last_frame_image"] == "https://a/l.png"

    def test_first_last_with_one_frame_rejected(self):
        with pytest.raises(ValueError, match="both"):
            self.build({"prompt": "x", "operation": "first_last_frame_to_video", "image_url": "https://a/f.png"})

    def test_reference_lists_keep_image_video_audio_order(self):
        op, fn, payload = self.build({
            "prompt": "x",
            "reference_audio_urls": ["https://a/a.wav"],
            "reference_video_urls": ["https://a/v.mp4"],
            "reference_image_urls": ["https://a/1.png", "https://a/2.png"],
        })
        assert (op, fn) == ("reference_to_video", "reference-to-video")
        assert payload["references"] == [
            {"type": "image", "url": "https://a/1.png"},
            {"type": "image", "url": "https://a/2.png"},
            {"type": "video", "url": "https://a/v.mp4"},
            {"type": "audio", "url": "https://a/a.wav"},
        ]

    def test_native_references_preserve_supplied_order(self):
        refs = [{"type": "video", "url": "https://a/v.mp4"}, {"type": "image", "url": "https://a/1.png"}]
        _, _, payload = self.build({"prompt": "x", "references": refs})
        assert payload["references"] == refs

    def test_provider_params_merge_and_are_validated(self):
        _, _, payload = self.build({"prompt": "x", "provider_params": {"output_mode": "video"}})
        assert payload["output_mode"] == "video"
        with pytest.raises(Exception):
            self.build({"prompt": "x", "provider_params": {"not_a_field": 1}})

    @pytest.mark.parametrize(
        ("inputs", "match"),
        [
            ({"prompt": "x", "duration": 2}, "between 3 and 15"),
            ({"prompt": "x", "duration": 16}, "between 3 and 15"),
            ({"prompt": "x", "duration": "5.5"}, "whole number"),
            ({"prompt": "x", "resolution": "720p"}, "resolution must be one of"),
            ({"prompt": "x", "aspect_ratio": "2:1"}, "aspect_ratio must be one of"),
            ({"prompt": "x", "generate_audio": False}, "always generates"),
            ({"prompt": "x", "operation": "text_to_video", "image_url": "https://a/f.png"}, "use image_to_video"),
            ({"prompt": "x", "operation": "text_to_video", "reference_image_urls": ["https://a/1.png"]}, "use reference_to_video"),
            ({"prompt": "x", "image_url": "data:image/png;base64,AAAA"}, "http\\(s\\) URL"),
            ({"prompt": "x", "image_url": "https://a/f.png", "image_path": "/tmp/f.png"}, "not both"),
            ({"prompt": "x", "reference_image_urls": [f"https://a/{i}.png" for i in range(10)]}, "At most 9 image"),
            ({"prompt": "x", "reference_video_urls": [f"https://a/{i}.mp4" for i in range(4)]}, "At most 3 video"),
            ({"prompt": "x", "reference_audio_urls": ["https://a/a.wav"]}, "at least one image or video"),
            ({"prompt": "x", "model": "pika-2.5"}, "Unsupported model"),
            ({"prompt": "   "}, "prompt is required"),
        ],
    )
    def test_rejected_locally_before_spending(self, inputs, match):
        with pytest.raises(ValueError, match=match):
            self.build(inputs)

    def test_total_reference_limit(self):
        refs = [f"https://a/{i}.png" for i in range(9)]
        videos = [f"https://a/{i}.mp4" for i in range(3)]
        audio = ["https://a/a.wav"]
        with pytest.raises(ValueError, match="12 references"):
            self.build({"prompt": "x", "reference_image_urls": refs, "reference_video_urls": videos,
                        "reference_audio_urls": audio})


# ------------------------------------------------------------------
# Lifecycle
# ------------------------------------------------------------------

class TestLifecycle:
    def test_submit_poll_download_and_settled_cost(self, pika_env, fake_http, tmp_path):
        happy_path(fake_http)
        out = tmp_path / "clip.mp4"
        result = PikaVideo().execute({
            "prompt": "A calm harbor at dawn", "duration": 5, "resolution": "768p",
            "seed": 3, "output_path": str(out),
        })
        assert result.success, result.error
        assert out.read_bytes().startswith(b"\x00\x00\x00\x18ftyp")
        assert result.artifacts == [str(out)]
        assert result.cost_usd == pytest.approx(0.372189)
        assert result.seed == 3 and result.model == MODEL

        posts = fake_http.by("POST", f"/v1/media/pika/{MODEL}/text-to-video")
        assert len(posts) == 1
        assert posts[0]["headers"]["X-API-Key"] == "pk-test-key"
        assert posts[0]["headers"]["Idempotency-Key"]
        assert posts[0]["json"] == {"prompt": "A calm harbor at dawn", "duration": 5, "resolution": "768p",
                                    "rewrite": True, "seed": 3}
        assert len(fake_http.by("GET", f"/v1/media/jobs/{JOB_ID}")) == 3

        data = result.data
        assert data["provider"] == "pika" and data["job_id"] == JOB_ID
        assert data["cost_status"] == "settled"
        assert data["billing"]["charge_micro_usd"] == 372189
        assert data["usage"] == {"video_output_tokens": 50638}
        assert data["estimated_cost_usd"] == pytest.approx(0.12)
        assert data["resume_job"]["id"] == JOB_ID and data["resume_job"]["tool"] == "pika_video"
        assert data["native_audio"] is True

    def test_job_path_persists_checkpoint(self, pika_env, fake_http, tmp_path):
        happy_path(fake_http)
        job_path = tmp_path / "jobs" / "pika.json"
        PikaVideo().execute({"prompt": "x", "output_path": str(tmp_path / "o.mp4"), "job_path": str(job_path)})
        saved = json.loads(job_path.read_text())
        assert saved["id"] == JOB_ID and saved["function"] == "text-to-video"

    def test_default_output_path_uses_job_id(self, pika_env, fake_http, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        happy_path(fake_http)
        result = PikaVideo().execute({"prompt": "x"})
        assert result.success
        assert Path(result.artifacts[0]).name == f"pika_{JOB_ID}.mp4"

    def test_completed_without_video_url_fails(self, pika_env, fake_http, tmp_path):
        happy_path(fake_http, polls=[job("completed", output=False)])
        result = PikaVideo().execute({"prompt": "x", "output_path": str(tmp_path / "o.mp4")})
        assert result.success is False and "no video URL" in result.error
        assert result.data["job_id"] == JOB_ID


class TestBilling:
    @pytest.mark.parametrize("error", [ConnectionError("offline"), Timeout("timed out"),
                                       module.PikaAPIError("unavailable", status=503)])
    @pytest.mark.parametrize("recovers", [False, True])
    def test_refresh_errors_preserve_completed_video(self, error, recovers, pika_env, fake_http,
                                                     tmp_path, monkeypatch):
        pending = {"state": "pending", "reason": "reconciling"}
        happy_path(fake_http, polls=[job("completed", billing=pending)])
        original = fake_http.request
        polls = 0

        def request(method, url, **kwargs):
            nonlocal polls
            if method == "GET" and "/v1/media/jobs/" in url:
                polls += 1
                if polls > 1:
                    if recovers and polls > 2:
                        return FakeResponse(200, job("completed"))
                    raise error
            return original(method, url, **kwargs)

        monkeypatch.setattr(fake_http, "request", request)
        out = tmp_path / "completed.mp4"
        result = PikaVideo().execute({"prompt": "x", "output_path": str(out)})
        assert result.success, result.error
        assert result.artifacts == [str(out)] and out.read_bytes().startswith(b"\x00\x00\x00\x18ftyp")
        assert result.data["output"] == str(out)
        assert result.data["resume_job"]["id"] == JOB_ID
        assert result.data["estimated_cost_usd"] == pytest.approx(0.12)
        assert result.data["cost_status"] == ("settled" if recovers else "pending")
        assert result.cost_usd == pytest.approx(0.372189 if recovers else 0.12)
        if not recovers:
            assert result.data["billing"] == pending
        assert len(fake_http.by("POST", "/v1/media/pika/")) == 1

    def test_pending_then_settled(self, pika_env, fake_http, tmp_path):
        happy_path(fake_http, polls=[
            job("completed", billing={"state": "pending"}),
            job("completed", billing={"state": "pending"}),
            job("completed", billing={"state": "settled", "charge_micro_usd": 100000}),
        ])
        result = PikaVideo().execute({"prompt": "x", "output_path": str(tmp_path / "o.mp4")})
        assert result.success and result.cost_usd == pytest.approx(0.10)
        assert result.data["cost_status"] == "settled"

    def test_never_settles_reports_estimate_as_pending(self, pika_env, fake_http, tmp_path):
        happy_path(fake_http, polls=[job("completed", billing={"state": "pending"})])
        result = PikaVideo().execute({"prompt": "x", "resolution": "480p", "duration": 3,
                                      "output_path": str(tmp_path / "o.mp4")})
        assert result.success
        assert result.data["cost_status"] == "pending"
        assert result.cost_usd == pytest.approx(0.04)   # the preflight estimate, flagged as pending

    def test_promotional_free_job_settles_at_zero(self, pika_env, fake_http, tmp_path):
        done = job("completed", billing={"state": "settled", "charge_micro_usd": 0})
        done["free_generation"] = {"promo_id": "daily-free-api-2026", "allowance": "i2v", "resets_at": "2026-11-07T00:00:00Z"}
        happy_path(fake_http, polls=[done])
        result = PikaVideo().execute({"prompt": "x", "output_path": str(tmp_path / "o.mp4")})
        assert result.success
        assert result.cost_usd == 0.0
        assert result.data["cost_status"] == "settled"
        assert result.data["free_generation"]["promo_id"] == "daily-free-api-2026"

    def test_unavailable_billing_is_flagged(self, pika_env, fake_http, tmp_path):
        happy_path(fake_http, polls=[job("completed", billing={"state": "unavailable"})])
        result = PikaVideo().execute({"prompt": "x", "output_path": str(tmp_path / "o.mp4")})
        assert result.success and result.data["cost_status"] == "unavailable"

    def test_failed_job_costs_nothing(self, pika_env, fake_http):
        fake_http.add("POST", f"/v1/media/pika/{MODEL}/", FakeResponse(200, {"id": JOB_ID, "status": "queued"}))
        fake_http.add("GET", f"/v1/media/jobs/{JOB_ID}",
                      job("running"), job("failed", error={"code": "content_moderation", "message": "nope"}))
        result = PikaVideo().execute({"prompt": "x"})
        assert result.success is False and result.cost_usd == 0.0
        assert result.data["error_code"] == "content_moderation"
        assert "moderation" in result.error and result.data["retryable"] is False


# ------------------------------------------------------------------
# Errors: never a second paid submission
# ------------------------------------------------------------------

class TestErrors:
    def test_insufficient_balance_envelope(self, pika_env, fake_http):
        envelope = {"id": JOB_ID, "status": "failed",
                    "error": {"code": "insufficient_balance", "message": "balance too low"}}
        fake_http.add("POST", f"/v1/media/pika/{MODEL}/", FakeResponse(403, envelope))
        result = PikaVideo().execute({"prompt": "x"})
        assert result.success is False
        assert result.data["error_code"] == "insufficient_balance"
        assert "Add funds" in result.error and "dev.pika.art" in result.error
        assert len(fake_http.by("POST", "/v1/media/pika/")) == 1
        assert result.cost_usd == 0.0

    def test_rate_limited_surfaces_retry_after(self, pika_env, fake_http):
        envelope = {"id": JOB_ID, "status": "failed", "error": {"code": "rate_limited", "message": "slow down"}}
        fake_http.add("POST", f"/v1/media/pika/{MODEL}/", FakeResponse(429, envelope, headers={"Retry-After": "30"}))
        result = PikaVideo().execute({"prompt": "x"})
        assert result.success is False
        assert result.data["retry_after"] == "30" and result.data["retryable"] is True
        assert len(fake_http.calls) == 1

    def test_validation_message_is_surfaced(self, pika_env, fake_http):
        fake_http.add("POST", f"/v1/media/pika/{MODEL}/", FakeResponse(422, {"message": "duration must be <= 15"}))
        result = PikaVideo().execute({"prompt": "x"})
        assert result.success is False and "duration must be <= 15" in result.error

    def test_unauthorized(self, pika_env, fake_http):
        fake_http.add("POST", f"/v1/media/pika/{MODEL}/", FakeResponse(401, {"message": "Unauthorized"}))
        result = PikaVideo().execute({"prompt": "x"})
        assert result.success is False and "Unauthorized" in result.error

    def test_200_with_failed_status_is_a_failure(self, pika_env, fake_http):
        envelope = {"id": JOB_ID, "status": "failed", "error": {"code": "invalid_input", "message": "bad prompt"}}
        fake_http.add("POST", f"/v1/media/pika/{MODEL}/", FakeResponse(200, envelope))
        result = PikaVideo().execute({"prompt": "x"})
        assert result.success is False and result.data["error_code"] == "invalid_input"
        assert fake_http.by("GET", "/v1/media/jobs/") == []


class TestAssetCache:
    @pytest.fixture(autouse=True)
    def isolated_cache(self, monkeypatch, tmp_path):
        from lib.asset_cache import reset_default_asset_cache

        monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE", "1")
        monkeypatch.setenv("OPENMONTAGE_ASSET_CACHE_DIR", str(tmp_path / "cache"))
        reset_default_asset_cache()
        yield
        reset_default_asset_cache()

    @pytest.mark.parametrize(("alias", "first", "second", "request_key"), [
        ("seconds", 5, 10, "duration"),
        ("ratio", "16:9", "9:16", "aspect_ratio"),
        ("prompt_optimizer", True, False, "rewrite"),
        ("first_frame_image", "https://a/first.png", "https://a/second.png", "image"),
        ("image_url", "https://a/first.png", "https://a/second.png", "image"),
        ("last_frame_image", "https://a/first.png", "https://a/second.png", "last_frame_image"),
        ("end_image_url", "https://a/first.png", "https://a/second.png", "last_frame_image"),
    ])
    def test_alias_changes_generate_fresh_media(self, alias, first, second, request_key,
                                                pika_env, fake_http, tmp_path):
        happy_path(fake_http)
        tool = PikaVideo()
        inputs = {"prompt": "x", "seed": 77, alias: first, "output_path": str(tmp_path / "a.mp4")}
        initial = tool.execute(inputs)
        inputs.update({alias: second, "output_path": str(tmp_path / "b.mp4")})
        changed = tool.execute(inputs)
        assert initial.success and changed.success
        assert not changed.from_cache
        assert changed.data["request"][request_key] == second
        assert len(fake_http.by("POST", "/v1/media/pika/")) == 2

        cached = tool.execute({**inputs, "output_path": str(tmp_path / "c.mp4")})
        assert cached.success and cached.from_cache
        assert cached.data["request"][request_key] == second
        assert Path(cached.artifacts[0]).read_bytes() == Path(changed.artifacts[0]).read_bytes()
        assert len(fake_http.by("POST", "/v1/media/pika/")) == 2

    @pytest.mark.parametrize(("field", "extension"), [
        ("image_path", ".png"), ("reference_image_path", ".png"),
        ("last_frame_image_path", ".png"), ("reference_image_paths", ".png"),
        ("reference_video_paths", ".mp4"), ("reference_audio_paths", ".wav"),
        ("reference_paths", ".mp4"), ("references", ".mp4"),
    ])
    def test_replacing_local_media_invalidates_cache(self, field, extension, pika_env, fake_http,
                                                    tmp_path, monkeypatch):
        happy_path(fake_http)
        media = tmp_path / f"input{extension}"
        media.write_bytes(b"original reference")
        uploads = []

        def upload(self, path, headers):
            uploads.append(path.read_bytes())
            return f"https://a/uploaded{extension}"

        monkeypatch.setattr(PikaVideo, "_upload", upload)
        value = ([{"type": "video", "path": str(media)}] if field == "references" else
                 [str(media)] if field.endswith("paths") else str(media))
        inputs = {"prompt": "x", "seed": 77, field: value, "reference_video_seconds": 6}
        if field == "reference_audio_paths":
            inputs["reference_image_urls"] = ["https://a/image.png"]
        tool = PikaVideo()
        initial = tool.execute({**inputs, "output_path": str(tmp_path / "a.mp4")})
        media.write_bytes(b"replacement reference")
        changed = tool.execute({**inputs, "output_path": str(tmp_path / "b.mp4")})
        assert initial.success and changed.success
        assert not changed.from_cache
        assert uploads == [b"original reference", b"replacement reference"]
        assert len(fake_http.by("POST", "/v1/media/pika/")) == 2

    def test_cached_success_does_not_bypass_audio_validation(self, pika_env, fake_http, tmp_path):
        happy_path(fake_http)
        inputs = {"prompt": "x", "seed": 77, "output_path": str(tmp_path / "a.mp4")}
        tool = PikaVideo()
        assert tool.execute(inputs).success
        result = tool.execute({**inputs, "generate_audio": False, "output_path": str(tmp_path / "b.mp4")})
        assert not result.success and "always generates" in result.error
        assert len(fake_http.by("POST", "/v1/media/pika/")) == 1

    def test_resume_job_is_not_replaced_by_cached_generation(self, pika_env, fake_http, tmp_path):
        happy_path(fake_http)
        inputs = {"prompt": "x", "seed": 77}
        tool = PikaVideo()
        generated = tool.execute({**inputs, "output_path": str(tmp_path / "a.mp4")})
        assert generated.success
        other_id = "media_another_job"
        fake_http.add("GET", f"/v1/media/jobs/{other_id}", job("completed"))
        resumed = tool.execute({**inputs, "resume_job": {**generated.data["resume_job"], "id": other_id},
                                "output_path": str(tmp_path / "b.mp4")})
        assert resumed.success and not resumed.from_cache
        assert resumed.data["job_id"] == other_id
        assert len(fake_http.by("GET", f"/v1/media/jobs/{other_id}")) == 1
        assert len(fake_http.by("POST", "/v1/media/pika/")) == 1


# ------------------------------------------------------------------
# Resume
# ------------------------------------------------------------------

class TestResume:
    def test_timeout_returns_resume_job(self, pika_env, fake_http):
        fake_http.add("POST", f"/v1/media/pika/{MODEL}/", FakeResponse(200, {"id": JOB_ID, "status": "queued"}))
        fake_http.add("GET", f"/v1/media/jobs/{JOB_ID}", job("running"))
        result = PikaVideo().execute({"prompt": "x", "poll_timeout": 0.01, "poll_interval": 0.005})
        assert result.success is False
        assert result.data["retryable"] is True
        assert result.data["resume_job"]["id"] == JOB_ID
        assert "do not resubmit" in result.error

    def test_resume_polls_without_resubmitting(self, pika_env, fake_http, tmp_path):
        fake_http.add("GET", f"/v1/media/jobs/{JOB_ID}", job("completed"))
        fake_http.add("GET", VIDEO_URL, FakeResponse(200, content=b"mp4"))
        resume = {"id": JOB_ID, "tool": "pika_video", "model": MODEL, "operation": "text_to_video",
                  "function": "text-to-video", "request": {"prompt": "x", "duration": 5, "resolution": "768p",
                                                            "rewrite": True, "seed": 9},
                  "estimated_cost_usd": 0.12}
        result = PikaVideo().execute({"prompt": "x", "resume_job": resume, "output_path": str(tmp_path / "o.mp4")})
        assert result.success, result.error
        assert fake_http.by("POST", "/v1/media/pika/") == []
        assert result.seed == 9 and result.data["request"]["prompt"] == "x"

    def test_foreign_resume_job_is_rejected(self, pika_env, fake_http):
        result = PikaVideo().execute({"prompt": "x", "resume_job": {"id": "abc", "tool": "minimax_video", "model": "MiniMax-H3"}})
        assert result.success is False and "does not belong" in result.error
        assert fake_http.calls == []


# ------------------------------------------------------------------
# Uploads and dry run
# ------------------------------------------------------------------

class TestUploadsAndDryRun:
    def test_local_first_frame_is_uploaded_with_signed_headers(self, pika_env, fake_http, tmp_path):
        frame = tmp_path / "first.png"
        frame.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 10)
        ticket = {"upload_url": "https://uploads.pika.art/signed/abc", "url": "https://cdn.pika.art/perm/abc.png",
                  "headers": {"Content-Type": "image/png", "Content-Length": str(frame.stat().st_size), "x-amz-meta-k": "v"}}
        fake_http.add("POST", "/v1/media/uploads", FakeResponse(200, ticket))
        fake_http.add("PUT", "uploads.pika.art/signed/abc", FakeResponse(200))
        happy_path(fake_http)

        result = PikaVideo().execute({"prompt": "x", "reference_image_path": str(frame),
                                      "output_path": str(tmp_path / "o.mp4")})
        assert result.success, result.error
        upload_request = fake_http.by("POST", "/v1/media/uploads")[0]
        assert upload_request["json"] == {"content_type": "image/png", "size_bytes": frame.stat().st_size}
        put = fake_http.by("PUT", "signed/abc")[0]
        assert put["headers"] == ticket["headers"]
        submit = fake_http.by("POST", f"/v1/media/pika/{MODEL}/image-to-video")[0]
        assert submit["json"]["image"] == "https://cdn.pika.art/perm/abc.png"

    def test_reference_paths_are_typed_by_extension(self, pika_env, fake_http, tmp_path):
        files = {}
        for name in ("hero.png", "move.mp4", "beat.wav"):
            p = tmp_path / name
            p.write_bytes(b"x" * 4)
            files[name] = p
        # Uploads happen in the supplied order: beat.wav, move.mp4, hero.png.
        fake_http.add("POST", "/v1/media/uploads", *[
            FakeResponse(200, {"upload_url": f"https://u/{i}", "url": f"https://cdn/{name}", "headers": {}})
            for i, name in enumerate(("beat.wav", "move.mp4", "hero.png"))
        ])
        fake_http.add("PUT", "https://u/", FakeResponse(200))
        happy_path(fake_http)
        result = PikaVideo().execute({
            "prompt": "x", "reference_paths": [str(files["beat.wav"]), str(files["move.mp4"]), str(files["hero.png"])],
            "reference_video_seconds": 4, "output_path": str(tmp_path / "o.mp4"),
        })
        assert result.success, result.error
        submit = fake_http.by("POST", f"/v1/media/pika/{MODEL}/reference-to-video")[0]
        assert submit["json"]["references"] == [
            {"type": "audio", "url": "https://cdn/beat.wav"},
            {"type": "video", "url": "https://cdn/move.mp4"},
            {"type": "image", "url": "https://cdn/hero.png"},
        ]

    def test_missing_local_file_fails_before_submit(self, pika_env, fake_http):
        result = PikaVideo().execute({"prompt": "x", "image_path": "/nonexistent/frame.png"})
        assert result.success is False and "not found" in result.error
        assert fake_http.calls == []

    def test_dry_run_quotes_without_uploading_or_submitting(self, pika_env, fake_http, tmp_path):
        frame = tmp_path / "first.png"
        frame.write_bytes(b"x")
        fake_http.add("POST", "/catalog/apis/pika%2Fpika-h3-flex%2Fimage-to-video/quote",
                      FakeResponse(200, {"sell_usd": "0.1", "micro_usd": 100000}))
        result = PikaVideo().execute({"prompt": "x", "image_path": str(frame), "dry_run": True, "resolution": "480p"})
        assert result.success, result.error
        assert result.cost_usd == 0.0
        assert result.data["dry_run"] is True and result.data["quoted_cost_usd"] == pytest.approx(0.10)
        assert result.data["cost_status"] == "quoted"
        assert fake_http.by("POST", "/v1/media/") == [] and fake_http.by("PUT", "") == []
        assert result.data["request"]["image"] == "https://dry-run.invalid/first.png"
        assert result.data["local_files"] == [str(frame)]


# ------------------------------------------------------------------
# Selector routing
# ------------------------------------------------------------------

class TestSelectorRouting:
    @pytest.fixture()
    def selector(self, pika_env):
        from tools.tool_registry import registry
        from tools.video.video_selector import VideoSelector

        registry.discover()
        return VideoSelector()

    @pytest.mark.parametrize("operation", ["text_to_video", "image_to_video", "reference_to_video"])
    def test_ranked_for_each_operation(self, selector, operation):
        inputs = {"prompt": "A product spins on a turntable with a soft synth bed", "operation": "rank",
                  "target_operation": operation}
        if operation == "image_to_video":
            inputs["reference_image_url"] = "https://a/first.png"
        if operation == "reference_to_video":
            inputs["reference_image_urls"] = ["https://a/first.png"]
        result = selector.execute(inputs)
        assert result.success, result.error
        names = [r.get("tool") or r.get("tool_name") or r.get("name") for r in result.data["rankings"]]
        assert "pika_video" in names

    def test_explicit_route_by_tool_and_model(self, selector):
        from tools.provider_routing import filter_explicit_route

        providers = selector._providers()
        by_tool = filter_explicit_route({"preferred_tool": "pika_video", "operation": "text_to_video"}, providers)
        assert [t.name for t in by_tool] == ["pika_video"]
        by_model = filter_explicit_route({"model": MODEL, "hosting_provider": "pika",
                                          "operation": "reference_to_video"}, providers)
        assert [t.name for t in by_model] == ["pika_video"]
        none = filter_explicit_route({"preferred_tool": "pika_video", "operation": "video_edit"}, providers)
        assert none == []

    def test_selector_passes_local_frame_through_without_fal(self, selector, fake_http, tmp_path, monkeypatch):
        """With preferred_tool, the selector must hand reference_image_path to pika_video, which
        uploads it to Pika; no fal upload is attempted because image_url is not advertised."""
        frame = tmp_path / "first.png"
        frame.write_bytes(b"\x89PNG")
        monkeypatch.delenv("FAL_KEY", raising=False)
        fake_http.add("POST", "/v1/media/uploads",
                      FakeResponse(200, {"upload_url": "https://u/1", "url": "https://cdn/first.png", "headers": {}}))
        fake_http.add("PUT", "https://u/1", FakeResponse(200))
        happy_path(fake_http)
        result = selector.execute({
            "prompt": "the still comes alive", "operation": "image_to_video",
            "reference_image_path": str(frame), "preferred_tool": "pika_video",
            "output_path": str(tmp_path / "o.mp4"),
        })
        assert result.success, result.error
        assert result.data["selected_tool"] == "pika_video"
        submit = fake_http.by("POST", f"/v1/media/pika/{MODEL}/image-to-video")[0]
        assert submit["json"]["image"] == "https://cdn/first.png"
