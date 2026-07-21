"""CLI wrapper for WaveSpeed image-edit generation."""

from __future__ import annotations

from tools.wavespeed_generation import cli_main


if __name__ == "__main__":
    raise SystemExit(cli_main(tool_name="wavespeed_image_edit", task_type="image_edit", asset_type="image"))
