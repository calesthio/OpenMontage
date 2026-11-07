"""Contract tests for the local Seedance configuration bridge."""

from __future__ import annotations

import json

import pytest

from lib.seedance_config import (
    DEFAULT_API_BASE,
    DEFAULT_IMAGE_MODEL,
    DEFAULT_VIDEO_MODEL,
    SeedanceConfigError,
    load_seedance_config,
    mask_api_key,
)


def _write_config(path, **overrides):
    config = {
        "api_key": "ark-file-key",
        "api_base": "https://ark.example.test/api/v3",
        "image_model": "image-from-file",
        "video_model": "video-from-file",
        "default_duration": 10,
        "default_ratio": "1:1",
    }
    config.update(overrides)
    path.write_text(json.dumps(config), encoding="utf-8")
    return config


def test_environment_key_overrides_config_file(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    _write_config(config_file)
    monkeypatch.setenv("ARK_API_KEY", "ark-env-key")

    assert load_seedance_config(config_file).api_key == "ark-env-key"


def test_config_file_supplies_models_without_environment_overrides(
    tmp_path, monkeypatch
):
    config_file = tmp_path / "config.json"
    _write_config(config_file)
    for name in (
        "ARK_API_KEY",
        "ARK_BASE_URL",
        "ARK_SEEDREAM_MODEL",
        "ARK_SEEDANCE_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)

    config = load_seedance_config(config_file)

    assert config.api_key == "ark-file-key"
    assert config.api_base == "https://ark.example.test/api/v3"
    assert config.image_model == "image-from-file"
    assert config.video_model == "video-from-file"
    assert config.default_duration == 10
    assert config.default_ratio == "1:1"
    assert config.source == str(config_file)


def test_environment_overrides_all_model_settings(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    _write_config(config_file)
    monkeypatch.setenv("ARK_BASE_URL", "https://ark-env.example.test/api/v3")
    monkeypatch.setenv("ARK_SEEDREAM_MODEL", "image-from-env")
    monkeypatch.setenv("ARK_SEEDANCE_MODEL", "video-from-env")

    config = load_seedance_config(config_file)

    assert config.api_base == "https://ark-env.example.test/api/v3"
    assert config.image_model == "image-from-env"
    assert config.video_model == "video-from-env"


def test_config_path_environment_variable_is_used(tmp_path, monkeypatch):
    config_file = tmp_path / "custom-config.json"
    _write_config(config_file)
    monkeypatch.setenv("SEEDANCE_CONFIG_PATH", str(config_file))
    monkeypatch.delenv("ARK_API_KEY", raising=False)

    assert load_seedance_config().api_key == "ark-file-key"


def test_missing_key_raises_beginner_readable_error(tmp_path, monkeypatch):
    monkeypatch.delenv("ARK_API_KEY", raising=False)

    with pytest.raises(SeedanceConfigError, match="火山方舟"):
        load_seedance_config(tmp_path / "missing.json")


def test_invalid_json_does_not_echo_secret(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    config_file.write_text('{"api_key": "ark-super-secret",}', encoding="utf-8")
    monkeypatch.delenv("ARK_API_KEY", raising=False)

    with pytest.raises(SeedanceConfigError) as caught:
        load_seedance_config(config_file)

    assert "ark-super-secret" not in str(caught.value)
    assert "JSON" in str(caught.value)


def test_invalid_duration_is_rejected_without_echoing_key(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    _write_config(config_file, api_key="ark-private-value", default_duration=0)
    monkeypatch.delenv("ARK_API_KEY", raising=False)

    with pytest.raises(SeedanceConfigError) as caught:
        load_seedance_config(config_file)

    assert "default_duration" in str(caught.value)
    assert "ark-private-value" not in str(caught.value)


def test_plain_http_api_base_is_rejected(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    _write_config(
        config_file,
        api_key="ark-private-value",
        api_base="http://ark.example.test/api/v3",
    )
    monkeypatch.delenv("ARK_API_KEY", raising=False)

    with pytest.raises(SeedanceConfigError, match="https"):
        load_seedance_config(config_file)


def test_defaults_apply_when_optional_model_fields_are_absent(
    tmp_path, monkeypatch
):
    config_file = tmp_path / "config.json"
    config_file.write_text('{"api_key": "ark-file-key"}', encoding="utf-8")
    for name in (
        "ARK_API_KEY",
        "ARK_BASE_URL",
        "ARK_SEEDREAM_MODEL",
        "ARK_SEEDANCE_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)

    config = load_seedance_config(config_file)

    assert config.api_base == DEFAULT_API_BASE
    assert config.image_model == DEFAULT_IMAGE_MODEL
    assert config.video_model == DEFAULT_VIDEO_MODEL
    assert config.default_duration == 8
    assert config.default_ratio == "9:16"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("ark-1234567890abcdef", "ark-...cdef"),
        ("short", "***"),
        ("", "***"),
    ],
)
def test_mask_api_key_never_returns_full_secret(value, expected):
    assert mask_api_key(value) == expected
    if value:
        assert mask_api_key(value) != value
