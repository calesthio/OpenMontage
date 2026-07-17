"""AI-generated-content labeling (《人工智能生成合成内容标识办法》, in force
2025-09-01).

Every final video deliverable MUST carry BOTH:

1. An EXPLICIT label — visible text ("AI生成") on the opening frames,
   prominent enough to be read (font height ~5% of the shorter edge, per the
   companion practice guide to GB/T 45438). Each render engine burns this
   natively:
     - ffmpeg _compose: a PIL-prerendered label PNG overlaid (movie/overlay
       filter — NOT drawtext, which needs a libfreetype-enabled ffmpeg build
       many machines lack) during the first segment's encode
     - Remotion: the AigcBadge layer (remotion-composer/src/AigcLabel.tsx),
       applied to every registered composition via withAigcLabel in Root.tsx
     - HyperFrames: a label clip div injected by _generate_index_html
     - atelier (bespoke Remotion entries): burn_explicit_label() post-pass,
       since the entry's JSX is hand-authored and can't be trusted to include
       the badge
2. An IMPLICIT label — file metadata identifying the service provider
   (name + code) and a content ID, embedded via embed_aigc_metadata()'s
   lossless remux (`-c copy`), so it survives download/export unchanged
   (export_bundle copies byte-for-byte with shutil.copy2).

Labeling is ON BY DEFAULT — it is a legal requirement, not a preference.
The only opt-out is config.yaml's `aigc_label.enabled: false`, which logs a
loud warning and puts the compliance burden on the operator (e.g. a
downstream pipeline that applies its own labels).

The metadata payload follows the GB/T 45438-2025 shape (an "AIGC" JSON
object with Label / ContentProducer / ProduceID fields), written to both a
custom `AIGC` mp4 tag (requires `-movflags use_metadata_tags`) and the
standard `comment` tag as a lowest-common-denominator fallback readers can
always see.
"""

from __future__ import annotations

import json
import logging
import subprocess
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

EXPLICIT_LABEL_TEXT = "AI生成"
EXPLICIT_LABEL_SECONDS = 4.0
# Practice-guide minimum: label text height >= 5% of the shorter edge.
EXPLICIT_LABEL_FONT_RATIO = 0.05

DEFAULT_PROVIDER_NAME = "OpenMontage"
DEFAULT_PROVIDER_CODE = "openmontage"

# CJK-capable fonts to try for ffmpeg drawtext, in preference order.
# (drawtext needs a real font file; "AI生成" contains CJK glyphs.)
_CJK_FONT_CANDIDATES = [
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    # Linux (Noto / WenQuanYi)
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
]


def _config_block() -> dict[str, Any]:
    """The aigc_label block from config.yaml (empty dict when absent)."""
    try:
        raw = yaml.safe_load((REPO_ROOT / "config.yaml").read_text()) or {}
        block = raw.get("aigc_label") or {}
        return block if isinstance(block, dict) else {}
    except Exception:
        return {}


def labeling_enabled() -> bool:
    """Whether AIGC labeling is active. Disabling it is a LOUD, logged act."""
    block = _config_block()
    enabled = block.get("enabled", True)
    if not enabled:
        logger.warning(
            "AIGC labeling is DISABLED via config.yaml aigc_label.enabled=false. "
            "《人工智能生成合成内容标识办法》 requires labels on AI-generated "
            "video — the operator is now responsible for applying them "
            "downstream."
        )
    return bool(enabled)


def provider_identity() -> tuple[str, str]:
    block = _config_block()
    return (
        str(block.get("provider_name") or DEFAULT_PROVIDER_NAME),
        str(block.get("provider_code") or DEFAULT_PROVIDER_CODE),
    )


def new_content_id(output_path: Path | str) -> str:
    """Stable-ish, unique content ID: <project>-<file stem>-<uuid8>.

    The project name is recovered from the projects/<name>/... convention
    when present, so a content ID can be traced back to its production run.
    """
    p = Path(output_path)
    project = ""
    parts = p.resolve().parts
    if "projects" in parts:
        idx = parts.index("projects")
        if idx + 1 < len(parts):
            project = parts[idx + 1]
    bits = [b for b in (project, p.stem) if b]
    return "-".join(bits + [uuid.uuid4().hex[:8]])


def build_metadata_payload(content_id: str) -> dict[str, Any]:
    name, code = provider_identity()
    return {
        "AIGC": {
            "Label": "AI-Generated",          # explicit machine-readable marker
            "ContentProducer": name,           # 服务提供者名称
            "ProducerCode": code,              # 服务提供者编码
            "ProduceID": content_id,           # 内容 ID
        }
    }


def embed_aigc_metadata(
    output_path: Path | str,
    content_id: Optional[str] = None,
    run_command: Optional[Callable[..., Any]] = None,
) -> Optional[dict[str, Any]]:
    """Embed the implicit AIGC label into the file's container metadata.

    Lossless in-place remux (`-c copy`): no quality change, survives
    byte-copy export. Returns {"content_id", "embedded": True} on success;
    None when labeling is disabled or the remux failed (failure is logged,
    never silent, but doesn't destroy an otherwise-good render).
    """
    if not labeling_enabled():
        return None
    path = Path(output_path)
    if not path.is_file():
        return None
    cid = content_id or new_content_id(path)
    payload = json.dumps(build_metadata_payload(cid), ensure_ascii=False)
    tmp = path.with_suffix(".aigc_tmp" + path.suffix)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(path),
        "-map", "0",
        "-c", "copy",
        "-map_metadata", "0",
        # use_metadata_tags persists the custom AIGC key into the mp4 (udta);
        # faststart keeps the deliverable web-streamable after the remux.
        "-movflags", "use_metadata_tags+faststart",
        "-metadata", f"AIGC={payload}",
        "-metadata", f"comment={payload}",
        str(tmp),
    ]
    try:
        if run_command is not None:
            run_command(cmd)
        else:
            subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        tmp.replace(path)
    except Exception as exc:
        logger.warning("AIGC metadata embed failed for %s: %s", path, exc)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return None
    return {"content_id": cid, "embedded": True}


def find_cjk_font() -> Optional[str]:
    for cand in _CJK_FONT_CANDIDATES:
        if Path(cand).is_file():
            return cand
    return None


def explicit_label_fontsize(width: int, height: int) -> int:
    return max(20, round(min(width, height) * EXPLICIT_LABEL_FONT_RATIO))


def render_label_png(
    width: int,
    height: int,
    out_path: Path | str,
    text: str = EXPLICIT_LABEL_TEXT,
) -> Optional[Path]:
    """Pre-render the label pill (white text on translucent black, rounded)
    as a PNG sized for a width×height video.

    PIL + a real CJK font file, NOT ffmpeg drawtext — drawtext requires an
    ffmpeg built with libfreetype, which common builds (e.g. this repo's
    macOS dev machine) lack; the `overlay` filter is in every build. Returns
    None (logged) when no CJK-capable font is found — the caller must
    surface that instead of silently shipping an unlabeled render.
    """
    font_path = find_cjk_font()
    if font_path is None:
        logger.warning(
            "No CJK-capable font found for the AIGC explicit label "
            "(tried %s) — the opening-frame label cannot be rendered.",
            _CJK_FONT_CANDIDATES,
        )
        return None
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        logger.warning("Pillow unavailable — AIGC explicit label cannot be rendered.")
        return None
    fontsize = explicit_label_fontsize(width, height)
    try:
        font = ImageFont.truetype(font_path, fontsize)
    except OSError as exc:
        logger.warning("AIGC label: failed to load font %s: %s", font_path, exc)
        return None
    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    left, top, right, bottom = probe.textbbox((0, 0), text, font=font)
    tw, th = right - left, bottom - top
    pad_x, pad_y = round(fontsize * 0.6), round(fontsize * 0.3)
    img = Image.new("RGBA", (tw + 2 * pad_x, th + 2 * pad_y), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        [0, 0, img.width - 1, img.height - 1],
        radius=round(fontsize * 0.35),
        fill=(0, 0, 0, 102),        # black @ 0.4
    )
    draw.text((pad_x - left, pad_y - top), text, font=font, fill=(255, 255, 255, 235))
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def _filter_escape_path(path: Path) -> str:
    """Escape a filesystem path for use inside an ffmpeg filtergraph value."""
    return str(path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def opening_label_filter(
    width: int,
    height: int,
    workdir: Path | str,
    seconds: float = EXPLICIT_LABEL_SECONDS,
) -> Optional[str]:
    """Filtergraph SUFFIX overlaying the opening-frame label onto a chain.

    Concatenate directly (NO comma) onto a comma-joined -filter:v chain:

        "scale=...,fps=30" + suffix
        → "scale=...,fps=30[aigc_base];movie='label.png'[aigc_wm];
           [aigc_base][aigc_wm]overlay=...:enable='lt(t,4)'"

    The `movie` source lets a single -filter:v carry the PNG watermark, so
    every existing one-input segment command stays a one-input command.
    Returns None when labeling is disabled or no font exists.
    """
    if not labeling_enabled():
        return None
    png = render_label_png(width, height, Path(workdir) / "aigc_label.png")
    if png is None:
        return None
    pad = max(12, explicit_label_fontsize(width, height) // 2)
    return (
        f"[aigc_base];movie='{_filter_escape_path(png.resolve())}'[aigc_wm];"
        f"[aigc_base][aigc_wm]overlay=W-w-{pad}:{pad}:enable='lt(t,{seconds})'"
    )


def burn_explicit_label(
    output_path: Path | str,
    run_command: Optional[Callable[..., Any]] = None,
    codec: str = "libx264",
    crf: int = 18,
    preset: str = "medium",
) -> bool:
    """Whole-file post-pass burning the explicit label onto the opening frames.

    Used by the atelier path, whose hand-authored Remotion entry can't be
    trusted to include the badge. Re-encodes video (crf 18 to keep the loss
    minimal); audio is stream-copied. Returns True on success.
    """
    if not labeling_enabled():
        return False
    path = Path(output_path)
    if not path.is_file():
        return False
    # Probe dimensions for a concrete label size.
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", str(path)],
            check=True, capture_output=True, text=True, timeout=60,
        )
        width, height = (int(v) for v in probe.stdout.strip().split("x")[:2])
    except Exception as exc:
        logger.warning("AIGC label burn: ffprobe failed for %s: %s", path, exc)
        return False
    png = render_label_png(width, height, path.parent / ".aigc_label.png")
    if png is None:
        return False
    pad = max(12, explicit_label_fontsize(width, height) // 2)
    tmp = path.with_suffix(".aigc_label_tmp" + path.suffix)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(path),
        "-i", str(png),
        "-filter_complex",
        f"[0:v][1:v]overlay=W-w-{pad}:{pad}:enable='lt(t,{EXPLICIT_LABEL_SECONDS})'",
        "-c:v", codec, "-crf", str(crf), "-preset", preset,
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(tmp),
    ]
    try:
        if run_command is not None:
            run_command(cmd, timeout=1800)
        else:
            subprocess.run(cmd, check=True, capture_output=True, timeout=1800)
        tmp.replace(path)
    except Exception as exc:
        logger.warning("AIGC explicit-label burn failed for %s: %s", path, exc)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False
    finally:
        try:
            png.unlink(missing_ok=True)
        except OSError:
            pass
    return True
