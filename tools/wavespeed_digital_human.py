"""CLI wrapper for WaveSpeed digital-human generation."""

from __future__ import annotations

from tools.wavespeed_generation import cli_main


if __name__ == "__main__":
    raise SystemExit(cli_main(tool_name="wavespeed_digital_human", task_type="digital_human", asset_type="video"))
