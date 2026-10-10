#!/usr/bin/env python3
"""Create or update a tutorial's translation sidecar (<name>.i18n.<lang>.json).

  # 1) get a template (every step's source line, empty `narration` to fill):
  python translate_tutorial.py --tutorial sales-tour --client-dir ../circuitauction-backoffice/client \
      --lang de --template -o /tmp/sales-tour.de.json
  # 2) fill the `narration` lines and the `recipe` texts (by hand or with an LLM), then:
  python translate_tutorial.py --tutorial sales-tour --client-dir ../circuitauction-backoffice/client \
      --lang de --from /tmp/sales-tour.de.json

The template is built from the committed source-language timings.json, so run
author_tutorial.py for the source language first. Then author the new language:
  python author_tutorial.py --tutorial sales-tour --client-dir … --lang de --from-timings
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from lib import tutorial_i18n as I18N  # noqa: E402
from render_tutorial import resolve_tutorial  # noqa: E402


def template_for(tut: dict) -> dict:
    source_steps = (tut.get("source_timings") or {}).get("steps") or []
    if not source_steps:
        src_name = I18N.timings_path(tut["spec"], tut["name"], tut["source_lang"], tut["source_lang"]).name
        raise FileNotFoundError(
            f"no source-language timings for {tut['name']} ({src_name}); "
            "run author_tutorial.py for the source language first"
        )
    return I18N.build_template(
        source_lang=tut["source_lang"], lang=tut["lang"], recipe=tut["recipe"],
        source_steps=source_steps, existing=tut.get("i18n"),
    )


def write_sidecar(tut: dict, doc: dict) -> Path:
    if tut.get("i18n_path") is None:
        raise ValueError(f"{tut['lang']} is the source language of this tutorial; nothing to translate")
    source_steps = (tut.get("source_timings") or {}).get("steps") or []
    errs = I18N.validate_translation(doc, lang=tut["lang"], source_steps=source_steps)
    if errs:
        raise ValueError("translation not saved:\n  - " + "\n  - ".join(errs))
    src_by_idx = {int(s["index"]): (s.get("narration") or "").strip() for s in source_steps}
    clean = {
        "lang": tut["lang"],
        "source_lang": tut["source_lang"],
        "recipe": {k: v for k, v in (doc.get("recipe") or {}).items()
                   if k in I18N.TRANSLATABLE_RECIPE_KEYS and isinstance(v, str) and v.strip()},
        "steps": [
            {"index": int(s["index"]),
             "source": src_by_idx.get(int(s["index"]), (s.get("source") or "").strip()),
             "narration": s["narration"].strip()}
            for s in sorted(doc["steps"], key=lambda x: int(x["index"]))
        ],
    }
    out: Path = tut["i18n_path"]
    if out.is_symlink():
        raise ValueError(f"refusing to write through a symlink: {out}")
    out.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tutorial", required=True)
    ap.add_argument("--client-dir", required=True)
    ap.add_argument("--lang", required=True, help="target language code, e.g. de")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--template", action="store_true", help="print/write the translation template")
    mode.add_argument("--from", dest="from_file", help="filled template JSON to validate and save")
    ap.add_argument("-o", "--output", default=None, help="with --template: write here instead of stdout")
    args = ap.parse_args()

    try:
        tut = resolve_tutorial(Path(args.client_dir).resolve(), args.tutorial, lang=args.lang)
        if args.template:
            doc = template_for(tut)
            text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
            if args.output:
                Path(args.output).write_text(text, encoding="utf-8")
                print(f"OK wrote template {args.output}")
            else:
                sys.stdout.write(text)
            return 0
        doc = json.loads(Path(args.from_file).read_text(encoding="utf-8"))
        out = write_sidecar(tut, doc)
        print(f"OK wrote {out} ({len(doc['steps'])} steps). "
              f"Next: author_tutorial.py --lang {args.lang} --from-timings")
        return 0
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
