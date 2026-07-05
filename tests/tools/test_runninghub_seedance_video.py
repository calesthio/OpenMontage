from pathlib import Path

from tools.base_tool import ToolStatus
from tools.video.seedance_replicate import SeedanceReplicate
from tools.video.seedance_video import SeedanceVideo
from tools.video.runninghub_seedance_video import RunningHubSeedanceVideo


class FakeResponse:
    def __init__(self, payload=None, content=b"", status_code=200):
        self._payload = payload
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_status_unavailable_without_api_key(monkeypatch):
    monkeypatch.delenv("RUNNINGHUB_API_KEY", raising=False)

    assert RunningHubSeedanceVideo().get_status() == ToolStatus.UNAVAILABLE


def test_submit_poll_and_download_maps_openmontage_inputs(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNNINGHUB_API_KEY", "test-key")
    calls = {"post": [], "get": []}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["post"].append(
            {"url": url, "headers": headers, "json": json, "timeout": timeout}
        )
        if url.endswith("/query"):
            return FakeResponse(
                {
                    "taskId": "task-1",
                    "status": "SUCCESS",
                    "errorCode": "",
                    "errorMessage": "",
                    "usage": {"consumeMoney": "0.25", "taskCostTime": "12"},
                    "results": [
                        {
                            "url": "https://example.com/result.mp4",
                            "nodeId": "2",
                            "outputType": "mp4",
                            "text": None,
                        }
                    ],
                }
            )
        return FakeResponse(
            {
                "taskId": "task-1",
                "status": "RUNNING",
                "errorCode": "",
                "errorMessage": "",
                "results": None,
            }
        )

    def fake_get(url, timeout=None):
        calls["get"].append({"url": url, "timeout": timeout})
        return FakeResponse(content=b"mp4 bytes")

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr("time.sleep", lambda _: None)

    output_path = tmp_path / "runninghub.mp4"
    result = RunningHubSeedanceVideo().execute(
        {
            "prompt": "竖屏短视频，城市夜景，镜头缓慢推进",
            "duration": "8",
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "generate_audio": False,
            "image_url": "https://example.com/ref.png",
            "seed": 123,
            "output_path": str(output_path),
        }
    )

    assert result.success, result.error
    assert output_path.read_bytes() == b"mp4 bytes"
    assert result.data["provider"] == "runninghub"
    assert result.data["task_id"] == "task-1"
    assert result.data["output_path"] == str(output_path)
    assert result.cost_usd == 0.25

    submit = calls["post"][0]
    assert submit["url"].endswith(
        "/openapi/v2/rhart-video/sparkvideo-2.0-mini/multimodal-video"
    )
    assert submit["headers"]["Authorization"] == "Bearer test-key"
    assert submit["json"]["prompt"] == "竖屏短视频，城市夜景，镜头缓慢推进"
    assert submit["json"]["duration"] == "8"
    assert submit["json"]["ratio"] == "9:16"
    assert submit["json"]["resolution"] == "720p"
    assert submit["json"]["generateAudio"] is False
    assert submit["json"]["imageUrls"] == ["https://example.com/ref.png"]
    assert submit["json"]["seed"] == 123
    assert calls["get"][0]["url"] == "https://example.com/result.mp4"


def test_failed_task_returns_structured_error(monkeypatch):
    monkeypatch.setenv("RUNNINGHUB_API_KEY", "test-key")

    def fake_post(url, headers=None, json=None, timeout=None):
        if url.endswith("/query"):
            return FakeResponse(
                {
                    "taskId": "task-1",
                    "status": "FAILED",
                    "errorCode": "bad_prompt",
                    "errorMessage": "Prompt rejected",
                    "failedReason": {"node": "reason"},
                    "results": [],
                }
            )
        return FakeResponse({"taskId": "task-1", "status": "RUNNING"})

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("time.sleep", lambda _: None)

    result = RunningHubSeedanceVideo().execute({"prompt": "bad prompt"})

    assert not result.success
    assert "Prompt rejected" in result.error


def test_runninghub_seedance_defaults_to_15s_and_480p(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNNINGHUB_API_KEY", "test-key")
    calls = {"post": [], "get": []}

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["post"].append({"url": url, "json": json})
        if url.endswith("/query"):
            return FakeResponse(
                {
                    "taskId": "task-1",
                    "status": "SUCCESS",
                    "results": [{"url": "https://example.com/result.mp4"}],
                }
            )
        return FakeResponse({"taskId": "task-1", "status": "RUNNING"})

    def fake_get(url, timeout=None):
        calls["get"].append({"url": url})
        return FakeResponse(content=b"mp4 bytes")

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr("time.sleep", lambda _: None)

    result = RunningHubSeedanceVideo().execute(
        {
            "prompt": "默认参数测试",
            "output_path": str(tmp_path / "default.mp4"),
        }
    )

    assert result.success, result.error
    assert calls["post"][0]["json"]["duration"] == "15"
    assert calls["post"][0]["json"]["resolution"] == "480p"
    assert result.data["duration"] == "15"
    assert result.data["resolution"] == "480p"


def test_runninghub_seedance_rejects_duration_over_15s(monkeypatch):
    monkeypatch.setenv("RUNNINGHUB_API_KEY", "test-key")

    result = RunningHubSeedanceVideo().execute(
        {"prompt": "时长错误", "duration": "16"}
    )

    assert not result.success
    assert "between 4s and 15s" in result.error


def test_runninghub_seedance_rejects_unsupported_resolution(monkeypatch):
    monkeypatch.setenv("RUNNINGHUB_API_KEY", "test-key")

    result = RunningHubSeedanceVideo().execute(
        {"prompt": "分辨率错误", "resolution": "1080p"}
    )

    assert not result.success
    assert "480p or 720p" in result.error


def test_runninghub_seedance_rejects_batch_over_5(monkeypatch):
    monkeypatch.setenv("RUNNINGHUB_API_KEY", "test-key")

    result = RunningHubSeedanceVideo().execute(
        {"prompt": "批量错误", "batch_size": 6}
    )

    assert not result.success
    assert "at most 5" in result.error


def test_seedance_provider_schemas_share_product_constraints():
    expected_durations = [str(seconds) for seconds in range(4, 16)]
    for tool in [RunningHubSeedanceVideo(), SeedanceVideo(), SeedanceReplicate()]:
        props = tool.input_schema["properties"]
        assert props["duration"]["enum"] == expected_durations
        assert props["duration"]["default"] == "15"
        assert props["resolution"]["enum"] == ["480p", "720p"]
        assert props["resolution"]["default"] == "480p"
        assert props["batch_size"]["default"] == 1
        assert props["batch_size"]["maximum"] == 5
