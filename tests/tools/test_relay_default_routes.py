"""Channel defaults must not bill a different relay or change another media kind."""
from types import SimpleNamespace

import pytest
import yaml

from tools.base_tool import ToolRuntime, ToolStatus
from tools.provider_routing import filter_explicit_route, no_provider_message
from tools.relay.config import RelayConfigError, RoutingPolicy, parse_relay_config


class Provider:
    runtime = ToolRuntime.API
    is_relay_tool = True

    def __init__(self, name, host, kind="video", model="grok"):
        self.name, self.provider, self.hosting_provider = name, host, host
        self.capability = {"video": "video_generation", "image": "image_generation"}[kind]
        self.input_schema = {"properties": {"model": {"enum": [model]}}}

    def get_info(self):
        return {}

    def get_status(self):
        return ToolStatus.AVAILABLE


@pytest.fixture
def channels(monkeypatch):
    cfg = SimpleNamespace(routing=RoutingPolicy("relay_only", {"image": "tokenshop_image", "video": "chiyi_video"}))
    monkeypatch.setattr("tools.relay.config.try_load_relay_config", lambda: cfg)
    return cfg, Provider("tokenshop_video", "tokenshop"), Provider("chiyi_video", "chiyi")


def test_model_name_does_not_escape_default_channel(channels):
    _, old, new = channels
    assert filter_explicit_route({"model": "grok"}, [old, new]) == [new]


def test_image_and_video_defaults_are_independent(channels):
    _, old, new = channels
    image = Provider("tokenshop_image", "tokenshop", "image", "gpt-image")
    assert filter_explicit_route({}, [old, new]) == [new]
    assert filter_explicit_route({}, [image]) == [image]


@pytest.mark.parametrize("route", [{"preferred_tool": "tokenshop_video"}, {"hosting_provider": "tokenshop"}])
def test_explicit_project_route_overrides_new_default(channels, route):
    _, old, new = channels
    assert filter_explicit_route(route, [old, new]) == [old]


def test_other_model_stays_on_default_channel(channels):
    _, old, new = channels
    other = Provider("chiyi_other", "chiyi", model="other")
    competitor = Provider("tokenshop_other", "tokenshop", model="other")
    assert filter_explicit_route({"model": "other"}, [old, new, other, competitor]) == [other]


def test_missing_default_never_falls_back_to_billable_alternative(channels):
    _, old, _ = channels
    assert filter_explicit_route({}, [old]) == []
    assert filter_explicit_route({"model": "grok"}, [old]) == []
    assert "no automatic channel fallback" in no_provider_message("Unavailable.", {}, [old])


def config():
    def relay(model, protocol, caps):
        return {"base_url": "https://example.org", "api_key_env": "EXAMPLE_KEY", "models": [{"model": model, "protocol": protocol, "capabilities": caps}]}
    return {"routing": {"default_tools": {"image": "relay_img_gpt", "video": "relay_new_grok"}}, "relays": {
        "img": relay("gpt", "openai_images", ["text_to_image"]),
        "old": relay("grok", "openai_videos", ["text_to_video"]),
        "new": relay("grok", "openai_videos", ["text_to_video"]),
    }}


def test_mismatched_default_is_a_configuration_error():
    data = config()
    data["routing"]["default_tools"]["video"] = "relay_img_gpt"
    assert "configured video tool" in parse_relay_config(data).errors[0]


@pytest.mark.parametrize("value", ["video", {"bad_kind": "x"}, {"video": 12}])
def test_malformed_defaults_fail_before_routing(value):
    data = config()
    data["routing"]["default_tools"] = value
    with pytest.raises(RelayConfigError):
        parse_relay_config(data)


def test_switch_back_and_forth_preserves_image_provider_and_history(tmp_path, monkeypatch, capsys):
    from tools.relay.__main__ import main

    path = tmp_path / "relays.yaml"
    path.write_text(yaml.safe_dump(config()), encoding="utf-8")
    job = tmp_path / "old-job.json"
    job.write_text('{"tool":"relay_old_grok","task_id":"original-task"}', encoding="utf-8")
    original_job = job.read_bytes()
    monkeypatch.setenv("OPENMONTAGE_RELAY_CONFIG", str(path))
    for name in ("relay_old_grok", "relay_new_grok"):
        assert main(["route", "--kind", "video", "--tool", name]) == 0
        updated = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert updated["routing"]["default_tools"] == {"image": "relay_img_gpt", "video": name}
        assert len(updated["relays"]) == 3
        assert job.read_bytes() == original_job
    assert "original-task" not in capsys.readouterr().out


def test_invalid_switch_does_not_change_configuration(tmp_path, monkeypatch):
    from tools.relay.__main__ import main

    path = tmp_path / "relays.yaml"
    path.write_text(yaml.safe_dump(config()), encoding="utf-8")
    original = path.read_bytes()
    monkeypatch.setenv("OPENMONTAGE_RELAY_CONFIG", str(path))
    assert main(["route", "--kind", "video", "--tool", "relay_img_gpt"]) == 1
    assert path.read_bytes() == original
