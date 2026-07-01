"""CLI wrapper for WaveSpeed text-to-audio generation."""

from __future__ import annotations

from tools.wavespeed_generation import cli_main


if __name__ == "__main__":
    raise SystemExit(cli_main(tool_name="wavespeed_text_to_audio", task_type="text_to_audio", asset_type="audio"))
