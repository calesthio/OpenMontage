"""Live run of every ComfyUI-backed capability against a real server.

This is the check that the tools, the bundled graphs and a ComfyUI server
agree, which the faked contract tests cannot give: a graph can be valid JSON
and still be refused by ``/prompt``. It generates real media on the GPU behind
``COMFYUI_SERVER_URL`` (default ``http://localhost:8188``, e.g. an SSH tunnel
to a rented machine), so it is opt-in and takes several minutes:

    OPENMONTAGE_ALLOW_NETWORK=1 .venv/bin/python -m pytest \
        tests/tools/test_comfyui_live_gpu.py -m live_api -v -s

Set ``OPENMONTAGE_LIVE_OUTPUT_DIR`` to keep the generated files for a look and
a listen. The tests run in file order and later ones reuse earlier outputs (the
image becomes the first frame of the image-to-video clip, the designed voice
becomes the cloning reference). A test whose capability the server lacks is
skipped with the reason.

Nothing here names a model family: the selectors and the tools must run on
whatever the server has installed.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import pytest

from tools._comfyui.client import ComfyUIClient
from tools.base_tool import ToolStatus
from tools.tool_registry import registry

pytestmark = pytest.mark.live_api

NARRATION = "Open weights can now draw, film, score and narrate a short video."
SECOND_LINE = "This second line is spoken in the same voice as the first one."

_outputs: dict[str, Path] = {}
_timings: dict[str, float] = {}


@pytest.fixture(scope="module")
def tools():
    client = ComfyUIClient()
    if not client.is_available():
        pytest.skip(f"no ComfyUI server at {client.server_url}")
    registry.discover()
    return registry


@pytest.fixture(scope="module")
def out_dir(tmp_path_factory) -> Path:
    configured = os.environ.get("OPENMONTAGE_LIVE_OUTPUT_DIR")
    path = Path(configured) if configured else tmp_path_factory.mktemp("comfyui_live")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _require_available(tool) -> None:
    status = tool.get_status()
    if status != ToolStatus.AVAILABLE:
        pytest.skip(f"{tool.name} is {status.value} on this server")


def _probe(path: Path) -> dict:
    if not shutil.which("ffprobe"):
        pytest.skip("ffprobe is needed to inspect the generated media")
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    return json.loads(proc.stdout)


def _streams(info: dict, kind: str) -> list[dict]:
    return [s for s in info["streams"] if s["codec_type"] == kind]


def _run(name: str, tool, inputs: dict):
    started = time.time()
    result = tool.execute(inputs)
    _timings[name] = round(time.time() - started, 1)
    assert result.success, f"{name} failed: {result.error}"
    print(f"\n[{name}] {_timings[name]} s -> {result.data.get('output')}")
    return result


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


# ------------------------------------------------------------------
# Preflight
# ------------------------------------------------------------------


def test_preflight_lists_comfyui_for_every_capability_it_serves(tools):
    summary = tools.provider_menu_summary()
    by_capability = {c["capability"]: c for c in summary["capabilities"]}
    missing = [
        capability
        for capability in ("image_generation", "video_generation", "music_generation", "tts")
        if "comfyui" not in by_capability[capability]["available_providers"]
    ]
    assert not missing, f"preflight does not list comfyui as available for: {missing}"


# ------------------------------------------------------------------
# Image, video
# ------------------------------------------------------------------


def test_image_through_the_selector_without_naming_a_model(tools, out_dir):
    image_tool = tools.get("comfyui_image")
    _require_available(image_tool)
    expected_family = image_tool.get_info()["default_model_family"]

    result = _run(
        "image",
        tools.get("image_selector"),
        {
            "prompt": (
                "A lighthouse on a rocky coast at golden hour, waves breaking on "
                "the rocks, warm side light, wide cinematic photograph"
            ),
            "allowed_providers": ["comfyui"],
            "width": 1344,
            "height": 768,
            "seed": 7,
            "output_path": str(out_dir / "live_image.png"),
        },
    )
    assert result.data["selected_tool"] == "comfyui_image"
    assert result.data["model_family"] == expected_family
    assert result.data["model_family_auto_selected"] is True

    from PIL import Image

    path = Path(result.data["output"])
    with Image.open(path) as image:
        assert image.size == (1344, 768)
    _outputs["image"] = path


def test_text_to_video_through_the_selector_without_naming_a_model(tools, out_dir):
    video_tool = tools.get("comfyui_video")
    _require_available(video_tool)
    expected_family = video_tool.get_info()["default_model_family"]["text_to_video"]

    result = _run(
        "text_to_video",
        tools.get("video_selector"),
        {
            "prompt": (
                "A lighthouse on a rocky coast at golden hour. Waves roll in and "
                "break on the rocks, sea spray drifts, the camera slowly pushes in. "
                "Sound of surf and distant gulls."
            ),
            "operation": "text_to_video",
            "allowed_providers": ["comfyui"],
            "duration": 4,
            "seed": 7,
            "timeout_seconds": 1500,
            "output_path": str(out_dir / "live_t2v.mp4"),
        },
    )
    assert result.data["selected_tool"] == "comfyui_video"
    assert result.data["model_family"] == expected_family
    assert result.data["model_family_auto_selected"] is True

    info = _probe(Path(result.data["output"]))
    video = _streams(info, "video")
    assert len(video) == 1
    assert (video[0]["width"], video[0]["height"]) == (
        result.data["width"],
        result.data["height"],
    )
    assert float(info["format"]["duration"]) == pytest.approx(
        result.data["duration_seconds"], abs=0.3
    )
    if result.data.get("has_audio"):
        assert _streams(info, "audio"), "the tool reported audio but the file has none"
    _outputs["text_to_video"] = Path(result.data["output"])


def test_image_to_video_starts_from_the_generated_image(tools, out_dir):
    video_tool = tools.get("comfyui_video")
    _require_available(video_tool)
    if "image" not in _outputs:
        pytest.skip("needs the image from the image test")

    result = _run(
        "image_to_video",
        tools.get("video_selector"),
        {
            "prompt": (
                "The waves keep rolling in and breaking on the rocks, the "
                "lighthouse lamp turns on, the camera holds steady. Sound of surf."
            ),
            "operation": "image_to_video",
            "allowed_providers": ["comfyui"],
            "reference_image_path": str(_outputs["image"]),
            "duration": 4,
            "seed": 7,
            "timeout_seconds": 1500,
            "output_path": str(out_dir / "live_i2v.mp4"),
        },
    )
    assert result.data["selected_tool"] == "comfyui_video"
    info = _probe(Path(result.data["output"]))
    video = _streams(info, "video")
    assert len(video) == 1
    # The canvas follows the 1344x768 reference image.
    assert (video[0]["width"], video[0]["height"]) == (1344, 768)
    _outputs["image_to_video"] = Path(result.data["output"])


# ------------------------------------------------------------------
# Music
# ------------------------------------------------------------------


def test_music(tools, out_dir):
    music_tool = tools.get("comfyui_music")
    _require_available(music_tool)
    result = _run(
        "music",
        music_tool,
        {
            "prompt": "calm cinematic ambient, soft piano, warm strings, slow, instrumental",
            "duration_seconds": 10,
            "seed": 7,
            "output_path": str(out_dir / "live_music.mp3"),
        },
    )
    info = _probe(Path(result.data["output"]))
    assert _streams(info, "audio")
    assert float(info["format"]["duration"]) == pytest.approx(10, abs=1.5)


# ------------------------------------------------------------------
# Speech
# ------------------------------------------------------------------


def test_speech_with_the_default_designed_voice(tools, out_dir):
    tts_tool = tools.get("comfyui_tts")
    _require_available(tts_tool)
    result = _run(
        "tts_design",
        tts_tool,
        {"text": NARRATION, "output_path": str(out_dir / "live_tts_design.wav")},
    )
    assert result.data["voice_mode"] == "design"
    info = _probe(Path(result.data["output"]))
    audio = _streams(info, "audio")
    assert audio and audio[0]["codec_name"].startswith("pcm"), "a .wav must hold PCM"
    assert 2.0 < float(info["format"]["duration"]) < 15.0
    _outputs["tts_design"] = Path(result.data["output"])


def test_speech_through_the_selector_picks_comfyui(tools, out_dir):
    _require_available(tools.get("comfyui_tts"))
    result = _run(
        "tts_selector",
        tools.get("tts_selector"),
        {
            "text": SECOND_LINE,
            "allowed_providers": ["comfyui"],
            "output_path": str(out_dir / "live_tts_selector.wav"),
        },
    )
    assert result.data["selected_tool"] == "comfyui_tts"


def test_speech_cloned_from_an_uploaded_reference(tools, out_dir):
    tts_tool = tools.get("comfyui_tts")
    _require_available(tts_tool)
    if "tts_design" not in _outputs:
        pytest.skip("needs the take from the designed-voice test as reference")
    result = _run(
        "tts_clone_upload",
        tts_tool,
        {
            "text": SECOND_LINE,
            "reference_audio_path": str(_outputs["tts_design"]),
            "reference_text": NARRATION,
            "output_path": str(out_dir / "live_tts_clone_upload.wav"),
        },
    )
    assert result.data["voice_mode"] == "clone"
    assert result.data["voice"].startswith("om_ref_")
    _outputs["tts_clone_upload"] = Path(result.data["output"])


def test_speech_cloned_from_a_voice_on_the_server(tools, out_dir):
    tts_tool = tools.get("comfyui_tts")
    _require_available(tts_tool)
    voices = [
        v for v in tts_tool.get_info()["server_voices"] if not v.startswith("om_ref_")
    ]
    library = [v for v in voices if v.startswith("style_")] or voices
    if not library:
        pytest.skip("the server has no reference voice in ComfyUI/input")
    voice = Path(library[0]).stem
    result = _run(
        "tts_clone_server_voice",
        tts_tool,
        {
            "text": SECOND_LINE,
            "voice": voice,
            "output_path": str(out_dir / "live_tts_clone_server.mp3"),
        },
    )
    assert result.data["voice"] == library[0]
    info = _probe(Path(result.data["output"]))
    assert _streams(info, "audio")[0]["codec_name"] == "mp3"


# ------------------------------------------------------------------
# Speech back to text
# ------------------------------------------------------------------


@pytest.mark.parametrize(
    "key, spoken",
    [("tts_design", NARRATION), ("tts_clone_upload", SECOND_LINE)],
)
def test_transcriber_hears_the_words_that_were_asked_for(tools, out_dir, key, spoken):
    transcriber = tools.get("transcriber")
    _require_available(transcriber)
    if key not in _outputs:
        pytest.skip(f"needs the take from the {key} test")
    result = _run(
        f"transcribe_{key}",
        transcriber,
        {
            "input_path": str(_outputs[key]),
            "model_size": "small",
            "language": "en",
            "output_dir": str(out_dir / f"stt_{key}"),
        },
    )
    heard = _words(" ".join(s.get("text", "") for s in result.data["segments"]))
    wanted = _words(spoken)
    missing = [word for word in wanted if word not in heard]
    assert len(missing) <= max(1, len(wanted) // 5), (
        f"asked for {wanted}, heard {heard}"
    )
    assert result.data["word_timestamps"], "captions need word timings"


def test_report_timings():
    """Not a check: prints what each generation took on this server."""
    print("\nseconds per step:", json.dumps(_timings, indent=2))
