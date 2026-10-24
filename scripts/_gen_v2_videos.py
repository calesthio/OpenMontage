"""Generate the eight clips for 'Dưới tán hoa — Ngày 10', anime cut, 9:16.

Each clip starts on its own codex-generated frame rather than on the previous
clip's last frame. The script never shows the woman's face, so wardrobe, garden
and light are the only things that must match — and those are pinned by a shared
preamble in the image prompts. Chaining would have forced every shot to continue
the previous composition, which this script does not want: it calls for a wide,
a back view, two hand close-ups and a final zoom.

Runs strictly sequentially — flow_video holds a lock, because there is one
browser and one Flow composer.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.video.flow_video import FlowVideo  # noqa: E402

IMAGES = Path("projects/duoi-tan-hoa-ngay-10/assets/v2/images")
VIDEO = Path("projects/duoi-tan-hoa-ngay-10/assets/v2/video")

AUDIO_TAIL = " no dialogue, no music, no voices."

SHOTS = [
    ("01_vuon_trong", "6",
     "The camera pans slowly left to right across the empty garden; dry grass stirs in "
     "the breeze, dust and haze drift through the low morning light. No people. "
     "ambient: early birdsong, wind through dry grass." + AUDIO_TAIL),
    ("02_co_gai_vao_vuon", "6",
     "Seen from behind, she walks slowly away from camera further into the garden, the "
     "small wooden box held against her chest; her dress and hair move in the breeze. "
     "The camera follows gently. Her face is never seen. "
     "ambient: footsteps on dry grass, soft wind." + AUDIO_TAIL),
    ("03_mo_hop", "6",
     "Her hands lift the lid of the small wooden box and hold it open, revealing a single "
     "pale seed on folded paper. Only hands and the box in frame; a slow push-in. "
     "ambient: a wooden lid, faint wind." + AUDIO_TAIL),
    ("04_dao_ho", "8",
     "Seen from behind and slightly above, she kneels and works a hand trowel into the dry "
     "earth, opening a small hole; soil breaks and falls. Her face stays turned away. "
     "ambient: a trowel in soil, a quiet breath, distant birds." + AUDIO_TAIL),
    ("05_dat_hat_mam", "8",
     "Her fingers lower the single seed into the small hole, then gently push loose dark "
     "earth over it and press it flat. Only hands and soil in frame; a slow push-in. "
     "ambient: soil falling, distant birds." + AUDIO_TAIL),
    ("06_tuoi_nuoc", "10",
     "Seen from behind, she tips the watering can and a fine stream falls onto the seeded "
     "soil; droplets catch the low sun and glitter, the earth darkens as it drinks. "
     "Her face is never seen. ambient: pouring water, water soaking into soil." + AUDIO_TAIL),
    ("07_dung_nhin_lai", "8",
     "Seen from behind, she stands still and looks out over the patch of turned soil; a "
     "single pink petal drifts slowly across the frame on the breeze. Her face is never "
     "seen. ambient: wind, leaves rustling." + AUDIO_TAIL),
    ("08_bang_ten", "6",
     "The camera pushes in close and low on the patch of freshly turned soil as a hand "
     "presses a small wooden marker sign firmly into the earth beside the seeded spot, "
     "then withdraws. ambient: wood pressed into soil, the wind dropping away." + AUDIO_TAIL),
]


def main() -> int:
    VIDEO.mkdir(parents=True, exist_ok=True)
    tool = FlowVideo()
    results = []

    for name, duration, prompt in SHOTS:
        out = VIDEO / f"{name}.mp4"
        if out.is_file() and out.stat().st_size > 200_000:
            print(f"skip {name} (already generated)", flush=True)
            results.append({"name": name, "ok": True, "skipped": True})
            continue

        started = time.time()
        result = tool.execute({
            "prompt": prompt,
            "operation": "image_to_video",
            "reference_image_path": str(IMAGES / f"{name}.png"),
            "model_variant": "Omni",
            "duration": duration,
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "output_path": str(out),
            "timeout_seconds": 600,
        })
        took = round(time.time() - started, 1)

        row = {"name": name, "ok": result.success, "seconds": took}
        if result.success:
            row["credits"] = result.data.get("flow_credits")
            row["duration"] = result.data.get("duration_seconds")
            print(f"{name}: ok ({took}s) — {row['duration']}s, "
                  f"{row['credits']} credits", flush=True)
        else:
            row["error"] = result.error
            print(f"{name}: FAILED ({took}s)\n   {result.error}", flush=True)
        results.append(row)

        Path("v2_videos_result.json").write_text(
            json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")

    failed = [r["name"] for r in results if not r["ok"]]
    spent = sum(r.get("credits") or 0 for r in results)
    print(f"\ndone: {len(results) - len(failed)}/{len(results)} clips, {spent} credits")
    if failed:
        print("failed:", ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
