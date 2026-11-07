"""Magnific audio APIs: music generation, sound effects, and audio isolation.

Three separate tools so the registry routes each by its own capability. All the
shared plumbing lives in `MagnificTool`.

  * MagnificMusic          POST /v1/ai/music-generation   (ElevenLabs Music)
  * MagnificSoundEffects   POST /v1/ai/sound-effects
  * MagnificAudioIsolation POST /v1/ai/audio-isolation    (SAM Audio)

API: https://docs.magnific.com/api-reference/music-generation/overview
"""

from __future__ import annotations

from typing import Any

from tools import _magnific as mag
from tools._magnific import MagnificTool
from tools.base_tool import Determinism, ToolResult, ToolTier


class MagnificMusic(MagnificTool):
    """Generate an original music track from a text description."""

    name = "magnific_music"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "music_generation"
    determinism = Determinism.STOCHASTIC
    agent_skills = ["music", "elevenlabs"]

    capabilities = ["generate_background_music", "generate_instrumental"]
    supports = {"exact_duration": True, "style_control": True, "instrumental": True}
    best_for = [
        "background score cut to an exact runtime (10-240s)",
        "genre-, mood-, and instrument-directed beds for explainers and trailers",
    ]
    not_good_for = ["vocals with specific lyrics", "tracks longer than 4 minutes", "licensed or recognizable music"]
    fallback_tools = ["fal_elevenlabs_music", "music_gen", "google_music", "pixabay_music"]
    quality_score = 0.85

    input_schema = {
        "type": "object",
        "required": ["prompt", "duration_seconds"],
        "properties": {
            "prompt": {
                "type": "string",
                "maxLength": 2500,
                "description": "Name the genre, mood, instruments, and tempo — e.g. 'slow melancholic piano with soft strings'.",
            },
            "duration_seconds": {"type": "integer", "minimum": 10, "maximum": 240},
            "output_path": {"type": "string", "default": "magnific_music.mp3"},
            "webhook_url": {"type": "string"},
        },
    }
    output_schema = {"type": "object", "properties": {"output_path": {"type": "string"}}}
    idempotency_key_fields = ["prompt", "duration_seconds"]
    side_effects = ["writes an audio file to output_path", "calls the Magnific API (consumes credits)"]
    user_visible_verification = ["Listen end to end — check the loop point and that the mood matches the edit"]

    @staticmethod
    def _seconds(inputs: dict[str, Any]) -> int:
        return int(inputs.get("duration_seconds", 60) or 60)

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Planning estimate; Magnific bills in credits with no published USD rate.
        return round(0.02 * max(1, self._seconds(inputs) / 30), 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 30.0 + self._seconds(inputs) * 0.5

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        return self._generate(
            inputs,
            "/v1/ai/music-generation",
            {"prompt": inputs["prompt"], "music_length_seconds": int(inputs["duration_seconds"])},
            model="magnific_music",
        )


class MagnificSoundEffects(MagnificTool):
    """Generate a sound effect from a text description."""

    name = "magnific_sound_effects"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "sound_effects"
    determinism = Determinism.STOCHASTIC
    agent_skills = ["sound-effects"]

    capabilities = ["generate_sound_effect", "generate_loopable_ambience"]
    supports = {"loopable": True, "prompt_influence": True, "short_form_only": True}
    best_for = [
        "one-off foley and UI stings for a cut (0.5-22s)",
        "seamlessly looping ambience beds (loop=true)",
    ]
    not_good_for = ["music", "dialogue or speech", "anything longer than 22 seconds"]
    fallback_tools = ["freesound_music"]
    quality_score = 0.82

    input_schema = {
        "type": "object",
        "required": ["text", "duration_seconds"],
        "properties": {
            "text": {"type": "string", "maxLength": 2500, "description": "The sound to create, e.g. 'ocean waves crashing on shingle'."},
            "duration_seconds": {"type": "number", "minimum": 0.5, "maximum": 22},
            "loop": {"type": "boolean", "default": False, "description": "Produce a seamlessly looping effect."},
            "prompt_influence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "default": 0.3,
                "description": "Higher sticks closer to the text; lower is more varied.",
            },
            "output_path": {"type": "string", "default": "magnific_sfx.mp3"},
            "webhook_url": {"type": "string"},
        },
    }
    output_schema = {"type": "object", "properties": {"output_path": {"type": "string"}}}
    idempotency_key_fields = ["text", "duration_seconds", "loop", "prompt_influence"]
    side_effects = ["writes an audio file to output_path", "calls the Magnific API (consumes credits)"]
    user_visible_verification = ["Listen in context against the picture; for loops, check the seam"]

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.01

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 20.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        return self._generate(
            inputs,
            "/v1/ai/sound-effects",
            {
                "text": inputs["text"],
                "duration_seconds": float(inputs["duration_seconds"]),
                "loop": inputs.get("loop"),
                "prompt_influence": inputs.get("prompt_influence"),
            },
            model="magnific_sound_effects",
        )


class MagnificAudioIsolation(MagnificTool):
    """Isolate a described sound from an audio or video file (SAM Audio)."""

    name = "magnific_audio_isolation"
    version = "0.1.0"
    tier = ToolTier.ENHANCE
    capability = "audio_processing"
    determinism = Determinism.DETERMINISTIC
    agent_skills = ["ffmpeg", "speech-to-text"]

    capabilities = ["isolate_sound", "denoise_speech", "stem_separation"]
    supports = {"audio_input": True, "video_input": True, "spatial_bounding_box": True, "text_targeted": True}
    best_for = [
        "pulling clean dialogue out of a noisy location recording",
        "lifting one instrument or effect out of a mixed track",
        "isolating the sound of a specific on-screen region of a video (x1/y1/x2/y2)",
    ]
    not_good_for = ["generating new audio", "restoring detail that was never recorded"]
    fallback_tools = ["audio_enhance"]
    quality_score = 0.84

    input_schema = {
        "type": "object",
        "required": ["description"],
        "properties": {
            "description": {"type": "string", "maxLength": 2500, "description": "The sound to isolate, e.g. 'a person speaking'."},
            "audio": {"type": "string", "description": "WAV/MP3/FLAC/OGG/M4A as https URL or local path. Mutually exclusive with `video`."},
            "video": {"type": "string", "description": "MP4/MOV/WEBM/AVI as https URL or local path. Mutually exclusive with `audio`."},
            "x1": {"type": "integer", "minimum": 0, "description": "Bounding box left edge, video input only."},
            "y1": {"type": "integer", "minimum": 0, "description": "Bounding box top edge, video input only."},
            "x2": {"type": "integer", "minimum": 0, "description": "Bounding box right edge, video input only."},
            "y2": {"type": "integer", "minimum": 0, "description": "Bounding box bottom edge, video input only."},
            "sample_fps": {"type": "number", "description": "Frames per second sampled for source localization."},
            "output_path": {"type": "string", "default": "magnific_isolated.wav"},
            "webhook_url": {"type": "string"},
        },
    }
    output_schema = {"type": "object", "properties": {"output_path": {"type": "string"}}}
    idempotency_key_fields = ["description", "audio", "video", "x1", "y1", "x2", "y2"]
    side_effects = ["writes a WAV file to output_path", "calls the Magnific API (consumes credits)"]
    user_visible_verification = ["Listen for artefacts and check the target sound survived intact"]

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.05

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 60.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        audio, video = inputs.get("audio"), inputs.get("video")
        if bool(audio) == bool(video):
            return ToolResult(
                success=False,
                error="Provide exactly one of `audio` or `video` — the API rejects both and neither.",
            )
        try:
            media = {"audio": mag.as_input(audio)} if audio else {"video": mag.as_input(video)}
        except ValueError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(success=False, error=f"Could not read the media input: {e}")

        payload: dict[str, Any] = {"description": inputs["description"], **media}
        if video:
            for field in ("x1", "y1", "x2", "y2", "sample_fps"):
                payload[field] = inputs.get(field)
        return self._generate(inputs, "/v1/ai/audio-isolation", payload, model="magnific_audio_isolation")
