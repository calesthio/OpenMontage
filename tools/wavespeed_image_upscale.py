"""CLI wrapper for WaveSpeed image-upscale generation."""

from __future__ import annotations

from tools.wavespeed_generation import cli_main


if __name__ == "__main__":
    raise SystemExit(cli_main(tool_name="wavespeed_image_upscale", task_type="image_upscale", asset_type="image"))
