"""One command: a product URL in, a finished vertical ad out.

Chains the pieces that were built and measured separately:

    shopify_product.py  ->  product.json + images
    build_ad_props.py   ->  Remotion props (beat-quantised, DNA-constrained)
    remotion render     ->  silent picture
    ffmpeg              ->  music bed, loudnorm to the TikTok target

Image source is the one real choice. `--stills-dir` uses AI-generated 9:16 model
stills (the DNA-faithful look) and falls back to nothing if they are absent;
without it the ad is built from the shop's own photography, which is square, so
`blur_pad` is selected automatically. Square photos through `cover` decapitate
the model — that is measured, not a guess.

Run `--demo` for the self-check.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REMOTION_DIR = ROOT / "remotion-composer"
PROJECT = REMOTION_DIR / "projects" / "xmas-dna"
PUBLIC = PROJECT / "public"
FPS = 30

# Measured off the four reference ads; see workspace/xmas_dna/dna.json.
DNA_BPM_RANGE = (136.0, 162.0)


def resolve(exe: str) -> str:
    """Windows ships npx as npx.cmd; subprocess without a shell will not find it."""
    found = shutil.which(exe)
    if not found:
        raise SystemExit(f"{exe} not on PATH")
    return found


def run(cmd: list[str], cwd: Path | None = None) -> None:
    r = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit(f"failed: {' '.join(cmd[:3])}...\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")


def stage_images(stills_dir: Path | None, product_dir: Path, prefix: str) -> tuple[list[str], str]:
    """Copy the chosen imagery into the Remotion public dir.

    Returns (filenames, fit). AI stills are natively 9:16 so they take `cover`;
    shop photography is 1:1 and takes `blur_pad`.
    """
    PUBLIC.mkdir(parents=True, exist_ok=True)
    for old in PUBLIC.glob(f"{prefix}_*.jpg"):
        old.unlink()

    if stills_dir and stills_dir.is_dir():
        # Clips win over stills when both exist: a generated clip already moves,
        # which is what the references do in 32/32 shots. The composition turns
        # Ken Burns off for video shots so the motion is not doubled.
        vids = sorted(q for q in stills_dir.glob("*.mp4"))
        if vids:
            for old_v in PUBLIC.glob(f"{prefix}_*.mp4"):
                old_v.unlink()
            names = []
            for i, v in enumerate(vids):
                dst = PUBLIC / f"{prefix}_{i:02d}.mp4"
                shutil.copyfile(v, dst)
                names.append(dst.name)
            return names, "cover"

        srcs = sorted(q for q in stills_dir.glob("*.jpg") if q.name != "prompts.json")
        if srcs:
            names = []
            for i, s in enumerate(srcs):
                dst = PUBLIC / f"{prefix}_{i:02d}.jpg"
                shutil.copyfile(s, dst)
                names.append(dst.name)
            return names, "cover"

    # The scraper already ranked every image. Ignoring that ranking is how a
    # "PRODUCT DETAIL - peel off the protective film" instruction graphic and a
    # burned-in marketing disclaimer ended up as two shots of a finished ad.
    meta = product_dir / "product.json"
    ranked: list[Path] = []
    if meta.is_file():
        doc = json.loads(meta.read_text(encoding="utf-8"))
        order = {"best": 0, "usable": 1}
        keep = [im for im in doc.get("images", [])
                if str(im.get("reference_quality", "usable")).lower() != "unsuitable"]
        keep.sort(key=lambda im: (order.get(str(im.get("reference_quality", "usable")).lower(), 2),
                                  int(str(im.get("position", "99")) or 99)))
        seen: set[str] = set()
        for im in keep:
            f = im.get("file")
            digest = str(im.get("sha256", f))
            if not f or digest in seen:          # positions can repeat one file
                continue
            cand = product_dir / f
            if cand.is_file():
                ranked.append(cand)
                seen.add(digest)
        dropped = len(doc.get("images", [])) - len(ranked)
        if dropped:
            print(f"      dropped {dropped} image(s): unsuitable as reference or duplicate")

    srcs = ranked or sorted(product_dir.glob("*.jpg"))
    if not srcs:
        raise SystemExit(f"no usable images in {product_dir} and no stills in {stills_dir}")
    names = []
    for i, s in enumerate(srcs):
        dst = PUBLIC / f"{prefix}_{i:02d}.jpg"
        shutil.copyfile(s, dst)
        names.append(dst.name)
    return names, "blur_pad"


def pick_music(out_dir: Path, query: str) -> tuple[Path, float]:
    """Search, MEASURE the tempo, and reject anything outside the DNA range.

    The first result is usually too slow: five candidates were tried when this
    was worked out by hand and four of them (108-129 BPM) missed the window.
    """
    import librosa
    import numpy as np
    from tools.audio.pixabay_music import PixabayMusic

    tool = PixabayMusic()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Pixabay is an HTML scrape and its results shift run to run, so a bed that
    # has already passed the tempo gate is reused rather than re-hunted. Without
    # this the same command can succeed and then fail an hour later.
    bed = out_dir / "bed.mp3"
    if bed.is_file():
        y, sr = librosa.load(str(bed), sr=22050)
        bpm = float(np.atleast_1d(librosa.beat.beat_track(y=y, sr=sr)[0])[0])
        if DNA_BPM_RANGE[0] <= bpm <= DNA_BPM_RANGE[1]:
            print(f"  {bpm:6.1f} BPM  IN  (cached bed.mp3)")
            return bed, bpm

    best: tuple[Path, float] | None = None
    for i, q in enumerate([query, "festive jingle bells upbeat", "fast happy dance pop",
                           "upbeat christmas rock", "energetic holiday pop"]):
        cand = out_dir / f"cand_{i}.mp3"
        res = tool.execute({"query": q, "min_duration": 15, "max_duration": 160,
                            "output_path": str(cand)})
        if not res.success:
            continue
        y, sr = librosa.load(str(cand), sr=22050)
        bpm = float(np.atleast_1d(librosa.beat.beat_track(y=y, sr=sr)[0])[0])
        lo, hi = DNA_BPM_RANGE
        print(f"  {bpm:6.1f} BPM  {'IN ' if lo <= bpm <= hi else '   '} {res.data['track_title'][:40]}")
        if lo <= bpm <= hi and (best is None or abs(bpm - 149) < abs(best[1] - 149)):
            best = (cand, bpm)
    if best is None:
        raise SystemExit(f"no track found inside {DNA_BPM_RANGE} BPM; widen the query")
    shutil.copyfile(best[0], bed)
    return bed, best[1]


def _has_audible_audio(path: Path, floor_db: float = -60.0) -> bool:
    """True when the file carries a real audio track, not a silent placeholder.

    Remotion emits a silent AAC track when nothing sounds, which measures about
    -91 dB - indistinguishable from "has audio" unless the level is checked.
    """
    import re
    r = subprocess.run([resolve("ffmpeg"), "-hide_banner", "-i", str(path),
                        "-af", "volumedetect", "-f", "null", "-"],
                       text=True, capture_output=True, encoding="utf-8", errors="replace")
    mm = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stdout + r.stderr)
    return bool(mm) and float(mm.group(1)) > floor_db


def measure_loudnorm(path: Path, duration: float) -> dict:
    import re
    r = subprocess.run(
        [resolve("ffmpeg"), "-hide_banner", "-i", str(path), "-af",
         f"atrim=0:{duration},loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
        text=True, capture_output=True, encoding="utf-8", errors="replace")
    m = re.search(r"\{[^{}]*input_i[^{}]*\}", r.stdout + r.stderr, re.S)
    if not m:
        raise SystemExit("loudnorm measurement failed")
    return json.loads(m.group(0))


SFX_DIR = ROOT / "workspace/xmas_dna/sfx"


# A comedic pass, used when the SFX dir holds meme stings rather than the
# synthesized utility kit. Keyed by filename stem so a dir missing one of them
# simply drops that cue instead of failing.
COMIC_ORDER = ["laugh_01_cut.wav", "impact_01_cut.wav", "oooh_01_cut.wav",
               "groan_01_cut.wav", "drama_01_cut.wav"]


def sfx_plan_comic(props_path: Path, sfx_dir: Path) -> list[tuple[float, str, float]]:
    """Meme stings on the cuts, a laugh on the first reaction, a win on the CTA.

    Levels sit well under the bed because the clips already carry real diegetic
    laughter - a meme laugh stacked on top of a genuine one at equal level just
    sounds like two laughs, so these are accents, not the joke itself.
    """
    props = json.loads(props_path.read_text(encoding="utf-8"))
    cuts, acc = [], 0
    for sh in props["shots"]:
        acc += sh["durationInFrames"]
        cuts.append(acc / FPS)
    swap = [c["fromFrame"] / FPS for c in props["captions"] if c["fromFrame"] > 0]

    plan: list[tuple[float, str, float]] = []
    for i, t in enumerate(cuts[:-1]):
        f = COMIC_ORDER[i % len(COMIC_ORDER)]
        plan.append((max(0.0, t - 0.06), f, -7.0))
    for t in swap:
        plan.append((max(0.0, t - 0.05), "jackpot_01_cut.wav", -6.0))
    return [(t, f, g) for t, f, g in plan if (sfx_dir / f).is_file()]


def sfx_plan(props_path: Path) -> list[tuple[float, str, float]]:
    """Place SFX against the cut list. Returns (seconds, file, gain_db).

    NOTE THIS IS A DELIBERATE DIVERGENCE FROM THE REFERENCES. All four reference
    ads contain ZERO designed sound effects - every transient in them sits on the
    music's own beat grid. This layer exists because it was asked for, not because
    the measurement supports it. Default is off.

    Gains are deliberately low: the bed is already at -14 LUFS and the point is a
    lift on the cut, not a separate event competing with the music.
    """
    props = json.loads(props_path.read_text(encoding="utf-8"))
    cuts, acc = [], 0
    for sh in props["shots"]:
        acc += sh["durationInFrames"]
        cuts.append(acc / FPS)
    swap = [c["fromFrame"] / FPS for c in props["captions"] if c["fromFrame"] > 0]

    plan: list[tuple[float, str, float]] = [(0.05, "sleighbells_01.wav", -9.0)]
    for i, t in enumerate(cuts[:-1]):                 # not the final boundary
        plan.append((t, "whoosh_01.wav" if i % 2 == 0 else "whoosh_02.wav", -11.0))
    for t in swap:
        # -7 dB was measured INAUDIBLE here: the peak in that window was
        # identical with and without the cue, i.e. fully masked by the bed.
        plan.append((t, "pop_01.wav", -2.0))          # the caption swap is the beat
    if cuts:
        plan.append((cuts[-1] - 0.35, "ding_01.wav", -8.0))
    return [(t, f, g) for t, f, g in plan if (SFX_DIR / f).is_file()]


def apply_sfx(video: Path, props_path: Path, out: Path, sfx_dir: Path | None = None) -> int:
    sfx_dir = sfx_dir or SFX_DIR
    comic = sfx_plan_comic(props_path, sfx_dir)
    plan = comic if comic else sfx_plan(props_path)
    if not plan:
        raise SystemExit("no SFX files found; run the kit generator first")
    inputs: list[str] = ["-i", str(video)]
    for _, f, _ in plan:
        inputs += ["-i", str(sfx_dir / f)]

    parts, labels = [], []
    for i, (t, _f, gain) in enumerate(plan, start=1):
        lbl = f"s{i}"
        parts.append(f"[{i}:a]adelay={int(t * 1000)}|{int(t * 1000)},volume={gain}dB[{lbl}]")
        labels.append(f"[{lbl}]")
    # Re-normalise AFTER the layer. Mixing extra sources in pushes the whole
    # track up: a first pass measured true peak -0.2 dBFS (target is -1.5) and
    # the cues themselves only cleared the background by ~0.7 dB, so the layer
    # was both too hot overall and too quiet where it mattered.
    graph = (";".join(parts) + ";" + "[0:a]" + "".join(labels)
             + f"amix=inputs={len(plan) + 1}:duration=first:dropout_transition=0:normalize=0,"
               "alimiter=limit=0.89,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]")

    run([resolve("ffmpeg"), "-hide_banner", "-v", "error", "-y", *inputs,
         "-filter_complex", graph, "-map", "0:v:0", "-map", "[a]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
         "-movflags", "+faststart", str(out)])
    return len(plan)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--product-dir", type=Path, required=True,
                    help="scraped product dir containing product.json + images")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--hook", required=True)
    ap.add_argument("--cta", default="")
    ap.add_argument("--duration", type=float, default=15.0)
    ap.add_argument("--cta-mode", default="punchline_swap",
                    choices=["punchline_swap", "comment_gate", "brand_end_card"])
    ap.add_argument("--stills-dir", type=Path, default=None,
                    help="AI-generated 9:16 stills; falls back to shop photos when absent")
    ap.add_argument("--music-query", default="upbeat festive pop")
    ap.add_argument("--prefix", default="ad")
    ap.add_argument("--sfx-dir", type=Path, default=None,
                    help="folder of SFX wavs; a comedic set is detected by filename")
    ap.add_argument("--sfx", action="store_true",
                    help="add the SFX layer. DIVERGES from the references, which have none")
    a = ap.parse_args()

    # Remotion runs with cwd=remotion-composer, so a relative --out would be
    # written next to the npm project instead of where the caller asked.
    a.out = a.out.resolve()
    a.product_dir = a.product_dir.resolve()
    if a.stills_dir:
        a.stills_dir = a.stills_dir.resolve()

    product_json = a.product_dir / "product.json"
    if not product_json.is_file():
        raise SystemExit(f"missing {product_json}")

    print("[1/4] staging images")
    images, fit = stage_images(a.stills_dir, a.product_dir, a.prefix)
    print(f"      {len(images)} images, fit={fit}")

    print("[2/4] music")
    bed, bpm = pick_music(ROOT / "workspace/xmas_dna/music", a.music_query)
    print(f"      {bed.name} @ {bpm:.1f} BPM")

    print("[3/4] props + render")
    props = PROJECT / f"props.{a.prefix}.json"
    run([sys.executable, str(ROOT / "scripts/build_ad_props.py"), str(product_json),
         "-o", str(props), "--hook", a.hook, "--cta", a.cta,
         "--duration", str(a.duration), "--cta-mode", a.cta_mode,
         "--fit", fit, "--bpm", f"{bpm:.3f}", "--images", *images], cwd=ROOT)

    silent = a.out.with_name(a.out.stem + "_silent.mp4")
    a.out.parent.mkdir(parents=True, exist_ok=True)
    run([resolve("npx"), "remotion", "render", "projects/xmas-dna/index.tsx", "XmasAd",
         str(silent), f"--props={props}", f"--public-dir={PUBLIC}",
         "--codec=h264", "--crf=18", "--concurrency=4"], cwd=REMOTION_DIR)

    print("[4/4] audio")
    m = measure_loudnorm(bed, a.duration)
    fade_at = max(0.0, a.duration - 1.5)
    bed_af = (f"atrim=0:{a.duration},asetpts=N/SR/TB,afade=t=out:st={fade_at}:d=1.5,"
              f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
              f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
              f"offset={m['target_offset']}:linear=true,aresample=48000")

    # Generated clips come back carrying their own DIEGETIC audio - real laughter
    # and in-world lines like "That is the greatest thing I have ever seen".
    # That is exactly what 2 of the 4 reference ads have, and it is not something
    # a soundboard can supply. Replacing it with a music bed throws away the best
    # audio in the piece, so when it exists the bed gets ducked underneath it
    # instead (DNA: duck_music_under_dialogue = true when dialogue is present).
    has_diegetic = _has_audible_audio(silent)
    if has_diegetic:
        print("      clip audio present -> ducking the bed under it")
        graph = (
            f"[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"loudnorm=I=-16:TP=-1.5:LRA=11,asplit=2[vo][sc];"
            f"[1:a]{bed_af},volume=-6dB[bedq];"
            f"[bedq][sc]sidechaincompress=threshold=0.03:ratio=4:attack=15:release=350:"
            f"detection=rms:link=maximum[duck];"
            f"[duck][vo]amix=inputs=2:duration=first:dropout_transition=0:normalize=0,"
            f"loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]"
        )
    else:
        graph = f"[1:a]{bed_af}[a]"

    run([resolve("ffmpeg"), "-hide_banner", "-v", "error", "-y", "-i", str(silent), "-i", str(bed),
         "-filter_complex", graph, "-map", "0:v:0", "-map", "[a]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
         "-shortest", "-movflags", "+faststart", str(a.out)])
    silent.unlink(missing_ok=True)

    if a.sfx:
        print("[5/5] sfx (divergence: the references have none)")
        tmp = a.out.with_name(a.out.stem + "_withsfx.mp4")
        n = apply_sfx(a.out, props, tmp, a.sfx_dir)
        tmp.replace(a.out)
        print(f"      {n} cues placed")

    print(f"\n[done] {a.out}  ({a.out.stat().st_size / 1e6:.1f} MB)")
    return 0


def demo() -> None:
    """Checks the wiring that would silently produce a wrong ad."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        td_p = Path(td)
        stills = td_p / "stills"
        stills.mkdir()
        prod = td_p / "prod"
        prod.mkdir()
        for i in range(3):
            (prod / f"{i}.jpg").write_bytes(b"x")

        # No stills -> shop photos -> blur_pad, because shop photos are square.
        names, fit = stage_images(stills, prod, "demotest")
        assert fit == "blur_pad", fit
        assert len(names) == 3, names

        # Stills present -> cover, because AI stills are natively 9:16.
        for i in range(2):
            (stills / f"s{i}.jpg").write_bytes(b"x")
        names, fit = stage_images(stills, prod, "demotest")
        assert fit == "cover", fit
        assert len(names) == 2, names

        # Staging must not leave the previous product's frames behind — that is
        # how ad A ends up carrying ad B's pictures on a batch run.
        assert len(list(PUBLIC.glob("demotest_*.jpg"))) == 2
        for f in PUBLIC.glob("demotest_*.jpg"):
            f.unlink()
    print("demo ok: image staging + fit selection")


if __name__ == "__main__":
    raise SystemExit(demo() if "--demo" in sys.argv else main())
