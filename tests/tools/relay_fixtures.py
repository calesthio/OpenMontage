"""Shared fixtures for relay provider tests: mock relay + a config pointing at it."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from tools.relay.mock_server import MockRelay

TEST_KEY = "mock-relay-key-1234567890"
OTHER_KEY = "mock-ark-key-0987654321"


def mock_config_yaml(url: str, *, policy: str = "relay_only", live: bool = False) -> str:
    """Two relays on the same loopback server: one OpenAI-style, one Ark + custom."""
    return textwrap.dedent(
        f"""
        version: 1
        routing:
          paid_provider_policy: {policy}
        relays:
          mockrelay:
            base_url: {url}
            api_key_env: MOCKRELAY_API_KEY
            live: {str(live).lower()}
            models:
              - name: gpt-image-2
                model: gpt-image-2
                protocol: openai_images
                capabilities: [text_to_image, image_to_image]
                image_input: multipart
                defaults: {{size: "1024x1024"}}
                pricing: {{per_image: 0.04}}
              - name: edit-only
                model: edit-only-image
                protocol: openai_images
                capabilities: [image_to_image]
                image_input: multipart
                pricing: {{per_image: 0.02}}
              - name: sora-2
                model: sora-2
                protocol: openai_videos
                capabilities: [text_to_video, image_to_video]
                image_input: multipart
                limits: {{durations: [4, 8, 12], size_map: {{"16:9": "1280x720", "9:16": "720x1280"}}}}
                defaults: {{duration: 4, aspect_ratio: "16:9"}}
                pricing: {{per_second: 0.1}}
                poll: {{interval_seconds: 0.01, timeout_seconds: 5}}
              - name: kling
                model: kling-v2
                protocol: openai_video_generations
                capabilities: [text_to_video, image_to_video]
                image_input: data_uri
                limits: {{durations: [5, 10], aspect_ratios: ["16:9", "9:16"]}}
                defaults: {{duration: 5, aspect_ratio: "16:9", resolution: 720p}}
                pricing: {{currency: CNY, per_request: 3.6, cny_per_usd: 7.2}}
                poll: {{interval_seconds: 0.01, timeout_seconds: 5}}
              - name: t2v-only
                model: veo-3-fast
                protocol: openai_video_generations
                capabilities: [text_to_video]
                defaults: {{duration: 8, size: "1280x720"}}
                pricing: {{per_request: 0.5}}
                poll: {{interval_seconds: 0.01, timeout_seconds: 5}}
              - name: unpriced
                model: mystery-video
                protocol: openai_video_generations
                capabilities: [text_to_video]
                poll: {{interval_seconds: 0.01, timeout_seconds: 5}}
              - name: tts
                model: tts-1
                protocol: openai_speech
                capabilities: [text_to_speech]
                limits: {{max_chars: 500, voices: [alloy, nova]}}
                defaults: {{voice: alloy, output_format: wav}}
                pricing: {{per_1k_chars: 0.015}}
          arkmock:
            base_url: {url}
            api_key_env: ARKMOCK_API_KEY
            live: {str(live).lower()}
            models:
              - name: seedance
                model: doubao-seedance-2-0-260128
                protocol: ark_seedance
                capabilities: [text_to_video, image_to_video, first_last_frame]
                defaults: {{resolution: 480p, aspect_ratio: "16:9", duration: 5}}
                pricing: {{currency: CNY, per_second: 1.0}}
                poll: {{interval_seconds: 0.01, timeout_seconds: 5}}
                agent_skills: [seedance-2-0]
              - name: custom-i2v
                model: wan-i2v
                protocol: generic_async
                kind: video
                capabilities: [image_to_video]
                image_input: base64
                api_root: ""
                limits: {{durations: [5]}}
                defaults: {{duration: 5}}
                pricing: {{per_second: 0.05}}
                poll: {{interval_seconds: 0.01, timeout_seconds: 5}}
                request:
                  submit:
                    path: /custom/api/submit
                    body:
                      model: "{{{{model}}}}"
                      input: {{prompt: "{{{{prompt}}}}", first_frame_image: "{{{{first_frame}}}}"}}
                      parameters: {{duration: "{{{{duration}}}}", seed: "{{{{seed}}}}"}}
                  response: {{task_id: "data.task_id"}}
                  poll:
                    path: /custom/api/task/{{task_id}}
                    status: data.state
                    success: [SUCCESS]
                    failure: [FAILED]
                    error: data.fail_msg
                    result_url: data.result.url
        """
    )


@pytest.fixture
def mock_relay():
    relay = MockRelay(expected_key=None).start()
    try:
        yield relay
    finally:
        relay.stop()


@pytest.fixture
def relay_env(mock_relay, tmp_path, monkeypatch):
    """Point OpenMontage at a mock-relay config and a fresh registry."""
    from tools.tool_registry import registry

    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.delenv("OPENMONTAGE_PAID_PROVIDER_POLICY", raising=False)
    config = tmp_path / "relay_providers.yaml"
    config.write_text(mock_config_yaml(mock_relay.url), encoding="utf-8")
    monkeypatch.setenv("OPENMONTAGE_RELAY_CONFIG", str(config))
    monkeypatch.setenv("MOCKRELAY_API_KEY", TEST_KEY)
    monkeypatch.setenv("ARKMOCK_API_KEY", OTHER_KEY)
    registry.clear()
    registry.discover()
    try:
        yield {"relay": mock_relay, "config": config, "registry": registry, "tmp": tmp_path}
    finally:
        registry.clear()


def rewrite_config(env, **kwargs) -> None:
    from tools.tool_registry import registry

    env["config"].write_text(mock_config_yaml(env["relay"].url, **kwargs), encoding="utf-8")
    import os
    import time

    # make sure mtime changes even on coarse filesystems
    stamp = time.time() + 2
    os.utime(env["config"], (stamp, stamp))
    registry.clear()
    registry.discover()


def write_png(path: Path, color=(10, 200, 90), size=(64, 36)) -> Path:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path)
    return path
