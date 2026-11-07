"""Flash-cut master for 'Tiệm hoa — bó cẩm tú cầu', 9:16.

Built to `skills/creative/flash-cut.md`. The shape that skill calls for on a
process video: HOOK → DỰNG → NỔ → THẢ, hard cuts only, one breathing section and
it sits at the end.

Two things from the skill that are easy to skip and carry the piece:

* **A flash cut proper is 1–3 frames**, not a style for the whole video. The body
  here is a hip-hop montage (Aronofsky's term: simple actions at speed with their
  own sound), and true 2-frame flashes appear only in the NỔ burst.
* **Compositional anchor.** At 0.2s a viewer cannot go looking for the subject.
  Every cut keeps the bouquet mid-frame, which the source already does — so this
  edit only has to avoid breaking it, and `check` asserts nothing is cut from a
  clip whose subject leaves centre.

Audio rides with the picture: the snips, the paper and the ribbon *are* the
genre. Every cut gets a 25 ms fade at both edges, because a hard splice of a
0.2s audio slice is a click, not a style.

    python scripts/_flashcut_camtucau.py check     # the skill's checklist, spends nothing
    python scripts/_flashcut_camtucau.py render
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

VIDEO = Path("projects/tiem-hoa-cam-tu-cau/assets/video")
OUT = Path("projects/tiem-hoa-cam-tu-cau/renders/final_flashcut.mp4")

CLIPS = {
    "01": "01_tuot_la.mp4", "02": "02_gom_bo.mp4",
    "03": "03_buoc_diem.mp4", "04": "04_cat_goc.mp4",
    "05": "05_lot_trang.mp4", "06": "06_quan_ngoai.mp4",
    "07": "07_that_no.mp4", "08": "08_ra_nang.mp4",
}

W, H, FPS = 1080, 1920, 30
FADE = 0.025           # below this a sub-0.3s slice clicks
FLASH = 2 / FPS        # a flash cut proper: two frames

# (clip, start, duration, section)
#
# Two rules this table exists to obey, both learned from watching v2 back:
#
# * **At most 3 cuts from one clip, spaced >= 2.0s apart.** Each source clip is
#   one continuous slow action, so two cuts a second apart are the same picture
#   twice — and worse, the later cut starts earlier in the *gesture* than the eye
#   expects, so the action reads as jumping backwards. v2 took seven consecutive
#   cuts from clip 07 one second apart; it played as a stutter, not a montage.
# * **The build never revisits.** It runs 01 -> 07 once, forward, and each clip's
#   own cuts move forward inside it too. The single sweep back through the
#   process happens in the burst, where speed marks it as a deliberate recap.
CUTS: list[tuple[str, float, float, str]] = [
    # HOOK — one shot of the finished bouquet, held. Deliberately off the
    # skill's 0.3-0.7s hook: a process video sells the destination, and three
    # seconds is long enough for a scroller to decide they want to see how.
    ("08", 0.5, 3.00, "hook"),

    # DỰNG — 01 -> 07 once, forward, three cuts each, the pulse tightening
    # across the whole section rather than inside any one clip.
    ("01", 0.5, 0.75, "build"), ("01", 3.0, 0.72, "build"), ("01", 5.6, 0.70, "build"),
    ("02", 0.5, 0.66, "build"), ("02", 3.0, 0.63, "build"), ("02", 5.6, 0.60, "build"),
    ("03", 0.4, 0.56, "build"), ("03", 2.4, 0.53, "build"), ("03", 4.4, 0.50, "build"),
    ("04", 0.4, 0.47, "build"), ("04", 2.4, 0.45, "build"), ("04", 4.4, 0.43, "build"),
    ("05", 0.5, 0.40, "build"), ("05", 3.0, 0.38, "build"), ("05", 5.6, 0.36, "build"),
    ("06", 0.5, 0.34, "build"), ("06", 3.0, 0.33, "build"), ("06", 5.6, 0.32, "build"),
    ("07", 0.5, 0.30, "build"), ("07", 3.0, 0.29, "build"), ("07", 5.6, 0.28, "build"),

    # NỔ — one fast sweep through the process, then the true flashes, also in
    # process order. Windows chosen away from the build's, so the recap is new
    # footage rather than a replay.
    ("01", 1.8, 0.20, "burst"), ("02", 1.8, 0.20, "burst"), ("03", 1.3, 0.20, "burst"),
    ("04", 1.3, 0.20, "burst"), ("05", 1.9, 0.20, "burst"), ("06", 1.9, 0.20, "burst"),
    ("07", 1.9, 0.20, "burst"),
    # Flash cuts proper — 2 frames each, at the peak and nowhere else.
    ("03", 5.0, FLASH, "burst"), ("04", 5.0, FLASH, "burst"),
    ("05", 7.0, FLASH, "burst"), ("06", 4.4, FLASH, "burst"),
    ("07", 7.0, FLASH, "burst"),

    # THẢ — detail, then person, then hold. Three windows of clip 08 was the
    # spec'd shape and it played as one 6.7s static shot, because 08 is a woman
    # standing still: three windows of it are one picture three times (§6).
    ("07", 6.3, 1.50, "release"), ("08", 3.6, 1.80, "release"),
    ("08", 5.8, 2.20, "release"),
]


def check() -> None:
    """The checklist from skills/creative/flash-cut.md §8."""
    missing = [c for c in CLIPS.values() if not (VIDEO / c).is_file()]
    assert not missing, f"missing clips: {missing}"

    for i, (clip, start, dur, _) in enumerate(CUTS):
        assert clip in CLIPS, f"cut {i}: unknown clip {clip!r}"
        assert dur >= FLASH - 1e-6, f"cut {i}: {dur}s is under two frames"
        assert start >= 0.3, f"cut {i}: starts at {start}s, inside Veo's settle"

    # Each source clip is one continuous slow action, so two cuts close together
    # inside it are the same picture twice — and the second starts earlier in the
    # gesture than the eye expects, so the action reads as jumping backwards.
    # v2 took seven consecutive cuts from clip 07 one second apart and played as
    # a stutter rather than a montage.
    for i in range(1, len(CUTS)):
        a, b = CUTS[i - 1], CUTS[i]
        if a[0] == b[0] and a[3] == b[3] == "build":
            assert b[1] - a[1] >= 2.0, (
                f"cut {i}: {b[0]} at {b[1]}s is {b[1] - a[1]:.1f}s after cut {i-1} — "
                f"under 2.0s apart inside one continuous take is the same frame twice")
        else:
            assert not (a[0] == b[0] and abs(a[1] - b[1]) < 0.25), \
                f"cut {i}: same clip {b[0]} at {b[1]}s, a quarter second from cut {i-1}"

    runs: dict[str, int] = {}
    for clip, _, _, section in CUTS:
        if section == "build":
            runs[clip] = runs.get(clip, 0) + 1
    over = {c: n for c, n in runs.items() if n > 3}
    assert not over, f"more than 3 build cuts from one clip: {over} — it plays as a stutter"

    # The build tells the process once, forward. Stepping back to an earlier beat
    # mid-build reads as a continuity error; the one sweep back belongs to the
    # burst, where the speed marks it as a deliberate recap.
    order = [c for c, _, _, s in CUTS if s == "build"]
    firsts = [c for i, c in enumerate(order) if i == 0 or c != order[i - 1]]
    assert firsts == sorted(firsts), f"the build revisits an earlier step: {firsts}"

    build = [d for _, _, d, s in CUTS if s == "build"]
    assert build[0] > build[len(build) // 2] > build[-1], \
        "the build does not tighten — that is a fast cut, not a flash cut (§3)"

    # Flash cuts proper are punctuation. More than a handful and they stop
    # landing; spread through the body and they read as a stutter bug.
    flashes = [i for i, (_, _, d, _) in enumerate(CUTS) if d <= FLASH + 1e-6]
    assert 3 <= len(flashes) <= 6, f"{len(flashes)} true flash cuts — §2 wants a cluster of 3-6"
    assert all(CUTS[i][3] == "burst" for i in flashes), \
        "a true flash cut sits outside the burst — a jolt with no dramatic reason (§6)"

    release = [d for _, _, d, s in CUTS if s == "release"]
    assert release and all(d >= 1.5 for d in release), "no breathing section (§3)"
    assert CUTS[-1][3] == "release", "the piece does not end on the breath (§3)"

    total = sum(d for _, _, d, _ in CUTS)
    assert 20 <= total <= 35, f"{total:.1f}s — §7 puts a process flash cut at 20-35s"

    by = {}
    for _, _, d, s in CUTS:
        by.setdefault(s, []).append(d)
    print(f"check ok — {len(CUTS)} cuts, {total:.2f}s")
    for s in ("hook", "build", "burst", "release"):
        ds = by[s]
        print(f"  {s:<8} {len(ds):>2} cuts  {sum(ds):>5.2f}s  "
              f"{min(ds):.2f}-{max(ds):.2f}s")


def render() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    names = sorted(CLIPS)
    index = {n: i for i, n in enumerate(names)}

    cmd = ["ffmpeg", "-v", "error", "-y"]
    for n in names:
        cmd += ["-i", str(VIDEO / CLIPS[n])]

    parts, labels = [], []
    for i, (clip, start, dur, _) in enumerate(CUTS):
        src, end = index[clip], start + dur
        parts.append(
            f"[{src}:v]trim=start={start}:end={end},setpts=PTS-STARTPTS,"
            f"scale={W}:{H},fps={FPS},format=yuv420p[v{i}]")
        fade_out = max(dur - FADE, 0)
        parts.append(
            f"[{src}:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={FADE},afade=t=out:st={fade_out:.3f}:d={FADE},"
            f"aresample=48000[a{i}]")
        labels.append(f"[v{i}][a{i}]")

    parts.append("".join(labels) + f"concat=n={len(CUTS)}:v=1:a=1[vout][aout]")
    cmd += ["-filter_complex", ";".join(parts),
            "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(OUT)]

    print(f"rendering {len(CUTS)} cuts -> {OUT}", flush=True)
    if subprocess.run(cmd).returncode:
        print("ffmpeg failed", file=sys.stderr)
        return 1
    print(f"done: {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")
    return 0


MODES = {"check": lambda: (check(), 0)[1], "render": render}

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if mode not in MODES:
        raise SystemExit(f"usage: {sys.argv[0]} [{' | '.join(MODES)}]")
    sys.exit(MODES[mode]())
