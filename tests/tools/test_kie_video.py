from pathlib import Path

from tools.base_tool import ToolStatus
from tools.video.kie_video import KieVideo


def test_kie_video_is_unavailable_without_api_key(monkeypatch):
    monkeypatch.delenv("KIE_API_KEY", raising=False)
    monkeypatch.delenv("KIE_AI_API_KEY", raising=False)

    assert KieVideo().get_status() == ToolStatus.UNAVAILABLE


def test_kie_video_builds_seedance_text_payload(monkeypatch):
    tool = KieVideo()

    payload = tool._build_create_payload(
        {
            "prompt": "small workshop, warm light",
            "operation": "text_to_video",
            "aspect_ratio": "9:16",
            "duration": "5",
            "resolution": "720p",
            "generate_audio": False,
        },
        "bytedance/seedance-2",
        "text_to_video",
        {
            "durations": [4, 5, 8, 10, 15],
            "default_duration": 5,
            "resolutions": ["480p", "720p", "1080p"],
            "default_resolution": "720p",
        },
        "test-key",
    )

    assert payload == {
        "model": "bytedance/seedance-2",
        "input": {
            "prompt": "small workshop, warm light",
            "duration": 5,
            "resolution": "720p",
            "aspect_ratio": "9:16",
            "generate_audio": False,
            "web_search": False,
            "nsfw_checker": False,
        },
    }


def test_kie_video_uploads_local_image_for_seedance_i2v(monkeypatch, tmp_path):
    image_path = tmp_path / "frame.png"
    image_path.write_bytes(b"fake-image")
    monkeypatch.setattr(KieVideo, "_upload_file", staticmethod(lambda api_key, path, upload_path="openmontage": "https://cdn.example/frame.png"))

    payload = KieVideo()._build_create_payload(
        {
            "prompt": "animate this frame gently",
            "operation": "image_to_video",
            "reference_image_path": str(image_path),
        },
        "bytedance/seedance-2",
        "image_to_video",
        {
            "durations": [4, 5, 8, 10, 15],
            "default_duration": 5,
            "resolutions": ["480p", "720p", "1080p"],
            "default_resolution": "720p",
        },
        "test-key",
    )

    assert payload["input"]["first_frame_url"] == "https://cdn.example/frame.png"


def test_kie_video_extracts_upload_file_url_from_documented_shape():
    assert KieVideo._extract_uploaded_file_url(
        {"code": 200, "data": {"fileUrl": "https://cdn.example/file.png"}}
    ) == "https://cdn.example/file.png"


def test_kie_video_extracts_upload_download_url_from_live_shape():
    assert KieVideo._extract_uploaded_file_url(
        {
            "success": True,
            "code": 200,
            "data": {
                "filePath": "kieai/11359937/openmontage/frame.png",
                "downloadUrl": "https://tempfile.redpandaai.co/kieai/11359937/openmontage/frame.png",
            },
        }
    ) == "https://tempfile.redpandaai.co/kieai/11359937/openmontage/frame.png"


def test_kie_video_resolves_kling_model_for_operation():
    assert KieVideo._resolve_model("kling/v3-turbo-text-to-video", "image_to_video") == "kling/v3-turbo-image-to-video"
    assert KieVideo._resolve_model("kling/v3-turbo-image-to-video", "text_to_video") == "kling/v3-turbo-text-to-video"
