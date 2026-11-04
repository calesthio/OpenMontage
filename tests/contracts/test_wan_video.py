"""Contract tests for the local Wan 2.x video tool.

These run without a GPU, without model weights and without network: they cover
the tool contract, the variant catalog's internal consistency, and the frame /
segment arithmetic that decides how a long clip is chained together.
"""

import pytest

from tools.base_tool import (
    BaseTool,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)
from tools.tool_registry import ToolRegistry
from tools.video._shared import WAN_VARIANTS
from tools.video._wan_engine import (
    _PIPELINE_FOR_OPERATION,
    _oom_aware_error,
    generate_wan,
    plan_segments,
    resolve_offload_mode,
    resolve_precision,
    snap_dimension,
    snap_frames,
)
from tools.video.wan_video import DEFAULT_VARIANT, WanVideo

# Wan's VAE compresses 4x in time.  Spatial alignment is per-variant: the VAE's
# spatial compression times the transformer patch size, which is 32 for the
# 16x-VAE TI2V line and 16 for every 8x-VAE Wan line.
TEMPORAL_SCALE = 4


# ------------------------------------------------------------------
# Contract compliance
# ------------------------------------------------------------------


class TestContract:
    def test_inherits_base_tool(self):
        assert issubclass(WanVideo, BaseTool)

    def test_identity(self):
        tool = WanVideo()
        assert tool.name == "wan_video"
        assert tool.provider == "wan"
        assert tool.capability == "video_generation"
        assert tool.tier == ToolTier.GENERATE
        assert tool.stability == ToolStability.EXPERIMENTAL
        assert tool.runtime == ToolRuntime.LOCAL_GPU

    def test_input_schema(self):
        schema = WanVideo().input_schema
        assert schema["type"] == "object"
        assert "prompt" in schema["required"]
        assert schema["properties"]["model_variant"]["default"] == DEFAULT_VARIANT

    def test_local_generation_is_free(self):
        assert WanVideo().estimate_cost({"prompt": "x"}) == 0.0

    def test_status_requires_opt_in(self, monkeypatch):
        monkeypatch.delenv("VIDEO_GEN_LOCAL_ENABLED", raising=False)
        assert WanVideo().get_status() == ToolStatus.UNAVAILABLE

    def test_registry_discovers_tool(self):
        registry = ToolRegistry()
        registry.discover()
        assert "wan_video" in registry.list_all()
        assert registry.get("wan_video").provider == "wan"

    def test_schema_operations_match_engine(self):
        declared = set(WanVideo().input_schema["properties"]["operation"]["enum"])
        assert declared == set(_PIPELINE_FOR_OPERATION)


# ------------------------------------------------------------------
# Variant catalog
# ------------------------------------------------------------------


@pytest.mark.parametrize("key", sorted(WAN_VARIANTS), ids=lambda k: k)
class TestVariantCatalog:
    def test_required_fields(self, key):
        meta = WAN_VARIANTS[key]
        for field in (
            "name",
            "hf_id",
            "params_b",
            "operations",
            "default_width",
            "default_height",
            "default_num_frames",
            "spatial_alignment",
            "temporal_scale",
            "default_steps",
            "default_guidance",
            "fps",
            "license",
        ):
            assert field in meta, f"{key} is missing {field}"

    def test_operations_are_known_and_non_empty(self, key):
        operations = WAN_VARIANTS[key]["operations"]
        assert operations
        assert set(operations) <= set(_PIPELINE_FOR_OPERATION)

    def test_default_geometry_is_vae_aligned(self, key):
        meta = WAN_VARIANTS[key]
        alignment = meta["spatial_alignment"]
        assert meta["default_width"] % alignment == 0
        assert meta["default_height"] % alignment == 0

    def test_declares_vae_scales(self, key):
        meta = WAN_VARIANTS[key]
        assert meta["spatial_alignment"] in (16, 32)
        assert meta["temporal_scale"] == TEMPORAL_SCALE

    def test_default_frame_count_is_vae_aligned(self, key):
        frames = WAN_VARIANTS[key]["default_num_frames"]
        assert (frames - 1) % TEMPORAL_SCALE == 0

    def test_image_operations_have_a_checkpoint(self, key):
        """A variant may only claim an operation it has weights for."""
        meta = WAN_VARIANTS[key]
        for operation in meta["operations"]:
            assert meta.get(f"hf_{operation}_id") or meta["hf_id"]

    def test_legacy_flags_agree_with_operations(self, key):
        meta = WAN_VARIANTS[key]
        assert meta["t2v"] is ("text_to_video" in meta["operations"])
        assert meta["i2v"] is ("image_to_video" in meta["operations"])


def test_wan21_1_3b_does_not_claim_image_to_video():
    """Wan 2.1 never shipped 1.3B I2V weights; claiming it pulled a 14B model."""
    meta = WAN_VARIANTS["wan2.1-1.3b"]
    assert "image_to_video" not in meta["operations"]
    assert "1.3B" in meta["hf_id"] or "1.3B" in meta["name"]


def test_default_variant_covers_the_full_matrix():
    """The default must handle every operation the tool advertises."""
    assert set(WAN_VARIANTS[DEFAULT_VARIANT]["operations"]) == set(_PIPELINE_FOR_OPERATION)


# ------------------------------------------------------------------
# Frame and segment arithmetic
# ------------------------------------------------------------------


class TestGeometry:
    @pytest.mark.parametrize("value", [1, 5, 25, 80, 81, 100, 121, 720])
    def test_snap_frames_lands_on_a_latent_boundary(self, value):
        snapped = snap_frames(value)
        assert snapped == 1 or (snapped - 1) % TEMPORAL_SCALE == 0
        assert snapped >= 1

    def test_snap_frames_is_idempotent(self):
        assert snap_frames(snap_frames(97)) == snap_frames(97)

    def test_snap_frames_rejects_zero(self):
        with pytest.raises(ValueError):
            snap_frames(0)

    @pytest.mark.parametrize("value", [17, 300, 480, 704, 1280])
    def test_snap_dimension_aligns(self, value):
        assert snap_dimension(value, 32) % 32 == 0

    def test_snap_dimension_never_returns_zero(self):
        assert snap_dimension(3, 32) == 32


class TestSegmentPlanning:
    @pytest.mark.parametrize("segment", [25, 49, 121])
    def test_plan_covers_every_requested_length(self, segment):
        """Segments must always reach the target; the tail is trimmed, never short.

        Swept rather than spot-checked: an off-by-one in the carry (using the
        segment length instead of segment-1) still lands on the right answer for
        most inputs and only shows up at particular totals.
        """
        for total in range(1, 40 * segment):
            count = plan_segments(total, segment)
            covered = segment + (count - 1) * (segment - 1)
            assert covered >= total, f"{total} frames left short by {total - covered}"
            # and must never buy a segment it does not need
            if count > 1:
                previous = segment + (count - 2) * (segment - 1)
                assert previous < total

    def test_carry_accounts_for_the_duplicated_anchor_frame(self):
        """Each continuation reproduces the anchor, so it adds segment-1 frames."""
        segment = 121
        # 1210 is an exact multiple of the segment length but not of the carry,
        # which is where an off-by-one in the carry first becomes visible.
        total = segment + 1210
        count = plan_segments(total, segment)
        assert segment + (count - 1) * (segment - 1) >= total

    def test_single_segment_when_it_fits(self):
        assert plan_segments(121, 121) == 1
        assert plan_segments(50, 121) == 1

    def test_thirty_seconds_at_24fps(self):
        """The headline case: 30s of 24fps video off a 121-frame model."""
        count = plan_segments(30 * 24, 121)
        assert count == 6
        assert 121 + (count - 1) * 120 >= 720


class TestPrecisionSelection:
    def test_explicit_precision_is_respected(self):
        assert resolve_precision("int4", 5.0) == "int4"
        assert resolve_precision("bf16", 28.0) == "bf16"

    def test_auto_degrades_as_the_model_grows(self, monkeypatch):
        monkeypatch.setattr("tools.video._wan_engine._vram_gb", lambda: 12.0)
        assert resolve_precision("auto", 1.3) == "bf16"
        assert resolve_precision("auto", 28.0) == "int4"

    def test_auto_on_a_big_card_stays_bf16(self, monkeypatch):
        monkeypatch.setattr("tools.video._wan_engine._vram_gb", lambda: 80.0)
        assert resolve_precision("auto", 28.0) == "bf16"

    def test_cpu_never_asks_for_a_cuda_only_quantizer(self, monkeypatch):
        monkeypatch.setattr("tools.video._wan_engine._vram_gb", lambda: 0.0)
        assert resolve_precision("auto", 28.0) == "bf16"


# ------------------------------------------------------------------
# Planning surface on the tool
# ------------------------------------------------------------------


class TestPlan:
    def test_duration_drives_segment_count(self):
        plan = WanVideo()._plan({"prompt": "x", "duration_seconds": 30})
        assert plan["fps"] == 24
        assert plan["total_frames"] == 720
        assert plan["segments"] == 6

    def test_native_length_needs_one_segment(self):
        plan = WanVideo()._plan({"prompt": "x"})
        assert plan["segments"] == 1

    def test_explicit_num_frames_overrides_duration(self):
        plan = WanVideo()._plan({"prompt": "x", "duration_seconds": 30, "num_frames": 49})
        assert plan["total_frames"] == 49
        assert plan["segments"] == 1

    def test_text_to_image_is_a_single_frame(self):
        plan = WanVideo()._plan({"prompt": "x", "operation": "text_to_image", "duration_seconds": 30})
        assert plan["total_frames"] == 1
        assert plan["segments"] == 1

    def test_longer_request_estimates_longer_runtime(self):
        tool = WanVideo()
        short = tool.estimate_runtime({"prompt": "x", "duration_seconds": 5})
        long = tool.estimate_runtime({"prompt": "x", "duration_seconds": 30})
        assert long > short


# ------------------------------------------------------------------
# Validation happens before any weights are touched
# ------------------------------------------------------------------


def _generate(**inputs):
    return generate_wan(
        tool_name="wan_video",
        variants=WAN_VARIANTS,
        default_variant=DEFAULT_VARIANT,
        inputs={"prompt": "a cat", **inputs},
    )


class TestValidation:
    def test_unknown_variant_is_rejected(self):
        result = _generate(model_variant="wan9000")
        assert not result.success
        assert "Unknown model_variant" in result.error

    def test_unknown_operation_is_rejected(self):
        result = _generate(operation="mind_to_video")
        assert not result.success
        assert "Unknown operation" in result.error

    def test_operation_unsupported_by_variant_is_rejected(self):
        """wan2.1-1.3b has no I2V weights — this must fail fast, not load 14B."""
        result = _generate(model_variant="wan2.1-1.3b", operation="image_to_video")
        assert not result.success
        assert "does not support" in result.error

    def test_missing_prompt_is_rejected(self):
        result = generate_wan(
            tool_name="wan_video",
            variants=WAN_VARIANTS,
            default_variant=DEFAULT_VARIANT,
            inputs={"prompt": ""},
        )
        assert not result.success
        assert "prompt is required" in result.error

    def test_unavailable_tool_reports_install_instructions(self, monkeypatch):
        monkeypatch.delenv("VIDEO_GEN_LOCAL_ENABLED", raising=False)
        result = WanVideo().execute({"prompt": "a cat"})
        assert not result.success
        assert "VIDEO_GEN_LOCAL_ENABLED" in result.error


def test_ti2v_is_the_only_32_aligned_line():
    """The 16x VAE plus 2x patching is what forces 1280x704 instead of 1280x720."""
    assert WAN_VARIANTS["wan2.2-ti2v-5b"]["spatial_alignment"] == 32
    assert WAN_VARIANTS["wan2.2-ti2v-5b"]["default_height"] == 704
    for key, meta in WAN_VARIANTS.items():
        if key != "wan2.2-ti2v-5b":
            assert meta["spatial_alignment"] == 16


# ------------------------------------------------------------------
# Offload strategy and allocator diagnostics
# ------------------------------------------------------------------


class TestOffloadSelection:
    def test_explicit_mode_is_respected(self):
        assert resolve_offload_mode("model", "bf16", 5.0) == "model"
        assert resolve_offload_mode("sequential", "bf16", 1.3) == "sequential"

    def test_bf16_5b_on_a_12gb_card_goes_sequential(self, monkeypatch):
        """10GB of resident bf16 weights leaves no room for activations."""
        monkeypatch.setattr("tools.video._wan_engine._vram_gb", lambda: 11.6)
        assert resolve_offload_mode("auto", "bf16", 5.0) == "sequential"

    def test_quantized_weights_fit_resident_on_the_same_card(self, monkeypatch):
        monkeypatch.setattr("tools.video._wan_engine._vram_gb", lambda: 11.6)
        assert resolve_offload_mode("auto", "int4", 5.0) == "model"

    def test_big_card_keeps_weights_resident(self, monkeypatch):
        monkeypatch.setattr("tools.video._wan_engine._vram_gb", lambda: 80.0)
        assert resolve_offload_mode("auto", "bf16", 28.0) == "model"

    def test_cpu_only_does_not_ask_for_sequential(self, monkeypatch):
        monkeypatch.setattr("tools.video._wan_engine._vram_gb", lambda: 0.0)
        assert resolve_offload_mode("auto", "bf16", 28.0) == "model"


class TestAllocatorDiagnostics:
    def test_nvml_assert_is_reported_as_a_driver_mismatch(self):
        """PyTorch calls NVML while reporting OOM, so a driver mismatch masks it."""
        result = _oom_aware_error(
            RuntimeError(
                "NVML_SUCCESS == DriverAPI::get()->nvmlInit_v2_() INTERNAL ASSERT FAILED"
            ),
            "wan2.2-ti2v-5b", "bf16", "sequential", 704, 480, 121,
        )
        assert not result.success
        assert "driver" in result.error.lower()
        assert "reboot" in result.error.lower()

    def test_real_oom_suggests_sequential_offload_first(self):
        result = _oom_aware_error(
            RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB"),
            "wan2.2-ti2v-5b", "bf16", "model", 1280, 704, 121,
        )
        assert not result.success
        assert "sequential" in result.error

    def test_oom_already_sequential_does_not_suggest_it_again(self):
        result = _oom_aware_error(
            RuntimeError("CUDA out of memory"),
            "wan2.2-ti2v-5b", "bf16", "sequential", 1280, 704, 121,
        )
        assert 'offload_mode="sequential"' not in result.error
        assert "resolution" in result.error

    def test_unrelated_failure_is_passed_through(self):
        result = _oom_aware_error(
            ValueError("something else entirely"),
            "wan2.2-ti2v-5b", "bf16", "model", 704, 480, 49,
        )
        assert "something else entirely" in result.error


class TestRuntimeEstimate:
    def test_scales_with_segment_count(self):
        """Each chained segment pays the full per-step cost again."""
        tool = WanVideo()
        base = dict(prompt="x", width=704, height=480, num_inference_steps=20,
                    offload_mode="sequential")
        one = tool.estimate_runtime({**base, "num_frames": 121})
        six = tool.estimate_runtime({**base, "duration_seconds": 30})
        assert 5.0 < (six / one) < 7.0

    def test_matches_measured_704x480_run(self):
        """Fitted against a real run: 49 frames, 20 steps, sequential -> 248s."""
        estimate = WanVideo().estimate_runtime({
            "prompt": "x", "num_frames": 49, "width": 704, "height": 480,
            "num_inference_steps": 20, "offload_mode": "sequential",
        })
        assert 0.7 < estimate / 248.0 < 1.4

    def test_sequential_costs_more_than_resident(self):
        tool = WanVideo()
        base = dict(prompt="x", num_frames=49, width=704, height=480, num_inference_steps=20)
        assert (
            tool.estimate_runtime({**base, "offload_mode": "sequential"})
            > tool.estimate_runtime({**base, "offload_mode": "model"})
        )


# ------------------------------------------------------------------
# Single-pass operations must not be handed a long-form frame count
# ------------------------------------------------------------------


class TestNonChainableOperations:
    """Only text_to_video and image_to_video can continue from a last frame.

    Everything else is single-pass, so a long ``duration_seconds`` must be
    clamped to the model's native clip length instead of being sent to the GPU
    as one enormous denoise.
    """

    @staticmethod
    def _run(monkeypatch, **inputs):
        """Drive generate_wan with the GPU replaced by a recorder."""
        from PIL import Image

        from tools.video import _wan_engine

        calls = {}

        class FakePipeline:
            vae_scale_factor_temporal = 4
            vae_scale_factor_spatial = 16
            transformer = None

        monkeypatch.setattr(_wan_engine, "load_wan_pipeline", lambda **kw: FakePipeline())
        monkeypatch.setattr(_wan_engine, "pipeline_scales", lambda pipeline: (4, 32))

        def fake_single(pipeline, **kwargs):
            calls["num_frames"] = kwargs["num_frames"]
            return [Image.new("RGB", (16, 16))] * kwargs["num_frames"]

        def fake_chained(pipeline, **kwargs):
            calls["segment_count"] = kwargs["segment_count"]
            total = kwargs["total_frames"]
            return [Image.new("RGB", (16, 16))] * total, []

        monkeypatch.setattr(_wan_engine, "_generate_single", fake_single)
        monkeypatch.setattr(_wan_engine, "_generate_chained", fake_chained)
        monkeypatch.setattr(_wan_engine, "export_frames", lambda *a, **k: None)
        monkeypatch.setattr("tools.video._shared.probe_output", lambda path: {})

        result = _wan_engine.generate_wan(
            tool_name="wan_video",
            variants=WAN_VARIANTS,
            default_variant=DEFAULT_VARIANT,
            inputs={"prompt": "x", **inputs},
        )
        return result, calls

    NATIVE = WAN_VARIANTS[DEFAULT_VARIANT]["default_num_frames"]

    @pytest.mark.parametrize("operation", ["video_to_video", "first_last_frame"])
    def test_long_request_is_clamped_to_one_pass(self, monkeypatch, operation, tmp_path):
        result, calls = self._run(
            monkeypatch,
            operation=operation,
            duration_seconds=30,
            source_video_path=str(tmp_path / "in.mp4"),
            output_path=str(tmp_path / "out.mp4"),
        )
        assert result.success, result.error
        assert result.data["segments"] == 1
        assert calls["num_frames"] <= self.NATIVE
        # and the caller is told it was clamped rather than silently short-changed
        assert result.data["clamped_from_frames"] == 30 * 24

    def test_text_to_video_still_chains(self, monkeypatch, tmp_path):
        result, calls = self._run(
            monkeypatch,
            operation="text_to_video",
            duration_seconds=30,
            output_path=str(tmp_path / "out.mp4"),
        )
        assert result.success, result.error
        assert calls["segment_count"] == 6
        assert result.data["clamped_from_frames"] is None

    def test_short_request_is_not_marked_as_clamped(self, monkeypatch, tmp_path):
        result, _ = self._run(
            monkeypatch,
            operation="first_last_frame",
            num_frames=49,
            output_path=str(tmp_path / "out.mp4"),
        )
        assert result.success, result.error
        assert result.data["clamped_from_frames"] is None

    def test_chainable_operations_are_exactly_the_video_continuations(self):
        chainable = {"text_to_video", "image_to_video"}
        assert chainable < set(_PIPELINE_FOR_OPERATION)
        assert "video_to_video" not in chainable
        assert "first_last_frame" not in chainable
