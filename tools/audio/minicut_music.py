"""Lyria 3.5 music through the MiniCut CLI (price first, then one yes)."""

from __future__ import annotations

from typing import Any

from tools.minicut_tool import APPROVAL_SCHEMA, RESUME_SCHEMA, MiniCutTool


class MiniCutMusic(MiniCutTool):
    name = "minicut_music"
    capability = "music_generation"
    model = "lyria-3-5"
    default_output = "minicut_music.mp3"
    agent_skills = ["lyria", "music"]

    capabilities = ["generate_background_music", "generate_song"]
    supports = {"style_control": True, "exact_duration": False, "price_quote_before_run": True}
    best_for = [
        "Lyria 3.5 tracks, with or without singing, on the same sign-in as MiniCut video, images and voice",
        "paid runs that must show the price and wait for a yes",
    ]
    fallback_tools = ["music_gen", "google_music"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Mood, style and instruments. Say 'instrumental' for a track with no singing.",
            },
            "negative_prompt": {"type": "string", "description": "What the track should not have"},
            "approval": APPROVAL_SCHEMA,
            "resume_job": RESUME_SCHEMA,
            "poll_timeout": {"type": "integer", "default": 900},
            "output_path": {"type": "string", "default": "minicut_music.mp3"},
        },
    }
    idempotency_key_fields = ["prompt", "negative_prompt"]
    side_effects = [
        "writes an audio file to output_path",
        "spends MiniCut credits after approval",
        "keeps a copy of the result in the MiniCut library",
    ]
    user_visible_verification = ["Listen for the mood and instruments asked for"]

    def _request(self, inputs: dict[str, Any]):
        return inputs["prompt"], {"negative-prompt": inputs.get("negative_prompt")}, []
