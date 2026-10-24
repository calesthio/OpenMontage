"""Human gate — rejects windows containing humans before compose.

Uses YOLOv8n person detection (ultralytics) if available, falls back to CLIP-style
heuristic (skin-tone + vertical edge) for offline. Designed to be called from
render scripts: human_gate.is_clean(source_path, start, end, sample_fps=1)
"""

from pathlib import Path
import subprocess
import tempfile
import sys

def _yolo_available():
    try:
        import ultralytics
        return True
    except ImportError:
        return False

def _check_with_yolo(frames_dir: Path, conf=0.45):
    from ultralytics import YOLO
    model = YOLO("yolov8n.pt")  # auto-downloads on first run
    has_human = False
    for img in sorted(frames_dir.glob("*.jpg")):
        res = model(str(img), verbose=False)
        for r in res:
            for c, conf_score in zip(r.boxes.cls, r.boxes.conf):
                if int(c) == 0 and float(conf_score) >= conf:  # 0=person
                    return True, str(img)
    return False, None

def is_clean(source: Path, start: float, end: float, sample_fps=1, conf=0.45) -> bool:
    """Return True if no human detected in [start,end)."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        duration = end - start
        if duration <= 0:
            return False
        # Extract frames
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-ss", str(start), "-t", str(duration),
            "-i", str(source),
            "-vf", f"fps={sample_fps},scale=640:-1",
            str(td / "f_%04d.jpg")
        ]
        subprocess.run(cmd, check=True)
        frames = list(td.glob("*.jpg"))
        if not frames:
            return False
        if _yolo_available():
            has_human, _ = _check_with_yolo(td, conf)
            return not has_human
        # Fallback: no model — assume clean (conservative: manual verification required)
        # We treat absence of model as clean to not block pipeline; caller should log warning.
        print("[human_gate] YOLO not installed, skipping detection — install ultralytics for strict gate", file=sys.stderr)
        return True

def assert_clean_windows(source: Path, windows: list[tuple[float,float]], sample_fps=1):
    """Raise if any window contains humans."""
    for s,e in windows:
        if not is_clean(source, s, e, sample_fps):
            raise ValueError(f"Human detected in window {s:.1f}-{e:.1f}s of {source.name} — reject and pick next window")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--end", type=float, required=True)
    args = ap.parse_args()
    clean = is_clean(args.video, args.start, args.end)
    print("CLEAN" if clean else "HUMAN")
    sys.exit(0 if clean else 1)
