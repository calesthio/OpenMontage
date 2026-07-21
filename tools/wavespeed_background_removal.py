"""CLI wrapper for WaveSpeed background-removal generation."""

from __future__ import annotations

from tools.wavespeed_generation import cli_main


if __name__ == "__main__":
    raise SystemExit(cli_main(tool_name="wavespeed_background_removal", task_type="background_removal", asset_type="image"))
