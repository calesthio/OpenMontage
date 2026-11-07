"""Bridge from a Cypress tutorial recording into the OpenMontage pipeline.

- run_tutorial_spec: run a *.tutorial.cy.js spec (real or collect-only) and locate
  its raw video + step manifest sidecar.
- normalize_capture: recover each step's true video time from the drift markers
  (robust to Cypress's variable-FPS screencast by re-encoding to CFR first), then
  crop the marker strip away and letterbox to the target resolution.

Requires the `ffmpeg`/`ffprobe` binaries (already an OpenMontage dependency).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Optional

CFR_FPS = 30
BG_HEX = "0x0f1216"  # matches the title-card background


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, **kw)


def probe(path: str) -> dict:
    """Return {width, height, duration} for a video via ffprobe."""
    out = subprocess.check_output(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height:format=duration",
            "-of", "json", str(path),
        ],
        text=True,
    )
    j = json.loads(out)
    st = j["streams"][0]
    dur = float(j.get("format", {}).get("duration", 0.0) or 0.0)
    return {"width": int(st["width"]), "height": int(st["height"]), "duration": dur}


# --- running a tutorial spec ------------------------------------------------

def run_tutorial_spec(
    client_dir: str,
    spec: str,
    base_url: Optional[str] = None,
    collect_only: bool = False,
    timeout: int = 1800,
    lang: Optional[str] = None,
) -> dict:
    """Run one tutorial spec via `cypress run` and return its manifest sidecar.

    spec is relative to client_dir (e.g. "cypress/e2e-tutorials/sales/sales-tour.tutorial.cy.js").
    Returns the parsed manifest dict (with an added "manifest_path" and the raw
    "video" path when a video was recorded).
    """
    client = Path(client_dir).resolve()
    import os

    config_pairs = []
    if base_url:
        config_pairs.append(f"baseUrl={base_url}")
    if collect_only:
        config_pairs.append("video=false")

    cmd = [
        "npx", "cypress", "run",
        "--config-file", "cypress.tutorial.config.js",
        "--spec", spec,
    ]
    # Browser: Electron (Cypress default) crashes its renderer on some heavy
    # backoffice pages; `chrome` is reliable. Resolved from TUTORIAL_BROWSER /
    # CYPRESS_BROWSER, else the "browser" key of tutorial.config.json.
    browser = _resolve_browser()
    if browser:
        cmd += ["--browser", browser]
    if config_pairs:
        cmd += ["--config", ",".join(config_pairs)]

    # CLI --env beats cypress.env.json. Forward CYPRESS_* / bare TEST_* so a
    # stale committed TEST_SALE_ID cannot silently send us to a missing node.
    env_pairs: list[str] = []
    if collect_only:
        env_pairs.append("tutorialCollectOnly=1")
    if lang:
        env_pairs.append(f"tutorialLang={lang}")
    for key in (
        "TEST_SALE_ID",
        "TEST_ITEM_ID",
        "TEST_CLIENT_ID",
        "TEST_CONSIGNMENT_ID",
        "TEST_ORDER_ID",
        "TEST_STATEMENT_ID",
        "TEST_UID",
        "BACKEND_URL",
    ):
        val = os.environ.get(f"CYPRESS_{key}") or os.environ.get(key)
        if val:
            env_pairs.append(f"{key}={val}")
    if env_pairs:
        cmd += ["--env", ",".join(env_pairs)]

    env = os.environ.copy()
    env["CYPRESS_NO_COMMAND_LOG"] = "1"
    if lang:
        env["CYPRESS_TUTORIAL_LANG"] = lang  # cypress.tutorial.config.js picks <name>.timings.<lang>.json
    _run(cmd, cwd=str(client), env=env, timeout=timeout)

    manifest, manifest_path = _find_manifest(client, spec)
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def _resolve_browser() -> str:
    import os
    val = os.environ.get("TUTORIAL_BROWSER") or os.environ.get("CYPRESS_BROWSER")
    if val:
        return val.strip()
    cfg = Path(__file__).resolve().parents[2] / "tutorial.config.json"
    try:
        return str(json.loads(cfg.read_text()).get("browser") or "").strip()
    except (OSError, ValueError):
        return ""


def _find_manifest(client: Path, spec: str) -> tuple[dict, Path]:
    """Locate the newest manifest sidecar written for `spec`.

    Prefers an EXACT `manifest.spec == spec` match (so a prefix-colliding tutorial,
    e.g. `sales-tour-2` vs `sales-tour`, never wins); only falls back to a name
    substring when no exact match exists.
    """
    videos = client / "cypress" / "videos"
    spec_rel = spec.replace("\\", "/")
    spec_name = Path(spec_rel).name
    exact: list[tuple[float, Path, dict]] = []
    loose: list[tuple[float, Path, dict]] = []
    if videos.exists():
        for p in videos.rglob("*.manifest.json"):
            try:
                data = json.loads(p.read_text())
            except Exception:
                continue
            mt = p.stat().st_mtime
            if data.get("spec") == spec_rel:
                exact.append((mt, p, data))
            elif spec_name in p.name:
                loose.append((mt, p, data))
    pool = exact or loose
    if not pool:
        raise FileNotFoundError(
            f"No tutorial manifest found for spec {spec!r} under {videos}. "
            "Did the run register the manifest tasks (cypress.tutorial.config.js)?"
        )
    pool.sort(key=lambda x: x[0])
    return pool[-1][2], pool[-1][1]


# --- normalization: marker detection + crop/pad -----------------------------

def _marker_height(manifest: dict) -> int:
    h = 0
    for s in manifest.get("steps", []):
        mk = s.get("marker") or {}
        h = max(h, int(mk.get("heightPx", 0) or 0))
    return h


def _to_cfr(src: str, dst: str, fps: int = CFR_FPS) -> None:
    """Re-encode to constant frame rate so frame_index/fps == real time.

    Cypress records via CDP screencast at variable FPS; without this, timestamps
    drift over long specs. We keep the source resolution here (the marker strip
    must stay in place for detection).
    """
    _run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-i", str(src),
            "-r", str(fps), "-fps_mode", "cfr",
            "-an", "-c:v", "libx264", "-crf", "23", "-preset", "veryfast",
            str(dst),
        ]
    )


def _is_marker(r: int, g: int, b: int) -> bool:
    return r > 200 and g < 90 and b > 200


def _marker_row(cfr_video: str, info: dict, cx: int, cw: int) -> int:
    """Topmost row that ever turns marker-coloured, or -1.

    The strip is at y=0 of the app viewport, but the recording can include the
    Cypress runner's own header above the app, which pushes it down.
    """
    h = info["height"]
    proc = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-i", str(cfr_video),
            "-vf", f"fps=10,crop={cw}:{h}:{cx}:0,scale=1:{h}:flags=area,format=rgb24",
            "-f", "rawvideo", "-",
        ],
        capture_output=True,
        check=True,
    )
    raw = proc.stdout
    best = -1
    for f in range(len(raw) // (3 * h)):
        base = 3 * h * f
        for y in range(h if best < 0 else best):
            o = base + 3 * y
            if _is_marker(raw[o], raw[o + 1], raw[o + 2]):
                best = y
                break
    return best


def _marker_edges(cfr_video: str, cw: int, ch: int, cx: int, y: int, fps: int) -> list[float]:
    proc = subprocess.run(
        [
            "ffmpeg", "-v", "error", "-i", str(cfr_video),
            "-vf", f"crop={cw}:{ch}:{cx}:{y},scale=1:1:flags=area,format=rgb24",
            "-f", "rawvideo", "-",
        ],
        capture_output=True,
        check=True,
    )
    raw = proc.stdout
    times: list[float] = []
    prev_on = False
    for i in range(len(raw) // 3):
        on = _is_marker(raw[3 * i], raw[3 * i + 1], raw[3 * i + 2])
        if on and not prev_on:
            times.append(i / fps)
        prev_on = on
    return times


def detect_marker_times(
    cfr_video: str,
    marker_height_px: int,
    fps: int = CFR_FPS,
) -> list[float]:
    """Rising-edge times (seconds) of the top drift-marker flashes in a CFR video.

    Samples a small region inside the marker strip, averaged to one pixel per
    frame, and finds frames that transition into the marker colour (magenta).
    """
    if marker_height_px <= 0:
        return []
    info = probe(cfr_video)
    ch = max(2, min(marker_height_px - 1, info["height"]))
    cw = 16
    cx = max(0, info["width"] // 2 - cw // 2)
    times = _marker_edges(cfr_video, cw, ch, cx, 0, fps)
    if not times:
        row = _marker_row(cfr_video, info, cx, cw)
        if row > 0:
            times = _marker_edges(cfr_video, cw, max(2, ch - 2), cx, row + 1, fps)
    return times


def align_marker_times(
    marker_times: list[float], step_t_s: list[float], tolerance_s: float = 0.75,
) -> list[float]:
    """Per-step video times when some marker flashes were not captured.

    The screencast can drop a 140 ms flash while the page is busy. The detected
    markers still fix the offset between the manifest's wall clock and the
    video: take the offset most markers agree on, keep each step's own marker
    when one is within tolerance, and place the rest at wall clock + offset.
    Returns [] when no offset is supported by at least two markers.
    """
    best: tuple[int, float] = (0, 0.0)
    for m in marker_times:
        for t in step_t_s:
            off = m - t
            hits = sum(1 for t2 in step_t_s
                       if any(abs(m2 - (t2 + off)) <= tolerance_s for m2 in marker_times))
            if hits > best[0]:
                best = (hits, off)
    hits, off = best
    if hits < 2:
        return []
    out: list[float] = []
    for t in step_t_s:
        near = [m for m in marker_times if abs(m - (t + off)) <= tolerance_s]
        out.append(min(near, key=lambda m: abs(m - (t + off))) if near else t + off)
    return out


def extend_capture(path: str, min_duration_s: float, fps: int = CFR_FPS) -> float:
    """Hold the last frame so the clip lasts at least min_duration_s; returns the duration.

    Cypress's CDP screencast emits frames only while the screen changes, so a
    capture that ends on a static step is cut short of that step's hold.
    """
    cur = probe(path)["duration"]
    if min_duration_s <= cur + 1.0 / fps:
        return cur
    src = Path(path)
    tmp = src.with_name(src.stem + ".ext" + src.suffix)
    _run([
        "ffmpeg", "-y", "-v", "error", "-i", str(src),
        "-vf", f"tpad=stop_mode=clone:stop_duration={min_duration_s - cur:.3f}",
        "-r", str(fps), "-fps_mode", "cfr",
        "-an", "-c:v", "libx264", "-crf", "20", "-preset", "medium",
        "-movflags", "faststart",
        str(tmp),
    ])
    tmp.replace(src)
    return probe(path)["duration"]


def normalize_capture(
    raw_video: str,
    manifest: dict,
    out_path: str,
    target: tuple[int, int] = (1920, 1080),
    preroll_s: float = 1.0,
    workdir: Optional[str] = None,
    fps: int = CFR_FPS,
) -> dict:
    """Produce a clean, CFR, target-resolution body clip and recover step times.

    Returns {"video", "marker_times_s" (relative to the trimmed start, may be
    empty on detection failure → caller falls back to manifest t_ms),
    "body_duration_s", "trim_start_s"}.
    """
    raw = Path(raw_video)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wd = Path(workdir) if workdir else out.parent
    wd.mkdir(parents=True, exist_ok=True)

    mh = _marker_height(manifest)
    n_marker_steps = sum(1 for s in manifest.get("steps", []) if s.get("marker"))

    cfr = wd / (out.stem + ".cfr.mp4")
    _to_cfr(str(raw), str(cfr), fps=fps)

    marker_times = detect_marker_times(str(cfr), mh, fps=fps) if mh else []

    # Trim the pre-first-step preamble (login/navigation) only when we have a
    # confident, complete marker read.
    trim_start = 0.0
    rel_times: list[float] = []
    steps = manifest.get("steps", [])
    if marker_times and n_marker_steps and len(marker_times) != n_marker_steps \
            and n_marker_steps == len(steps):
        # Some flashes were missed: recover the rest from the wall-clock times.
        marker_times = align_marker_times(
            marker_times, [float(s.get("t_ms", 0)) / 1000.0 for s in steps])
    if marker_times and n_marker_steps and len(marker_times) == n_marker_steps:
        trim_start = max(0.0, marker_times[0] - preroll_s)
        rel_times = [max(0.0, t - trim_start) for t in marker_times]

    tw, th = target
    tw -= tw % 2
    th -= th % 2
    crop = f"crop=iw:ih-{mh}:0:{mh}," if mh > 0 else ""
    vf = (
        f"{crop}"
        f"scale={tw}:{th}:force_original_aspect_ratio=decrease,"
        f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:color={BG_HEX}"
    )
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if trim_start > 0:
        cmd += ["-ss", f"{trim_start:.3f}"]
    cmd += [
        "-i", str(cfr),
        "-vf", vf,
        "-r", str(fps), "-fps_mode", "cfr",
        "-an", "-c:v", "libx264", "-crf", "20", "-preset", "medium",
        "-movflags", "faststart",
        str(out),
    ]
    _run(cmd)
    try:
        cfr.unlink()
    except OSError:
        pass

    return {
        "video": str(out),
        "marker_times_s": rel_times,
        "body_duration_s": probe(str(out))["duration"],
        "trim_start_s": trim_start,
    }
