"""Shared plumbing for the VLM clip-rating tool family.

This module keeps the four rating tools (`vlm_clip_rating`, `vlm_zoom_rating`,
`vlm_editorial_ranking`, `vlm_comparative_rank`) free of duplicated
infrastructure: Ollama HTTP transport, frame extraction, JSONL corpus I/O,
and defensive JSON parsing.

Design notes
------------
- All heavy imports (urllib, subprocess, numpy) are lazy so importing this
  module never costs anything at registry-discovery time.
- Every function is pure and dependency-injectable: the tools pass in an
  ``ollama_url`` and ``model`` rather than reading globals, which keeps the
  unit tests hermetic (they mock the HTTP layer).
- JSONL append is the storage primitive. Tools resume by loading the set of
  already-rated clip ids from the output file, so re-runs are idempotent.
"""

from __future__ import annotations

import base64
import ipaddress
import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Optional
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Ollama HTTP transport
# ---------------------------------------------------------------------------


def validate_local_ollama_url(ollama_url: str) -> str:
    """Validate that an Ollama endpoint is HTTP(S) on the local machine."""
    parsed = urlparse(ollama_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("ollama_url must be an http(s) URL on localhost")
    if parsed.username or parsed.password:
        raise ValueError("ollama_url must not include credentials")
    host = parsed.hostname.lower()
    if host != "localhost":
        try:
            if not ipaddress.ip_address(host).is_loopback:
                raise ValueError
        except ValueError as exc:
            raise ValueError(
                "ollama_url must use localhost or a loopback IP; VLM frames "
                "must not be sent to a remote endpoint"
            ) from exc
    return ollama_url.rstrip("/")


def ollama_model_available(
    ollama_url: str = "http://127.0.0.1:11434",
    model: str = "gemma4:12b",
    *,
    timeout: float = 2.0,
) -> bool:
    """Return whether the local Ollama service has *model* installed."""
    import urllib.request

    try:
        base_url = validate_local_ollama_url(ollama_url)
        with urllib.request.urlopen(f"{base_url}/api/tags", timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        installed = {
            str(item.get("name") or item.get("model") or "")
            for item in payload.get("models", [])
        }
        candidates = {model}
        if ":" not in model:
            candidates.add(f"{model}:latest")
        return bool(candidates & installed)
    except Exception:
        return False


def ollama_generate(
    ollama_url: str,
    model: str,
    prompt: str,
    images: list[str],
    *,
    temperature: float = 0.1,
    num_predict: int = 1500,
    format_json: bool = True,
    timeout: float = 600.0,
    max_retries: int = 3,
    retry_backoff: float = 5.0,
) -> str:
    """Call Ollama's /api/generate with base64 images and return raw text.

    Raises ``RuntimeError`` after exhausting retries. This is intentionally
    the only network-touching helper in the family; everything else operates
    on already-fetched data.
    """
    import urllib.request

    ollama_url = validate_local_ollama_url(ollama_url)

    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "images": images,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": num_predict},
    }
    if format_json:
        payload["format"] = "json"

    data = json.dumps(payload).encode()
    last_err: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                ollama_url + "/api/generate",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                out = json.loads(resp.read().decode("utf-8"))
            if out.get("error"):
                raise RuntimeError(f"Ollama error: {out['error']}")
            return str(out.get("response", ""))
        except Exception as exc:  # noqa: BLE001 - retry everything transient
            last_err = exc
            if attempt < max_retries - 1:
                time.sleep(retry_backoff * (attempt + 1))
    raise RuntimeError(f"Ollama request failed after {max_retries} attempts: {last_err}")


# ---------------------------------------------------------------------------
# Defensive JSON parsing (VLM output is not guaranteed well-formed)
# ---------------------------------------------------------------------------


def parse_vlm_json(raw: str) -> dict[str, Any]:
    """Parse a VLM's JSON response, tolerating surrounding prose and drift.

    Strategy: try strict ``json.loads`` first; if that fails, extract the
    largest balanced ``{...}`` region with a brace matcher and try again.
    Returns ``{"error": ..., "raw": ...}`` on total failure so callers can
    record the failure instead of crashing the whole batch.
    """
    raw = (raw or "").strip()
    if not raw:
        return {"error": "empty_response", "raw": raw}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    # Brace-match the largest balanced object.
    start = raw.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(raw)):
            if raw[i] == "{":
                depth += 1
            elif raw[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = raw[start : i + 1]
                    try:
                        parsed = json.loads(candidate)
                        if isinstance(parsed, dict):
                            return parsed
                    except json.JSONDecodeError:
                        break
    return {"error": "json_parse_failed", "raw": raw[:400]}


def safe_float(value: Any, default: float = 0.0) -> float:
    """Coerce a value to float, tolerating strings like '': 6.25, '."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_drift(
    record: dict[str, Any], aliases: dict[str, list[str]]
) -> dict[str, Any]:
    """Fold known field-name drift from VLM output into canonical names.

    ``aliases`` maps canonical name -> list of tolerated alternates. Only the
    first present alternate is used. Mutates and returns ``record``.
    """
    for canonical, alternates in aliases.items():
        if canonical in record:
            continue
        for alt in alternates:
            if alt in record:
                record[canonical] = record[alt]
                break
    return record


# ---------------------------------------------------------------------------
# Frame extraction
# ---------------------------------------------------------------------------


def probe_duration(video_path: str, default: float = 8.0) -> float:
    """Return video duration in seconds via ffprobe (fallback ``default``)."""
    import subprocess

    out = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        capture_output=True,
        text=True,
    ).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return default


def extract_frames(
    video_path: str,
    out_dir: str,
    n_frames: int = 8,
    scale: int = 640,
) -> tuple[list[str], str, float]:
    """Extract ``n_frames`` evenly-spaced frames across the whole clip.

    Returns ``(frame_paths, frame_map_text, duration_s)`` where
    ``frame_map_text`` is a prompt-ready listing of ``frame_NN.jpg = <t>s``
    mappings that lets the VLM anchor timestamps to real seconds.

    Frames are sampled by FPS so they spread across the full duration
    regardless of source framerate (100fps source, 24fps source, whatever).
    """
    import glob
    import os
    import subprocess

    out_dir_p = Path(out_dir)
    out_dir_p.mkdir(parents=True, exist_ok=True)
    for existing in out_dir_p.glob("f_*.jpg"):
        existing.unlink()

    dur = probe_duration(video_path, default=8.0)
    # fps = n_frames / duration spreads frames evenly; clamp so we never
    # request more than n_frames total.
    fps_rate = max(n_frames / dur, 0.5) if dur > 0 else 1.0
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-i", video_path,
            "-vf", f"fps={fps_rate:.4f},scale={scale}:-2",
            "-frames:v", str(n_frames),
            f"{out_dir_p / 'f_%02d.jpg'}",
        ],
        check=True,
        capture_output=True,
    )
    paths = sorted(glob.glob(str(out_dir_p / "f_*.jpg")))
    n = len(paths)
    times = [round(i * dur / max(n - 1, 1), 2) for i in range(n)]
    frame_map = "\n".join(
        f"  frame_{i + 1:02d}.jpg = {t}s" for i, t in enumerate(times)
    )
    return paths, frame_map, dur


def extract_window(
    video_path: str,
    t0: float,
    t1: float,
    out_dir: str,
    *,
    zoom_fps: float = 4.0,
    max_frames: int = 12,
    scale: int = 640,
) -> tuple[list[str], str, float]:
    """Extract high-density frames inside a short window ``[t0, t1]``.

    Used by the zoom pass to get frame-accurate sub-beat timestamps inside
    an already-flagged highlight window. Returns same shape as
    ``extract_frames`` (times are relative to the window start).
    """
    import glob
    import subprocess

    out_dir_p = Path(out_dir)
    out_dir_p.mkdir(parents=True, exist_ok=True)
    for existing in out_dir_p.glob("f_*.jpg"):
        existing.unlink()

    win_dur = max(t1 - t0, 0.5)
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error",
            "-ss", str(max(t0, 0)), "-t", str(win_dur),
            "-i", video_path,
            "-vf", f"fps={zoom_fps},scale={scale}:-2",
            "-frames:v", str(max_frames),
            f"{out_dir_p / 'f_%02d.jpg'}",
        ],
        check=True,
        capture_output=True,
    )
    paths = sorted(glob.glob(str(out_dir_p / "f_*.jpg")))
    n = len(paths)
    times = [round(i * win_dur / max(n - 1, 1), 2) for i in range(n)]
    frame_map = "\n".join(
        f"  frame_{i + 1:02d}.jpg = {t}s" for i, t in enumerate(times)
    )
    return paths, frame_map, win_dur


def images_b64(paths: Iterable[str]) -> list[str]:
    """Base64-encode a list of image paths for the Ollama payload."""
    encoded = []
    for p in paths:
        with open(p, "rb") as fh:
            encoded.append(base64.b64encode(fh.read()).decode())
    return encoded


# ---------------------------------------------------------------------------
# JSONL corpus I/O (append + resume)
# ---------------------------------------------------------------------------


def load_rated_ids(jsonl_path: str) -> set[str]:
    """Return successfully processed clip ids from a JSONL corpus.

    Error records are intentionally excluded so transient ffmpeg/Ollama
    failures remain retryable on the next invocation.
    """
    rated: set[str] = set()
    p = Path(jsonl_path)
    if not p.exists():
        return rated
    with p.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            clip = None if record.get("error") else (record.get("clip") or record.get("id"))
            if clip:
                rated.add(clip)
    return rated


def append_record(jsonl_path: str, record: dict[str, Any]) -> None:
    """Append one JSON record to a JSONL file (creates parent dirs)."""
    p = Path(jsonl_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Generic rubric builder
# ---------------------------------------------------------------------------


def build_behavior_taxonomy(custom: Optional[str] = None) -> str:
    """Return the behavior taxonomy line for prompts.

    ``custom`` may be an extra comma-separated list of labels appended to the
    default set (e.g. campaign-specific behaviors).
    """
    base = (
        "walking_calm|pulling|sniffing|trotting|sitting|lying|"
        "greeting|playing|expression|other"
    )
    if custom:
        return f"{base}|{custom}"
    return base
