"""Local Wan 2.x generation engine.

Covers the full Wan operation matrix on a single consumer GPU:

  text_to_video     WanPipeline
  image_to_video    WanImageToVideoPipeline
  video_to_video    WanVideoToVideoPipeline
  first_last_frame  WanImageToVideoPipeline (``last_image``)
  text_to_image     WanPipeline with a single frame

The entry point is :func:`generate_wan`.  When the requested duration exceeds
what a Wan model produces in one pass (~5s), it chains image-to-video segments
off each previous segment's last frame to reach the target length.

Wan's VAE constrains the request geometry: frame counts must land on
``temporal * k + 1`` and both spatial dimensions must be a multiple of the
spatial compression factor.  Callers pass whatever they like; this module snaps
the values and reports what it actually used.
"""

from __future__ import annotations

import gc
import math
from pathlib import Path
from typing import Any

# Wan 2.1 uses a 8x8x4 VAE, Wan 2.2's TI2V line uses the 16x16x4 high-compression
# VAE.  Both are read off the loaded pipeline; these are only the fallbacks used
# for planning before a pipeline exists.
_DEFAULT_TEMPORAL_SCALE = 4
_DEFAULT_SPATIAL_SCALE = 16

# Wan's own reference implementation ships this Chinese negative prompt and the
# model is visibly tuned for it; it suppresses the static/oversaturated failure
# mode far better than an English equivalent.
DEFAULT_NEGATIVE_PROMPT = (
    "色调艳丽,过曝,静态,细节模糊不清,字幕,风格,作品,画作,画面,静止,整体发灰,最差质量,"
    "低质量,JPEG压缩残留,丑陋的,残缺的,多余的手指,画得不好的手部,画得不好的脸部,畸形的,"
    "毁容的,形态畸形的肢体,手指融合,静止不动的画面,杂乱的背景,三条腿,背景人很多,倒着走"
)

_PIPELINE_FOR_OPERATION = {
    "text_to_video": "WanPipeline",
    "text_to_image": "WanPipeline",
    "image_to_video": "WanImageToVideoPipeline",
    "first_last_frame": "WanImageToVideoPipeline",
    "video_to_video": "WanVideoToVideoPipeline",
}

# Keyed by (model_id, pipeline class, precision, offload enabled, offload mode).
# One loaded pipeline is 10-28GB of host RAM, so at most one is kept alive.
_PIPELINE_CACHE: dict[tuple[str, str, str, bool, str], Any] = {}


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------


def snap_frames(num_frames: int, temporal_scale: int = _DEFAULT_TEMPORAL_SCALE) -> int:
    """Snap ``num_frames`` down onto the nearest valid ``temporal_scale * k + 1``.

    Wan's causal VAE encodes the first frame on its own and then groups every
    following ``temporal_scale`` frames, so only these counts round-trip.  We
    round to nearest and clamp to a single latent group.
    """
    if num_frames < 1:
        raise ValueError("num_frames must be >= 1")
    if num_frames == 1:
        return 1  # single-image mode
    k = max(1, round((num_frames - 1) / temporal_scale))
    return temporal_scale * k + 1


def snap_dimension(value: int, spatial_scale: int = _DEFAULT_SPATIAL_SCALE) -> int:
    """Snap a width/height onto a multiple of the VAE spatial compression."""
    if value < spatial_scale:
        return spatial_scale
    return int(round(value / spatial_scale)) * spatial_scale


def plan_segments(total_frames: int, segment_frames: int) -> int:
    """Number of chained segments needed to cover ``total_frames``.

    The first segment contributes all of its frames.  Every continuation is
    seeded with the previous segment's last frame, so it reproduces that frame
    and contributes only ``segment_frames - 1`` new ones.
    """
    if total_frames <= segment_frames:
        return 1
    carry = segment_frames - 1
    return 1 + math.ceil((total_frames - segment_frames) / carry)


# --------------------------------------------------------------------------
# loading
# --------------------------------------------------------------------------


def _vram_gb() -> float:
    try:
        import torch

        if not torch.cuda.is_available():
            return 0.0
        return torch.cuda.get_device_properties(0).total_memory / 1024**3
    except Exception:
        return 0.0


def resolve_precision(precision: str, model_params_b: float) -> str:
    """Pick a weight precision that fits the visible GPU.

    ``model_params_b`` is the transformer size in billions of parameters; bf16
    needs roughly 2GB per billion resident on the device, and cpu-offload only
    keeps one module at a time, so the transformer alone sets the floor.
    """
    if precision != "auto":
        return precision
    vram = _vram_gb()
    if vram <= 0:
        return "bf16"  # CPU/MPS: quantization backends are CUDA-only
    bf16_need = model_params_b * 2.0 + 2.5  # weights + activation headroom
    if vram >= bf16_need:
        return "bf16"
    if vram >= model_params_b * 1.0 + 2.5:
        return "int8"
    return "int4"


def resolve_offload_mode(offload_mode: str, precision: str, model_params_b: float) -> str:
    """Choose how aggressively to offload weights to host RAM.

    ``model`` keeps a whole component resident and is fastest.  It only works if
    the largest component plus its activations fit; a bf16 5B transformer is
    10GB, so on a 12GB card that leaves too little for anything above about
    512x320.  ``sequential`` streams one submodule at a time, costing PCIe
    bandwidth per step but freeing almost the entire card for activations.
    """
    if offload_mode != "auto":
        return offload_mode
    vram = _vram_gb()
    if vram <= 0:
        return "model"
    bytes_per_param = {"int4": 0.55, "int8": 1.05}.get(precision, 2.0)
    resident = model_params_b * bytes_per_param
    # Need room for the weights and a working set of activations on top.
    return "model" if vram >= resident + 3.0 else "sequential"


def _quant_config(precision: str):
    from diffusers import BitsAndBytesConfig

    import torch

    if precision == "int8":
        return BitsAndBytesConfig(load_in_8bit=True)
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
    )


def free_wan_pipelines() -> None:
    """Drop every cached pipeline and release GPU memory."""
    _PIPELINE_CACHE.clear()
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def load_wan_pipeline(
    *,
    model_id: str,
    operation: str,
    precision: str = "bf16",
    enable_offload: bool = True,
    offload_mode: str = "model",
):
    """Load (and cache) the Wan pipeline class matching ``operation``.

    Wan repos declare a single ``_class_name`` in ``model_index.json`` but the
    same weights back several tasks, so the pipeline class is chosen from the
    operation rather than the repo metadata.  Components absent from the repo
    (Wan 2.2 TI2V has no CLIP image encoder) are optional on the diffusers
    classes and resolve to ``None``.
    """
    import diffusers
    import torch

    from tools.video._shared import get_torch_device

    pipeline_name = _PIPELINE_FOR_OPERATION.get(operation)
    if pipeline_name is None:
        raise ValueError(
            f"Unsupported operation: {operation}. "
            f"Expected one of {', '.join(sorted(_PIPELINE_FOR_OPERATION))}"
        )

    key = (model_id, pipeline_name, precision, enable_offload, offload_mode)
    if key in _PIPELINE_CACHE:
        return _PIPELINE_CACHE[key]

    # Only one Wan pipeline fits in host RAM at a time.
    free_wan_pipelines()

    device = get_torch_device()
    if device == "cuda" and torch.cuda.is_bf16_supported():
        dtype = torch.bfloat16
    elif device == "cpu":
        dtype = torch.float32
    else:
        dtype = torch.float16

    pipeline_class = getattr(diffusers, pipeline_name)
    kwargs: dict[str, Any] = {"torch_dtype": dtype}

    if precision in {"int4", "int8"} and device == "cuda":
        # Quantize the transformer(s) only.  The T5 text encoder runs once per
        # prompt and the VAE once per clip, so offloading those is cheaper than
        # paying the dequantization cost on every denoising step.
        from diffusers import WanTransformer3DModel

        quant = _quant_config(precision)
        transformer = WanTransformer3DModel.from_pretrained(
            model_id, subfolder="transformer", quantization_config=quant, torch_dtype=dtype
        )
        kwargs["transformer"] = transformer
        if _has_subfolder(model_id, "transformer_2"):
            kwargs["transformer_2"] = WanTransformer3DModel.from_pretrained(
                model_id, subfolder="transformer_2", quantization_config=quant, torch_dtype=dtype
            )

    pipeline = pipeline_class.from_pretrained(model_id, **kwargs)

    # bitsandbytes modules cannot be moved after load; the accelerate hooks
    # dispatch rather than relocate them, so offload still applies.
    if enable_offload and device == "cuda":
        if offload_mode == "sequential":
            # Keeps only the executing submodule on the GPU.  A 5B transformer
            # in bf16 is 10GB, which leaves nothing for activations on a 12GB
            # card; sequential offload trades PCIe bandwidth for that headroom
            # and is what makes 480p/720p reachable here at all.
            pipeline.enable_sequential_cpu_offload()
        else:
            pipeline.enable_model_cpu_offload()
    elif precision in {"int4", "int8"}:
        pass  # already placed by the quantization loader
    else:
        pipeline = pipeline.to(device)

    vae = getattr(pipeline, "vae", None)
    if vae is not None:
        # Tiling keeps VAE decode of a 720p/121-frame clip off the OOM line;
        # it is the single biggest peak-memory win for long clips.
        if hasattr(vae, "enable_tiling"):
            vae.enable_tiling()
        if hasattr(vae, "enable_slicing"):
            vae.enable_slicing()

    pipeline._is_sequentially_offloaded = bool(
        enable_offload and device == "cuda" and offload_mode == "sequential"
    )
    _PIPELINE_CACHE[key] = pipeline
    return pipeline


def _has_subfolder(model_id: str, subfolder: str) -> bool:
    local = Path(model_id)
    if local.is_dir():
        return (local / subfolder).is_dir()
    try:
        from huggingface_hub import model_info

        return any(s.rfilename.startswith(f"{subfolder}/") for s in model_info(model_id).siblings)
    except Exception:
        return False


def pipeline_scales(pipeline) -> tuple[int, int]:
    """Read (temporal, spatial) VAE compression factors off a loaded pipeline."""
    temporal = getattr(pipeline, "vae_scale_factor_temporal", None) or _DEFAULT_TEMPORAL_SCALE
    spatial = getattr(pipeline, "vae_scale_factor_spatial", None) or _DEFAULT_SPATIAL_SCALE
    # Transformer patch size doubles the effective spatial alignment requirement.
    transformer = getattr(pipeline, "transformer", None)
    patch = getattr(getattr(transformer, "config", None), "patch_size", None)
    if patch:
        spatial = spatial * int(patch[-1])
    return int(temporal), int(spatial)


# --------------------------------------------------------------------------
# media io
# --------------------------------------------------------------------------


def load_image(path: str | None, url: str | None, width: int, height: int):
    """Load a reference still from disk or URL, resized to the target geometry."""
    from io import BytesIO

    from PIL import Image

    if path:
        image = Image.open(path).convert("RGB")
    elif url:
        import requests

        response = requests.get(url, timeout=60)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content)).convert("RGB")
    else:
        raise ValueError("This operation requires reference_image_path or reference_image_url")
    return image.resize((width, height), Image.LANCZOS)


def load_video_frames(path: str, width: int, height: int, max_frames: int) -> list:
    """Read up to ``max_frames`` frames from a video file as resized PIL images."""
    import imageio.v3 as iio
    from PIL import Image

    frames = []
    for index, frame in enumerate(iio.imiter(path)):
        if index >= max_frames:
            break
        frames.append(Image.fromarray(frame).convert("RGB").resize((width, height), Image.LANCZOS))
    if not frames:
        raise ValueError(f"No frames could be read from {path}")
    return frames


def export_frames(frames: list, output_path: Path, fps: int) -> None:
    """Encode PIL frames to an H.264 MP4 that plays everywhere."""
    import imageio
    import numpy as np

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = imageio.get_writer(
        str(output_path),
        fps=fps,
        codec="libx264",
        quality=8,
        macro_block_size=None,
        ffmpeg_params=["-pix_fmt", "yuv420p"],
    )
    try:
        for frame in frames:
            writer.append_data(np.asarray(frame))
    finally:
        writer.close()


def _to_pil_list(output) -> list:
    """Normalise a diffusers video output into a flat list of PIL images."""
    from PIL import Image
    import numpy as np

    frames = output.frames[0] if hasattr(output, "frames") else output.images
    result = []
    for frame in frames:
        if isinstance(frame, Image.Image):
            result.append(frame)
        else:
            array = np.asarray(frame)
            if array.dtype != np.uint8:
                array = (np.clip(array, 0.0, 1.0) * 255).round().astype(np.uint8)
            result.append(Image.fromarray(array))
    return result


# --------------------------------------------------------------------------
# drift control
# --------------------------------------------------------------------------


def channel_stats(frames: list) -> tuple:
    """Per-channel mean and std over a list of frames, for drift correction."""
    import numpy as np

    sample = np.stack([np.asarray(f, dtype=np.float32) for f in frames[:: max(1, len(frames) // 8)]])
    return sample.mean(axis=(0, 1, 2)), sample.std(axis=(0, 1, 2)) + 1e-6


def match_channel_stats(frames: list, reference: tuple) -> list:
    """Re-grade ``frames`` so their colour statistics match ``reference``.

    Chained image-to-video drifts in contrast and colour temperature every hop,
    because each segment is conditioned on an already-generated frame.  Matching
    each segment back to the opening segment's statistics keeps a 30s chain from
    visibly fading or warming over its length.
    """
    import numpy as np
    from PIL import Image

    ref_mean, ref_std = reference
    cur_mean, cur_std = channel_stats(frames)
    scale = ref_std / cur_std
    corrected = []
    for frame in frames:
        array = np.asarray(frame, dtype=np.float32)
        array = (array - cur_mean) * scale + ref_mean
        corrected.append(Image.fromarray(np.clip(array, 0, 255).astype(np.uint8)))
    return corrected


# --------------------------------------------------------------------------
# generation
# --------------------------------------------------------------------------


def _generator(seed: int | None):
    import torch

    if seed is None:
        return None
    # A CPU generator stays reproducible regardless of how the pipeline is
    # offloaded across devices.
    return torch.Generator(device="cpu").manual_seed(seed)


def _run_pass(
    pipeline,
    *,
    operation: str,
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    num_frames: int,
    steps: int,
    guidance_scale: float,
    guidance_scale_2: float | None,
    seed: int | None,
    image=None,
    last_image=None,
    video=None,
    strength: float = 0.8,
) -> list:
    """Run one Wan pipeline call and return its frames as PIL images."""
    args: dict[str, Any] = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "height": height,
        "width": width,
        "num_inference_steps": steps,
        "guidance_scale": guidance_scale,
        "generator": _generator(seed),
        "output_type": "pil",
    }
    # WanVideoToVideoPipeline derives its length from the input clip and takes
    # no num_frames; every other Wan pipeline requires it.
    if operation == "video_to_video":
        args["video"] = video
        args["strength"] = strength
    else:
        args["num_frames"] = num_frames

    # guidance_scale_2 only exists on the MoE (A14B) pipelines that carry a
    # second expert; passing it to the 5B dense model raises.
    if guidance_scale_2 is not None and getattr(pipeline, "transformer_2", None) is not None:
        args["guidance_scale_2"] = guidance_scale_2

    if image is not None:
        args["image"] = image
    if last_image is not None:
        args["last_image"] = last_image

    return _to_pil_list(pipeline(**args))


def generate_wan(
    *,
    tool_name: str,
    variants: dict[str, dict[str, Any]],
    default_variant: str,
    inputs: dict[str, Any],
):
    """Generate with a local Wan model, chaining segments for long durations."""
    from tools.base_tool import ToolResult

    variant_key = inputs.get("model_variant") or default_variant
    if variant_key not in variants:
        return ToolResult(
            success=False,
            error=f"Unknown model_variant: {variant_key}. Available: {', '.join(sorted(variants))}",
        )
    meta = variants[variant_key]
    operation = inputs.get("operation", "text_to_video")

    if operation not in _PIPELINE_FOR_OPERATION:
        return ToolResult(
            success=False,
            error=(
                f"Unknown operation: {operation}. "
                f"Expected one of {', '.join(sorted(_PIPELINE_FOR_OPERATION))}"
            ),
        )
    supported = meta.get("operations", [])
    if operation not in supported:
        return ToolResult(
            success=False,
            error=(
                f"{meta['name']} does not support {operation}. "
                f"It supports: {', '.join(supported)}."
            ),
        )

    prompt = inputs.get("prompt")
    if not prompt:
        return ToolResult(success=False, error="prompt is required")

    model_id = meta.get(f"hf_{operation}_id") or meta["hf_id"]
    precision = resolve_precision(inputs.get("precision", "auto"), meta["params_b"])
    enable_offload = inputs.get("enable_model_offload", True)
    offload_mode = resolve_offload_mode(
        inputs.get("offload_mode", "auto"), precision, meta["params_b"]
    )

    try:
        pipeline = load_wan_pipeline(
            model_id=model_id,
            operation=operation,
            precision=precision,
            enable_offload=enable_offload,
            offload_mode=offload_mode,
        )
    except Exception as exc:
        return ToolResult(success=False, error=f"Failed to load {model_id}: {exc}")

    temporal_scale, spatial_scale = pipeline_scales(pipeline)
    width = snap_dimension(int(inputs.get("width") or meta["default_width"]), spatial_scale)
    height = snap_dimension(int(inputs.get("height") or meta["default_height"]), spatial_scale)
    fps = int(inputs.get("fps") or meta["fps"])

    segment_frames = snap_frames(
        int(inputs.get("segment_frames") or meta["default_num_frames"]), temporal_scale
    )

    # Requested length: explicit num_frames wins, else duration_seconds, else
    # the model's native single-pass clip length.
    if inputs.get("num_frames"):
        total_frames = int(inputs["num_frames"])
    elif inputs.get("duration_seconds"):
        total_frames = max(1, round(float(inputs["duration_seconds"]) * fps))
    else:
        total_frames = segment_frames

    if operation == "text_to_image":
        total_frames = segment_frames = 1

    steps = int(inputs.get("num_inference_steps") or meta["default_steps"])
    guidance_scale = float(inputs.get("guidance_scale") or meta["default_guidance"])
    guidance_scale_2 = inputs.get("guidance_scale_2")
    negative_prompt = inputs.get("negative_prompt", DEFAULT_NEGATIVE_PROMPT)
    seed = inputs.get("seed")
    strength = float(inputs.get("strength", 0.8))

    output_path = Path(
        inputs.get("output_path")
        or f"{tool_name}_{variant_key}_{operation}.{'png' if operation == 'text_to_image' else 'mp4'}"
    )

    # Only text_to_video and image_to_video can be continued from a last frame.
    # The rest are single-pass, so a long duration request is clamped to what the
    # model can actually denoise at once rather than being sent to certain OOM.
    chainable = operation in {"text_to_video", "image_to_video"}
    clamped_from = None
    if chainable:
        segment_count = plan_segments(total_frames, segment_frames)
    else:
        segment_count = 1
        if total_frames > segment_frames:
            clamped_from = total_frames
            total_frames = segment_frames
    progress = inputs.get("progress_callback")

    try:
        if segment_count > 1:
            frames, segment_log = _generate_chained(
                pipeline,
                operation=operation,
                inputs=inputs,
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                segment_frames=segment_frames,
                total_frames=total_frames,
                segment_count=segment_count,
                steps=steps,
                guidance_scale=guidance_scale,
                guidance_scale_2=guidance_scale_2,
                seed=seed,
                correct_drift=inputs.get("correct_drift", True),
                progress=progress,
            )
        else:
            frames = _generate_single(
                pipeline,
                operation=operation,
                inputs=inputs,
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                num_frames=snap_frames(total_frames, temporal_scale)
                if total_frames > 1
                else 1,
                steps=steps,
                guidance_scale=guidance_scale,
                guidance_scale_2=guidance_scale_2,
                seed=seed,
                strength=strength,
            )
            segment_log = [{"index": 0, "frames": len(frames), "operation": operation}]
    except Exception as exc:
        return _oom_aware_error(exc, variant_key, precision, offload_mode, width, height, total_frames)

    if operation == "text_to_image":
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frames[0].save(output_path)
        artifact_kind = "image"
    else:
        frames = frames[:total_frames]
        export_frames(frames, output_path, fps)
        artifact_kind = "video"

    from tools.video._shared import probe_output

    data = {
        "provider": tool_name,
        "model_variant": variant_key,
        "provider_name": meta["name"],
        "mode": "local",
        "operation": operation,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "model_id": model_id,
        "precision": precision,
        "offload_mode": offload_mode if enable_offload else "none",
        "width": width,
        "height": height,
        "fps": fps,
        "num_frames": len(frames),
        "duration_seconds": round(len(frames) / fps, 2),
        "segments": segment_count,
        "segment_frames": segment_frames,
        "clamped_from_frames": clamped_from,
        "segment_log": segment_log,
        "num_inference_steps": steps,
        "guidance_scale": guidance_scale,
        "output": str(output_path),
        "format": "png" if artifact_kind == "image" else "mp4",
        "license": meta["license"],
    }
    if artifact_kind == "video":
        data.update(probe_output(output_path))

    return ToolResult(
        success=True,
        data=data,
        artifacts=[str(output_path)],
        seed=seed,
        model=model_id,
    )


def derive_pipeline(base, target_operation: str):
    """Build a sibling Wan pipeline that shares ``base``'s loaded weights.

    Chained generation starts in text-to-video and continues in image-to-video.
    Both tasks run the same checkpoint, so re-reading tens of GB from disk just
    to change pipeline class would dominate the runtime.  Instead the modules
    are handed to the other class directly; components that class declares but
    this checkpoint lacks (Wan 2.2 TI2V has no CLIP image encoder) are optional
    and resolve to ``None``.  Falls back to a plain reload if anything about the
    checkpoint makes the shortcut invalid.
    """
    import inspect

    import diffusers

    target_name = _PIPELINE_FOR_OPERATION[target_operation]
    if type(base).__name__ == target_name:
        return base

    target_class = getattr(diffusers, target_name)
    components = dict(base.components)
    config = dict(base.config)

    kwargs: dict[str, Any] = {}
    for name in list(inspect.signature(target_class.__init__).parameters)[1:]:
        if name in components:
            kwargs[name] = components[name]
        elif name in config:
            kwargs[name] = config[name]
        else:
            kwargs[name] = None

    # Offload hooks belong to whichever pipeline installed them; move them over
    # rather than leaving two pipelines fighting over the same modules.
    offloaded = getattr(base, "_all_hooks", None)
    sequential = getattr(base, "_is_sequentially_offloaded", False)
    if offloaded:
        base.remove_all_hooks()

    derived = target_class(**kwargs)
    if sequential:
        derived.enable_sequential_cpu_offload()
    elif offloaded:
        derived.enable_model_cpu_offload()

    vae = getattr(derived, "vae", None)
    if vae is not None:
        if hasattr(vae, "enable_tiling"):
            vae.enable_tiling()
        if hasattr(vae, "enable_slicing"):
            vae.enable_slicing()
    return derived


def _generate_single(
    pipeline,
    *,
    operation: str,
    inputs: dict[str, Any],
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    num_frames: int,
    steps: int,
    guidance_scale: float,
    guidance_scale_2: float | None,
    seed: int | None,
    strength: float,
) -> list:
    image = last_image = video = None

    if operation in {"image_to_video", "first_last_frame"}:
        image = load_image(
            inputs.get("reference_image_path"), inputs.get("reference_image_url"), width, height
        )
    if operation == "first_last_frame":
        last_image = load_image(
            inputs.get("last_image_path"), inputs.get("last_image_url"), width, height
        )
    if operation == "video_to_video":
        source = inputs.get("source_video_path")
        if not source:
            raise ValueError("video_to_video requires source_video_path")
        video = load_video_frames(source, width, height, num_frames)
        # This pipeline takes its length from the clip rather than num_frames,
        # so the clip itself must land on a latent boundary.
        usable = snap_frames(len(video))
        if usable > len(video):
            usable -= _DEFAULT_TEMPORAL_SCALE
        video = video[: max(1, usable)]

    return _run_pass(
        pipeline,
        operation=operation,
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        num_frames=num_frames,
        steps=steps,
        guidance_scale=guidance_scale,
        guidance_scale_2=guidance_scale_2,
        seed=seed,
        image=image,
        last_image=last_image,
        video=video,
        strength=strength,
    )


def _generate_chained(
    pipeline,
    *,
    operation: str,
    inputs: dict[str, Any],
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    segment_frames: int,
    total_frames: int,
    segment_count: int,
    steps: int,
    guidance_scale: float,
    guidance_scale_2: float | None,
    seed: int | None,
    correct_drift: bool,
    progress,
) -> tuple[list, list[dict[str, Any]]]:
    """Produce a long clip by chaining image-to-video off each segment's last frame.

    Wan models are trained for roughly five seconds per pass; anything longer is
    built by continuation.  Each segment after the first is seeded with the
    previous segment's final frame, which it regenerates as its own frame 0 —
    that duplicate is dropped when the segments are joined so the seam lands on
    a single shared frame.

    ``segment_prompts`` lets a caller drive the clip through a shot list; with a
    single prompt every segment is asked for the same thing, which reads as one
    continuous take.
    """
    segment_prompts = inputs.get("segment_prompts") or []
    frames: list = []
    log: list[dict[str, Any]] = []
    reference_stats = None
    anchor = None

    for index in range(segment_count):
        segment_prompt = (
            segment_prompts[index] if index < len(segment_prompts) else prompt
        )
        segment_seed = None if seed is None else seed + index

        if index == 0:
            segment_operation = operation
            if operation == "image_to_video":
                anchor = load_image(
                    inputs.get("reference_image_path"),
                    inputs.get("reference_image_url"),
                    width,
                    height,
                )
        else:
            segment_operation = "image_to_video"

        if index > 0:
            # No-op once the chain is already running on the I2V pipeline.
            pipeline = derive_pipeline(pipeline, "image_to_video")

        if progress:
            progress(index + 1, segment_count, segment_prompt)

        produced = _run_pass(
            pipeline,
            operation=segment_operation,
            prompt=segment_prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            num_frames=segment_frames,
            steps=steps,
            guidance_scale=guidance_scale,
            guidance_scale_2=guidance_scale_2,
            seed=segment_seed,
            image=anchor if segment_operation == "image_to_video" else None,
        )

        if index == 0:
            reference_stats = channel_stats(produced)
            kept = produced
        else:
            if correct_drift and reference_stats is not None:
                produced = match_channel_stats(produced, reference_stats)
            # Frame 0 is the anchor the model was handed; keep the original.
            kept = produced[1:]

        frames.extend(kept)
        anchor = frames[-1]
        log.append(
            {
                "index": index,
                "operation": segment_operation,
                "prompt": segment_prompt,
                "seed": segment_seed,
                "frames_generated": len(produced),
                "frames_kept": len(kept),
                "cumulative_frames": len(frames),
            }
        )

        if len(frames) >= total_frames:
            break

    return frames, log


# When the installed NVIDIA userspace libraries do not match the loaded kernel
# module, nvmlInit fails.  PyTorch calls it while composing an out-of-memory
# report, so on such a machine every OOM — and several unrelated allocator
# paths — surface as this assert instead of the real error.
_NVML_ASSERT_MARKER = "nvmlInit"


def _oom_aware_error(
    exc: Exception,
    variant: str,
    precision: str,
    offload_mode: str,
    width: int,
    height: int,
    frames: int,
):
    """Turn an allocator failure into advice the caller can act on."""
    from tools.base_tool import ToolResult

    free_wan_pipelines()
    message = str(exc)

    if _NVML_ASSERT_MARKER in message:
        return ToolResult(
            success=False,
            error=(
                "The NVIDIA driver on this machine is in a mismatched state: the loaded "
                "kernel module and the installed userspace libraries are different versions, "
                "so nvmlInit fails. CUDA compute still runs, but PyTorch calls NVML while "
                "reporting an out-of-memory condition, so real OOMs surface as an internal "
                "assert and bitsandbytes quantization cannot load at all. Reboot to load the "
                "matching kernel module (check with 'cat /proc/driver/nvidia/version' against "
                "'nvidia-smi'). Until then, stay on precision=\"bf16\" and reduce resolution "
                "or segment_frames so generation never reaches the OOM path."
            ),
        )

    if "out of memory" not in message.lower():
        return ToolResult(success=False, error=f"Wan generation failed: {exc}")

    smaller = f"{max(320, (width * 2) // 3)}x{max(320, (height * 2) // 3)}"
    hints = []
    if offload_mode != "sequential":
        hints.append('set offload_mode="sequential" to free the card for activations')
    next_precision = {"bf16": "int8", "int8": "int4"}.get(precision)
    if next_precision:
        hints.append(f'set precision="{next_precision}"')
    hints.append(f"lower the resolution (try around {smaller})")
    hints.append("reduce segment_frames")
    return ToolResult(
        success=False,
        error=(
            f"Ran out of GPU memory generating {width}x{height} x{frames} frames with "
            f"{variant} at {precision} (offload_mode={offload_mode}). "
            "Try one of: " + "; ".join(hints) + "."
        ),
    )
