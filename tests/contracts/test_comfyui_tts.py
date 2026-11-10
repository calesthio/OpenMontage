"""Contract tests for comfyui_tts (VoxCPM2 speech through a ComfyUI server).

No ComfyUI server is needed: the client is faked. The node inputs pinned here
were read from ``/object_info`` of a live ComfyUI 0.44.0 with
``wildminder/ComfyUI-VoxCPM`` installed (2026-11-10), so a bundled graph that
drops a required input fails here and not on the GPU.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools._comfyui.client import ComfyUIClient, ComfyUIError
from tools.audio.comfyui_tts import ComfyUITTS
from tools.base_tool import ToolRuntime, ToolStatus, ToolTier

WORKFLOW_DIR = (
    Path(__file__).resolve().parent.parent.parent / "tools" / "_comfyui" / "workflows"
)
SKILLS_ROOT = Path(__file__).resolve().parent.parent.parent / ".agents" / "skills"

# Required inputs of the two VoxCPM nodes, as the live server reports them.
VOXCPM_TTS_REQUIRED = {
    "model_name",
    "lora_name",
    "text",
    "voice_design",
    "cfg",
    "steps",
    "normalize_text",
    "seed",
    "force_offload",
    "device",
    "dtype",
}
VOICE_CLONING_REQUIRED = {"trim_silence"}
VOICE_CLONING_OPTIONAL = {"prompt_text", "prompt_audio", "reference_audio"}


def _load(name: str) -> dict:
    with open(WORKFLOW_DIR / name) as f:
        return json.load(f)


def _tool(*, voices=("style_m_low_host.wav",), transcripts=None, seen=None):
    """A tool whose client never touches the network.

    *voices* are the audio files the server lists; *transcripts* maps a file
    name in ComfyUI/input to its text. *seen* collects what was submitted.
    """
    transcripts = dict(transcripts or {})
    seen = seen if seen is not None else {}
    tool = ComfyUITTS()
    tool._client.is_available = lambda: True
    tool._client.has_node = lambda node_class: True
    tool._client.list_input_audio = lambda: list(voices)
    tool._client.input_file_text = lambda name: transcripts.get(name)

    def fake_upload(local_path, name):
        seen["uploaded"] = (Path(local_path), name)
        return name

    def fake_generate(workflow, output_node, dest, **kwargs):
        seen["workflow"] = workflow
        seen["output_node"] = output_node
        seen["dest"] = Path(dest)
        seen["timeout"] = kwargs.get("timeout")
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(b"fLaC-fake")
        return [Path(dest)]

    def fake_transcode(source, target):
        seen["transcoded"] = (Path(source), Path(target))
        Path(target).write_bytes(b"converted")

    tool._client.upload_audio = fake_upload
    tool._client.generate = fake_generate
    tool._transcode = fake_transcode
    return tool


# ------------------------------------------------------------------
# Bundled graphs
# ------------------------------------------------------------------


@pytest.mark.parametrize("filename", ["voxcpm2-tts.json", "voxcpm2-clone.json"])
def test_workflow_is_a_valid_api_graph(filename):
    graph = _load(filename)
    for node_id, node in graph.items():
        assert set(node) == {"class_type", "inputs"}, node_id
        for key, value in node["inputs"].items():
            if isinstance(value, list):
                assert value[0] in graph, f"{node_id}.{key} links to a missing node"


@pytest.mark.parametrize("filename", ["voxcpm2-tts.json", "voxcpm2-clone.json"])
def test_tts_node_has_every_required_input_and_runs_voxcpm2(filename):
    node = _load(filename)["1"]
    assert node["class_type"] == "VoxCPM_TTS"
    assert VOXCPM_TTS_REQUIRED <= set(node["inputs"])
    assert node["inputs"]["model_name"] == "VoxCPM2"
    assert node["inputs"]["lora_name"] == "None"


@pytest.mark.parametrize("filename", ["voxcpm2-tts.json", "voxcpm2-clone.json"])
def test_workflow_saves_the_generated_audio_losslessly(filename):
    graph = _load(filename)
    assert graph["2"]["class_type"] == "SaveAudio"
    assert graph["2"]["inputs"]["audio"] == ["1", 0]


def test_design_workflow_has_no_reference_voice():
    graph = _load("voxcpm2-tts.json")
    assert "voice_config" not in graph["1"]["inputs"]
    assert {n["class_type"] for n in graph.values()} == {"VoxCPM_TTS", "SaveAudio"}


def test_clone_workflow_feeds_the_reference_into_the_tts_node():
    graph = _load("voxcpm2-clone.json")
    assert graph["3"]["class_type"] == "LoadAudio"
    cloning = graph["4"]
    assert cloning["class_type"] == "VoxCPM_VoiceCloning"
    assert VOICE_CLONING_REQUIRED <= set(cloning["inputs"])
    assert set(cloning["inputs"]) <= VOICE_CLONING_REQUIRED | VOICE_CLONING_OPTIONAL
    assert cloning["inputs"]["reference_audio"] == ["3", 0]
    assert cloning["inputs"]["prompt_audio"] == ["3", 0]
    assert graph["1"]["inputs"]["voice_config"] == ["4", 0]


# ------------------------------------------------------------------
# Tool contract
# ------------------------------------------------------------------


def test_identity_matches_the_other_comfyui_tools_and_the_tts_capability():
    tool = ComfyUITTS()
    assert tool.name == "comfyui_tts"
    assert tool.capability == "tts"
    assert tool.provider == "comfyui"
    assert tool.tier == ToolTier.VOICE
    assert tool.runtime == ToolRuntime.LOCAL_GPU
    assert tool.input_schema["required"] == ["text"]


def test_agent_skills_point_at_real_skills():
    for skill in ComfyUITTS.agent_skills:
        assert (SKILLS_ROOT / skill / "SKILL.md").is_file(), skill


def test_uses_its_own_server_override_env_var():
    assert ComfyUITTS()._client._capability_env_var == "COMFYUI_TTS_SERVER_URL"


def test_status_is_unavailable_without_a_server():
    tool = _tool()
    tool._client.is_available = lambda: False
    assert tool.get_status() == ToolStatus.UNAVAILABLE


def test_status_is_degraded_when_the_voxcpm_nodes_are_not_installed():
    tool = _tool()
    asked = []

    def has_node(node_class):
        asked.append(node_class)
        return False

    tool._client.has_node = has_node
    assert tool.get_status() == ToolStatus.DEGRADED
    assert asked == ["VoxCPM_TTS"]


def test_status_is_available_when_the_voxcpm_nodes_are_installed():
    assert _tool().get_status() == ToolStatus.AVAILABLE


def test_tts_selector_discovers_the_tool():
    from tools.audio.tts_selector import TTSSelector
    from tools.tool_registry import registry

    registry.discover()
    assert "comfyui_tts" in [tool.name for tool in TTSSelector()._providers()]


# ------------------------------------------------------------------
# execute(): voice design
# ------------------------------------------------------------------


def test_design_mode_patches_the_text_and_the_voice_description(tmp_path):
    seen = {}
    result = _tool(seen=seen).execute(
        {
            "text": "Black holes bend light.",
            "voice_description": "A calm woman with a low voice",
            "seed": 11,
            "output_path": str(tmp_path / "line.flac"),
        }
    )
    assert result.success, result.error
    inputs = seen["workflow"]["1"]["inputs"]
    assert inputs["text"] == "Black holes bend light."
    assert inputs["voice_design"] == "A calm woman with a low voice"
    assert inputs["seed"] == 11
    assert "voice_config" not in inputs
    assert seen["output_node"] == "2"
    assert result.data["voice_mode"] == "design"
    assert result.seed == 11


def test_a_call_with_only_text_gets_a_default_voice_and_a_fixed_seed(tmp_path):
    """The same narrator on every call, so sections of one script match."""
    first, second = {}, {}
    _tool(seen=first).execute({"text": "One.", "output_path": str(tmp_path / "a.flac")})
    _tool(seen=second).execute({"text": "Two.", "output_path": str(tmp_path / "b.flac")})
    a, b = first["workflow"]["1"]["inputs"], second["workflow"]["1"]["inputs"]
    assert a["voice_design"] and a["voice_design"] == b["voice_design"]
    assert a["seed"] == b["seed"] >= 0, "-1 would ask the node for a random seed"


def test_generation_settings_follow_the_tested_defaults_and_can_be_overridden(tmp_path):
    seen = {}
    tool = _tool(seen=seen)
    tool.execute({"text": "x", "output_path": str(tmp_path / "a.flac")})
    inputs = seen["workflow"]["1"]["inputs"]
    assert (inputs["cfg"], inputs["steps"]) == (2.0, 10)
    assert inputs["normalize_text"] is False
    # Offloading after each take leaves the VRAM to the video model.
    assert inputs["force_offload"] is True

    tool.execute(
        {
            "text": "x",
            "cfg": 2.5,
            "steps": 16,
            "normalize_text": True,
            "keep_model_loaded": True,
            "output_path": str(tmp_path / "b.flac"),
        }
    )
    inputs = seen["workflow"]["1"]["inputs"]
    assert (inputs["cfg"], inputs["steps"]) == (2.5, 16)
    assert inputs["normalize_text"] is True
    assert inputs["force_offload"] is False


# ------------------------------------------------------------------
# execute(): cloning a voice that is on the server
# ------------------------------------------------------------------


def test_server_voice_is_cloned_with_its_transcript(tmp_path):
    seen = {}
    tool = _tool(
        transcripts={"style_m_low_host.reference.txt": "สวัสดีครับ วันนี้มาเล่าให้ฟัง\n"},
        seen=seen,
    )
    result = tool.execute(
        {
            "text": "Hello there.",
            "voice": "style_m_low_host",
            "output_path": str(tmp_path / "line.flac"),
        }
    )
    assert result.success, result.error
    graph = seen["workflow"]
    assert graph["3"]["inputs"]["audio"] == "style_m_low_host.wav"
    assert graph["4"]["inputs"]["prompt_text"] == "สวัสดีครับ วันนี้มาเล่าให้ฟัง"
    assert graph["4"]["inputs"]["prompt_audio"] == ["3", 0]
    assert graph["1"]["inputs"]["voice_config"] == ["4", 0]
    assert graph["1"]["inputs"]["voice_design"] == ""
    assert result.data["voice_mode"] == "clone"
    assert result.data["voice"] == "style_m_low_host.wav"


def test_server_voice_without_a_transcript_is_cloned_from_the_audio_alone(tmp_path):
    seen = {}
    result = _tool(seen=seen).execute(
        {
            "text": "Hello there.",
            "voice": "style_m_low_host.wav",
            "output_path": str(tmp_path / "line.flac"),
        }
    )
    assert result.success, result.error
    cloning = seen["workflow"]["4"]["inputs"]
    assert cloning["reference_audio"] == ["3", 0]
    assert "prompt_audio" not in cloning and "prompt_text" not in cloning
    assert result.data["voice_mode"] == "clone_reference_only"


def test_voice_id_is_accepted_as_an_alias_of_voice(tmp_path):
    seen = {}
    result = _tool(seen=seen).execute(
        {
            "text": "x",
            "voice_id": "style_m_low_host",
            "output_path": str(tmp_path / "line.flac"),
        }
    )
    assert result.success, result.error
    assert seen["workflow"]["3"]["inputs"]["audio"] == "style_m_low_host.wav"


def test_unknown_server_voice_fails_and_lists_what_is_there(tmp_path):
    result = _tool(voices=("style_a.wav", "style_b.wav")).execute(
        {"text": "x", "voice": "rachel", "output_path": str(tmp_path / "line.flac")}
    )
    assert result.success is False
    assert "rachel" in result.error
    assert "style_a" in result.error and "style_b" in result.error


# ------------------------------------------------------------------
# execute(): cloning a local reference file
# ------------------------------------------------------------------


def test_local_reference_is_uploaded_and_cloned_with_its_text(tmp_path):
    reference = tmp_path / "narrator ref.wav"
    reference.write_bytes(b"RIFF")
    seen = {}
    result = _tool(seen=seen).execute(
        {
            "text": "Second section.",
            "reference_audio_path": str(reference),
            "reference_text": "First section, spoken earlier.",
            "output_path": str(tmp_path / "line.flac"),
        }
    )
    assert result.success, result.error
    uploaded_path, uploaded_name = seen["uploaded"]
    assert uploaded_path == reference
    assert uploaded_name.endswith(".wav") and " " not in uploaded_name
    graph = seen["workflow"]
    assert graph["3"]["inputs"]["audio"] == uploaded_name
    assert graph["4"]["inputs"]["prompt_text"] == "First section, spoken earlier."
    assert result.data["voice_mode"] == "clone"


def test_local_reference_wins_over_a_server_voice(tmp_path):
    reference = tmp_path / "ref.wav"
    reference.write_bytes(b"RIFF")
    seen = {}
    _tool(seen=seen).execute(
        {
            "text": "x",
            "voice": "style_m_low_host",
            "reference_audio_path": str(reference),
            "output_path": str(tmp_path / "line.flac"),
        }
    )
    assert seen["workflow"]["3"]["inputs"]["audio"] == seen["uploaded"][1]


def test_missing_local_reference_fails_before_anything_is_sent(tmp_path):
    seen = {}
    result = _tool(seen=seen).execute(
        {
            "text": "x",
            "reference_audio_path": str(tmp_path / "nope.wav"),
            "output_path": str(tmp_path / "line.flac"),
        }
    )
    assert result.success is False
    assert "nope.wav" in result.error
    assert "workflow" not in seen and "uploaded" not in seen


# ------------------------------------------------------------------
# execute(): output file
# ------------------------------------------------------------------


def test_flac_output_is_downloaded_as_is(tmp_path):
    seen = {}
    target = tmp_path / "line.flac"
    result = _tool(seen=seen).execute({"text": "x", "output_path": str(target)})
    assert result.success, result.error
    assert seen["dest"] == target
    assert "transcoded" not in seen
    assert result.data["output"] == str(target)
    assert result.data["format"] == "flac"
    assert result.artifacts == [str(target)]


@pytest.mark.parametrize("suffix", [".wav", ".mp3"])
def test_other_formats_are_converted_from_the_server_flac(tmp_path, suffix):
    """The server saves FLAC; a .wav path must not end up holding FLAC bytes."""
    seen = {}
    target = tmp_path / f"line{suffix}"
    result = _tool(seen=seen).execute({"text": "x", "output_path": str(target)})
    assert result.success, result.error
    assert seen["dest"].suffix == ".flac"
    source, converted = seen["transcoded"]
    assert source == seen["dest"] and converted == target
    assert target.read_bytes() == b"converted"
    assert not source.exists(), "the downloaded FLAC is a temporary file"
    assert result.data["output"] == str(target)
    assert result.data["format"] == suffix.lstrip(".")


def test_default_output_is_a_wav_file_in_the_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = _tool().execute({"text": "x"})
    assert result.success, result.error
    assert Path(result.data["output"]).suffix == ".wav"
    assert (tmp_path / result.data["output"]).exists()


def test_result_describes_the_take(tmp_path):
    result = _tool().execute({"text": "Hello world.", "output_path": str(tmp_path / "a.flac")})
    assert result.data["provider"] == "comfyui"
    assert result.data["model"] == "VoxCPM2"
    assert result.data["text_length"] == len("Hello world.")
    assert result.cost_usd == 0.0
    assert result.model == "VoxCPM2"
    assert result.data["workflow_provenance"]["workflow"] == "voxcpm2-tts.json"
    assert result.data["workflow_provenance"]["workflow_hash_sha256"]


# ------------------------------------------------------------------
# execute(): failures
# ------------------------------------------------------------------


@pytest.mark.parametrize("text", ["", "   \n"])
def test_empty_text_is_rejected(tmp_path, text):
    seen = {}
    result = _tool(seen=seen).execute({"text": text, "output_path": str(tmp_path / "a.flac")})
    assert result.success is False
    assert "text" in result.error
    assert "workflow" not in seen


def test_unreachable_server_reports_how_to_point_at_one(tmp_path):
    tool = _tool()
    tool._client.is_available = lambda: False
    result = tool.execute({"text": "x", "output_path": str(tmp_path / "a.flac")})
    assert result.success is False
    assert "COMFYUI_TTS_SERVER_URL" in result.error


def test_missing_nodes_report_the_node_pack_to_install(tmp_path):
    tool = _tool()
    tool._client.has_node = lambda node_class: False
    result = tool.execute({"text": "x", "output_path": str(tmp_path / "a.flac")})
    assert result.success is False
    assert "ComfyUI-VoxCPM" in result.error
    assert result.data["setup"]["node_pack"].endswith("ComfyUI-VoxCPM")


def test_a_server_side_error_is_returned_not_raised(tmp_path):
    tool = _tool()

    def failing_generate(*_args, **_kwargs):
        raise ComfyUIError("Execution error: out of memory", prompt_id="abc")

    tool._client.generate = failing_generate
    result = tool.execute({"text": "x", "output_path": str(tmp_path / "a.flac")})
    assert result.success is False
    assert "out of memory" in result.error
    assert result.data["prompt_id"] == "abc"


# ------------------------------------------------------------------
# Client helpers the tool relies on
# ------------------------------------------------------------------


class _Response:
    def __init__(self, *, status=200, payload=None, content=b""):
        self.status_code = status
        self._payload = payload
        self.content = content

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_upload_audio_posts_the_file_to_the_input_folder(tmp_path, monkeypatch):
    local = tmp_path / "ref.wav"
    local.write_bytes(b"RIFFdata")
    sent = {}

    def fake_post(url, files=None, data=None, timeout=None):
        sent["url"] = url
        sent["name"] = files["image"][0]
        sent["bytes"] = files["image"][1].read()
        sent["data"] = data
        return _Response(payload={"name": "ref.wav", "subfolder": "", "type": "input"})

    monkeypatch.setattr("tools._comfyui.client.requests.post", fake_post)
    name = ComfyUIClient("http://comfy.test").upload_audio(local, "ref.wav")
    assert name == "ref.wav"
    assert sent["url"] == "http://comfy.test/upload/image"
    assert sent["name"] == "ref.wav" and sent["bytes"] == b"RIFFdata"
    assert sent["data"] == {"overwrite": "true"}


def test_input_file_text_decodes_utf8_whatever_the_server_header_says(monkeypatch):
    thai = "สวัสดีครับ"

    def fake_get(url, params=None, timeout=None):
        assert url == "http://comfy.test/view"
        assert params == {"filename": "a.reference.txt", "subfolder": "", "type": "input"}
        return _Response(content=thai.encode("utf-8"))

    monkeypatch.setattr("tools._comfyui.client.requests.get", fake_get)
    assert ComfyUIClient("http://comfy.test").input_file_text("a.reference.txt") == thai


def test_input_file_text_is_none_when_the_file_is_not_there(monkeypatch):
    monkeypatch.setattr(
        "tools._comfyui.client.requests.get",
        lambda url, params=None, timeout=None: _Response(status=404),
    )
    assert ComfyUIClient("http://comfy.test").input_file_text("nope.txt") is None


@pytest.mark.parametrize(
    "spec",
    [
        # V3 nodes (ComfyUI 0.44): ["COMBO", {"options": [...]}]
        ["COMBO", {"multiselect": False, "options": ["a.wav", "b.wav"]}],
        # older nodes: [[...], {...}]
        [["a.wav", "b.wav"], {"audio_upload": True}],
    ],
)
def test_list_input_audio_reads_both_combo_formats(monkeypatch, spec):
    payload = {"LoadAudio": {"input": {"required": {"audio": spec}}}}
    monkeypatch.setattr(
        "tools._comfyui.client.requests.get",
        lambda url, timeout=None: _Response(payload=payload),
    )
    assert ComfyUIClient("http://comfy.test").list_input_audio() == ["a.wav", "b.wav"]
