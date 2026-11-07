"""Offline end-to-end coverage for the product scene workflow."""

from __future__ import annotations

import base64
import io
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from lib.checkpoint import init_project
from schemas.artifacts import validate_artifact
from tools.audio.pixabay_music import PixabayMusic
from tools.graphics.seedream_ark_image import SeedreamArkImage
from tools.video.seedance_ark import SeedanceArkVideo
from tools.video.video_compose import VideoCompose


class _Response:
    def __init__(self, payload=None, *, content: bytes = b"", status_code: int = 200):
        self._payload = payload or {}
        self.content = content
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _UrlResponse(_Response):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.content


def _png_bytes() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (640, 640), "white").save(stream, format="PNG")
    return stream.getvalue()


def _ffmpeg(*args: str) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg is required for the offline end-to-end test")
    subprocess.run(
        [ffmpeg, "-y", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _copy_variants() -> dict:
    return {
        "grassroots": {
            "title": "日常护理的精致一步",
            "subtitle": "轻盈使用感，融入日常生活",
            "highlights": ["质地清爽", "包装简洁", "适合日常护理"],
            "social_copy": "认真照顾自己，从日常的小仪式开始。",
        },
        "premium": {
            "title": "恰到好处的精致",
            "subtitle": "简洁设计融入现代生活",
            "highlights": ["视觉简洁", "细节克制", "使用体验自然"],
            "social_copy": "高级感来自恰到好处的细节。",
        },
        "conversion": {
            "title": "了解这款日常护理产品",
            "subtitle": "查看卖点、使用方式与适用场景",
            "highlights": ["产品信息清晰", "使用步骤简单", "适合日常护理", "购买前可确认规格"],
            "social_copy": "想升级日常护理流程，可以先了解这款产品。",
        },
    }


def test_product_scene_workflow_runs_offline(monkeypatch, tmp_path):
    project = init_project(
        "product-scene-e2e",
        title="产品场景离线验收",
        pipeline_type="seedance-product-scene",
        pipeline_dir=tmp_path,
    )
    (project / "assets/input").mkdir(parents=True, exist_ok=True)
    product_image = project / "assets/input/product.png"
    product_image.write_bytes(_png_bytes())

    config_path = tmp_path / "seedance-config.json"
    config_path.write_text(
        json.dumps(
            {
                "api_key": "ark-offline-e2e-key",
                "api_base": "https://ark.example.test/api/v3",
                "image_model": "doubao-seedream-test",
                "video_model": "doubao-seedance-2-5-260628",
                "default_duration": 8,
                "default_ratio": "9:16",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SEEDANCE_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("ARK_API_KEY", "ark-offline-e2e-key")

    source_video = tmp_path / "source.mp4"
    _ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=180x320:d=1",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(source_video),
    )
    source_audio = tmp_path / "source.mp3"
    _ffmpeg(
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=1",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "64k",
        str(source_audio),
    )

    image_b64 = base64.b64encode(_png_bytes()).decode("ascii")
    posts = []

    def fake_post(url, *, headers, json, timeout):
        posts.append((url, json))
        if url.endswith("/images/generations"):
            return _Response({"data": [{"b64_json": image_b64}]})
        if url.endswith("/contents/generations/tasks"):
            return _Response({"id": "cgt-offline-e2e"})
        raise AssertionError(f"unexpected POST {url}")

    def fake_get(url, *, headers=None, timeout):
        if url.endswith("/cgt-offline-e2e"):
            return _Response(
                {
                    "id": "cgt-offline-e2e",
                    "model": "doubao-seedance-2-5-260628",
                    "status": "succeeded",
                    "content": {"video_url": "https://ark.example.test/result.mp4"},
                    "usage": {"completion_tokens": 1000},
                }
            )
        if url == "https://ark.example.test/result.mp4":
            return _Response(content=source_video.read_bytes())
        raise AssertionError(f"unexpected GET {url}")

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("requests.get", fake_get)

    image_tool = SeedreamArkImage()
    preview = image_tool.execute(
        {
            "prompt": "轻奢产品场景，保持产品主体不变",
            "source_image_path": str(product_image),
            "scene_preset": "luxury",
            "product_name": "精华液",
            "count": 1,
            "output_dir": str(project / "assets/images/previews/luxury"),
        }
    )
    assert preview.success, preview.error
    selected_style = "luxury"

    images = image_tool.execute(
        {
            "prompt": "三段式轻奢产品场景，保持产品主体不变",
            "source_image_path": str(product_image),
            "scene_preset": selected_style,
            "product_name": "精华液",
            "count": 3,
            "output_dir": str(project / "assets/images/luxury"),
        }
    )
    assert images.success, images.error
    selected_image = Path(images.data["outputs"][1])

    video_output = project / "assets/video/luxury/seedance-source.mp4"
    video_result = SeedanceArkVideo().execute(
        {
            "operation": "image_to_video",
            "reference_image_path": str(selected_image),
            "prompt": "三段式产品广告，保持产品主体不变",
            "model_variant": "2.5",
            "custom_price_cny_per_million_tokens": 1,
            "duration": 8,
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "generate_audio": False,
            "output_path": str(video_output),
            "poll_interval_seconds": 0,
        }
    )
    assert video_result.success, video_result.error
    video_payload = next(payload for url, payload in posts if url.endswith("/tasks"))
    assert video_payload["duration"] == 8
    assert video_payload["ratio"] == "9:16"
    assert video_payload["generate_audio"] is False

    product_copy = {
        "version": "1.0",
        "product_name": "精华液",
        "generation_source": "codex_active_session",
        "assumptions": [],
        "styles": [{"style": "luxury", "variants": _copy_variants()}],
    }
    validate_artifact("product_copy", product_copy)
    copy_path = project / "artifacts/product_copy.json"
    copy_path.write_text(json.dumps(product_copy, ensure_ascii=False, indent=2), encoding="utf-8")

    music_tool = PixabayMusic()
    candidates = [
        {
            "title": name,
            "artist": artist,
            "duration": 1,
            "audio_url": f"https://cdn.pixabay.com/audio/{index}.mp3",
            "pixabay_id": index,
        }
        for index, (name, artist) in enumerate(
            [
                ("Quiet Product Reveal", "Artist One"),
                ("Soft Luxury Motion", "Artist Two"),
                ("Elegant Brand Bed", "Artist Three"),
            ],
            start=1,
        )
    ]
    monkeypatch.setattr(music_tool, "_search", lambda inputs: candidates)
    music_search = music_tool.execute(
        {
            "query": "elegant luxury product commercial",
            "operation": "search",
            "max_results": 3,
            "output_path": str(project / "assets/music/luxury/candidates"),
        }
    )
    assert music_search.success, music_search.error
    assert len(music_search.data["candidates"]) == 3
    assert not (project / "assets/music/luxury/candidates").exists()
    selected_music = music_search.data["candidates"][1]
    monkeypatch.setattr(
        "tools.audio.pixabay_music.urllib.request.urlopen",
        lambda *args, **kwargs: _UrlResponse(content=source_audio.read_bytes()),
    )
    music_path = project / "assets/music/luxury/selected.mp3"
    music_download = music_tool.execute(
        {
            "query": "elegant luxury product commercial",
            "operation": "download",
            "candidate_index": selected_music["index"],
            "download_url": selected_music["download_url"],
            "title": selected_music["title"],
            "artist": selected_music["artist"],
            "duration_seconds": selected_music["duration_seconds"],
            "output_path": str(music_path),
        }
    )
    assert music_download.success, music_download.error

    final_video = project / "renders/luxury/final.mp4"
    compose = VideoCompose().execute(
        {
            "operation": "compose",
            "output_path": str(final_video),
            "audio_path": str(music_path),
            "edit_decisions": {
                "version": "1.0",
                "cuts": [
                    {
                        "source": str(video_output),
                        "in_seconds": 0,
                        "out_seconds": 1,
                    }
                ],
                "metadata": {
                    "compose_target": {
                        "width": 180,
                        "height": 320,
                        "fit": "cover",
                    }
                },
            },
        }
    )
    assert compose.success, compose.error
    assert final_video.is_file()

    delivery = {
        "version": "1.0",
        "product_name": "精华液",
        "selected_styles": [selected_style],
        "packages": [
            {
                "style": selected_style,
                "images": [
                    {
                        "path": path.relative_to(project).as_posix(),
                        "candidate_index": index,
                        "approved": path == selected_image,
                    }
                    for index, path in enumerate(map(Path, images.data["outputs"]), start=1)
                ],
                "selected_image": {
                    "path": selected_image.relative_to(project).as_posix(),
                    "candidate_index": 2,
                    "approved": True,
                },
                "video": {
                    "path": video_output.relative_to(project).as_posix(),
                    "task_id": "cgt-offline-e2e",
                    "model": "doubao-seedance-2-5-260628",
                    "duration_seconds": 1,
                    "ratio": "9:16",
                    "resolution": "720p",
                    "approved": True,
                },
                "music": {
                    "path": music_path.relative_to(project).as_posix(),
                    "title": selected_music["title"],
                    "artist": selected_music["artist"],
                    "license": selected_music["license"],
                    "approved": True,
                },
                "music_candidates": music_search.data["candidates"],
                "copy": {
                    "path": copy_path.relative_to(project).as_posix(),
                    "style": selected_style,
                },
                "output": {
                    "video_path": final_video.relative_to(project).as_posix(),
                    "copy_path": copy_path.relative_to(project).as_posix(),
                },
            }
        ],
        "approvals": {
            "proposal": True,
            "style_selection": True,
            "images": True,
            "videos": True,
            "copy": True,
            "music": True,
            "delivery": False,
        },
        "total_estimated_cost_usd": None,
    }
    validate_artifact("product_delivery", delivery)
    delivery_path = project / "artifacts/product_delivery.json"
    delivery_path.write_text(json.dumps(delivery, ensure_ascii=False, indent=2), encoding="utf-8")

    assert all((project / package["output"]["video_path"]).is_file() for package in delivery["packages"])
    assert delivery_path.is_file()
    assert all(url.startswith("https://ark.example.test/") for url, _ in posts)
