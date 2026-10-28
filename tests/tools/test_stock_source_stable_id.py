"""Issue #596 regression: source_id must be stable across processes."""

import os
from pathlib import Path
import subprocess
import sys

from tools.video.stock_sources.base import stable_source_id


def test_stable_source_id_is_deterministic():
    url = "https://example.com/x"
    source_id = stable_source_id(url)

    assert source_id == stable_source_id(url)
    assert len(source_id) == 8
    assert all(char in "0123456789abcdef" for char in source_id)


def test_stable_source_id_matches_subprocess_with_random_seed():
    repo_root = Path(__file__).resolve().parents[2]
    command = (
        "from tools.video.stock_sources.base import stable_source_id; "
        "print(stable_source_id('https://example.com/x'))"
    )
    outputs = []
    for seed in ("1", "2"):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = seed
        outputs.append(
            subprocess.check_output(
                [sys.executable, "-c", command],
                cwd=repo_root,
                env=env,
                text=True,
            ).strip()
        )

    assert outputs[0] == outputs[1] == stable_source_id("https://example.com/x")
