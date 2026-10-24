"""Generate the eight opening frames for 'Dưới tán hoa — Ngày 10'.

Every prompt carries the same first sentence describing garden, light and
wardrobe. That shared preamble is the whole consistency mechanism here: the
script deliberately never shows the woman's face, so the only things that have
to match across shots are the set, the light and the cream dress — all of which
are describable in words, unlike a face.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from tools.graphics.codex_image import CodexImage

STYLE = (
    "Cinematic film still, 35mm, shallow depth of field. A wide neglected garden "
    "in early morning: dry pale-yellow grass, sparse leggy shrubs, a few bare young "
    "trees, low brick edging. Low sun rakes in from the left through the trees with "
    "thin haze. The palette is wilted but bright and warm — pale gold and soft green, "
    "hopeful rather than bleak. "
)
WOMAN = (
    "A young woman in a cream linen dress with loose hair. Her face is never visible. "
)

SHOTS = [
    ("01_vuon_trong",
     STYLE + "No people. A slow wide view across the empty garden, the dry lawn "
     "stretching to a line of trees, morning light and dust in the air."),
    ("02_co_gai_vao_vuon",
     STYLE + WOMAN + "Seen from behind at a distance, she walks into the garden along "
     "the dry grass, carrying a small wooden box held against her chest. Back view only."),
    ("03_mo_hop",
     STYLE + WOMAN + "Close-up of her hands only, opening a small wooden box. Inside, "
     "on folded paper, sits a single pale seed. Only hands and the box in frame."),
    ("04_dao_ho",
     STYLE + WOMAN + "Seen from behind and slightly above, she kneels on the dry grass "
     "and digs a small hole with a hand trowel. Her face is turned away."),
    ("05_dat_hat_mam",
     STYLE + WOMAN + "Close-up of her hands lowering the single seed into the small "
     "hole in dark soil, then cupping loose earth over it. Only hands and soil in frame."),
    ("06_tuoi_nuoc",
     STYLE + WOMAN + "Seen from behind, she tips a small watering can over the patch of "
     "soil; water catches the low sun in bright droplets. Back view, face away."),
    ("07_dung_nhin_lai",
     STYLE + WOMAN + "Seen from behind, she has stood up and looks back over the patch of "
     "turned soil. A single pink petal drifts across the frame on the breeze. Back view."),
    ("08_bang_ten",
     STYLE + "Very close low view of the patch of freshly turned dark soil. A hand pushes "
     "a small wooden marker sign into the earth beside the seeded spot. Only the hand, the "
     "sign and the soil are in frame."),
]

OUT = Path("projects/duoi-tan-hoa-ngay-10/assets/images")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tool = CodexImage()
    results = []
    for name, prompt in SHOTS:
        target = OUT / f"{name}.png"
        if target.is_file() and target.stat().st_size > 50_000:
            print(f"skip {name} (already generated)", flush=True)
            results.append({"name": name, "ok": True, "skipped": True})
            continue
        started = time.time()
        result = tool.execute({
            "prompt": prompt,
            "size": "1536x1024",
            "output_path": str(target),
        })
        took = round(time.time() - started, 1)
        print(f"{name}: {'ok' if result.success else 'FAILED'} ({took}s)", flush=True)
        if not result.success:
            print(f"   {result.error}", flush=True)
        results.append({"name": name, "ok": result.success, "seconds": took,
                        "error": None if result.success else result.error})

    Path("images_result.json").write_text(
        json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    failed = [r["name"] for r in results if not r["ok"]]
    print(f"\ndone: {len(results) - len(failed)}/{len(results)} generated")
    if failed:
        print("failed:", ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
