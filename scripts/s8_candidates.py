#!/usr/bin/env python3
"""S8-1: read-only Hugging Face model-card metadata for the license/fit gate.

Only the public model API and the model card / license files are read. No
weights are downloaded, nothing is executed from the hub.

For every candidate it records:
  - the declared licence (name + link) as the card states it,
  - whether the repo is gated,
  - the parameter count and the dtype mix the hub reports,
  - the total size of the weight files,
  - the diffusers pipeline class the repo declares,
  - the official dtype / VRAM / step-count statements found in the card.

The result is a JSON evidence file; the human-readable verdict table is
docs/openmontage/image_gen/CANDIDATES_S8.md.

Usage:
  python scripts/s8_candidates.py --out docs/openmontage/image_gen/S8_CANDIDATE_FACTS.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
API = "https://huggingface.co/api/models/{repo}"

DEFAULT_CANDIDATES = [
    "ByteDance/SDXL-Lightning",
    "Lykon/dreamshaper-xl-lightning",
    "krea/Krea-2-Turbo",
    "Efficient-Large-Model/Sana_Sprint_1.6B_1024px",
    "Efficient-Large-Model/Sana_Sprint_1.6B_1024px_diffusers",
    "stabilityai/sdxl-turbo",
    "Efficient-Large-Model/Sana_1600M_1024px_diffusers",
    "PixArt-alpha/PixArt-Sigma-XL-2-1024-MS",
    "segmind/SSD-1B",
]

WEIGHT_SUFFIXES = (".safetensors", ".bin", ".pth", ".pt", ".ckpt")
# Statements we look for in the card text, with the sentence kept verbatim.
CARD_PATTERNS = [
    "fp16", "float16", "bfloat16", "VRAM", "GB", "T4", "steps",
    "guidance", "timestep_spacing", "trailing", "Euler", "LCM",
    "commercial", "license",
]


def _get(url: str, timeout: int = 60) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": "openmontage-s8/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except Exception as exc:  # pragma: no cover - network failure
        return 0, str(exc).encode()


def fetch_meta(repo: str) -> Dict[str, Any]:
    status, body = _get(API.format(repo=repo) + "?blobs=true")
    if status != 200:
        return {"repo": repo, "error": f"HTTP {status}", "status": status}
    return json.loads(body)


def parse_facts(repo: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    """Turn the raw hub metadata into the fields the gate needs."""
    card = meta.get("cardData") or {}
    safe = meta.get("safetensors") or {}
    params = safe.get("parameters") or {}
    total_params = safe.get("total") or sum(params.values()) or None

    weight_bytes = 0
    weight_files: List[Dict[str, Any]] = []
    for sib in meta.get("siblings") or []:
        name = sib.get("rfilename") or ""
        if not name.endswith(WEIGHT_SUFFIXES):
            continue
        size = sib.get("size") or 0
        weight_bytes += size
        weight_files.append({"file": name, "bytes": size})
    weight_files.sort(key=lambda f: -f["bytes"])

    pipeline_class = None
    cfg = meta.get("config") or {}
    if isinstance(cfg, dict) and isinstance(cfg.get("diffusers"), dict):
        pipeline_class = cfg["diffusers"].get("_class_name")
    if not pipeline_class:
        for tag in meta.get("tags") or []:
            if tag.startswith("diffusers:"):
                pipeline_class = tag.split(":", 1)[1]
                break

    return {
        "repo": repo,
        "model_id": meta.get("modelId", repo),
        "author": meta.get("author"),
        "gated": meta.get("gated"),
        "license": card.get("license"),
        "license_name": card.get("license_name"),
        "license_link": card.get("license_link"),
        "pipeline_tag": meta.get("pipeline_tag"),
        "pipeline_class": pipeline_class,
        "parameters_total": total_params,
        "parameters_by_dtype": params,
        "weight_bytes_total": weight_bytes,
        "weight_files_top": weight_files[:8],
        "library_name": meta.get("library_name"),
        "tags": [t for t in (meta.get("tags") or [])
                 if t.startswith(("license:", "diffusers:", "base_model:", "arxiv:"))],
        "last_modified": meta.get("lastModified"),
        "downloads": meta.get("downloads"),
    }


def fetch_card(repo: str) -> Dict[str, Any]:
    """Read the model card README and the licence file (text only)."""
    out: Dict[str, Any] = {}
    for name, key in (("README.md", "readme"), ("LICENSE.md", "license_md"),
                      ("LICENSE", "license"), ("LICENSE.txt", "license_txt")):
        status, body = _get(
            f"https://huggingface.co/{repo}/raw/main/{name}")
        if status == 200 and body:
            out[key] = body.decode("utf-8", errors="replace")
    return out


def card_statements(text: str, max_items: int = 24) -> List[str]:
    """Sentences from the card that mention dtype / VRAM / steps / licence."""
    found: List[str] = []
    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block or block.startswith("|"):
            continue
        low = block.lower()
        if any(p.lower() in low for p in CARD_PATTERNS):
            flat = " ".join(block.split())
            if flat not in found:
                found.append(flat[:400])
        if len(found) >= max_items:
            break
    return found


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(
        REPO / "docs/openmontage/image_gen/S8_CANDIDATE_FACTS.json"))
    ap.add_argument("--repos", default=",".join(DEFAULT_CANDIDATES))
    ap.add_argument("--no-cards", action="store_true",
                    help="skip README/LICENSE downloads")
    args = ap.parse_args(argv)

    repos = [r.strip() for r in args.repos.split(",") if r.strip()]
    facts: List[Dict[str, Any]] = []
    for repo in repos:
        meta = fetch_meta(repo)
        entry = parse_facts(repo, meta)
        if "error" not in entry and not args.no_cards:
            card = fetch_card(repo)
            entry["card_statements"] = card_statements(card.get("readme", ""))
            for key in ("license_md", "license", "license_txt"):
                if card.get(key):
                    entry["license_text_excerpt"] = commercial_clauses(
                        card[key])[:12]
                    break
        facts.append(entry)
        if "error" in entry:
            print(f"{repo}: ERROR {entry['error']}")
            continue
        print(f"{repo}: licence={entry['license'] or entry['license_name']} "
              f"gated={entry['gated']} params={entry['parameters_total']} "
              f"weights={entry['weight_bytes_total'] / 1e9:.2f} GB "
              f"class={entry['pipeline_class']}")

    out = Path(args.out)
    out.write_text(json.dumps({
        "schema_version": "1.0",
        "milestone": "S8-1",
        "source": "https://huggingface.co/api/models/<repo> (public model API) "
                  "and huggingface.co/<repo>/raw/main/{README.md,LICENSE*}",
        "read_only": True,
        "candidates": facts,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


COMMERCIAL_PATTERNS = [
    r"[^.]*commercial[^.]*\.",
    r"[^.]*licen[cs]e[^.]*\.",
    r"[^.]*use restrictions?[^.]*\.",
]


def commercial_clauses(text: str) -> List[str]:
    """Sentences from a licence file that mention commercial use or the licence."""
    flat = " ".join(text.split())
    out: List[str] = []
    for pat in COMMERCIAL_PATTERNS:
        for m in re.finditer(pat, flat, flags=re.IGNORECASE):
            s = m.group(0).strip()
            if 40 <= len(s) <= 600 and s not in out:
                out.append(s)
            if len(out) >= 12:
                return out
    return out


if __name__ == "__main__":
    sys.exit(main())
