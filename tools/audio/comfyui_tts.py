"""ComfyUI text-to-speech via VoxCPM2 on a local or remote ComfyUI server.

Runs the ``VoxCPM_TTS`` node of ``wildminder/ComfyUI-VoxCPM`` through the same
server (and the same SSH tunnel, on a rented GPU) as comfyui_image,
comfyui_video and comfyui_music, so narration needs no API key.

Three ways to choose the voice, in this order of precedence:

* ``reference_audio_path`` (+ ``reference_text``): a local clip is uploaded and
  cloned.
* ``voice``: an audio file that is already in the server's ``ComfyUI/input``
  folder is cloned, with ``<voice>.reference.txt`` as its transcript when that
  file is there.
* ``voice_description``: voice design in plain words. With nothing given, a
  neutral narrator description and a fixed seed are used.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)
from tools._comfyui.client import ComfyUIClient, ComfyUIError
from tools._comfyui.metadata import COMFYUI_SETUP_OFFER, workflow_hash

_WORKFLOWS = Path(__file__).resolve().parent.parent / "_comfyui" / "workflows"
_DESIGN_WORKFLOW = "voxcpm2-tts.json"
_CLONE_WORKFLOW = "voxcpm2-clone.json"

# Node IDs in the bundled workflows
_TTS_NODE = "1"
_OUTPUT_NODE = "2"
_LOAD_AUDIO_NODE = "3"
_CLONING_NODE = "4"

_NODE_CLASS = "VoxCPM_TTS"
_MODEL_NAME = "VoxCPM2"

_DEFAULT_VOICE_DESCRIPTION = (
    "A clear, warm adult narrator with a natural, unhurried delivery"
)
# A fixed seed, not a random one: sections of one script are separate calls
# and should come out in the same voice.
_DEFAULT_SEED = 42
_DEFAULT_OUTPUT = "tts_output.wav"
_AUDIO_SUFFIXES = (".wav", ".flac", ".mp3", ".ogg", ".m4a")

# What a ComfyUI server needs before this tool is ready.
VOXCPM_SETUP: dict[str, str] = {
    "node_pack": "https://github.com/wildminder/ComfyUI-VoxCPM",
    "model": "https://huggingface.co/openbmb/VoxCPM2",
    "model_destination_hint": "ComfyUI/models/tts/VoxCPM/VoxCPM2/",
    "license": "Apache-2.0 (model and node pack)",
    "install": (
        "git clone the node pack into ComfyUI/custom_nodes, pip install -r its "
        "requirements.txt, then restart ComfyUI. The model downloads on first "
        "use, or link an existing copy into models/tts/VoxCPM/VoxCPM2."
    ),
}


class ComfyUITTS(BaseTool):
    name = "comfyui_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "comfyui"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = []
    setup_offer = COMFYUI_SETUP_OFFER
    install_instructions = (
        "Start a ComfyUI server and set COMFYUI_SERVER_URL "
        "(default http://localhost:8188).\n"
        "Install the VoxCPM nodes on it: git clone "
        "https://github.com/wildminder/ComfyUI-VoxCPM into ComfyUI/custom_nodes, "
        "pip install -r its requirements.txt, restart ComfyUI. The VoxCPM2 model "
        "(Apache-2.0) downloads on first use.\n"
        "Running a separate ComfyUI instance for speech? Set COMFYUI_TTS_SERVER_URL "
        "instead -- it takes priority over COMFYUI_SERVER_URL for this tool only.\n"
        "Output other than .flac is converted locally and needs ffmpeg."
    )
    agent_skills = ["comfyui"]

    capabilities = ["text_to_speech", "voice_design", "voice_cloning"]
    supports = {
        "voice_cloning": True,
        "voice_design": True,
        "multilingual": True,
        "seed": True,
        "offline": True,
        "native_audio": True,
        "word_timestamps": False,
    }
    best_for = [
        "free narration on a GPU that already runs the ComfyUI image and video models",
        "one consistent narrator: clone a reference clip for every section of a script",
        "non-English narration such as Thai (VoxCPM2 is multilingual)",
    ]
    not_good_for = [
        "setups without a running ComfyUI server or without the ComfyUI-VoxCPM nodes",
        "word-level timestamps (run the transcriber on the output instead)",
        "cloning a real person's voice without their consent",
    ]
    fallback = "piper_tts"
    fallback_tools = ["piper_tts"]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {
                "type": "string",
                "description": (
                    "Text to speak. Punctuation sets the pauses: a period or '?' is a "
                    "clear pause, a comma a short one."
                ),
            },
            "voice": {
                "type": "string",
                "description": (
                    "Reference voice to clone: an audio file in the server's "
                    "ComfyUI/input folder, with or without its extension (e.g. "
                    "'style_m_low_host'). '<voice>.reference.txt' next to it is used "
                    "as the transcript. get_info()['server_voices'] lists what is there."
                ),
            },
            "voice_id": {
                "type": "string",
                "description": "Alias of voice, for callers that pass a capability-level voice_id.",
            },
            "voice_description": {
                "type": "string",
                "description": (
                    "Voice design in plain words, e.g. 'A calm woman in her thirties "
                    "with a low, warm voice'. Used when no reference voice is given; "
                    "ignored when a voice is cloned."
                ),
            },
            "reference_audio_path": {
                "type": "string",
                "description": (
                    "Local audio clip to upload and clone (5-20 s of clean speech). "
                    "Takes precedence over voice. Only use a voice you have consent for."
                ),
            },
            "reference_text": {
                "type": "string",
                "description": (
                    "Exact transcript of the reference audio. With it the clone "
                    "continues from the clip (closest match); without it only the "
                    "timbre of the clip is used."
                ),
            },
            "seed": {
                "type": "integer",
                "minimum": 0,
                "description": (
                    f"Generation seed (default {_DEFAULT_SEED}, fixed so repeated "
                    "calls keep the same voice)."
                ),
            },
            "cfg": {
                "type": "number",
                "default": 2.0,
                "minimum": 0.1,
                "maximum": 10.0,
                "description": "Guidance scale. Higher follows the voice prompt more closely.",
            },
            "steps": {
                "type": "integer",
                "default": 10,
                "minimum": 1,
                "maximum": 100,
                "description": "Diffusion steps. More is slower and slightly cleaner.",
            },
            "normalize_text": {
                "type": "boolean",
                "default": False,
                "description": (
                    "Let the node rewrite numbers and symbols as words. Off by "
                    "default: write the words the way they should be spoken."
                ),
            },
            "keep_model_loaded": {
                "type": "boolean",
                "default": False,
                "description": (
                    "Keep VoxCPM2 in VRAM after the take (faster for many takes in a "
                    "row). Off by default so the video model has the VRAM."
                ),
            },
            "output_path": {
                "type": "string",
                "description": (
                    f"Where to save the audio (default {_DEFAULT_OUTPUT}). The "
                    "extension picks the format; anything but .flac is converted "
                    "locally with ffmpeg."
                ),
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "How long to wait for the ComfyUI job (default 600).",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=8000, vram_mb=8000, disk_mb=100, network_required=False,
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout"])
    idempotency_key_fields = [
        "text",
        "voice",
        "voice_description",
        "reference_audio_path",
        "reference_text",
        "seed",
        "cfg",
        "steps",
    ]
    side_effects = [
        "writes audio file to output_path",
        "uploads reference_audio_path to the ComfyUI server's input folder",
    ]
    user_visible_verification = [
        "Listen to the generated audio: every word present, natural pacing, right voice",
    ]

    def __init__(self) -> None:
        self._client = ComfyUIClient(capability="tts")

    def get_status(self) -> ToolStatus:
        if not self._client.is_available():
            return ToolStatus.UNAVAILABLE
        if not self._client.has_node(_NODE_CLASS):
            return ToolStatus.DEGRADED
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        # Measured through this tool on a rented RTX 5090 (2026-11-10): 11-13.5 s
        # per one-sentence take (3.5-5 s of speech) with the model reloaded for
        # each take, and 26.5 s for the first take after ComfyUI started. Longer
        # texts are extrapolated at about half real time, taking speech as
        # roughly 15 characters per second.
        text = str(inputs.get("text") or "")
        return round(10.0 + len(text) / 15.0 * 0.5, 1)

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["setup_offer"] = self.setup_offer
        info["voxcpm_setup"] = dict(VOXCPM_SETUP)
        info["default_voice_description"] = _DEFAULT_VOICE_DESCRIPTION
        info["server_voices"] = self._client.list_input_audio()
        return info

    # ------------------------------------------------------------------
    # execute
    # ------------------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        text = str(inputs.get("text") or "").strip()
        if not text:
            return ToolResult(
                success=False, error="text is required and must not be empty."
            )

        reference_path: Path | None = None
        if inputs.get("reference_audio_path"):
            reference_path = Path(str(inputs["reference_audio_path"])).expanduser()
            if not reference_path.is_file():
                return ToolResult(
                    success=False,
                    error=f"reference_audio_path does not exist: {reference_path}",
                )

        if not self._client.is_available():
            return ToolResult(success=False, error=self._client.unavailable_reason())
        if not self._client.has_node(_NODE_CLASS):
            return ToolResult(
                success=False,
                data={"provider": "comfyui", "setup": dict(VOXCPM_SETUP)},
                error=(
                    f"ComfyUI server is running but has no {_NODE_CLASS} node. Install "
                    f"the ComfyUI-VoxCPM node pack ({VOXCPM_SETUP['node_pack']}) and "
                    "restart ComfyUI. See data.setup."
                ),
            )

        start = time.time()
        seed = _DEFAULT_SEED if inputs.get("seed") is None else int(inputs["seed"])
        output_path = Path(str(inputs.get("output_path") or _DEFAULT_OUTPUT))
        if not output_path.suffix:
            output_path = output_path.with_suffix(".wav")
        direct = output_path.suffix.lower() == ".flac"
        download_path = (
            output_path
            if direct
            else output_path.with_name(f"{output_path.stem}.download.flac")
        )

        try:
            workflow, workflow_name, voice_mode, server_voice = self._build_workflow(
                inputs, text, seed, output_path, reference_path
            )
            paths = self._client.generate(
                workflow,
                output_node=_OUTPUT_NODE,
                dest=download_path,
                timeout=inputs.get("timeout_seconds", 600),
                interval=2,
            )
            if not direct:
                self._transcode(paths[0], output_path)
                paths[0].unlink(missing_ok=True)
        except ComfyUIError as exc:
            data = {"prompt_id": exc.prompt_id} if exc.prompt_id else {}
            return ToolResult(success=False, error=str(exc), data=data)
        except Exception as exc:
            return ToolResult(
                success=False, error=f"ComfyUI speech generation failed: {exc}"
            )

        return ToolResult(
            success=True,
            data={
                "provider": "comfyui",
                "model": _MODEL_NAME,
                "text_length": len(text),
                "voice_mode": voice_mode,
                "voice": server_voice,
                "output": str(output_path),
                "format": output_path.suffix.lower().lstrip("."),
                "workflow_provenance": {
                    "source": "bundled",
                    "workflow": workflow_name,
                    "workflow_hash_sha256": workflow_hash(workflow),
                    "node_pack": VOXCPM_SETUP["node_pack"],
                    "output_node": _OUTPUT_NODE,
                },
            },
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            seed=seed,
            model=_MODEL_NAME,
        )

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------

    def _build_workflow(
        self,
        inputs: dict[str, Any],
        text: str,
        seed: int,
        output_path: Path,
        reference_path: Path | None,
    ) -> tuple[dict, str, str, str | None]:
        """Return ``(workflow, workflow_name, voice_mode, server_voice)``."""
        server_voice, transcript = self._resolve_reference(inputs, reference_path)
        tts_inputs: dict[str, Any] = {
            "text": text,
            "cfg": float(inputs.get("cfg", 2.0)),
            "steps": int(inputs.get("steps", 10)),
            "normalize_text": bool(inputs.get("normalize_text", False)),
            "seed": seed,
            "force_offload": not bool(inputs.get("keep_model_loaded", False)),
        }
        save_inputs = {"filename_prefix": f"audio/{output_path.stem}"}

        if server_voice is None:
            description = str(inputs.get("voice_description") or "").strip()
            tts_inputs["voice_design"] = description or _DEFAULT_VOICE_DESCRIPTION
            workflow = ComfyUIClient.patch_workflow(
                ComfyUIClient.load_workflow(_WORKFLOWS / _DESIGN_WORKFLOW),
                {_TTS_NODE: tts_inputs, _OUTPUT_NODE: save_inputs},
            )
            return workflow, _DESIGN_WORKFLOW, "design", None

        # A cloned voice ignores the design text, so none is sent.
        tts_inputs["voice_design"] = ""
        workflow = ComfyUIClient.patch_workflow(
            ComfyUIClient.load_workflow(_WORKFLOWS / _CLONE_WORKFLOW),
            {
                _TTS_NODE: tts_inputs,
                _OUTPUT_NODE: save_inputs,
                _LOAD_AUDIO_NODE: {"audio": server_voice},
            },
        )
        cloning = workflow[_CLONING_NODE]["inputs"]
        if transcript:
            cloning["prompt_text"] = transcript
            return workflow, _CLONE_WORKFLOW, "clone", server_voice
        # Without a transcript the clip can only lend its timbre.
        cloning.pop("prompt_text", None)
        cloning.pop("prompt_audio", None)
        return workflow, _CLONE_WORKFLOW, "clone_reference_only", server_voice

    def _resolve_reference(
        self, inputs: dict[str, Any], reference_path: Path | None
    ) -> tuple[str | None, str | None]:
        """Return ``(server-side audio name, transcript)`` of the voice to clone.

        ``(None, None)`` means no reference: the voice is designed from text.
        """
        transcript = str(inputs.get("reference_text") or "").strip() or None

        if reference_path is not None:
            digest = hashlib.sha256(reference_path.read_bytes()).hexdigest()[:12]
            suffix = reference_path.suffix.lower() or ".wav"
            name = self._client.upload_audio(reference_path, f"om_ref_{digest}{suffix}")
            return name, transcript

        voice = str(inputs.get("voice") or inputs.get("voice_id") or "").strip()
        if not voice:
            return None, None

        available = self._client.list_input_audio()
        candidates = [voice] + [f"{voice}{suffix}" for suffix in _AUDIO_SUFFIXES]
        name = next((c for c in candidates if c in available), None)
        if name is None:
            stems = sorted({Path(a).stem for a in available})
            listing = ", ".join(stems[:40]) or "none"
            raise ComfyUIError(
                f"Voice {voice!r} is not in the ComfyUI server's input folder. "
                f"Available voices: {listing}. Pass one of them as voice, upload a "
                "clip with reference_audio_path, or use voice_description."
            )
        if transcript is None:
            fetched = self._client.input_file_text(f"{Path(name).stem}.reference.txt")
            transcript = (fetched or "").strip() or None
        return name, transcript

    # ------------------------------------------------------------------
    # Local conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _transcode(source: Path, target: Path) -> None:
        """Convert the downloaded FLAC to the format of *target* with ffmpeg."""
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError(
                f"ffmpeg is needed to convert the audio to {target.suffix}; the "
                f"FLAC from ComfyUI is at {source}. Install ffmpeg or ask for a "
                ".flac output_path."
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-i", str(source), str(target)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if proc.returncode != 0 or not target.exists():
            raise RuntimeError(
                f"ffmpeg could not write {target} (exit {proc.returncode}): "
                f"{proc.stderr.strip()}. The FLAC from ComfyUI is at {source}."
            )
