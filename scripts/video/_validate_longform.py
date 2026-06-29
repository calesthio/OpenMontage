#!/usr/bin/env python3
"""
_validate_longform — exercise the build path for the long-form sleep format (30–60 min),
the channel's main growth lane that has never actually been built (closes a probe assumption).

Two proofs, both on real bon-mua narration assets (no asset-gen / TTS):
  PROOF 1 — batch-amix at scale: build a narration track from HUNDREDS of cues so the
            batched amix in build_narration_track is forced into many batches (no OOM /
            arg-limit blowup). Audio-only, so it stays cheap despite the long timeline.
  PROOF 2 — long build path: intro card + several long looped blocks + outro -> silent
            master -> fitting narration -> duck_mux. Proves concat/offset-helper/duck
            survive the long repetitive structure.

Run:
  PYTHONUTF8=1 python scripts/video/_validate_longform.py [OUT_DIR]
"""
from __future__ import annotations
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import montage_lib as m  # noqa: E402
import _qa  # noqa: E402

ROOT = "projects/bon-mua-cua-hoi-tho"
ASS = f"{ROOT}/assets"
SAMP = f"{ASS}/sample"
SCENE = f"{ASS}/video"
MUSIC = f"{ASS}/music/_new/bed-692.mp3"

# Real pre-rendered narration pool to cycle through.
NAR_POOL = [f"{SAMP}/nar_{g}e{e}_{x}.mp3"
            for g in ("g0", "g1", "g2", "g3") for e in range(4) for x in ("in", "ex")]


def proof_batch_amix(out_dir: str, *, n_cues: int = 240, spacing: float = 12.0) -> None:
    """PROOF 1: hundreds of cues over a long (audio-only) timeline -> many amix batches."""
    pool = [p for p in NAR_POOL if os.path.isfile(p)]
    if not pool:
        raise SystemExit("[longform] no narration assets found for batch-amix proof")
    # Manual absolute offsets (helper supports override): evenly spaced, realistic sleep cadence.
    cues = [(pool[i % len(pool)], round(5.0 + i * spacing, 2)) for i in range(n_cues)]
    total = cues[-1][1] + 20.0  # >= last cue end so build's -t trims nothing
    last_end = cues[-1][1] + m.probe_duration(cues[-1][0])  # amix duration=longest ends here
    batches = (n_cues + 30 - 1) // 30  # batch_size default = 30
    print(f"[longform] PROOF1 batch-amix: {n_cues} cues over {total:.0f}s "
          f"-> {batches} amix batches (batch_size=30)")
    narr = m.build_narration_track(cues, total, f"{out_dir}/longform_narration.m4a", reverb=False)
    got = m.probe_duration(narr)
    # Track ends at the last cue (no silence padding to `total`); confirm it spans the timeline.
    assert got <= total + 2.5, f"narration {got:.1f}s overran total {total:.1f}s"
    assert abs(got - last_end) < 2.5, f"narration {got:.1f}s != last-cue end {last_end:.1f}s"
    _qa.assert_voice_present(narr)
    print(f"[longform] PROOF1 OK: {batches}-batch narration built, {got:.0f}s -> {narr}")


def proof_long_build(out_dir: str) -> None:
    """PROOF 2: long sleep skeleton through the full visual+mix path (kept short to render fast)."""
    R = out_dir
    block_d = 40.0  # each looped block; 3 blocks + cards ~= 132s long-path smoke
    intro = m.make_card(f"{SCENE}/scene_than.mp4", "THIỀN NGỦ SÂU", 6.0,
                        f"{R}/lf_intro.mp4", text_small="Buông thư toàn thân — đi vào giấc ngủ")
    blocks = [intro]
    for i, sc in enumerate(["scene_tho", "scene_tam", "scene_phap"]):
        blocks.append(m.slow_loop_scene(f"{SCENE}/{sc}.mp4", block_d, f"{R}/lf_block{i}.mp4"))
    outro = m.make_card(f"{SCENE}/scene_phap.mp4", "NGỦ NGON", 6.0, f"{R}/lf_outro.mp4",
                        text_small="Đăng ký kênh để nghe thêm")
    blocks.append(outro)
    silent = m.concat_segments(blocks, f"{R}/lf_clean.mp4")
    total = m.probe_duration(silent)

    # Narration that fits the long structure (offset helper, sentence cadence).
    pool = [p for p in NAR_POOL if os.path.isfile(p)]
    cues = [{"path": pool[i % len(pool)], "gap": "line"} for i in range(12)]
    offs = m.narration_offsets_from_durations(cues, start=4.0)
    narr = m.build_narration_track(offs, total, f"{R}/lf_narr.m4a", reverb=True)
    final = m.duck_mux(silent, narr, MUSIC, f"{R}/lf_final.mp4", total=total)

    _qa.assert_video(final, want_dur=total)
    _qa.assert_voice_present(final)
    _qa.copyright_gate(MUSIC, final)
    print(f"[longform] PROOF2 OK: long build path {total:.0f}s -> {final}")


def main(out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    proof_batch_amix(out_dir)
    proof_long_build(out_dir)
    print("[longform] DONE — batch-amix scale + long build path both validated")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get("TEMP", "."), "tdsvp_longform")
    main(out)
