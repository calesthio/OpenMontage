"""Contract tests for the bundled open-weight ComfyUI workflows.

Covers the MiniMax H3 local T2V/I2V graphs and the Qwen-Image-2.1 text-to-image
graph. No ComfyUI server is needed: the client is faked.

The bundled graphs are hand-written API-format versions of the official
Comfy-Org templates (``video_minimax_h3_t2v``, ``video_minimax_h3_i2v``,
``image_qwen_image_2_1_t2i``), whose UI-format JSON cannot be submitted to
``/prompt`` directly. These tests check what each node *is* and how it is
wired, not only that an id exists, because a structurally valid graph with a
wrong node still produces plausible-looking output.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools._comfyui.metadata import BUNDLED_MODEL_STACKS
from tools.graphics.comfyui_image import ComfyUIImage
from tools.video.comfyui_video import (
    ComfyUIVideo,
    h3_canvas_for_ratio,
    h3_frame_count,
    h3_snap_canvas,
)

WORKFLOW_DIR = (
    Path(__file__).resolve().parent.parent.parent / "tools" / "_comfyui" / "workflows"
)

H3_STACK = "minimax-h3-local"
QWEN_STACK = "qwen-image-2-1-t2i"


def _load(name: str) -> dict:
    with open(WORKFLOW_DIR / name) as f:
        return json.load(f)


def _assert_valid_api_graph(graph: dict) -> None:
    assert graph, "empty workflow"
    for node_id, node in graph.items():
        assert isinstance(node_id, str)
        assert set(node) == {"class_type", "inputs"}, (
            f"node {node_id} must be exactly class_type + inputs (UI-format "
            f"fields do not belong in an API graph): {sorted(node)}"
        )
        for key, value in node["inputs"].items():
            if isinstance(value, list):
                assert len(value) == 2 and isinstance(value[0], str) and isinstance(
                    value[1], int
                ), f"{node_id}.{key} is not a [node_id, slot] link: {value!r}"
                assert value[0] in graph, (
                    f"{node_id}.{key} links to missing node {value[0]!r}"
                )


_LOADER_FIELDS = {
    "UNETLoader": "unet_name",
    "CLIPLoader": "clip_name",
    "VAELoader": "vae_name",
    "LoraLoaderModelOnly": "lora_name",
}


def _model_files(graph: dict) -> set[str]:
    return {
        node["inputs"][_LOADER_FIELDS[node["class_type"]]]
        for node in graph.values()
        if node["class_type"] in _LOADER_FIELDS
    }


def _classes(graph: dict) -> set[str]:
    return {node["class_type"] for node in graph.values()}


# ------------------------------------------------------------------
# MiniMax H3: bundled graphs
# ------------------------------------------------------------------

H3_WORKFLOWS = ["minimax-h3-t2v.json", "minimax-h3-i2v.json"]


@pytest.mark.parametrize("filename", H3_WORKFLOWS)
def test_h3_workflow_is_a_valid_api_graph(filename):
    _assert_valid_api_graph(_load(filename))


@pytest.mark.parametrize("filename", H3_WORKFLOWS)
def test_h3_workflow_wiring(filename):
    g = _load(filename)
    h3 = g["131"]
    assert h3["class_type"] == "MiniMaxH3ImageToVideo"
    # Text encoder and the *video* VAE feed the conditioning node.
    assert h3["inputs"]["clip"] == ["128", 0]
    assert h3["inputs"]["vae"] == ["119", 0]
    # Sampling: positive conditioning -> guider, empty AV latent -> sampler.
    assert g["126"]["class_type"] == "BasicGuider"
    assert g["126"]["inputs"]["conditioning"] == ["131", 0]
    assert g["126"]["inputs"]["model"] == ["127", 0]
    assert g["125"]["class_type"] == "SamplerCustomAdvanced"
    assert g["125"]["inputs"]["latent_image"] == ["131", 1]
    assert g["125"]["inputs"]["guider"] == ["126", 0]
    assert g["125"]["inputs"]["noise"] == ["129", 0]
    assert g["124"]["class_type"] == "BasicScheduler"
    assert g["124"]["inputs"]["model"] == ["127", 0]
    # Video and audio are decoded from the same sampler output with their own VAE.
    assert g["122"]["class_type"] == "VAEDecode"
    assert g["122"]["inputs"]["vae"] == ["119", 0]
    assert g["121"]["class_type"] == "VAEDecodeAudio"
    assert g["121"]["inputs"]["vae"] == ["120", 0]
    assert g["122"]["inputs"]["samples"] == g["121"]["inputs"]["samples"] == ["125", 0]
    # Muxed into one mp4 at H3's native 24 fps, then saved.
    assert g["130"]["class_type"] == "CreateVideo"
    assert g["130"]["inputs"]["fps"] == 24
    assert g["130"]["inputs"]["images"] == ["122", 0]
    assert g["130"]["inputs"]["audio"] == ["121", 0]
    assert g["92"]["class_type"] == "SaveVideo"
    assert g["92"]["inputs"]["video"] == ["130", 0]


@pytest.mark.parametrize("filename", H3_WORKFLOWS)
def test_h3_workflow_is_base_mode_without_turbo_lora(filename):
    """The bundled graph is the 20-step base path.

    A LoRA loader or switch node would make the graph depend on a file that
    ``check_models`` does not require for base mode.
    """
    g = _load(filename)
    assert not _classes(g) & {"LoraLoaderModelOnly", "ComfySwitchNode"}
    assert g["124"]["inputs"]["steps"] == 20
    assert g["123"]["inputs"]["sampler_name"] == "res_multistep"


def test_h3_t2v_has_no_keyframes():
    g = _load("minimax-h3-t2v.json")
    assert "first_frame" not in g["131"]["inputs"]
    assert "last_frame" not in g["131"]["inputs"]
    assert "LoadImage" not in _classes(g)


def test_h3_i2v_feeds_first_frame_from_load_image():
    g = _load("minimax-h3-i2v.json")
    assert g["114"]["class_type"] == "LoadImage"
    assert g["131"]["inputs"]["first_frame"] == ["114", 0]
    assert "last_frame" not in g["131"]["inputs"]


@pytest.mark.parametrize("filename", H3_WORKFLOWS)
def test_h3_workflow_models_match_the_metadata_stack(filename):
    """Graph loaders and ``check_models`` must name exactly the same files."""
    stack_names = {item["name"] for item in BUNDLED_MODEL_STACKS[H3_STACK]}
    assert _model_files(_load(filename)) == stack_names


def test_h3_stack_uses_the_fl2va_checkpoint_not_ref2va():
    """T2V/I2V need FL2VA; Ref2VA weights are not interchangeable."""
    diffusion = next(
        item for item in BUNDLED_MODEL_STACKS[H3_STACK] if item["role"] == "diffusion_model"
    )
    assert "fl2va" in diffusion["name"]
    assert "ref2va" not in diffusion["name"]


def test_h3_stack_entries_are_downloadable_from_the_comfy_org_repo():
    for item in BUNDLED_MODEL_STACKS[H3_STACK]:
        assert "Comfy-Org/MiniMax-H3" in item["download_url"], item["name"]
        assert item["destination_hint"].startswith("ComfyUI/models/"), item["name"]


# ------------------------------------------------------------------
# MiniMax H3: frame count and canvas helpers
# ------------------------------------------------------------------


@pytest.mark.parametrize(
    "seconds, frames",
    # 4 s = 96 frames; the 17k+5 grid runs ... 90, 107, ... so it snaps up to 107.
    [(1, 39), (4, 107), (5, 124), (10, 243), (15, 362)],
)
def test_h3_frame_count_known_values(seconds, frames):
    assert h3_frame_count(seconds) == frames


def test_h3_frame_count_is_always_on_the_17k_plus_5_grid_and_never_shorter():
    d = 1.0
    while d <= 15.0:
        n = h3_frame_count(d)
        assert (n - 5) % 17 == 0, (d, n)
        assert n >= round(d * 24), (d, n)
        d += 0.25


@pytest.mark.parametrize(
    "ratio, canvas",
    [
        ((16, 9), (1344, 768)),
        ((9, 16), (768, 1344)),
        ((1, 1), (768, 768)),
        ((4, 3), (1024, 768)),
        ((3, 4), (768, 1024)),
        # 21:9 at a 768 short edge would be 1792 wide, past the 1344 long edge.
        ((21, 9), (1344, 576)),
    ],
)
def test_h3_canvas_for_ratio(ratio, canvas):
    assert h3_canvas_for_ratio(*ratio) == canvas


def test_h3_canvas_for_ratio_accepts_pixel_sizes():
    assert h3_canvas_for_ratio(1920, 1080) == (1344, 768)
    assert h3_canvas_for_ratio(1080, 1920) == (768, 1344)


def test_h3_snap_canvas_rounds_to_the_nearest_multiple_of_32():
    # 1000 / 32 = 31.25 -> 31 * 32; 600 / 32 = 18.75 -> 19 * 32.
    assert h3_snap_canvas(1000, 600) == (992, 608)
    assert h3_snap_canvas(1344, 768) == (1344, 768)


@pytest.mark.parametrize("size", [(1920, 1080), (1376, 768), (1344, 800)])
def test_h3_snap_canvas_rejects_sizes_past_the_native_canvas(size):
    with pytest.raises(ValueError, match="1344"):
        h3_snap_canvas(*size)


# ------------------------------------------------------------------
# MiniMax H3: builder and execute()
# ------------------------------------------------------------------


def _video_tool(*, missing=(), generated=None):
    tool = ComfyUIVideo()
    tool._client.is_available = lambda: True
    tool._client.check_models = lambda required: (
        [m for m in required if m not in missing],
        [m for m in required if m in missing],
    )
    seen = generated if generated is not None else {}

    def fake_generate(workflow, output_node, dest, **_kwargs):
        seen["workflow"] = workflow
        seen["output_node"] = output_node
        return [Path(dest)]

    tool._client.generate = fake_generate
    return tool


def test_h3_t2v_builder_patches_the_nodes_it_owns():
    workflow, output_node, params = ComfyUIVideo()._build_h3_local(
        {"prompt": "A fox runs", "duration": 5},
        seed=7,
        output_path=Path("clip.mp4"),
        operation="text_to_video",
    )
    assert output_node == "92"
    assert workflow["131"]["inputs"]["prompt"] == "A fox runs"
    assert workflow["131"]["inputs"]["length"] == 124
    assert (workflow["131"]["inputs"]["width"], workflow["131"]["inputs"]["height"]) == (
        1344,
        768,
    )
    assert workflow["129"]["inputs"]["noise_seed"] == 7
    assert workflow["124"]["inputs"]["steps"] == 20
    assert workflow["92"]["inputs"]["filename_prefix"] == "video/clip"
    assert params == {"width": 1344, "height": 768, "num_frames": 124, "steps": 20}


def test_h3_builder_honours_steps_and_aspect_ratio():
    workflow, _, params = ComfyUIVideo()._build_h3_local(
        {"prompt": "p", "steps": 50, "aspect_ratio": "9:16", "duration": 10},
        seed=1,
        output_path=Path("c.mp4"),
        operation="text_to_video",
    )
    assert workflow["124"]["inputs"]["steps"] == 50
    assert (params["width"], params["height"]) == (768, 1344)
    assert (workflow["131"]["inputs"]["width"], workflow["131"]["inputs"]["height"]) == (
        768,
        1344,
    )
    assert workflow["131"]["inputs"]["length"] == 243


def test_h3_i2v_builder_uploads_the_image_and_matches_the_canvas_to_its_aspect(tmp_path):
    """``first_frame`` is stretched to the canvas, so the canvas must follow the image."""
    from PIL import Image

    landscape = tmp_path / "land.png"
    portrait = tmp_path / "port.png"
    Image.new("RGB", (1920, 1080)).save(landscape)
    Image.new("RGB", (1080, 1920)).save(portrait)

    tool = ComfyUIVideo()
    uploads = []
    tool._client.upload_image = (
        lambda local_path, name: uploads.append((local_path, name)) or "srv.png"
    )

    workflow, _, params = tool._build_h3_local(
        {"prompt": "p", "reference_image_path": str(landscape)},
        seed=1,
        output_path=tmp_path / "out.mp4",
        operation="image_to_video",
    )
    assert workflow["114"]["inputs"]["image"] == "srv.png"
    assert (params["width"], params["height"]) == (1344, 768)
    assert uploads and uploads[0][0] == landscape

    _, _, params = tool._build_h3_local(
        {"prompt": "p", "reference_image_path": str(portrait)},
        seed=1,
        output_path=tmp_path / "out.mp4",
        operation="image_to_video",
    )
    assert (params["width"], params["height"]) == (768, 1344)


def test_h3_i2v_requires_a_reference_image():
    from tools._comfyui.client import ComfyUIError

    with pytest.raises(ComfyUIError, match="reference_image"):
        ComfyUIVideo()._build_h3_local(
            {"prompt": "p"},
            seed=1,
            output_path=Path("o.mp4"),
            operation="image_to_video",
        )


def test_execute_h3_local_reports_missing_models_with_download_hints(tmp_path):
    names = [item["name"] for item in BUNDLED_MODEL_STACKS[H3_STACK]]
    tool = _video_tool(missing=names)
    result = tool.execute(
        {
            "prompt": "x",
            "model_family": "minimax_h3_local",
            "output_path": str(tmp_path / "o.mp4"),
        }
    )
    assert result.success is False
    assert result.data["workflow"] == "minimax-h3-t2v.json"
    assert {m["name"] for m in result.data["missing_models"]} == set(names)
    assert all(m["download_url"] for m in result.data["missing_models"])


def test_execute_h3_local_runs_the_bundled_workflow(tmp_path):
    seen = {}
    tool = _video_tool(generated=seen)
    result = tool.execute(
        {
            "prompt": "A fox runs",
            "model_family": "minimax_h3_local",
            "seed": 11,
            "output_path": str(tmp_path / "fox.mp4"),
        }
    )
    assert result.success, result.error
    assert seen["output_node"] == "92"
    assert seen["workflow"]["131"]["inputs"]["length"] == 124
    assert result.data["fps"] == 24
    assert result.data["num_frames"] == 124
    assert result.data["duration_seconds"] == round(124 / 24, 2)
    assert result.data["has_audio"] is True
    assert result.data["hosted"] is False
    assert (result.model or "").startswith("MiniMax-H3")
    prov = result.data["workflow_provenance"]
    assert prov["source"] == "bundled"
    assert prov["workflow"] == "minimax-h3-t2v.json"
    assert prov["workflow_hash_sha256"]
    assert {m["name"] for m in prov["model_stack"]} == {
        item["name"] for item in BUNDLED_MODEL_STACKS[H3_STACK]
    }


@pytest.mark.parametrize("duration", [2, 20])
def test_execute_h3_local_rejects_durations_outside_the_trained_range(tmp_path, duration):
    result = _video_tool().execute(
        {
            "prompt": "x",
            "model_family": "minimax_h3_local",
            "duration": duration,
            "output_path": str(tmp_path / "o.mp4"),
        }
    )
    assert result.success is False
    assert "duration" in (result.error or "")


def test_execute_h3_local_rejects_a_canvas_past_the_native_size(tmp_path):
    result = _video_tool().execute(
        {
            "prompt": "x",
            "model_family": "minimax_h3_local",
            "width": 1920,
            "height": 1080,
            "output_path": str(tmp_path / "o.mp4"),
        }
    )
    assert result.success is False
    assert "1344" in (result.error or "")


def test_execute_h3_local_custom_workflow_still_wins(tmp_path):
    seen = {}
    tool = _video_tool(generated=seen)
    result = tool.execute(
        {
            "prompt": "x",
            "model_family": "minimax_h3_local",
            "workflow_json": json.dumps({"99": {"class_type": "X", "inputs": {}}}),
            "output_node": "99",
            "output_path": str(tmp_path / "o.mp4"),
        }
    )
    assert result.success, result.error
    assert seen["output_node"] == "99"
    assert result.data["workflow_provenance"]["source"] == "user_supplied"


def test_h3_i2v_execute_uses_the_i2v_workflow(tmp_path):
    from PIL import Image

    ref = tmp_path / "ref.png"
    Image.new("RGB", (1280, 720)).save(ref)
    seen = {}
    tool = _video_tool(generated=seen)
    tool._client.upload_image = lambda _local_path, _name: "srv.png"
    result = tool.execute(
        {
            "prompt": "x",
            "operation": "image_to_video",
            "model_family": "minimax_h3_local",
            "reference_image_path": str(ref),
            "output_path": str(tmp_path / "o.mp4"),
        }
    )
    assert result.success, result.error
    assert seen["workflow"]["114"]["inputs"]["image"] == "srv.png"
    assert result.data["workflow_provenance"]["workflow"] == "minimax-h3-i2v.json"


def test_video_tool_info_lists_the_h3_stack():
    info = ComfyUIVideo().get_info()
    assert len(info["bundled_model_stacks"]["minimax_h3_local"]) == 4


# ------------------------------------------------------------------
# Qwen-Image-2.1: bundled graph
# ------------------------------------------------------------------


def test_qwen_workflow_is_a_valid_api_graph():
    _assert_valid_api_graph(_load("qwen-image-2-1-t2i.json"))


def test_qwen_workflow_wiring():
    g = _load("qwen-image-2-1-t2i.json")
    assert g["451"]["class_type"] == "UNETLoader"
    assert g["480"]["class_type"] == "QwenImage21Cache"
    assert g["480"]["inputs"]["model"] == ["451", 0]
    enc = g["452"]
    assert enc["class_type"] == "TextEncodeQwenImage21"
    assert enc["inputs"]["clip"] == ["453", 0]
    # Text-to-image: no reference images feed the encoder.
    assert not [k for k in enc["inputs"] if k.startswith("images")]
    ks = g["458"]
    assert ks["class_type"] == "KSampler"
    assert ks["inputs"]["model"] == ["480", 0]
    assert ks["inputs"]["positive"] == ["452", 0]
    assert ks["inputs"]["negative"] == ["452", 1]
    # T2I starts from an empty latent, not the encoder's reference-sized latent
    # (that output is for edits).
    assert g["456"]["class_type"] == "EmptyLatentImage"
    assert ks["inputs"]["latent_image"] == ["456", 0]
    assert g["457"]["class_type"] == "VAEDecode"
    assert g["457"]["inputs"]["samples"] == ["458", 0]
    assert g["457"]["inputs"]["vae"] == ["454", 0]
    assert g["461"]["class_type"] == "SaveImage"
    assert g["461"]["inputs"]["images"] == ["457", 0]


def test_qwen_workflow_omits_the_optional_prompt_enhancer():
    g = _load("qwen-image-2-1-t2i.json")
    assert not _classes(g) & {"TextGenerate", "ComfySwitchNode", "PreviewAny"}


def test_qwen_workflow_models_match_the_metadata_stack():
    stack = BUNDLED_MODEL_STACKS[QWEN_STACK]
    assert _model_files(_load("qwen-image-2-1-t2i.json")) == {i["name"] for i in stack}
    assert {i["role"] for i in stack} == {"diffusion_model", "text_encoder", "vae"}
    for item in stack:
        assert "Comfy-Org/Qwen-Image-2.1" in item["download_url"], item["name"]


def test_qwen_stack_uses_the_base_model_not_turbo():
    diffusion = next(
        i for i in BUNDLED_MODEL_STACKS[QWEN_STACK] if i["role"] == "diffusion_model"
    )
    assert "turbo" not in diffusion["name"]


# ------------------------------------------------------------------
# Qwen-Image-2.1: ComfyUIImage family handling
# ------------------------------------------------------------------


def _image_tool(*, missing=(), generated=None):
    tool = ComfyUIImage()
    tool._client.is_available = lambda: True
    tool._client.check_models = lambda required: (
        [m for m in required if m not in missing],
        [m for m in required if m in missing],
    )
    seen = generated if generated is not None else {}

    def fake_generate(workflow, output_node, dest, **_kwargs):
        seen["workflow"] = workflow
        seen["output_node"] = output_node
        return [Path(dest)]

    tool._client.generate = fake_generate
    return tool


def test_qwen_builder_patches_the_nodes_it_owns():
    workflow, output_node, params = ComfyUIImage()._build_workflow(
        "qwen_image_2.1",
        {"prompt": "a lighthouse", "negative_prompt": "blurry", "width": 1344, "height": 768},
        seed=5,
        output_path=Path("img.png"),
    )
    assert output_node == "461"
    assert workflow["452"]["inputs"]["prompt"] == "a lighthouse"
    assert workflow["452"]["inputs"]["negative_prompt"] == "blurry"
    assert workflow["456"]["inputs"]["width"] == 1344
    assert workflow["456"]["inputs"]["height"] == 768
    assert workflow["458"]["inputs"]["seed"] == 5
    assert workflow["461"]["inputs"]["filename_prefix"] == "img"
    # Qwen-Image-2.1 base runs at CFG 1; FLUX's 3.5 guidance default must not leak in.
    assert workflow["458"]["inputs"]["cfg"] == 1.0
    assert workflow["458"]["inputs"]["steps"] == 40
    assert params["guidance"] == 1.0 and params["steps"] == 40


def test_flux_builder_is_unchanged():
    workflow, output_node, params = ComfyUIImage()._build_workflow(
        "flux2",
        {"prompt": "a lighthouse", "width": 1024, "height": 1024},
        seed=5,
        output_path=Path("img.png"),
    )
    assert output_node == "13"
    assert workflow["4"]["inputs"]["text"] == "a lighthouse"
    assert workflow["5"]["inputs"]["guidance"] == 3.5
    assert workflow["7"]["inputs"]["noise_seed"] == 5
    assert workflow["10"]["inputs"]["steps"] == 20
    assert workflow["13"]["inputs"]["filename_prefix"] == "img"
    assert params["guidance"] == 3.5 and params["steps"] == 20


@pytest.mark.parametrize(
    "size",
    [
        (1000, 1000),  # not a multiple of 32
        (224, 1024),  # below the 256 minimum
        (2784, 1024),  # past the 2752 maximum side
        (2432, 2048),  # more than the native 2K area (2400 x 1792)
    ],
)
def test_qwen_builder_rejects_sizes_the_model_does_not_support(size):
    from tools._comfyui.client import ComfyUIError

    with pytest.raises(ComfyUIError, match="multiple of 32"):
        ComfyUIImage()._build_workflow(
            "qwen_image_2.1",
            {"prompt": "x", "width": size[0], "height": size[1]},
            seed=1,
            output_path=Path("i.png"),
        )


@pytest.mark.parametrize("size", [(1024, 1024), (1344, 768), (2400, 1792), (256, 256)])
def test_qwen_builder_accepts_supported_sizes(size):
    _, _, params = ComfyUIImage()._build_workflow(
        "qwen_image_2.1",
        {"prompt": "x", "width": size[0], "height": size[1]},
        seed=1,
        output_path=Path("i.png"),
    )
    assert (params["width"], params["height"]) == size


def test_flux_builder_does_not_apply_qwen_size_rules():
    """FLUX keeps accepting any size the caller passes, as before."""
    _, _, params = ComfyUIImage()._build_workflow(
        "flux2",
        {"prompt": "x", "width": 1000, "height": 600},
        seed=1,
        output_path=Path("i.png"),
    )
    assert (params["width"], params["height"]) == (1000, 600)


def test_execute_defaults_to_flux_and_reports_its_missing_models(tmp_path):
    flux_names = [i["name"] for i in BUNDLED_MODEL_STACKS["flux2-txt2img"]]
    result = _image_tool(missing=flux_names).execute(
        {"prompt": "x", "output_path": str(tmp_path / "i.png")}
    )
    assert result.success is False
    assert result.data["workflow"] == "flux2-txt2img.json"


def test_execute_qwen_reports_missing_models(tmp_path):
    names = [i["name"] for i in BUNDLED_MODEL_STACKS[QWEN_STACK]]
    result = _image_tool(missing=names).execute(
        {
            "prompt": "x",
            "model_family": "qwen_image_2.1",
            "output_path": str(tmp_path / "i.png"),
        }
    )
    assert result.success is False
    assert result.data["workflow"] == "qwen-image-2-1-t2i.json"
    assert {m["name"] for m in result.data["missing_models"]} == set(names)


def test_execute_qwen_runs_the_bundled_workflow(tmp_path):
    seen = {}
    result = _image_tool(generated=seen).execute(
        {
            "prompt": "a lighthouse",
            "model_family": "qwen_image_2.1",
            "seed": 9,
            "output_path": str(tmp_path / "i.png"),
        }
    )
    assert result.success, result.error
    assert seen["output_node"] == "461"
    assert result.model == "qwen-image-2.1"
    assert result.data["guidance"] == 1.0
    assert result.data["steps"] == 40
    prov = result.data["workflow_provenance"]
    assert prov["source"] == "bundled"
    assert prov["workflow"] == "qwen-image-2-1-t2i.json"
    assert {m["name"] for m in prov["model_stack"]} == {
        i["name"] for i in BUNDLED_MODEL_STACKS[QWEN_STACK]
    }


def test_execute_rejects_an_unknown_model_family(tmp_path):
    result = _image_tool().execute(
        {"prompt": "x", "model_family": "nope", "output_path": str(tmp_path / "i.png")}
    )
    assert result.success is False
    assert "model_family" in (result.error or "")


def test_image_status_is_available_when_either_family_is_complete():
    from tools.base_tool import ToolStatus

    flux = {i["name"] for i in BUNDLED_MODEL_STACKS["flux2-txt2img"]}
    qwen = {i["name"] for i in BUNDLED_MODEL_STACKS[QWEN_STACK]}
    everything = flux | qwen

    assert _image_tool(missing=flux).get_status() == ToolStatus.AVAILABLE
    assert _image_tool(missing=qwen).get_status() == ToolStatus.AVAILABLE
    assert _image_tool(missing=everything).get_status() == ToolStatus.DEGRADED


def test_image_tool_info_lists_both_stacks():
    info = ComfyUIImage().get_info()
    assert set(info["bundled_model_stacks"]) == {"flux2", "qwen_image_2.1"}
    # Existing consumers read the single-stack key.
    assert info["bundled_model_stack"] == BUNDLED_MODEL_STACKS["flux2-txt2img"]


def test_image_schema_advertises_model_family():
    prop = ComfyUIImage.input_schema["properties"]["model_family"]
    assert prop["enum"] == ["flux2", "qwen_image_2.1"]
    assert prop["default"] == "flux2"


# ------------------------------------------------------------------
# vast.ai guide stays in step with the metadata stacks
# ------------------------------------------------------------------

GUIDE = (
    Path(__file__).resolve().parent.parent.parent
    / "docs"
    / "vast-ai-open-weight-stack.md"
)


@pytest.mark.parametrize("stack", [H3_STACK, QWEN_STACK])
def test_vast_guide_downloads_every_file_in_the_bundled_stacks(stack):
    """The guide's download commands must name every file the tools check for."""
    text = GUIDE.read_text()
    for item in BUNDLED_MODEL_STACKS[stack]:
        assert item["name"] in text, f"{item['name']} missing from {GUIDE.name}"
        folder = item["destination_hint"].rstrip("/").split("/")[-1]
        line = next(ln for ln in text.splitlines() if item["name"] in ln and "fetch" in ln)
        assert folder in line, f"{item['name']} is fetched into the wrong folder: {line}"
