"""CLI wrapper for WaveSpeed text-to-video generation."""

from __future__ import annotations

from tools.wavespeed_generation import cli_main


if __name__ == "__main__":
    raise SystemExit(cli_main(tool_name="wavespeed_text_to_video", task_type="text_to_video", asset_type="video"))
