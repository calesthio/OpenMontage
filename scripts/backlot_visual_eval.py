"""Deterministic visual eval for Backlot.

Stages the fictional Backlot projects, captures canonical browser screenshots,
optionally compares them to goldens, and can run a small Playwright interaction
smoke against the staged board.

Examples:
    python scripts/backlot_visual_eval.py
    python scripts/backlot_visual_eval.py --bless
    python scripts/backlot_visual_eval.py --interactions
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops

REPO_ROOT = Path(__file__).resolve().parent.parent
STAGE_DIR = REPO_ROOT / ".backlot" / "screenshot-stage"
GOLDENS_DIR = REPO_ROOT / "internal" / "evals" / "goldens"
CAPTURE_ROOT = REPO_ROOT / "internal" / "evals" / "captures"
PORT = 4791

SHOTS = [
    ("library", "/?static=1", 1560, 500, 4200, [
        (1370, 20, 1510, 62),   # live/idle badge
        (90, 106, 422, 380),    # card border/status animation variance
        (440, 106, 772, 380),
        (790, 106, 1122, 380),
        (1140, 106, 1472, 380),
    ]),
    ("board-live", "/p/signal-in-the-static?static=1", 1560, 1150, 4200, []),
    ("script-gate", "/p/the-slow-orchard?static=1", 1560, 760, 3200, []),
    ("storyboard", "/p/the-last-lighthouse?static=1", 1560, 1500, 4200, []),
]


def compare_images(
    expected_path: Path,
    actual_path: Path,
    diff_path: Path,
    *,
    threshold: float = 0.015,
    masks: list[tuple[int, int, int, int]] | None = None,
) -> dict[str, Any]:
    """Compare screenshots by changed-pixel ratio and write a red diff image."""
    expected = Image.open(expected_path).convert("RGB")
    actual = Image.open(actual_path).convert("RGB")
    if expected.size != actual.size:
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        actual.save(diff_path)
        return {"passed": False, "changed_ratio": 1.0, "reason": f"size {expected.size} != {actual.size}"}

    masks = masks or []
    for box in masks:
        patch = expected.crop(box)
        actual.paste(patch, box)

    delta = ImageChops.difference(expected, actual)
    changed = 0
    pixels = delta.load()
    width, height = delta.size
    diff = Image.new("RGB", delta.size, (0, 0, 0))
    diff_px = diff.load()
    for y in range(height):
        for x in range(width):
            if max(pixels[x, y]) > 8:
                changed += 1
                diff_px[x, y] = (255, 40, 40)
            else:
                diff_px[x, y] = actual.getpixel((x, y))
    ratio = changed / float(width * height)
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    diff.save(diff_path)
    return {"passed": ratio <= threshold, "changed_ratio": round(ratio, 6), "threshold": threshold}


def run_stage() -> None:
    subprocess.run(
        [sys.executable, "scripts/backlot_screenshot_stage.py", "--stage-only"],
        cwd=REPO_ROOT,
        check=True,
        timeout=180,
    )


def start_server() -> subprocess.Popen:
    env = dict(os.environ)
    env["OPENMONTAGE_PROJECTS_DIR"] = str(STAGE_DIR)
    server = subprocess.Popen(
        [sys.executable, "-m", "backlot", "serve", "--port", str(PORT)],
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=1):
                return server
        except Exception:
            time.sleep(0.3)
    server.terminate()
    raise RuntimeError("Backlot server did not become healthy")


def capture_screenshot(url: str, output: Path, width: int, height: int, wait_ms: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "npx",
            "playwright",
            "screenshot",
            "--viewport-size",
            f"{width},{height}",
            "--wait-for-timeout",
            str(wait_ms),
            url,
            str(output),
        ],
        cwd=REPO_ROOT,
        check=True,
        timeout=120,
        shell=(os.name == "nt"),
    )


def capture_shots(capture_dir: Path) -> list[dict[str, Any]]:
    results = []
    for name, path, width, height, wait_ms, _masks in SHOTS:
        out = capture_dir / f"{name}.png"
        capture_screenshot(f"http://127.0.0.1:{PORT}{path}", out, width, height, wait_ms)
        results.append({"name": name, "path": out})
    return results


def compare_or_bless(capture_dir: Path, *, bless: bool, threshold: float) -> list[dict[str, Any]]:
    GOLDENS_DIR.mkdir(parents=True, exist_ok=True)
    report = []
    for name, _path, _width, _height, _wait_ms, masks in SHOTS:
        actual = capture_dir / f"{name}.png"
        golden = GOLDENS_DIR / f"{name}.png"
        if bless or not golden.exists():
            shutil.copyfile(actual, golden)
            report.append({"name": name, "status": "blessed", "golden": str(golden)})
            continue
        diff = capture_dir / "diffs" / f"{name}.png"
        result = compare_images(golden, actual, diff, threshold=threshold, masks=masks)
        result.update({"name": name, "diff": str(diff)})
        report.append(result)
    return report


def run_interactions(capture_dir: Path) -> dict[str, Any]:
    """Run browser interaction smoke through Python Playwright."""
    from playwright.sync_api import sync_playwright

    screenshot = capture_dir / "interaction-smoke.png"
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1560, "height": 1000})
        page.goto(f"http://127.0.0.1:{PORT}/p/the-last-lighthouse?static=1")
        page.wait_for_selector(".stage")
        page.locator(".stage").first.click()
        page.wait_for_selector(".drawer")
        drawer_text = page.locator(".drawer").inner_text()
        if "research" not in drawer_text:
            raise RuntimeError("stage drawer did not open")
        page.locator(".script-card").first.click()
        page.wait_for_selector(".modal-bg.open")
        page.keyboard.press("Escape")
        page.wait_for_function("() => !document.querySelector('.modal-bg')?.classList.contains('open')")
        if page.locator(".takes").count() < 1:
            raise RuntimeError("takes drawer not present on staged takes scene")
        replay_button = page.locator(".rp-btn", has_text="REPLAY RUN")
        if replay_button.count():
            replay_button.first.click()
            page.wait_for_selector('input[type="range"]')
            page.locator('input[type="range"]').fill("500")
        page.screenshot(path=str(screenshot), full_page=True)
        browser.close()
    return {"status": "passed", "screenshot": str(capture_dir / "interaction-smoke.png")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bless", action="store_true", help="Write current captures as goldens")
    parser.add_argument("--no-stage", action="store_true", help="Reuse existing .backlot/screenshot-stage")
    parser.add_argument("--interactions", action="store_true", help="Run Playwright interaction smoke")
    parser.add_argument("--threshold", type=float, default=0.015)
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    if not args.no_stage:
        run_stage()

    stamp = datetime.now().strftime("visual-%Y%m%d-%H%M%S")
    capture_dir = args.out_dir or (CAPTURE_ROOT / stamp)
    capture_dir.mkdir(parents=True, exist_ok=True)

    server = start_server()
    try:
        capture_shots(capture_dir)
        report = compare_or_bless(capture_dir, bless=args.bless, threshold=args.threshold)
        interaction_report = run_interactions(capture_dir) if args.interactions else None
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()

    passed = all(item.get("passed", item.get("status") == "blessed") for item in report)
    payload = {"capture_dir": str(capture_dir), "shots": report, "interactions": interaction_report}
    report_path = capture_dir / "report.json"
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
