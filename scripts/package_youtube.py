#!/usr/bin/env python3
"""Генерация пакета метаданных YouTube для пилота.

Читает docs/openmontage/pilot/PUBLISH.md и shot_list.json, вырабатывает
package.json с title/description/tags/thumbnail-промптом/главами.
Выход: projects/pilot/manifests/youtube_package.json (черновик, не публикация).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISH = ROOT / "docs/openmontage/pilot/PUBLISH.md"
SHOT_LIST = ROOT / "tools/kaggle_bridge/jobs/pilot-render/shot_list.json"
OUT = ROOT / "projects/pilot/manifests/youtube_package.json"


def parse_publish_md(text: str) -> dict:
    """Извлекает варианты заголовков, описание, теги, промпт превью, главы."""
    data: dict = {}

    # --- Варианты заголовков (таблица) ---
    titles = []
    in_table = False
    for line in text.splitlines():
        if "| # | Заголовок" in line:
            in_table = True
            continue
        if in_table:
            stripped = line.strip()
            if stripped.startswith("|---"):
                continue  # separator row — keep table open
            if stripped.startswith("|") and "---" not in stripped:
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                if len(cells) >= 2 and cells[0].isdigit():
                    titles.append({
                        "num": int(cells[0]),
                        "title": cells[1],
                        "len": int(cells[2]) if cells[2].isdigit() else 0,
                        "note": cells[3] if len(cells) > 3 else "",
                    })
            else:
                in_table = False
    data["title_options"] = titles

    # --- Описание (между ``` блоком) ---
    desc_match = re.search(r"```\n(.*?)\n```", text, re.DOTALL)
    data["description"] = desc_match.group(1).strip() if desc_match else ""

    # --- Теги ---
    tags = []
    in_tags = False
    for line in text.splitlines():
        if "Теги (tags)" in line:
            in_tags = True
            continue
        if in_tags:
            if line.startswith("Первичные:"):
                tags.extend([t.strip() for t in line.split(":", 1)[1].split(",")])
            elif line.startswith("Вторичные:"):
                tags.extend([t.strip() for t in line.split(":", 1)[1].split(",")])
            elif line.startswith("---"):
                break
    data["tags"] = tags

    # --- Промпт превью ---
    prompt_match = re.search(r"```\n(.*?)\n```", text[desc_match.end():] if desc_match else text, re.DOTALL)
    data["thumbnail_prompt"] = prompt_match.group(1).strip() if prompt_match else ""

    # --- Главы ---
    chapters = []
    in_chapters = False
    for line in text.splitlines():
        if "Главы (chapters) по таймкодам" in line:
            in_chapters = True
            continue
        if in_chapters:
            if line.strip().startswith("|") and "---" not in line:
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) >= 2 and re.match(r"^\d+:", cells[0]):
                    chapters.append({"timecode": cells[0], "title": cells[1]})
            elif line.startswith("---"):
                break
    data["chapters"] = chapters

    # --- Метаданные ---
    meta = {}
    for line in text.splitlines():
        if "| **Категория:**" in line:
            meta["category"] = line.split(":", 1)[1].strip()
        elif "| **Язык:**" in line:
            meta["language"] = line.split(":", 1)[1].strip()
        elif "| **Лицензия:**" in line:
            meta["license"] = line.split(":", 1)[1].strip()
    data["metadata"] = meta

    return data


def chapter_times_from_shots(shots: list[dict]) -> list[dict]:
    """Вычисляет абсолютные таймкоды глав из shot_list (начало каждой секции).

    В shot_list тайминги битов относительные к началу секции, поэтому
    суммируем длительности предыдущих секций для получения абсолютного смещения.
    """
    sec_durs: dict[int, float] = {}
    for s in shots:
        sec = s["section"]
        sec_durs[sec] = sec_durs.get(sec, 0.0) + (s["end"] - s["start"])
    chapters = []
    acc = 0.0
    for sec in sorted(sec_durs):
        chapters.append({"section": sec, "start_s": round(acc, 2),
                         "timecode": f"{int(acc//60)}:{int(acc%60):02d}"})
        acc += sec_durs[sec]
    return chapters


def main() -> int:
    if not PUBLISH.exists():
        print(f"[FAIL] PUBLISH.md не найден: {PUBLISH}", file=sys.stderr)
        return 1
    if not SHOT_LIST.exists():
        print(f"[FAIL] shot_list.json не найден: {SHOT_LIST}", file=sys.stderr)
        return 1

    publish_text = PUBLISH.read_text(encoding="utf-8")
    publish = parse_publish_md(publish_text)

    shot_data = json.loads(SHOT_LIST.read_text(encoding="utf-8"))
    shots = shot_data["shots"]
    computed_chapters = chapter_times_from_shots(shots)

    package = {
        "video_file": "remotion-composer/out/pilot-final.mp4",
        "status": "draft",
        "published": False,
        "titles": publish["title_options"],
        "description": publish["description"],
        "tags": publish["tags"],
        "thumbnail_prompt": publish["thumbnail_prompt"],
        "chapters_from_publish": publish["chapters"],
        "chapters_computed": computed_chapters,
        "metadata": publish["metadata"],
        "duration_s": shot_data.get("total_audio_s"),
        "total_frames": shot_data.get("total_frames"),
        "music": None,  # заполняется после решения владельца (B2)
        "rights_records": "projects/pilot/rights/",
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"YouTube пакет записан: {OUT}")
    print(f"  заголовков вариантов: {len(package['titles'])}")
    print(f"  тегов: {len(package['tags'])}")
    print(f"  глав (вычислено): {len(package['chapters_computed'])}")
    print(f"  статус: {package['status']} (не опубликовано)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
