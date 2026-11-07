"""Eight opening frames for 'Dưới tán hoa — Ngày 10', anime style, 9:16.

A restyle of the same eight beats, matching a reference the user supplied:
Ghibli-flavoured cel illustration, high-key warm palette, vertical short-video
framing.

Anime is a far kinder medium for character consistency than photoreal. A face
made of soft cel shapes is describable — hair length, eye size, dress cut — so
the same words reproduce it. That is why this version shows her face in the
establishing shot where the photoreal cut could not risk it.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.graphics.codex_image import CodexImage  # noqa: E402

# Every prompt opens with these two blocks. They are the consistency mechanism:
# style first so the render never drifts photoreal, then the character sheet.
STYLE = (
    "Anime illustration, Studio Ghibli inspired: soft cel shading, delicate linework, "
    "painterly watercolour foliage, warm golden sunlight with gentle bloom, high-key "
    "pastel palette of cream, soft gold and pale green. Vertical 9:16 composition. "
)
CHARACTER = (
    "A young woman of about twenty-five with long dark-brown wavy hair falling past her "
    "shoulders, fair skin and large dark eyes, wearing a long ivory-cream linen dress "
    "with three-quarter sleeves and a tiered skirt, and pale canvas shoes. "
)
SETTING = (
    "The place is a wide neglected garden in early morning: dry pale-gold grass, sparse "
    "leggy shrubs, a few bare young trees, low brick edging, and an old white-framed "
    "glasshouse standing empty at the far end. Wilted but bright and hopeful, never bleak. "
)

SHOTS = [
    ("01_vuon_trong",
     STYLE + SETTING + "No people. A tall vertical view down the length of the empty "
     "garden toward the glasshouse, morning light and drifting motes in the air."),
    ("02_co_gai_vao_vuon",
     STYLE + CHARACTER + SETTING + "She stands at the garden gate holding a small wooden "
     "box in both hands, seen from the front at full length, looking ahead with a calm, "
     "uncertain expression. Sunlight falls across her."),
    ("03_mo_hop",
     STYLE + CHARACTER + "Close vertical view of her hands only, opening a small wooden "
     "box. Inside, on folded paper, rests a single pale seed. Only hands and box in frame."),
    ("04_dao_ho",
     STYLE + CHARACTER + SETTING + "Seen from behind and slightly above, she kneels on the "
     "dry grass and digs a small hole with a hand trowel. Her face is turned away."),
    ("05_dat_hat_mam",
     STYLE + CHARACTER + "Close vertical view of her hands lowering a single pale seed into "
     "a small hole in dark soil, then cupping loose earth over it. Only hands and soil."),
    ("06_tuoi_nuoc",
     STYLE + CHARACTER + SETTING + "Seen from behind, she tips a small watering can over the "
     "patch of soil; water catches the low sun in bright droplets. Back view, face away."),
    ("07_dung_nhin_lai",
     STYLE + CHARACTER + SETTING + "Seen from behind, she has stood up and looks back over "
     "the patch of freshly turned soil. A single pink petal drifts across the frame."),
    ("08_bang_ten",
     STYLE + "Very close low vertical view of freshly turned dark soil edged with brick. A "
     "hand presses a small wooden marker sign into the earth beside the seeded spot. Only "
     "the hand, the sign and the soil in frame, warm golden light."),
]

OUT = Path("projects/duoi-tan-hoa-ngay-10/assets/v2/images")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tool = CodexImage()
    results = []
    for name, prompt in SHOTS:
        target = OUT / f"{name}.png"
        if target.is_file() and target.stat().st_size > 50_000:
            print(f"skip {name}", flush=True)
            results.append({"name": name, "ok": True, "skipped": True})
            continue
        started = time.time()
        result = tool.execute({
            "prompt": prompt,
            "size": "1024x1536",          # the portrait option; Flow renders 9:16
            "output_path": str(target),
        })
        took = round(time.time() - started, 1)
        print(f"{name}: {'ok' if result.success else 'FAILED'} ({took}s)", flush=True)
        if not result.success:
            print(f"   {result.error}", flush=True)
        results.append({"name": name, "ok": result.success, "seconds": took,
                        "error": None if result.success else result.error})

    Path("v2_images_result.json").write_text(
        json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    failed = [r["name"] for r in results if not r["ok"]]
    print(f"\ndone: {len(results) - len(failed)}/{len(results)}")
    if failed:
        print("failed:", ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
