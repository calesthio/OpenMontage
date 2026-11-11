#!/usr/bin/env python3
"""Split slides, Ken Burns 9:16 shorts, TTS, mix VO + BGM."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
except ImportError:
    Image = None  # type: ignore

BGM_URL = "https://assets.mixkit.co/music/32/32.mp3"
BGM_SOURCE = (
    "Driving Ambition — Ahjay Stelino — Mixkit License "
    "(https://mixkit.co/free-stock-music/tag/motivational/)"
)
EDGE = Path.home() / "Library/Python/3.9/bin/edge-tts"
if not EDGE.exists():
    EDGE = Path(shutil.which("edge-tts") or "edge-tts")


def run(cmd, **kw):
    subprocess.check_call(cmd, **kw)


def probe_dur(path: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        text=True,
    ).strip()
    return float(out or 0)


def which_ffmpeg_vencoder() -> list[str]:
    if sys.platform == "darwin":
        return ["h264_videotoolbox", "-b:v", "10M"]
    return ["libx264", "-preset", "veryfast", "-crf", "20"]


def require_ffmpeg():
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found. brew install ffmpeg")


# ---------- split ----------

def _col_row_means(im: Image.Image):
    w, h = im.size
    px = im.load()

    def lum(x, y):
        r, g, b = px[x, y][:3]
        return (r + g + b) / 3.0

    cols = []
    for x in range(w):
        s = 0.0
        n = 0
        for y in range(0, h, 2):
            s += lum(x, y)
            n += 1
        cols.append(s / n)
    rows = []
    for y in range(h):
        s = 0.0
        n = 0
        for x in range(0, w, 2):
            s += lum(x, y)
            n += 1
        rows.append(s / n)
    return cols, rows


def _peaks(series, min_gap: int, thresh: float | None = None):
    if thresh is None:
        hi = sorted(series, reverse=True)[: max(3, len(series) // 80)]
        thresh = (sum(hi) / len(hi)) * 0.55
        thresh = max(thresh, (min(series) + max(series)) * 0.45)
    idxs = [i for i, v in enumerate(series) if v >= thresh]
    groups = []
    for i in idxs:
        if not groups or i - groups[-1][-1] > 3:
            groups.append([i])
        else:
            groups[-1].append(i)
    centers = [g[len(g) // 2] for g in groups]
    filtered = []
    for c in centers:
        if not filtered or c - filtered[-1] >= min_gap:
            filtered.append(c)
    return filtered


def detect_grid(im: Image.Image, grid: str | None = None):
    w, h = im.size
    if grid:
        cols_n, rows_n = [int(x) for x in grid.lower().split("x")]
        cw, rh = w / cols_n, h / rows_n
        boxes = []
        for r in range(rows_n):
            for c in range(cols_n):
                boxes.append(
                    (
                        int(c * cw) + 1,
                        int(r * rh) + 1,
                        int((c + 1) * cw) - 1,
                        int((r + 1) * rh) - 1,
                    )
                )
        return boxes
    cols, rows = _col_row_means(im)
    v = _peaks(cols, min_gap=max(40, w // 8))
    hlines = _peaks(rows, min_gap=max(40, h // 8))
    xs = [0] + v + [w]
    ys = [0] + hlines + [h]
    # drop gutters that sit on the outer frame
    xs = [0] + [x for x in xs[1:-1] if 8 < x < w - 8] + [w]
    ys = [0] + [y for y in ys[1:-1] if 8 < y < h - 8] + [h]
    boxes = []
    for i in range(len(ys) - 1):
        for j in range(len(xs) - 1):
            x0, x1 = xs[j] + 1, xs[j + 1] - 1
            y0, y1 = ys[i] + 1, ys[i + 1] - 1
            if x1 - x0 > 40 and y1 - y0 > 40:
                boxes.append((x0, y0, x1, y1))
    return boxes


def cmd_split(args):
    if Image is None:
        sys.exit("Pillow required: pip3 install pillow")
    out = Path(args.out)
    slides = out / "slides"
    slides.mkdir(parents=True, exist_ok=True)
    images = [Path(p) for p in args.images]
    saved = []
    if len(images) == 1:
        im = Image.open(images[0]).convert("RGB")
        boxes = detect_grid(im, args.grid)
        print(f"split {images[0].name} -> {len(boxes)} tiles")
        for i, box in enumerate(boxes, 1):
            tile = im.crop(box)
            dest = slides / f"{i:02d}-slide.png"
            tile.save(dest, "PNG")
            saved.append(dest)
            print(f"  {dest.name} {tile.size}")
    else:
        for i, p in enumerate(images, 1):
            dest = slides / f"{i:02d}-{p.stem}.png"
            Image.open(p).convert("RGB").save(dest, "PNG")
            saved.append(dest)
            print(f"  copy {dest.name}")
    print(f"slides: {len(saved)}")


# ---------- portraits ----------

def compose_9x16(src: Image.Image) -> Image.Image:
    W, H = 1080, 1920
    bg = src.resize((W, H), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(28))
    bg = ImageEnhance.Brightness(bg).enhance(0.32)
    margin = 48
    tw = W - margin * 2
    th = int(src.height * tw / src.width)
    if th > H - 160:
        th = H - 160
        tw = int(src.width * th / src.height)
    tile = src.resize((tw, th), Image.Resampling.LANCZOS)
    canvas = bg.copy()
    px, py = (W - tw) // 2, (H - th) // 2 - 20
    canvas.paste(Image.new("RGB", (tw + 4, th + 4), (255, 198, 0)), (px - 2, py - 2))
    canvas.paste(tile, (px, py))
    return canvas


def cmd_portraits(args):
    if Image is None:
        sys.exit("Pillow required: pip3 install pillow")
    out = Path(args.out)
    dest_dir = out / "portraits-9x16"
    dest_dir.mkdir(parents=True, exist_ok=True)
    slides = sorted((out / "slides").glob("*.png"))
    if not slides:
        sys.exit(f"no slides in {out / 'slides'}")
    for p in slides:
        im = Image.open(p).convert("RGB")
        if im.width >= 720 and abs(im.width / im.height - 9 / 16) < 0.08:
            im.resize((1080, 1920), Image.Resampling.LANCZOS).save(dest_dir / p.name, "PNG")
        else:
            compose_9x16(im).save(dest_dir / p.name, "PNG")
        print(f"portrait {p.name}")


# ---------- tts ----------

def edge_tts(text_file: Path, mp3: Path, voice: str):
    mp3.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(5):
        try:
            run(
                [str(EDGE), "--voice", voice, "--rate=-5%", "--file", str(text_file), "--write-media", str(mp3)],
            )
            if mp3.exists() and mp3.stat().st_size > 2000 and probe_dur(mp3) > 1:
                return
        except subprocess.CalledProcessError:
            pass
        time.sleep(1.5 + attempt)
    sys.exit(f"TTS failed: {text_file}")


def cmd_tts(args):
    out = Path(args.out)
    voice_dir = out / "voice"
    scripts = json.loads((voice_dir / "scripts.json").read_text(encoding="utf-8"))
    clips = scripts["clips"]
    for slug, text in clips:
        txt = voice_dir / f"{slug}.txt"
        txt.write_text(text.strip() + "\n", encoding="utf-8")
        print(f"TTS {slug}")
        edge_tts(txt, voice_dir / f"{slug}.mp3", args.voice)
    if scripts.get("full"):
        (voice_dir / "full-short.txt").write_text(scripts["full"].strip() + "\n", encoding="utf-8")
        print("TTS full-short")
        edge_tts(voice_dir / "full-short.txt", voice_dir / "full-short.mp3", args.voice)


# ---------- encode + mux ----------

def ensure_bgm(out: Path) -> Path:
    bgm_dir = out / "voice" / "bgm"
    bgm_dir.mkdir(parents=True, exist_ok=True)
    dest = bgm_dir / "driving-ambition.mp3"
    if not dest.exists() or dest.stat().st_size < 10000:
        req = urllib.request.Request(
            BGM_URL,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://mixkit.co/free-stock-music/tag/motivational/",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as r, dest.open("wb") as f:
            f.write(r.read())
        (bgm_dir / "SOURCE.txt").write_text(BGM_SOURCE + "\n", encoding="utf-8")
    return dest


def kenburns(png: Path, mp4: Path, seconds: float):
    frames = max(30, int(seconds * 30))
    venc = which_ffmpeg_vencoder()
    vf = (
        f"scale=1296:2304:flags=lanczos,"
        f"zoompan=z='min(1.10,zoom+0.00055)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s=1080x1920:fps=30,format=yuv420p"
    )
    run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-i", str(png),
            "-filter_complex", f"[0:v]{vf}[v]",
            "-map", "[v]", "-t", f"{seconds:.3f}",
            "-c:v", venc[0], *venc[1:],
            "-movflags", "+faststart", str(mp4),
        ]
    )


def mux_vo_bgm(video: Path, vo: Path, bgm: Path | None, dest: Path):
    vdur = probe_dur(video)
    adur = probe_dur(vo)
    lead, tail = 0.25, 0.50
    needed = adur + lead + tail
    extra = max(0.0, needed - vdur)
    target = max(vdur, needed)
    fade_out = max(0.3, target - 1.1)
    venc = which_ffmpeg_vencoder()
    if bgm:
        fc = (
            f"[0:v]tpad=stop_mode=clone:stop_duration={extra:.3f}[v];"
            f"[1:a]adelay=250|250,loudnorm=I=-16:TP=-1.5:LRA=11[voice];"
            f"[2:a]atrim=0:{target:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d=0.45,afade=t=out:st={fade_out:.3f}:d=1.0,"
            f"volume=0.15,highpass=f=90,lowpass=f=3800[bg];"
            f"[bg][voice]sidechaincompress=threshold=0.06:ratio=7:attack=25:release=350:makeup=1.5[ducked];"
            f"[voice][ducked]amix=inputs=2:duration=first:dropout_transition=2,alimiter=limit=0.95[a]"
        )
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video), "-i", str(vo), "-i", str(bgm),
            "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
            "-t", f"{target:.3f}",
            "-c:v", venc[0], *venc[1:], "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", str(dest),
        ]
    else:
        fc = (
            f"[0:v]tpad=stop_mode=clone:stop_duration={extra:.3f}[v];"
            f"[1:a]adelay=250|250,loudnorm=I=-16:TP=-1.5:LRA=11,apad[a]"
        )
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(video), "-i", str(vo),
            "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
            "-t", f"{target:.3f}",
            "-c:v", venc[0], *venc[1:], "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart", str(dest),
        ]
    run(cmd)


def xfade_full(clips: list[Path], dest: Path):
    if len(clips) == 1:
        shutil.copy(clips[0], dest)
        return
    # equalize to 2.7s silent visuals then we mux VO separately; here concat with fade
    inputs = []
    for c in clips:
        inputs += ["-i", str(c)]
    n = len(clips)
    parts = []
    for i in range(1, n):
        left = "0" if i == 1 else f"v{i-1}"
        offset = i * (2.7 - 0.3)
        out = "vout" if i == n - 1 else f"v{i}"
        parts.append(f"[{left}][{i}]xfade=transition=fade:duration=0.3:offset={offset:.1f}[{out}]")
    venc = which_ffmpeg_vencoder()
    run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            *inputs,
            "-filter_complex", ";".join(parts),
            "-map", "[vout]",
            "-c:v", venc[0], *venc[1:],
            "-movflags", "+faststart", str(dest),
        ]
    )


def load_slugs(out: Path, n: int) -> list[str]:
    scripts_path = out / "voice" / "scripts.json"
    if scripts_path.exists():
        clips = json.loads(scripts_path.read_text(encoding="utf-8"))["clips"]
        if len(clips) != n:
            sys.exit(f"scripts.json has {len(clips)} clips but found {n} portraits")
        return [c[0] for c in clips]
    return [f"{i:02d}-slide" for i in range(1, n + 1)]


def cmd_encode(args):
    require_ffmpeg()
    out = Path(args.out)
    portraits = sorted((out / "portraits-9x16").glob("*.png"))
    if not portraits:
        sys.exit("no portraits-9x16")
    slugs = load_slugs(out, len(portraits))
    silent = out / "videos" / "_silent"
    silent.mkdir(parents=True, exist_ok=True)
    for p, slug in zip(portraits, slugs):
        dest = silent / f"{slug}.mp4"
        print(f"encode {slug}")
        kenburns(p, dest, 6.0)
    short_clips = out / "videos" / "_montage"
    short_clips.mkdir(exist_ok=True)
    for i, p in enumerate(portraits, 1):
        kenburns(p, short_clips / f"{i:02d}.mp4", 2.7)
    xfade_full(sorted(short_clips.glob("*.mp4")), out / "videos" / "_full-silent.mp4")
    print("encoded silent clips + montage")


def cmd_mux(args):
    require_ffmpeg()
    out = Path(args.out)
    scripts = json.loads((out / "voice" / "scripts.json").read_text(encoding="utf-8"))
    bgm = None if args.no_bgm else ensure_bgm(out)
    videos = out / "videos"
    tmp = videos / "_mux"
    tmp.mkdir(exist_ok=True)
    for slug, _ in scripts["clips"]:
        silent = videos / "_silent" / f"{slug}.mp4"
        if not silent.exists():
            sys.exit(f"missing silent clip {silent}")
        vo = out / "voice" / f"{slug}.mp3"
        if not vo.exists():
            sys.exit(f"missing VO {vo}")
        dest = tmp / f"{slug}.mp4"
        print(f"mux {slug}")
        mux_vo_bgm(silent, vo, bgm, dest)
        dest.replace(videos / f"{slug}.mp4")
    full_vo = out / "voice" / "full-short.mp3"
    silent_full = videos / "_full-silent.mp4"
    if full_vo.exists() and silent_full.exists():
        print("mux full-short")
        mux_vo_bgm(silent_full, full_vo, bgm, tmp / "full-short.mp4")
        (tmp / "full-short.mp4").replace(videos / "full-short.mp4")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(videos / "_silent", ignore_errors=True)
    shutil.rmtree(videos / "_montage", ignore_errors=True)
    silent_full.unlink(missing_ok=True)
    print("mux done")


def cmd_build(args):
    cmd_tts(args)
    cmd_encode(args)
    cmd_mux(args)


def main():
    p = argparse.ArgumentParser(description="Build 9:16 short videos from slides + transcript")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_out(sp):
        sp.add_argument("--out", required=True, help="Output folder docs/shorts/<slug>")

    sp = sub.add_parser("split")
    add_out(sp)
    sp.add_argument("--images", nargs="+", required=True)
    sp.add_argument("--grid", help="e.g. 3x4")
    sp.set_defaults(func=cmd_split)

    sp = sub.add_parser("portraits")
    add_out(sp)
    sp.set_defaults(func=cmd_portraits)

    sp = sub.add_parser("tts")
    add_out(sp)
    sp.add_argument("--voice", default="vi-VN-NamMinhNeural")
    sp.set_defaults(func=cmd_tts)

    sp = sub.add_parser("encode")
    add_out(sp)
    sp.set_defaults(func=cmd_encode)

    sp = sub.add_parser("mux")
    add_out(sp)
    sp.add_argument("--no-bgm", action="store_true")
    sp.set_defaults(func=cmd_mux)

    sp = sub.add_parser("build")
    add_out(sp)
    sp.add_argument("--voice", default="vi-VN-NamMinhNeural")
    sp.add_argument("--no-bgm", action="store_true")
    sp.set_defaults(func=cmd_build)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
