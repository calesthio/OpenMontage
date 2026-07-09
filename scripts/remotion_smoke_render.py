#!/usr/bin/env python3
"""Run the M0 Remotion render smoke with an external progress watchdog.

The smoke intentionally renders the checked-in zero-key `code-to-screen`
fixture, whose metadata resolves to 750 frames. It catches the failure mode
seen on small Fly machines: the renderer stops advancing without exiting.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
COMPOSER_DIR = ROOT_DIR / "remotion-composer"
DEFAULT_PROPS = COMPOSER_DIR / "public" / "demo-props" / "code-to-screen.json"
DEFAULT_OUTPUT = ROOT_DIR / "projects" / "m0-smoke" / "renders" / "code-to-screen-smoke.mp4"
PROGRESS_RE = re.compile(r"(?P<done>\d+)\s*/\s*(?P<total>\d+)")


def _find_browser_executable() -> str | None:
    for key in ("REMOTION_BROWSER_EXECUTABLE", "REMOTION_CHROMIUM_EXECUTABLE"):
        value = os.environ.get(key)
        if value and Path(value).is_file():
            return value

    remotion_dir = COMPOSER_DIR / "node_modules" / ".remotion"
    if not remotion_dir.exists():
        return None
    names = {"headless_shell", "chrome-headless-shell", "chrome", "chromium"}
    for path in remotion_dir.rglob("*"):
        if path.is_file() and path.name in names and os.access(path, os.X_OK):
            return str(path)
    return None


def _expected_frame_count(frames: str | None) -> int | None:
    if not frames:
        return None
    if "-" not in frames:
        return 1
    start, _, end = frames.partition("-")
    if not start or not end:
        return None
    return int(end) - int(start) + 1


def _kill_process(proc: subprocess.Popen[str]) -> None:
    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGTERM)
        else:
            proc.terminate()
        proc.wait(timeout=10)
    except Exception:
        try:
            if os.name == "posix":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
        except Exception:
            pass


def _probe_frame_count(output_path: Path) -> int | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    proc = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_frames",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "default=nokey=1:noprint_wrappers=1",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        return None
    text = proc.stdout.strip()
    return int(text) if text.isdigit() else None


def run_smoke(args: argparse.Namespace) -> int:
    npx = shutil.which("npx")
    if not npx:
        raise SystemExit("npx is required for the Remotion smoke render.")
    if not args.props.is_file():
        raise SystemExit(f"Props file not found: {args.props}")
    if not (COMPOSER_DIR / "node_modules").exists():
        raise SystemExit("remotion-composer/node_modules is missing; run npm ci first.")

    browser = _find_browser_executable()
    if args.require_browser_executable and not browser:
        raise SystemExit(
            "A baked Remotion browser executable is required but was not found. "
            "Run `npx remotion browser ensure` at build time and set "
            "REMOTION_BROWSER_EXECUTABLE."
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        args.output.unlink()

    cmd = [
        npx,
        "remotion",
        "render",
        "src/index.tsx",
        "Explainer",
        str(args.output),
        "--props",
        str(args.props),
        "--codec",
        "h264",
        f"--concurrency={args.concurrency}",
        f"--timeout={args.remotion_timeout_ms}",
    ]
    if args.frames:
        cmd.append(f"--frames={args.frames}")
    if browser:
        cmd.append(f"--browser-executable={browser}")

    print("[m0-smoke] running:", " ".join(cmd), flush=True)
    start = time.monotonic()
    last_progress = start
    last_frame = -1

    popen_kwargs = {
        "cwd": str(COMPOSER_DIR),
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "bufsize": 1,
    }
    if os.name == "posix":
        popen_kwargs["preexec_fn"] = os.setsid
    proc = subprocess.Popen(cmd, **popen_kwargs)  # noqa: S603

    assert proc.stdout is not None
    while True:
        line = proc.stdout.readline()
        now = time.monotonic()
        if line:
            print(line, end="", flush=True)
            match = PROGRESS_RE.search(line)
            if match:
                frame = int(match.group("done"))
                if frame > last_frame:
                    last_frame = frame
                    last_progress = now
            elif last_frame < 0:
                # Before Remotion starts printing frame counters, any output
                # confirms the process is alive.
                last_progress = now
        elif proc.poll() is not None:
            break
        else:
            if now - last_progress > args.watchdog_seconds:
                _kill_process(proc)
                raise SystemExit(
                    f"Remotion render stalled: no frame progress for "
                    f"{args.watchdog_seconds}s (last_frame={last_frame})."
                )
            if now - start > args.timeout_seconds:
                _kill_process(proc)
                raise SystemExit(f"Remotion smoke timed out after {args.timeout_seconds}s.")
            time.sleep(0.5)

    code = proc.wait()
    if code != 0:
        raise SystemExit(f"Remotion smoke failed with exit code {code}.")
    if not args.output.is_file() or args.output.stat().st_size == 0:
        raise SystemExit(f"Remotion smoke did not create output: {args.output}")

    expected = _expected_frame_count(args.frames)
    actual = _probe_frame_count(args.output)
    if expected is not None and actual is not None and actual != expected:
        raise SystemExit(f"Frame-count mismatch: expected {expected}, got {actual}.")

    print(
        f"[m0-smoke] ok output={args.output} "
        f"frames={actual if actual is not None else 'unprobed'} "
        f"seconds={time.monotonic() - start:.1f}",
        flush=True,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="OpenMontage M0 Remotion smoke render.")
    parser.add_argument("--props", type=Path, default=DEFAULT_PROPS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frames", default="0-749", help="Remotion --frames value.")
    parser.add_argument("--concurrency", type=int, default=int(os.environ.get("RAY_RENDER_CONCURRENCY", "1")))
    parser.add_argument("--watchdog-seconds", type=int, default=90)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--remotion-timeout-ms", type=int, default=240000)
    parser.add_argument("--require-browser-executable", action="store_true")
    return run_smoke(parser.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
