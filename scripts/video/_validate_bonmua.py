#!/usr/bin/env python3
"""
_validate_bonmua — prove montage_lib reproduces the Bốn Mùa build path on REAL bon-mua assets.

Reduced (not full 692s) like the original build script's `validate` mode: exercises every recipe
— make_card, slow_loop_scene, concat_segments, narration_offsets_from_durations,
build_narration_track, duck_mux, remux_audio — on the actual project assets, then runs the
Stage-8 QA gates. Read-only on the project: all output goes to a temp dir (never the published
renders/). Asset-gen / TTS are NOT invoked (uses pre-rendered narration + AI music bed).

Run (UTF-8 for Vietnamese card text):
  PYTHONUTF8=1 python scripts/video/_validate_bonmua.py [OUT_DIR]
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
FALLBACK_DUR = 692.0  # original published final.mp4 length, for context only (this is a reduced build)


def main(out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    R = out_dir

    # --- Narration cues (real pre-rendered TTS): intro, 4 tetrads x (in, ex), outro -----------
    groups = ["g0", "g1", "g2", "g3"]
    cues: list[dict] = [{"path": f"{SAMP}/nar_intro_full.mp3", "gap": "paragraph"}]
    for g in groups:
        for e in range(4):
            cues.append({"path": f"{SAMP}/nar_{g}e{e}_in.mp3", "gap": "sentence"})
            cues.append({"path": f"{SAMP}/nar_{g}e{e}_ex.mp3", "gap": "line"})
    cues.append({"path": f"{SAMP}/nar_outro_full.mp3", "gap": "sentence"})

    offs = m.narration_offsets_from_durations(cues, start=1.5)
    needed = max(off + m.probe_duration(p) for p, off in offs) + 3.0
    print(f"[bonmua] {len(offs)} narration cues, timeline needs ~{needed:.1f}s")

    # --- Visual segments: intro card + 4 scene blocks (720p -> rescaled) + outro card ---------
    scenes = ["scene_than", "scene_tho", "scene_tam", "scene_phap"]
    titles = ["QUÁN THÂN", "QUÁN THỌ", "QUÁN TÂM", "QUÁN PHÁP"]
    intro_d, outro_d = 6.0, 6.0
    block_d = max(8.0, (needed - intro_d - outro_d) / len(scenes))

    intro = m.make_card(f"{SCENE}/{scenes[0]}.mp4", "BỐN MÙA CỦA HƠI THỞ", intro_d,
                        f"{R}/seg_intro.mp4", text_small="Mười sáu phép quán niệm hơi thở")
    blocks = [intro]
    for sc, tt in zip(scenes, titles):
        blocks.append(m.slow_loop_scene(f"{SCENE}/{sc}.mp4", block_d, f"{R}/seg_{sc}.mp4"))
    outro = m.make_card(f"{SCENE}/{scenes[-1]}.mp4", "CẢM ƠN QUÝ VỊ ĐÃ XEM", outro_d,
                        f"{R}/seg_outro.mp4", text_small="Đăng ký kênh & bấm Thích để ủng hộ")
    blocks.append(outro)

    silent = m.concat_segments(blocks, f"{R}/final-clean.mp4")
    total = m.probe_duration(silent)

    # --- Audio: narration track + ducked AI music -------------------------------------------
    narr = m.build_narration_track(offs, total, f"{R}/narration.m4a", reverb=True)
    final = m.duck_mux(silent, narr, MUSIC, f"{R}/final.mp4", total=total)

    # --- QA gates (SOP Stage 8) -------------------------------------------------------------
    _qa.assert_video(silent, want_dur=total)
    _qa.assert_video(final, want_dur=total)
    _qa.assert_voice_present(final)
    _qa.copyright_gate(MUSIC, final)

    # --- remux_audio guard proof: accepts silent master, refuses non-silent final -----------
    remuxed = m.remux_audio(silent, narr, f"{R}/final-remuxed.mp4")
    print(f"[bonmua] remux on silent master OK -> {os.path.basename(remuxed)}")
    try:
        m.remux_audio(final, narr, f"{R}/should_not_exist.mp4")
        raise SystemExit("[bonmua][FAIL] remux guard did NOT reject a non-silent master")
    except ValueError:
        print("[bonmua] remux guard correctly refused non-silent master")

    print(f"[bonmua] DONE total={total:.1f}s (reduced; original published = {FALLBACK_DUR:.0f}s) -> {final}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get("TEMP", "."), "tdsvp_bonmua")
    main(out)
