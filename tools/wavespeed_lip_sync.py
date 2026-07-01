"""CLI wrapper for WaveSpeed lip-sync generation."""

from __future__ import annotations

from tools.wavespeed_generation import cli_main


if __name__ == "__main__":
    raise SystemExit(cli_main(tool_name="wavespeed_lip_sync", task_type="lip_sync", asset_type="video"))
