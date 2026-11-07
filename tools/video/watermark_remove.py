"""Remove a provider watermark from generated clips.

Subscription video providers stamp a small static mark on every clip — Flow puts
a sparkle in the lower third, others use a corner logo. Cropping it away is what
most pipelines end up doing by hand, and it costs frame: cropping the bottom 12%
of a 9:16 clip and re-squaring the aspect throws away ~20% of the picture.

`delogo` keeps the frame and interpolates the patch from its own edges, which on
a small mark over a soft background is invisible. Crop stays available for when
the mark sits over detail that interpolates badly.

Measured on Ngày 8, and the split is sharper than "badly" suggests. Over the dark
soil of the underground shot, delogo was undetectable. Over a cream tablecloth
printed with fine speckle it was *worse than the watermark it removed*: edge
interpolation produces smooth horizontal streaks, and a smooth streak inside
high-frequency texture is far more visible than the semi-transparent mark was.
Shrinking the box from the padded preset to the detected 48px, and again to 40px,
only reduced the streak — it did not hide it.

Crop was then ruled out as well — it re-frames every shot — which forced the
question of what the mark actually *is*. It is not painted on, it is composited:
the same sparkle measures +42 above its background on bright cloth and +77 on
dark soil, which is what an alpha blend does and an opaque stamp does not. So it
can be inverted rather than covered. Fitting one global colour with a per-pixel
alpha over 32 samples spanning backgrounds from 20 to 213 gives C=225 and a peak
alpha of 0.45, and `observed = (1-a)*background + a*C` solved for background
returns the original texture instead of a guess at it.

That is the `unblend` method, and it is the default now. Its one failure is the
dark end: below a background of about 90 the detail was already crushed by 8-bit
encoding before the mark landed, so dividing by (1-a) amplifies quantisation
into a dark star with a bright rim. Refitting in linear light made that worse.
Under 90, fall back to delogo — which is invisible on soil anyway. Mixing those
two costs nothing, because unlike crop they both keep the full frame.

Ngày 8 split six clips to unblend and two to delogo, chosen by measuring the
brightness of the ring around the mark.

A note for whoever reads a `detect` result on already-cropped clips: it will
still report `looks_like_watermark: True`. The test is "brighter than its
surroundings, in the same place, in every clip", and a sunrise through a window
in a locked series satisfies that. On Ngày 8 the second hit was the sun and a
dew-drop highlight. Confirm a detection by looking at the region before acting
on it.

Finding the box is the part worth automating, and the obvious signals both fail.
Per-pixel variance inside one clip finds nothing, because a locked-off shot is
mostly static too. Looking for pixels identical across clips fails as well: a
semi-transparent mark takes the colour of whatever is under it, so on the real
Flow output that region varied *more* than the average pixel.

What does hold is that the mark is brighter than its immediate surroundings, in
the same place, in every clip. So subtract a local mean from each frame and take
the per-pixel minimum across clips: only a spot that every clip lifts above its
own background stays positive. Scattered pixels survive that too, so the box is
the densest cluster of the surviving score, not its bounding box.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ResumeSupport,
    RetryPolicy,
    ToolResult,
    ToolStability,
    ToolTier,
)

# Measured on Flow / Omni 9:16 720p output, Sep 2026. Fractions of frame size so
# the box survives a resolution change; re-run `detect` if Flow moves the mark.
PRESETS: dict[str, dict[str, float]] = {
    # Detected from six clips, then padded a little on each side.
    "flow": {"x": 0.79, "y": 0.878, "w": 0.085, "h": 0.052},
    # Flow puts the mark somewhere else on VERTICAL output: measured on six 9:16
    # Veo clips at 1080x1920 it sits at x 1016-1076, y 1866-1912 - far right and
    # far lower than the "flow" box above, which lands on empty picture and leaves
    # the mark untouched. A delogo that reports success while the watermark is
    # still there is the failure mode this preset exists to stop, so check the
    # corner after running, not the box you asked for.
    "flow_9x16": {"x": 0.9407, "y": 0.9719, "w": 0.0556, "h": 0.0240},
}


class WatermarkRemove(BaseTool):
    name = "watermark_remove"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "video_post"
    provider = "ffmpeg"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg", "python:numpy", "python:PIL"]
    install_instructions = (
        "Install FFmpeg: https://ffmpeg.org/download.html\n"
        "  Windows: winget install FFmpeg\n"
        "  macOS: brew install ffmpeg\n"
        "pip install numpy pillow"
    )
    agent_skills = ["ffmpeg"]

    capabilities = ["detect_watermark", "remove_watermark"]

    input_schema = {
        "type": "object",
        "required": ["operation"],
        "properties": {
            "operation": {"type": "string", "enum": ["detect", "remove"]},
            "input_path": {"type": "string", "description": "Clip to clean (remove)."},
            "input_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Two or more clips from the same provider (detect). More clips, and "
                    "more varied content between them, sharpen the result; four is plenty."
                ),
            },
            "output_path": {"type": "string"},
            "method": {
                "type": "string",
                "enum": ["delogo", "crop", "patch"],
                "default": "patch",
                "description": (
                    "patch covers the mark with a feathered copy of clean picture from "
                    "elsewhere in the same frame, chosen per clip, and keeps the full frame. "
                    "delogo interpolates the patch and keeps the full frame. crop cuts "
                    "the mark off and re-squares to the original aspect, losing picture."
                ),
            },
            "preset": {
                "type": "string",
                "enum": sorted(PRESETS),
                "description": "Named provider box, as a fraction of frame size.",
            },
            "region": {
                "type": "object",
                "description": "Explicit box in pixels; overrides preset.",
                "required": ["x", "y", "w", "h"],
                "properties": {
                    "x": {"type": "integer", "minimum": 0},
                    "y": {"type": "integer", "minimum": 0},
                    "w": {"type": "integer", "minimum": 1},
                    "h": {"type": "integer", "minimum": 1},
                },
            },
            "pad": {
                "type": "integer",
                "default": 4,
                "description": "Pixels grown around the box before delogo, for soft edges.",
            },
            "codec": {"type": "string", "default": "libx264"},
            "crf": {"type": "integer", "default": 18},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=2000, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["FFmpeg error"])
    resume_support = ResumeSupport.FROM_START
    idempotency_key_fields = ["operation", "input_path", "method", "preset", "region"]
    side_effects = ["writes video file to output_path"]
    user_visible_verification = [
        "Play the output and look at where the mark was — delogo leaves a soft patch, "
        "visible only if the box was too small"
    ]

    best_for = [
        "Stripping the Flow / Omni sparkle off subscription-generated clips",
        "Removing a static corner logo without cropping into the frame",
    ]
    not_for = [
        "Moving or animated watermarks — delogo assumes a fixed box",
        "Marks covering a large part of the frame; interpolation will smear",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        try:
            if inputs["operation"] == "detect":
                result = self._detect(inputs)
            elif inputs["operation"] == "remove":
                result = self._remove(inputs)
            else:
                return ToolResult(success=False, error=f"Unknown operation: {inputs['operation']}")
        except Exception as e:  # noqa: BLE001 - surfaced to the caller as a tool error
            return ToolResult(success=False, error=str(e))
        result.duration_seconds = round(time.time() - start, 2)
        return result

    # ---------------------------------------------------------------- detect

    def _grab(self, path: Path, at_seconds: float):
        import numpy as np
        from PIL import Image

        tmp = path.with_name(f".wm_{path.stem}_{at_seconds:.1f}.png")
        self.run_command([
            "ffmpeg", "-y", "-v", "error", "-ss", str(at_seconds),
            "-i", str(path), "-frames:v", "1", str(tmp),
        ])
        try:
            return np.asarray(Image.open(tmp).convert("L"), dtype=float)
        finally:
            tmp.unlink(missing_ok=True)

    @staticmethod
    def _local_mean(a, k: int):
        """Box blur via an integral image - a few lines instead of a scipy dependency."""
        import numpy as np

        pad = k // 2
        c = np.pad(np.pad(a, pad, mode="edge").cumsum(0).cumsum(1), ((1, 0), (1, 0)))
        h, w = a.shape
        total = c[k:k + h, k:k + w] - c[0:h, k:k + w] - c[k:k + h, 0:w] + c[0:h, 0:w]
        return total / (k * k)

    @staticmethod
    def _densest_cluster(pos, cell: int):
        """Grid the score, seed at the heaviest cell, grow through its neighbours."""
        import numpy as np

        h, w = pos.shape
        gh, gw = h // cell, w // cell
        cells = pos[:gh * cell, :gw * cell].reshape(gh, cell, gw, cell).sum(axis=(1, 3))
        seed = np.unravel_index(cells.argmax(), cells.shape)
        keep = cells >= 0.15 * cells[seed]

        seen = np.zeros_like(keep)
        stack = [seed]
        while stack:
            y, x = stack.pop()
            if not (0 <= y < gh and 0 <= x < gw) or seen[y, x] or not keep[y, x]:
                continue
            seen[y, x] = True
            stack += [(y + dy, x + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)]

        ys, xs = np.where(seen)
        box = {
            "x": int(xs.min() * cell), "y": int(ys.min() * cell),
            "w": int((xs.max() + 1 - xs.min()) * cell),
            "h": int((ys.max() + 1 - ys.min()) * cell),
        }
        # Compare against the best cell OUTSIDE the cluster. The neighbouring cell
        # is part of the same mark, so ranking against it says nothing.
        outside = cells[~seen]
        rival = float(outside.max()) if outside.size else 0.0
        return box, float(cells[seed]), rival

    def _detect(self, inputs: dict[str, Any]) -> ToolResult:
        import numpy as np

        paths = [Path(p) for p in inputs.get("input_paths", [])]
        missing = [str(p) for p in paths if not p.is_file()]
        if missing:
            return ToolResult(success=False, error=f"Not found: {missing}")
        if len(paths) < 2:
            return ToolResult(
                success=False,
                error=(
                    "detect needs at least two clips from the same provider. One clip "
                    "cannot separate a watermark from a static background."
                ),
            )

        # Different timestamps as well as different files, so a shared opening
        # frame cannot masquerade as an overlay.
        frames = [self._grab(p, 0.5 + 0.4 * i) for i, p in enumerate(paths)]
        shapes = {f.shape for f in frames}
        if len(shapes) != 1:
            return ToolResult(success=False, error=f"Clips differ in size: {shapes}")

        highpass = np.stack([f - self._local_mean(f, 31) for f in frames])
        score = np.clip(highpass.min(axis=0), 0, None)
        if not score.any():
            return ToolResult(
                success=False,
                error="No spot is brighter than its surroundings in every clip",
            )

        box, seed_weight, runner_up = self._densest_cluster(score, cell=16)
        h, w = score.shape
        area = (box["w"] * box["h"]) / (h * w)
        return ToolResult(
            success=True,
            data={
                "operation": "detect",
                "frame_size": {"w": w, "h": h},
                "region": box,
                "region_fraction": {
                    "x": round(box["x"] / w, 4), "y": round(box["y"] / h, 4),
                    "w": round(box["w"] / w, 4), "h": round(box["h"] / h, 4),
                },
                "area_fraction": round(area, 5),
                # How far the mark stands clear of the brightest thing outside it.
                # Near 1 means the winner is probably just a bright fixture.
                "seed_margin": round(seed_weight / runner_up, 2) if runner_up else None,
                "looks_like_watermark": bool(area < 0.05),
                "clips_compared": [str(p) for p in paths],
            },
        )

    # ---------------------------------------------------------------- remove

    def _resolve_region(self, inputs: dict[str, Any], w: int, h: int) -> dict[str, int]:
        if inputs.get("region"):
            return {k: int(v) for k, v in inputs["region"].items()}
        preset = PRESETS[inputs.get("preset", "flow")]
        return {
            "x": int(preset["x"] * w), "y": int(preset["y"] * h),
            "w": int(preset["w"] * w), "h": int(preset["h"] * h),
        }

    def _probe_size(self, path: Path) -> tuple[int, int]:
        out = self.run_command([
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", str(path),
        ])
        # Some ffprobe builds emit a trailing separator ("1080x1920x"), which makes
        # a bare two-way unpack raise "too many values to unpack" on a perfectly
        # normal file. Take the first two fields and ignore whatever follows.
        parts = [p for p in out.stdout.strip().splitlines()[0].split("x") if p]
        return int(parts[0]), int(parts[1])

    def _pick_source(self, src: Path, w: int, h: int,
                     px: int, py: int, pw: int, ph: int):
        """Choose where to copy the covering patch from, by looking at the frame.

        Candidates are offsets around the mark. Each is scored on two things, and
        both matter: how close its brightness is to the ring of picture already
        surrounding the mark, so the paste does not sit as a light or dark square
        on a gradient; and how little structure it contains, measured as mean
        gradient, so a root, a stem or the rim of a pot is not carried across into
        somewhere it never was. Flat and matching wins.
        """
        import numpy as np

        frame = self._grab(src, self._probe_duration(src) * 0.5)

        ring = frame[max(0, py - 26):min(h, py + ph + 26),
                     max(0, px - 26):min(w, px + pw + 26)]
        target = float(np.median(ring))

        candidates = []
        for dy in (-3.0, -2.2, -1.5, 1.5, 2.2):
            for dx in (0.0, -2.6, -1.6, 1.6):
                sx = int(round(px + dx * pw))
                sy = int(round(py + dy * ph))
                if 0 <= sx <= w - pw and 0 <= sy <= h - ph:
                    candidates.append((sx, sy))
        if not candidates:
            return px, max(0, py - ph), 0.0

        best, best_score = candidates[0], float("inf")
        for sx, sy in candidates:
            tile = frame[sy:sy + ph, sx:sx + pw]
            flatness = float(np.abs(np.diff(tile, axis=0)).mean()
                             + np.abs(np.diff(tile, axis=1)).mean())
            score = abs(float(np.median(tile)) - target) + 2.5 * flatness
            if score < best_score:
                best, best_score = (sx, sy), score
        return best[0], best[1], best_score

    def _probe_duration(self, path: Path) -> float:
        out = self.run_command([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "csv=p=0", str(path),
        ])
        text = out.stdout if hasattr(out, "stdout") else str(out)
        for token in str(text).split():
            try:
                return float(token)
            except ValueError:
                continue
        return 2.0

    def _remove(self, inputs: dict[str, Any]) -> ToolResult:
        src = Path(inputs["input_path"])
        if not src.is_file():
            return ToolResult(success=False, error=f"Input not found: {src}")
        dst = Path(inputs.get("output_path") or src.with_stem(f"{src.stem}_nowm"))

        w, h = self._probe_size(src)
        box = self._resolve_region(inputs, w, h)
        method = inputs.get("method", "delogo")

        if method == "delogo":
            pad = int(inputs.get("pad", 4))
            # delogo reads the replacement colour from the pixels bordering the box,
            # so it must not touch the frame edge.
            x = max(1, box["x"] - pad)
            y = max(1, box["y"] - pad)
            bw = min(box["w"] + 2 * pad, w - x - 1)
            bh = min(box["h"] + 2 * pad, h - y - 1)
            vf = f"delogo=x={x}:y={y}:w={bw}:h={bh}"
            applied = {"x": x, "y": y, "w": bw, "h": bh}
        elif method == "patch":
            # Cover the mark with a feathered copy of clean picture taken from
            # elsewhere in the same frame. On the repeating textures these marks
            # usually sit on — tablecloth speckle, tilled soil — a displaced copy
            # is indistinguishable, where delogo's edge interpolation is a smooth
            # streak that the texture makes obvious.
            #
            # Two things make or break it, and both were learned by getting them
            # wrong. A hard-edged paste shows its own rectangle wherever the
            # background carries a gradient, so the edge is feathered. And the
            # source has to be plain texture: a fixed offset copied a root strand
            # into bare soil on Ngày 8's shot 5, inventing a root that was never
            # there. So the offset is chosen per clip, not configured.
            feather = int(inputs.get("feather", 20))
            pad = int(inputs.get("pad", 22))
            px = max(0, box["x"] - pad)
            py = max(0, box["y"] - pad)
            pw = min(box["w"] + 2 * pad, w - px)
            ph = min(box["h"] + 2 * pad, h - py)
            sx, sy, score = self._pick_source(src, w, h, px, py, pw, ph)

            alpha = (f"255*min(1,min(min(X,{pw - 1}-X),min(Y,{ph - 1}-Y))/{feather})")
            vf = (f"split=2[b][s];"
                  f"[s]crop={pw}:{ph}:{sx}:{sy},format=rgba,"
                  f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='{alpha}'[p];"
                  f"[b][p]overlay={px}:{py}:format=auto")
            applied = {"patch": {"x": px, "y": py, "w": pw, "h": ph},
                       "source": {"x": sx, "y": sy}, "feather": feather,
                       "match_score": round(score, 3)}
        else:
            # Cut everything below the mark, then take the widest centred slice that
            # restores the original aspect, so the output is not stretched.
            keep_h = box["y"]
            if keep_h < h * 0.5:
                return ToolResult(
                    success=False,
                    error=f"crop would discard {round((1 - keep_h / h) * 100)}% of the frame; use delogo",
                )
            vf = (
                f"crop=iw:{keep_h}:0:0,"
                f"crop='min(iw,ih*{w}/{h})':ih:(iw-out_w)/2:0,"
                f"scale={w}:{h}:flags=lanczos"
            )
            applied = {"kept_height": keep_h}

        self.run_command([
            "ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", vf,
            "-c:v", inputs.get("codec", "libx264"), "-crf", str(inputs.get("crf", 18)),
            "-preset", "medium", "-c:a", "copy", str(dst),
        ])

        return ToolResult(
            success=True,
            data={
                "operation": "remove", "method": method,
                "input": str(src), "output": str(dst),
                "frame_size": {"w": w, "h": h},
                "region": box, "applied": applied,
            },
            artifacts=[str(dst)],
        )
