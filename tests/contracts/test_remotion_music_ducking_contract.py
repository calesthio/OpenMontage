"""The Remotion Explainer must honour `audio.music.ducking`.

Before the 2026-11-11 audit the Explainer played music at one flat level under
the narration and ignored `ducking`, which the pipeline skills told agents to
set. `remotion-composer/src/lib/ducking.ts` now computes the gain; these tests
run it under node and check the Explainer wires it into the music volume.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSER_SRC = REPO_ROOT / "remotion-composer" / "src"
HELPER = COMPOSER_SRC / "lib" / "ducking.ts"


def _run(expr_lines: list[str]) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not on PATH")
    version = subprocess.run([node, "--version"], capture_output=True, text=True).stdout
    match = re.match(r"v(\d+)\.(\d+)", version.strip())
    if not match or (int(match.group(1)), int(match.group(2))) < (22, 6):
        pytest.skip(f"node {version.strip()} cannot strip TypeScript types")
    script = (
        f"const d = await import({json.dumps(HELPER.as_uri())});\n"
        + "const out = {};\n"
        + "\n".join(expr_lines)
        + "\nconsole.log(JSON.stringify(out));\n"
    )
    proc = subprocess.run(
        [node, "--experimental-strip-types", "--no-warnings", "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_resolve_ducking_settings() -> None:
    out = _run([
        "out.off = d.resolveDucking(false);",
        "out.missing = d.resolveDucking(undefined);",
        "out.on = d.resolveDucking(true);",
        "out.custom = d.resolveDucking({ duckedGain: 0.2 });",
    ])
    assert out["off"] is None and out["missing"] is None
    assert out["on"]["duckedGain"] == 0.35
    assert out["custom"]["duckedGain"] == 0.2
    assert out["custom"]["releaseSeconds"] == out["on"]["releaseSeconds"]


def test_caption_words_merge_across_short_pauses_only() -> None:
    out = _run([
        "out.iv = d.speechIntervalsFromCaptions(["
        "{ startMs: 2000, endMs: 2400 },"  # sorted on input order
        "{ startMs: 0, endMs: 400 }, { startMs: 700, endMs: 1000 },"
        "{ startMs: 5000, endMs: 5000 }"  # zero-length word is dropped
        "], 0.6);",
    ])
    assert out["iv"] == [{"start": 0, "end": 1}, {"start": 2, "end": 2.4}]


def test_gain_ducks_inside_speech_and_ramps_around_it() -> None:
    out = _run([
        "const o = d.resolveDucking(true);",
        "const iv = [{ start: 2, end: 4 }];",
        "out.inside = d.duckGainAt(3, iv, o);",
        "out.before = d.duckGainAt(0.5, iv, o);",
        "out.attack = d.duckGainAt(2 - o.attackSeconds / 2, iv, o);",
        "out.release = d.duckGainAt(4 + o.releaseSeconds / 2, iv, o);",
        "out.after = d.duckGainAt(6, iv, o);",
    ])
    assert out["inside"] == pytest.approx(0.35)
    assert out["before"] == 1 and out["after"] == 1
    assert 0.35 < out["attack"] < 1
    assert 0.35 < out["release"] < 1


def test_explainer_applies_ducking_to_the_music_volume() -> None:
    source = (COMPOSER_SRC / "Explainer.tsx").read_text(encoding="utf-8")
    assert 'from "./lib/ducking"' in source
    assert "ducking?: DuckingSetting" in source
    assert "duckGainAt(f / fps, speechIntervals, musicDucking)" in source
    assert "return Math.min(fadeIn, fadeOut) * duck;" in source
