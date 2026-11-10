"""Contract tests for the UberLLM video provider.

Every HTTP call is faked; the suite's network guard would block a real one.

Run: pytest tests/contracts/test_uberllm_video.py -v
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

import pytest
from jsonschema import ValidationError

from tools.base_tool import BaseTool, ResumeSupport, ToolRuntime, ToolStability, ToolStatus, ToolTier
from tools.provider_pricing import PriceQuoteRequired
from tools.video import uberllm_video as module
from tools.video.uberllm_video import DEFAULT_FAMILY, FAMILIES, MODEL_SPECS, UberLLMVideo

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE = "https://api.uberllm.dev"
JOB_ID = "6f1c2a9e-3b7d-4e0a-9c26-31d4f2a8e6b0"
VIDEO_URL = f"{BASE}/v1/media/artifacts/{JOB_ID}/0"
SEEDANCE_T2V = "bytedance/seedance-2-0-text-to-video"
SEEDANCE_I2V = "bytedance/seedance-2-0-image-to-video"
SEEDANCE_R2V = "bytedance/seedance-2-0-reference-to-video"
VIDU_T2V = "fal-ai/vidu/q3/text-to-video/turbo"


# ------------------------------------------------------------------
# Fake HTTP
# ------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status_code=200, json_data=None, headers=None, content=b"", reason="OK"):
        self.status_code = status_code
        self._json = json_data
        self.headers = headers or {}
        self.text = json.dumps(json_data) if json_data is not None else ""
        self.content = content
        self.reason = reason

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


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
                return queue.popleft() if len(queue) > 1 else queue[0]
        raise AssertionError(f"Unexpected request {method} {url}")

    def request(self, method, url, headers=None, timeout=None, json=None, files=None, **_):
        return self._respond(method, url, headers=headers, json=json, files=files)

    def get(self, url, headers=None, timeout=None, **_):
        return self._respond("GET", url, headers=headers, json=None, files=None)

    def by(self, method: str, contains: str) -> list[dict]:
        return [c for c in self.calls if c["method"] == method.upper() and contains in c["url"]]


def job(status, *, cost=0.76, pending=False, error=None, model=SEEDANCE_T2V):
    body = {"id": JOB_ID, "object": "media.job", "kind": "video", "status": status, "model": model}
    if status == "succeeded":
        body["results"] = [{"artifact_index": 0, "url": VIDEO_URL, "content_type": "video/mp4", "duration_seconds": 5}]
        body["usage"] = {"cost_usd": None, "cost_pending": True} if pending else {"cost_usd": cost, "cost_usdc": str(int(cost * 1e6))}
    if status in {"failed", "expired"}:
        body["error"] = error or {"message": "the model could not make this clip", "retryable": False}
    return body


def submitted(model=SEEDANCE_T2V, estimate=0.76):
    return FakeResponse(202, {"id": JOB_ID, "object": "media.job", "status": "queued", "model": model,
                              "estimated_cost_usd": estimate, "max_cost_usd": round(estimate * 1.1, 4),
                              "poll_url": f"/v1/video/generations/{JOB_ID}"})


@pytest.fixture()
def fake_http(monkeypatch):
    fake = FakeRequests()
    monkeypatch.setattr(module, "requests", fake)
    monkeypatch.setattr(module.time, "sleep", lambda *_: None)
    monkeypatch.setattr("tools.provider_jobs.time.sleep", lambda *_: None)
    return fake


@pytest.fixture()
def uberllm_env(monkeypatch):
    monkeypatch.setenv("UBERLLM_API_KEY", "ull_test_key")
    monkeypatch.delenv("UBERLLM_BASE_URL", raising=False)


@pytest.fixture()
def no_uberllm_env(monkeypatch):
    monkeypatch.delenv("UBERLLM_API_KEY", raising=False)


def happy_path(fake: FakeRequests, *, polls=None, model=SEEDANCE_T2V, estimate=0.76):
    fake.add("POST", "/v1/video/generations", submitted(model, estimate))
    fake.add("GET", f"/v1/video/generations/{JOB_ID}", *(polls or [job("queued"), job("running"), job("succeeded", model=model)]))
    fake.add("GET", VIDEO_URL, FakeResponse(200, content=b"\x00\x00\x00\x18ftypmp42"))


# ------------------------------------------------------------------
# Contract
# ------------------------------------------------------------------

class TestContract:
    def test_identity(self):
        tool = UberLLMVideo()
        assert isinstance(tool, BaseTool)
        assert (tool.name, tool.provider, tool.capability) == ("uberllm_video", "uberllm", "video_generation")
        assert tool.tier == ToolTier.GENERATE
        assert tool.stability == ToolStability.BETA
        assert tool.runtime == ToolRuntime.API
        assert tool.resume_support == ResumeSupport.FROM_CHECKPOINT
        assert tool.dependencies == ["env:UBERLLM_API_KEY"]
        assert tool.retry_policy.max_retries == 0

    def test_input_schema(self):
        props = UberLLMVideo().input_schema["properties"]
        for name in ("prompt", "operation", "model", "duration", "resolution", "aspect_ratio", "generate_audio",
                     "reference_image_url", "reference_image_path", "reference_image_urls", "reference_image_paths",
                     "max_cost_usd", "dry_run", "output_path", "job_path", "resume_job"):
            assert name in props, name
        assert set(FAMILIES) | set(MODEL_SPECS) == set(props["model"]["enum"])

    def test_schema_does_not_advertise_image_url(self):
        """video_selector uploads reference_image_path to fal for tools that expose image_url;
        uberllm_video uploads to UberLLM itself, so it must not advertise that name."""
        props = UberLLMVideo().input_schema["properties"]
        assert "image_url" not in props and "image_path" not in props

    def test_default_family_serves_every_operation_first(self):
        routes = UberLLMVideo().models
        assert next(iter(routes)) == DEFAULT_FAMILY
        assert set(routes[DEFAULT_FAMILY]) == {"text_to_video", "image_to_video", "reference_to_video"}

    def test_agent_skill_pointers_resolve(self):
        for skill in UberLLMVideo().agent_skills:
            assert (REPO_ROOT / ".agents" / "skills" / skill / "SKILL.md").exists(), skill

    def test_contract_file_is_consistent(self):
        contract = json.loads((REPO_ROOT / "tools" / "provider_contracts" / "uberllm_video.json").read_text("utf-8"))
        assert contract["_about"]["verified_on"]
        for family, routes in contract["families"].items():
            for operation, model_id in routes.items():
                spec = contract["models"][model_id]
                assert (spec["family"], spec["operation"]) == (family, operation)
                assert spec["input_schema"]["properties"]["model"]["const"] == model_id
                assert spec["usd_per_second"]["default"] > 0

    def test_get_info_serializes_with_billing_and_catalog(self, uberllm_env):
        info = UberLLMVideo().get_info()
        json.dumps(info)
        assert info["hosting_provider"] == "uberllm"
        assert info["billing"]["prepaid"] is True and info["billing"]["free_tier"] is False
        assert info["model_catalog"][VIDU_T2V]["usd_per_second"]["360p"] == pytest.approx(0.02975)


# ------------------------------------------------------------------
# Discovery and status
# ------------------------------------------------------------------

class TestDiscoveryAndStatus:
    def test_registry_discovers_tool(self, isolated_tool_registry):
        isolated_tool_registry.discover()
        tool = isolated_tool_registry.get("uberllm_video")
        assert tool is not None
        assert tool in isolated_tool_registry.get_by_capability("video_generation")

    def test_unavailable_without_key(self, no_uberllm_env):
        assert UberLLMVideo().get_status() == ToolStatus.UNAVAILABLE

    def test_available_with_key_and_no_network(self, uberllm_env, fake_http):
        assert UberLLMVideo().get_status() == ToolStatus.AVAILABLE
        assert fake_http.calls == []

    def test_execute_without_key_fails_with_setup_hint(self, no_uberllm_env):
        result = UberLLMVideo().execute({"prompt": "a harbor at dawn"})
        assert result.success is False
        assert "UBERLLM_API_KEY" in result.error and "uberllm.dev/signup" in result.error


# ------------------------------------------------------------------
# Estimates
# ------------------------------------------------------------------

class TestEstimates:
    @pytest.mark.parametrize(("inputs", "expected"), [
        ({"prompt": "x"}, 0.152 * 5),                                                     # seedance t2v, shortest 5 s
        ({"prompt": "x", "model": VIDU_T2V, "resolution": "360p", "duration": 1}, 0.02975),
        ({"prompt": "x", "model": "vidu-q3-turbo", "duration": "4s"}, 0.06545 * 4),
        ({"prompt": "x", "reference_image_url": "https://a/b.png", "resolution": "1080p", "duration": 10}, 0.3744 * 10),
        ({"prompt": "x", "reference_image_urls": ["https://a/1.png"]}, 0.05368 * 5),
    ])
    def test_estimate_from_pinned_rates(self, inputs, expected):
        assert UberLLMVideo().estimate_cost(inputs) == pytest.approx(expected)

    def test_estimate_of_local_media_never_uploads(self, fake_http, tmp_path):
        inputs = {"prompt": "x", "reference_image_path": str(tmp_path / "missing.png")}
        assert UberLLMVideo().estimate_cost(inputs) == pytest.approx(0.0704 * 5)
        assert fake_http.calls == []

    def test_unpinned_resolution_requires_quote(self, monkeypatch):
        spec = MODEL_SPECS[VIDU_T2V]
        monkeypatch.setitem(spec, "usd_per_second", {"default": 0.06545})
        with pytest.raises(PriceQuoteRequired):
            UberLLMVideo().estimate_cost({"prompt": "x", "model": VIDU_T2V, "resolution": "1080p"})

    def test_resume_estimate_is_the_saved_estimate(self, fake_http):
        saved = {"id": JOB_ID, "tool": "uberllm_video", "estimated_cost_usd": 0.48}
        assert UberLLMVideo().estimate_cost({"resume_job": saved}) == pytest.approx(0.48)
        assert fake_http.calls == []


# ------------------------------------------------------------------
# Payload building
# ------------------------------------------------------------------

class TestPayload:
    def build(self, inputs):
        return UberLLMVideo()._build_request(inputs, {}, mode="estimate")

    def test_text_to_video_defaults(self):
        op, model_id, payload = self.build({"prompt": "A calm harbor at dawn"})
        assert (op, model_id) == ("text_to_video", SEEDANCE_T2V)
        assert payload == {"model": SEEDANCE_T2V, "prompt": "A calm harbor at dawn", "duration_seconds": 5}

    def test_operation_inferred_from_pictures(self):
        assert self.build({"prompt": "x", "reference_image_url": "https://a/f.png"})[1] == SEEDANCE_I2V
        op, model_id, payload = self.build({"prompt": "x", "reference_image_urls": ["https://a/1.png", "https://a/2.png"]})
        assert (op, model_id) == ("reference_to_video", SEEDANCE_R2V)
        assert payload["input_images"] == ["https://a/1.png", "https://a/2.png"]

    def test_family_picks_route_and_exact_id_must_match_operation(self):
        assert self.build({"prompt": "x", "model": "veo-3.1-fast", "reference_image_url": "https://a/f.png"})[1] == \
            "fal-ai/veo3.1/fast/image-to-video"
        with pytest.raises(ValueError, match="not image_to_video"):
            self.build({"prompt": "x", "model": VIDU_T2V, "reference_image_url": "https://a/f.png"})
        with pytest.raises(ValueError, match="no reference_to_video"):
            self.build({"prompt": "x", "model": "kling-3-standard", "reference_image_urls": ["https://a/1.png"]})

    def test_settings_the_model_lacks_are_refused_not_ignored(self):
        with pytest.raises(ValueError, match="no aspect_ratio setting"):
            self.build({"prompt": "x", "aspect_ratio": "9:16"})
        op, _, payload = self.build({"prompt": "x", "model": "kling-3-standard", "aspect_ratio": "9:16",
                                     "generate_audio": False})
        assert payload["aspect_ratio"] == "9:16" and payload["audio"] is False

    def test_lengths_and_values_checked_against_pinned_schema(self):
        with pytest.raises(ValidationError):
            self.build({"prompt": "x", "duration": 3})                      # seedance: 5-15 s
        with pytest.raises(ValidationError):
            self.build({"prompt": "x", "model": VIDU_T2V, "resolution": "8k"})
        with pytest.raises(ValidationError):
            self.build({"prompt": "x", "provider_params": {"seed": 1}})     # unknown field

    def test_text_to_video_refuses_pictures(self):
        with pytest.raises(ValueError, match="does not take pictures"):
            self.build({"prompt": "x", "operation": "text_to_video", "reference_image_url": "https://a/f.png"})

    def test_http_picture_links_are_refused(self):
        with pytest.raises(ValueError, match="https://"):
            self.build({"prompt": "x", "reference_image_url": "http://a/f.png"})


# ------------------------------------------------------------------
# Lifecycle, billing and errors
# ------------------------------------------------------------------

class TestLifecycle:
    def test_submit_poll_download(self, uberllm_env, fake_http, tmp_path):
        happy_path(fake_http)
        result = UberLLMVideo().execute({"prompt": "x", "max_cost_usd": 1.0, "output_path": str(tmp_path / "o.mp4")})
        assert result.success, result.error
        submit = fake_http.by("POST", "/v1/video/generations")[0]
        assert submit["headers"]["Authorization"] == "Bearer ull_test_key"
        assert submit["headers"]["Idempotency-Key"]
        assert submit["json"] == {"model": SEEDANCE_T2V, "prompt": "x", "duration_seconds": 5, "max_cost": 1.0}
        assert Path(result.artifacts[0]).read_bytes().startswith(b"\x00\x00\x00\x18ftyp")
        assert fake_http.by("GET", VIDEO_URL)[0]["headers"]["Authorization"] == "Bearer ull_test_key"
        assert result.cost_usd == pytest.approx(0.76)
        assert result.data["cost_status"] == "settled"
        assert result.data["max_cost_usd"] == pytest.approx(0.836)

    def test_key_is_not_sent_to_a_foreign_download_host(self, uberllm_env, fake_http, tmp_path):
        foreign = "https://cdn.example.com/clip.mp4"
        fake_http.add("POST", "/v1/video/generations", submitted())
        done = job("succeeded")
        done["results"][0]["url"] = foreign
        fake_http.add("GET", f"/v1/video/generations/{JOB_ID}", done)
        fake_http.add("GET", foreign, FakeResponse(200, content=b"mp4"))
        assert UberLLMVideo().execute({"prompt": "x", "output_path": str(tmp_path / "o.mp4")}).success
        assert fake_http.by("GET", foreign)[0]["headers"] is None

    def test_pending_cost_settles_on_refetch(self, uberllm_env, fake_http, tmp_path):
        happy_path(fake_http, polls=[job("running"), job("succeeded", pending=True), job("succeeded", cost=0.71)])
        result = UberLLMVideo().execute({"prompt": "x", "output_path": str(tmp_path / "o.mp4")})
        assert result.success and result.cost_usd == pytest.approx(0.71)
        assert result.data["cost_status"] == "settled"

    def test_unsettled_cost_reports_listed_price_as_pending(self, uberllm_env, fake_http, tmp_path):
        happy_path(fake_http, polls=[job("succeeded", pending=True)])
        result = UberLLMVideo().execute({"prompt": "x", "output_path": str(tmp_path / "o.mp4")})
        assert result.success and result.cost_usd == pytest.approx(0.76)
        assert result.data["cost_status"] == "pending"

    @pytest.mark.parametrize("status", ["failed", "expired", "canceled"])
    def test_terminal_states_fail_without_charge(self, uberllm_env, fake_http, status):
        fake_http.add("POST", "/v1/video/generations", submitted())
        fake_http.add("GET", f"/v1/video/generations/{JOB_ID}", job(status))
        result = UberLLMVideo().execute({"prompt": "x"})
        assert result.success is False and result.cost_usd == 0.0
        assert "Nothing was charged" in result.error
        assert result.data["resume_job"]["id"] == JOB_ID

    def test_request_error_is_mapped_with_hint(self, uberllm_env, fake_http):
        fake_http.add("POST", "/v1/video/generations", FakeResponse(402, {"error": {
            "message": "Your balance is too low.", "type": "billing_error", "code": "insufficient_balance"}}))
        result = UberLLMVideo().execute({"prompt": "x"})
        assert result.success is False
        assert "insufficient_balance" in result.error and "dashboard/credits" in result.error
        assert result.data["retryable"] is False


# ------------------------------------------------------------------
# Resume
# ------------------------------------------------------------------

class TestResume:
    def test_timeout_returns_resume_job(self, uberllm_env, fake_http, tmp_path):
        fake_http.add("POST", "/v1/video/generations", submitted())
        fake_http.add("GET", f"/v1/video/generations/{JOB_ID}", job("running"))
        job_path = tmp_path / "job.json"
        result = UberLLMVideo().execute({"prompt": "x", "poll_timeout": 0.01, "poll_interval": 0.005,
                                         "job_path": str(job_path)})
        assert result.success is False and result.data["retryable"] is True
        assert result.data["resume_job"]["id"] == JOB_ID
        assert json.loads(job_path.read_text())["id"] == JOB_ID
        assert "do not resubmit" in result.error

    def test_resume_polls_without_resubmitting(self, uberllm_env, fake_http, tmp_path):
        fake_http.add("GET", f"/v1/video/generations/{JOB_ID}", job("succeeded"))
        fake_http.add("GET", VIDEO_URL, FakeResponse(200, content=b"mp4"))
        resume = {"id": JOB_ID, "tool": "uberllm_video", "model": SEEDANCE_T2V, "operation": "text_to_video",
                  "request": {"model": SEEDANCE_T2V, "prompt": "x", "duration_seconds": 5}, "estimated_cost_usd": 0.76}
        result = UberLLMVideo().execute({"prompt": "x", "resume_job": resume, "output_path": str(tmp_path / "o.mp4")})
        assert result.success, result.error
        assert fake_http.by("POST", "/v1/video/generations") == []

    def test_foreign_resume_job_is_rejected(self, uberllm_env, fake_http):
        result = UberLLMVideo().execute({"prompt": "x", "resume_job": {"id": "abc", "tool": "pika_video"}})
        assert result.success is False and "does not belong" in result.error
        assert fake_http.calls == []


# ------------------------------------------------------------------
# Uploads and dry run
# ------------------------------------------------------------------

class TestUploadsAndDryRun:
    def test_local_first_frame_is_uploaded_to_uberllm(self, uberllm_env, fake_http, tmp_path):
        frame = tmp_path / "first.png"
        frame.write_bytes(b"\x89PNG\r\n\x1a\n")
        file_url = f"{BASE}/v1/files/file_3f9c/content"
        fake_http.add("POST", "/v1/files", {"id": "file_3f9c", "object": "file", "url": file_url})
        happy_path(fake_http, model=SEEDANCE_I2V)
        result = UberLLMVideo().execute({"prompt": "x", "reference_image_path": str(frame),
                                         "output_path": str(tmp_path / "o.mp4")})
        assert result.success, result.error
        assert fake_http.by("POST", "/v1/files")[0]["files"]["file"][0] == "first.png"
        assert fake_http.by("POST", "/v1/video/generations")[0]["json"]["image_url"] == file_url

    def test_missing_local_file_fails_before_submit(self, uberllm_env, fake_http):
        result = UberLLMVideo().execute({"prompt": "x", "reference_image_path": "/nonexistent/frame.png"})
        assert result.success is False and "not found" in result.error
        assert fake_http.calls == []

    def test_dry_run_quotes_without_submitting_or_storing(self, uberllm_env, fake_http, tmp_path):
        frame = tmp_path / "first.png"
        frame.write_bytes(b"\x89PNG")
        fake_http.add("POST", "/v1/video/generations", {"object": "quote", "valid": True, "cost_usd": 0.352,
                                                         "max_cost_usd": 0.704, "unit": "second", "units": 5})
        result = UberLLMVideo().execute({"prompt": "x", "reference_image_path": str(frame), "dry_run": True})
        assert result.success, result.error
        assert result.cost_usd == 0.0 and result.data["cost_status"] == "quoted"
        assert result.data["quoted_cost_usd"] == pytest.approx(0.352)
        sent = fake_http.by("POST", "/v1/video/generations")[0]["json"]
        assert sent["validate"] is True and sent["image_url"].startswith("data:image/png;base64,")
        assert result.data["request"]["image_url"] == "data:...(inline picture)"
        assert fake_http.by("POST", "/v1/files") == []


# ------------------------------------------------------------------
# Selector routing
# ------------------------------------------------------------------

class TestSelectorRouting:
    @pytest.fixture()
    def selector(self, uberllm_env):
        from tools.tool_registry import registry
        from tools.video.video_selector import VideoSelector

        registry.discover()
        return VideoSelector()

    @pytest.mark.parametrize("operation", ["text_to_video", "image_to_video", "reference_to_video"])
    def test_ranked_for_each_operation(self, selector, operation):
        inputs = {"prompt": "A product spins on a turntable", "operation": "rank", "target_operation": operation}
        if operation == "image_to_video":
            inputs["reference_image_url"] = "https://a/first.png"
        if operation == "reference_to_video":
            inputs["reference_image_urls"] = ["https://a/first.png"]
        result = selector.execute(inputs)
        assert result.success, result.error
        names = [r.get("tool") or r.get("tool_name") or r.get("name") for r in result.data["rankings"]]
        assert "uberllm_video" in names

    def test_explicit_route_by_tool_family_and_exact_model(self, selector):
        from tools.provider_routing import filter_explicit_route

        providers = selector._providers()
        by_tool = filter_explicit_route({"preferred_tool": "uberllm_video", "operation": "image_to_video"}, providers)
        assert [t.name for t in by_tool] == ["uberllm_video"]
        by_family = filter_explicit_route({"model": "wan-2.7", "hosting_provider": "uberllm",
                                           "operation": "reference_to_video"}, providers)
        assert [t.name for t in by_family] == ["uberllm_video"]
        by_id = filter_explicit_route({"model": VIDU_T2V, "operation": "text_to_video"}, providers)
        assert [t.name for t in by_id] == ["uberllm_video"]
        assert filter_explicit_route({"preferred_tool": "uberllm_video", "operation": "video_edit"}, providers) == []

    def test_selector_passes_local_frame_through_without_fal(self, selector, fake_http, tmp_path, monkeypatch):
        frame = tmp_path / "first.png"
        frame.write_bytes(b"\x89PNG")
        monkeypatch.delenv("FAL_KEY", raising=False)
        fake_http.add("POST", "/v1/files", {"id": "file_1", "url": f"{BASE}/v1/files/file_1/content"})
        happy_path(fake_http, model=SEEDANCE_I2V)
        result = selector.execute({"prompt": "the still comes alive", "operation": "image_to_video",
                                   "reference_image_path": str(frame), "preferred_tool": "uberllm_video",
                                   "output_path": str(tmp_path / "o.mp4")})
        assert result.success, result.error
        assert result.data["selected_tool"] == "uberllm_video"
        assert fake_http.by("POST", "/v1/video/generations")[0]["json"]["image_url"].endswith("/file_1/content")
