"""Offline checks for the Magnific tool family.

Everything here runs without a network call or an API key: endpoint-table
consistency, input normalization, the poll loop's timing contract, and the
guards that reject a request before it costs credits.

Schema-default agreement is covered for magnific_video/magnific_image by the
shared regression suite in `test_provider_model_defaults.py`.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

import tools._magnific as mag
import tools.graphics.magnific_image as magnific_image
import tools.video.magnific_video as magnific_video
from tools.audio.magnific_audio import (
    MagnificAudioIsolation,
    MagnificMusic,
    MagnificSoundEffects,
)
from tools.enhancement.magnific_upscale import MagnificUpscale
from tools.graphics.magnific_image import MagnificImage
from tools.video.magnific_video import MagnificVideo

ALL_TOOLS = [
    MagnificUpscale,
    MagnificVideo,
    MagnificImage,
    MagnificMusic,
    MagnificSoundEffects,
    MagnificAudioIsolation,
]


@pytest.mark.parametrize("tool_cls", ALL_TOOLS)
def test_required_inputs_are_declared_properties(tool_cls):
    schema = tool_cls().input_schema
    props = schema.get("properties", {})
    for field in schema.get("required", []):
        assert field in props, f"{tool_cls.name}: required field {field!r} has no schema entry"


@pytest.mark.parametrize("tool_cls", ALL_TOOLS)
def test_output_path_default_is_declared(tool_cls):
    # MagnificTool.default_output() reads this at runtime, so a missing default
    # would only surface as a KeyError mid-generation, after credits were spent.
    assert tool_cls().default_output()


@pytest.mark.parametrize(
    "module, tool_cls",
    [(magnific_video, MagnificVideo), (magnific_image, MagnificImage)],
)
def test_model_enum_matches_the_model_table(module, tool_cls):
    # execute() resolves endpoints through _MODELS; an enum entry with no table
    # row would fail only at call time.
    assert set(tool_cls().input_schema["properties"]["model"]["enum"]) == set(module._MODELS)


def test_video_model_table_entries_are_complete():
    for name, spec in magnific_video._MODELS.items():
        endpoints = [spec.endpoint("text_to_video"), spec.endpoint("image_to_video")]
        assert any(endpoints), f"{name} supports neither operation"
        for endpoint in filter(None, endpoints):
            assert endpoint.startswith("/v1/ai/"), f"{name} endpoint is not an API path"
        if spec.status is not None:
            assert spec.status.startswith("/v1/ai/")
        assert spec.cost > 0 and spec.runtime > 0


def test_image_model_table_entries_are_complete():
    for name, spec in magnific_image._MODELS.items():
        assert spec.path.startswith("/v1/ai/"), f"{name} path is not an API path"
        assert spec.cost > 0 and spec.runtime > 0


def test_video_rejects_an_operation_the_model_cannot_do():
    tool = MagnificVideo()
    # pixverse_v6 is text-to-video only in the endpoint catalog.
    with pytest.raises(ValueError, match="does not support"):
        tool._resolve({"prompt": "x", "model": "pixverse_v6", "operation": "image_to_video"})
    # hailuo is image-to-video only.
    with pytest.raises(ValueError, match="does not support"):
        tool._resolve({"prompt": "x", "model": "minimax_hailuo_2_3_1080p"})


def test_video_infers_operation_and_endpoint():
    tool = MagnificVideo()
    _, _, op, endpoint = tool._resolve({"prompt": "x"})
    assert op == "text_to_video"
    assert endpoint == "/v1/ai/video/seedance-2-pro-1080p"

    _, spec, op, endpoint = tool._resolve({"prompt": "x", "image": "https://example.com/a.png"})
    assert op == "image_to_video"
    # Seedance serves both operations from one endpoint but polls a shared path.
    assert spec.status_for(endpoint) == "/v1/ai/video/seedance-2-pro"

    _, _, _, endpoint = tool._resolve({"prompt": "x", "model": "veo_3_1", "image": "https://e.com/a.png"})
    assert endpoint == "/v1/ai/image-to-video/veo-3-1"


def test_video_cost_and_runtime_scale_with_duration():
    tool = MagnificVideo()
    base = tool.estimate_cost({"model": "seedance_2_pro_1080p", "duration": 5})
    assert tool.estimate_cost({"model": "seedance_2_pro_1080p", "duration": 10}) == pytest.approx(base * 2)
    assert tool.estimate_runtime({"model": "seedance_2_pro_1080p", "duration": 10}) > tool.estimate_runtime({})


def test_image_4k_costs_more_only_for_mystic():
    tool = MagnificImage()
    assert tool.estimate_cost({"resolution": "4k"}) > tool.estimate_cost({"resolution": "2k"})
    # `resolution` is a Mystic-only body field. Scaling other models by it quoted
    # — and reserved budget for — 2x a request that never changed.
    flux = {"model": "flux_2_turbo"}
    assert tool.estimate_cost({**flux, "resolution": "4k"}) == tool.estimate_cost(flux)
    assert tool.estimate_runtime({**flux, "resolution": "4k"}) == tool.estimate_runtime(flux)


def test_image_rejects_references_the_model_would_ignore():
    # Silently dropping the reference still costs credits, so fail before paying.
    result = MagnificImage().execute(
        {"prompt": "x", "model": "flux_2_turbo", "style_reference": "https://e.com/a.png"}
    )
    assert result.success is False
    assert "style_reference" in result.error and "mystic" in result.error


def test_isolation_requires_exactly_one_media_input():
    tool = MagnificAudioIsolation()
    both = tool.execute({"description": "speech", "audio": "a.wav", "video": "v.mp4"})
    neither = tool.execute({"description": "speech"})
    for result in (both, neither):
        assert result.success is False
        assert "exactly one" in result.error


def test_isolation_refuses_to_inline_an_oversized_local_file(tmp_path):
    big = tmp_path / "big.wav"
    big.write_bytes(b"\0" * (mag.MAX_INLINE_BYTES + 1))
    result = MagnificAudioIsolation().execute({"description": "speech", "audio": str(big)})
    assert result.success is False
    assert "too large" in result.error


def test_as_input_passes_urls_through_and_encodes_files(tmp_path):
    import base64

    url = "https://example.com/a.png"
    assert mag.as_input(url) == url, "a URL must not be re-encoded — the docs warn it loses quality"

    f = tmp_path / "a.png"
    f.write_bytes(b"binary-bytes")
    assert base64.b64decode(mag.as_input(str(f))) == b"binary-bytes"

    assert mag.as_input("data:image/png;base64,QUJD") == "QUJD"


def test_as_input_size_guard_applies_to_every_local_file(tmp_path):
    # The guard lives in the shared client so all six tools inherit it, not just
    # audio isolation (upscale sources and video reference frames are large too).
    big = tmp_path / "big.png"
    big.write_bytes(b"\0" * 11)
    with pytest.raises(ValueError, match="too large"):
        mag.as_input(str(big), max_bytes=10)


@pytest.mark.parametrize(
    "content_type, expected",
    [("image/jpeg", ".jpg"), ("image/png", ".png"), ("video/mp4", ".mp4"), ("", ".bin")],
)
def test_suffix_for_content_type(content_type, expected):
    got = mag.suffix_for(content_type)
    # mimetypes may map image/jpeg to .jpg or .jpe depending on the platform.
    assert got == expected or (expected == ".jpg" and got in {".jpg", ".jpeg", ".jpe"})


def test_download_honors_a_caller_supplied_suffix(tmp_path, monkeypatch):
    # House convention (_kling/media.py:output_path_with_suffix, seedream_image,
    # openai_image): a suffix the caller chose is authoritative. Only fill one in
    # when it is missing. The true served type comes back separately.
    monkeypatch.setattr(
        mag,
        "asset_session",
        lambda: SimpleNamespace(
            get=lambda url, timeout=None: SimpleNamespace(
                headers={"Content-Type": "image/jpeg"},
                content=b"jpeg-bytes",
                raise_for_status=lambda: None,
            )
        ),
    )
    kept = mag.download("https://e.com/x", tmp_path / "out.png")
    assert kept.path.name == "out.png", "caller's extension must survive"
    assert kept.content_type == "image/jpeg", "the real format is still reported"

    derived = mag.download("https://e.com/x", tmp_path / "out")
    assert derived.path.suffix in {".jpg", ".jpeg", ".jpe"}


def test_submit_drops_none_so_server_defaults_survive(monkeypatch):
    sent = {}

    def fake_post(url, json=None, timeout=None):
        sent.update(json)
        return SimpleNamespace(status_code=200, json=lambda: {"data": {"task_id": "t1"}}, text="")

    monkeypatch.setenv(mag.ENV_KEY, "k")
    monkeypatch.setattr(mag, "session", lambda: SimpleNamespace(post=fake_post))
    mag.submit("/v1/ai/x", {"a": None, "b": 0, "c": False, "d": ""})
    assert sent == {"b": 0, "c": False, "d": ""}


def test_poll_checks_before_sleeping(monkeypatch):
    # Sleeping first charged every call a flat 5s floor — a 6s generation spent
    # ~78% of its wall-clock waiting to be looked at. Matches atlas_client.py:146
    # and _shared.py:494, which both GET before sleeping.
    order = []
    monkeypatch.setattr(mag.time, "sleep", lambda s: order.append(("sleep", s)))

    def fake_get(url, timeout=None):
        order.append(("get", None))
        return SimpleNamespace(
            status_code=200,
            json=lambda: {"data": {"status": "COMPLETED", "generated": ["u"]}},
            text="",
        )

    monkeypatch.setattr(mag, "session", lambda: SimpleNamespace(get=fake_get))
    assert mag.poll("/v1/ai/x", "t1") == ["u"]
    assert order == [("get", None)], "a task that is already done must not sleep at all"


def test_poll_backs_off_up_to_the_cap(monkeypatch):
    sleeps = []
    monkeypatch.setattr(mag.time, "sleep", sleeps.append)
    statuses = iter(["IN_PROGRESS"] * 6 + ["COMPLETED"])

    def fake_get(url, timeout=None):
        status = next(statuses)
        return SimpleNamespace(
            status_code=200,
            json=lambda: {"data": {"status": status, "generated": ["u"] if status == "COMPLETED" else []}},
            text="",
        )

    monkeypatch.setattr(mag, "session", lambda: SimpleNamespace(get=fake_get))
    mag.poll("/v1/ai/x", "t1", max_wait=600)
    assert sleeps[0] == mag._POLL_START, "first wait is short so fast tasks return fast"
    assert sleeps == sorted(sleeps), "interval must ramp, never shrink"
    assert max(sleeps) <= mag._POLL_CAP


def test_poll_reports_a_failed_task(monkeypatch):
    monkeypatch.setattr(mag.time, "sleep", lambda s: None)
    monkeypatch.setattr(
        mag,
        "session",
        lambda: SimpleNamespace(
            get=lambda url, timeout=None: SimpleNamespace(
                status_code=200,
                json=lambda: {"data": {"status": "FAILED", "error": "nsfw"}},
                text="",
            )
        ),
    )
    with pytest.raises(mag.MagnificError, match="nsfw"):
        mag.poll("/v1/ai/x", "t1")


def test_webhook_is_opt_in_per_call_only():
    # There is no ambient webhook env var: an env-wide default would make every
    # generation POST to a URL nothing in this repo listens on, and the tools
    # block on polling regardless.
    assert not hasattr(mag, "webhook_url")
    assert "MAGNIFIC_WEBHOOK" not in Path(".env.example").read_text()


@pytest.mark.parametrize("tool_cls", ALL_TOOLS)
def test_tools_fail_closed_without_a_key(monkeypatch, tool_cls):
    monkeypatch.delenv(mag.ENV_KEY, raising=False)
    tool = tool_cls()
    assert tool.get_status().value == "unavailable"
    # A missing key must be reported, never turned into a live request.
    minimal = {
        "prompt": "x", "image": "https://example.com/a.png", "text": "x",
        "description": "x", "audio": "https://example.com/a.wav", "duration_seconds": 5,
    }
    result = tool.execute(minimal)
    assert result.success is False
    assert mag.ENV_KEY in result.error



def test_asset_downloads_carry_no_credentials(monkeypatch):
    # The API key must never leave api.magnific.com. Generated assets live on a
    # separate CDN host, and requests only strips `Authorization` across a
    # cross-host redirect — a custom auth header would follow it and leak.
    monkeypatch.setenv(mag.ENV_KEY, "secret-key")
    mag._API_SESSION = None
    mag._ASSET_SESSION = None
    assert "x-magnific-api-key" in mag.session().headers
    assert "x-magnific-api-key" not in mag.asset_session().headers
    assert mag.session() is not mag.asset_session()


def test_poll_survives_transient_errors(monkeypatch):
    # The generation is already paid for; one reset connection must not bin it.
    monkeypatch.setattr(mag.time, "sleep", lambda s: None)
    attempts = {"n": 0}

    def flaky_get(url, timeout=None):
        attempts["n"] += 1
        if attempts["n"] <= 3:
            raise OSError("connection reset")
        return SimpleNamespace(
            status_code=200,
            json=lambda: {"data": {"status": "COMPLETED", "generated": ["u"]}},
            text="",
        )

    monkeypatch.setattr(mag, "session", lambda: SimpleNamespace(get=flaky_get))
    assert mag.poll("/v1/ai/x", "t1", max_wait=600) == ["u"]


def test_poll_gives_up_after_repeated_errors(monkeypatch):
    monkeypatch.setattr(mag.time, "sleep", lambda s: None)

    def always_fails(url, timeout=None):
        raise OSError("connection reset")

    monkeypatch.setattr(mag, "session", lambda: SimpleNamespace(get=always_fails))
    with pytest.raises(mag.MagnificError, match="may still be running"):
        mag.poll("/v1/ai/x", "t1", max_wait=600)


def test_poll_does_not_retry_a_4xx(monkeypatch):
    # A 400/404 will never become a 200; retrying it just burns the deadline.
    monkeypatch.setattr(mag.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def not_found(url, timeout=None):
        calls["n"] += 1
        return SimpleNamespace(status_code=404, text="nope", json=lambda: {})

    monkeypatch.setattr(mag, "session", lambda: SimpleNamespace(get=not_found))
    with pytest.raises(mag.MagnificError, match="404"):
        mag.poll("/v1/ai/x", "t1", max_wait=600)
    assert calls["n"] == 1


def test_as_input_rejects_a_missing_file_instead_of_posting_it(tmp_path):
    # Previously a typo'd path was POSTed verbatim as base64 and came back as an
    # opaque HTTP 400 after the request was already made.
    with pytest.raises(ValueError, match="File not found"):
        mag.as_input(str(tmp_path / "nope.png"))
    with pytest.raises(ValueError, match="File not found"):
        mag.as_input("projects/foo/frame_01.png")
    # A genuine base64 blob has no path shape and must still pass through.
    assert mag.as_input("aVZCT1J3MEtHZ28=") == "aVZCT1J3MEtHZ28="


def test_as_input_rejects_a_malformed_data_uri():
    with pytest.raises(ValueError, match="Malformed data"):
        mag.as_input("data:image/png;base64")


def test_video_always_sends_a_reproducible_seed():
    tool = MagnificVideo()
    # An explicit seed is honored.
    assert tool._seed({"seed": 42}) == 42
    # -1 and omitted both draw a concrete seed rather than letting the server
    # pick one the caller can never recover.
    for inputs in ({}, {"seed": -1}):
        seed = tool._seed(inputs)
        assert isinstance(seed, int) and 0 <= seed <= 4294967295


# --- Registry + selector routing (docs/PR_REVIEW_GUIDE.md "New Provider or Tool"
#     minimum coverage: registry discovery, status behavior, selector routing).

@pytest.mark.parametrize("tool_cls", ALL_TOOLS)
def test_registry_discovers_every_magnific_tool(tool_cls):
    from tools.tool_registry import registry

    registry.ensure_discovered()
    assert registry.get(tool_cls.name) is not None, f"{tool_cls.name} is not discoverable"


def test_registry_does_not_register_the_abstract_base():
    from tools.tool_registry import registry

    registry.ensure_discovered()
    registered = [n for n in registry.list_all() if "magnific" in n]
    assert len(registered) == len(ALL_TOOLS)
    assert not any(n.lower() == "magnifictool" for n in registry.list_all())


@pytest.mark.parametrize(
    "capability, tool_name",
    [
        ("video_generation", "magnific_video"),
        ("image_generation", "magnific_image"),
        ("music_generation", "magnific_music"),
        ("image_upscale", "magnific_upscale"),
    ],
)
def test_selectors_can_route_to_magnific(capability, tool_name):
    # Selectors auto-discover by capability (video_selector.py:252), so a wrong
    # capability string would silently make the tool unroutable.
    from tools.tool_registry import registry

    registry.ensure_discovered()
    found = registry.get_by_capability(capability)
    names = [getattr(t, "name", t) for t in found]
    assert tool_name in names, f"{tool_name} not reachable via capability {capability!r}"


@pytest.mark.parametrize(
    "ratio, expected",
    [
        ("16:9", "widescreen_16_9"),
        ("9:16", "social_story_9_16"),
        ("1:1", "square_1_1"),
        ("16x9", "widescreen_16_9"),
        ("widescreen_16_9", "widescreen_16_9"),
    ],
)
def test_selector_style_aspect_ratio_hints_are_normalized(ratio, expected):
    # image_selector declares aspect_ratio as a free-form string hint, so a
    # routed call arrives as "16:9" rather than Magnific's own name.
    assert mag.normalize_ratio(ratio, magnific_image._ASPECT_RATIOS) == expected
    assert mag.normalize_ratio(ratio, magnific_video._ASPECT_RATIOS) == expected


def test_unknown_aspect_ratio_is_left_alone_for_the_api_to_reject():
    # Guessing would be worse than a clear API error: 21:9 genuinely has no
    # image equivalent in Magnific's vocabulary.
    assert mag.normalize_ratio("7:3", magnific_image._ASPECT_RATIOS) == "7:3"
    assert mag.normalize_ratio("21:9", magnific_image._ASPECT_RATIOS) == "21:9"
    assert mag.normalize_ratio("21:9", magnific_video._ASPECT_RATIOS) == "film_horizontal_21_9"


@pytest.mark.parametrize("tool_cls", ALL_TOOLS)
def test_status_tracks_the_credential(monkeypatch, tool_cls):
    monkeypatch.setenv(mag.ENV_KEY, "k")
    assert tool_cls().get_status().value == "available"
    monkeypatch.delenv(mag.ENV_KEY)
    assert tool_cls().get_status().value == "unavailable"


@pytest.mark.parametrize("tool_cls", ALL_TOOLS)
def test_install_instructions_name_the_env_var(tool_cls):
    # The provider menu shows this text when the tool is unavailable.
    assert mag.ENV_KEY in tool_cls().install_instructions


def test_no_heavyweight_imports_at_module_import_time():
    # The registry imports every tool module to build its catalog, so a module
    # -level `import requests` would put network-stack import cost in discovery.
    import ast

    for path in (
        "tools/_magnific.py",
        "tools/video/magnific_video.py",
        "tools/graphics/magnific_image.py",
        "tools/audio/magnific_audio.py",
        "tools/enhancement/magnific_upscale.py",
    ):
        tree = ast.parse(Path(path).read_text())
        top_level = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        names = {a.name.split(".")[0] for n in top_level if isinstance(n, ast.Import) for a in n.names}
        names |= {n.module.split(".")[0] for n in top_level if isinstance(n, ast.ImportFrom) and n.module}
        assert "requests" not in names, f"{path} imports requests at module level"
