"""Stage demo productions + capture the README screenshots for Backlot.

Builds a handful of fictional projects (generated cinematic placeholder art —
safe for the public repo, no real project content) into a staging projects
dir, serves Backlot against it via OPENMONTAGE_PROJECTS_DIR, and captures
screenshots with Playwright.

    python scripts/backlot_screenshot_stage.py            # stage + shoot
    python scripts/backlot_screenshot_stage.py --stage-only
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STAGE_DIR = REPO_ROOT / ".backlot" / "screenshot-stage"
SHOTS_DIR = REPO_ROOT / "docs" / "images" / "backlot"
PORT = 4790

os.environ["OPENMONTAGE_PROJECTS_DIR"] = str(STAGE_DIR)
sys.path.insert(0, str(REPO_ROOT))

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

from lib.checkpoint import init_project, write_checkpoint  # noqa: E402
from lib.events import emit_event  # noqa: E402
from tests.contracts.test_phase0_contracts import sample_artifact  # noqa: E402


# ---------------------------------------------------------------------------
# generated cinematic frames
# ---------------------------------------------------------------------------

def cinematic_frame(path: Path, top, bottom, glow, seed: int, label: str = "") -> None:
    """A moody gradient plate: sky gradient, horizon glow, vignette, grain."""
    w, h = 960, 540
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        t = y / h
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        for x in range(w):
            px[x, y] = (r, g, b)

    # horizon glow + light disc (screen blend so it actually GLOWS)
    from PIL import ImageChops
    glow_layer = Image.new("RGB", (w, h), (0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    cx, cy = w // 2 + (seed % 200 - 100), int(h * 0.62)
    for radius, alpha in ((380, 70), (240, 120), (140, 180), (70, 255)):
        gd.ellipse([cx - radius, cy - radius // 2, cx + radius, cy + radius // 2],
                   fill=tuple(int(c * alpha / 255) for c in glow))
    gd.ellipse([cx - 34, cy - 90, cx + 34, cy - 22],
               fill=tuple(min(255, int(c * 1.15)) for c in glow))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(36))
    img = ImageChops.screen(img, glow_layer)

    d = ImageDraw.Draw(img)
    # horizon line + silhouette blocks
    d.line([(0, cy + 40), (w, cy + 40)], fill=tuple(int(c * 0.25) for c in glow), width=2)
    rnd = seed
    for i in range(6):
        rnd = (rnd * 16807) % 2147483647
        bx = (rnd % w)
        bw = 30 + rnd % 90
        bh = 20 + rnd % 70
        d.rectangle([bx, cy + 40 - bh, bx + bw, cy + 40], fill=(6, 7, 9))
    # grain
    rnd = seed + 7
    for _ in range(2600):
        rnd = (rnd * 48271) % 2147483647
        x, y = rnd % w, (rnd // w) % h
        v = px[x, y]
        px[x, y] = tuple(min(255, c + 10) for c in v)
    # vignette
    vin = Image.new("L", (w, h), 0)
    vd = ImageDraw.Draw(vin)
    vd.ellipse([-w * 0.25, -h * 0.35, w * 1.25, h * 1.35], fill=255)
    vin = vin.filter(ImageFilter.GaussianBlur(120))
    img = Image.composite(img, Image.new("RGB", (w, h), (0, 0, 0)), vin)
    if label:
        d = ImageDraw.Draw(img)
        d.text((28, h - 46), label.upper(), fill=(210, 205, 195))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


PALETTES = {
    "lighthouse": (((8, 12, 24), (28, 22, 16), (240, 168, 60))),
    "static":     (((14, 8, 28), (10, 16, 40), (120, 140, 255))),
    "orchard":    (((6, 18, 14), (20, 30, 18), (140, 220, 140))),
    "paper":      (((30, 24, 18), (16, 12, 10), (235, 200, 150))),
}


# ---------------------------------------------------------------------------
# project staging
# ---------------------------------------------------------------------------

def script_artifact(title: str, scenes: list) -> dict:
    return {
        "version": "1.0", "title": title,
        "total_duration_seconds": scenes[-1][3],
        "sections": [
            {"id": f"s{i+1}", "label": desc.split("—")[0].strip()[:40], "text": narr,
             "start_seconds": s0, "end_seconds": s1}
            for i, (sid, desc, s0, s1, narr) in enumerate(scenes)
        ],
    }


def scene_plan_artifact(scenes: list, hero: str) -> dict:
    return {
        "version": "1.0",
        "scenes": [
            {"id": sid, "type": "generated", "description": desc,
             "start_seconds": s0, "end_seconds": s1, "script_section_id": f"s{i+1}",
             "hero_moment": sid == hero,
             "shot_language": {"shot_size": ["wide", "medium", "close_up", "extreme_close_up"][i % 4],
                               "camera_movement": ["static", "dolly_in", "pan_right", "orbital"][i % 4],
                               "lens_mm": [24, 50, 85, 35][i % 4],
                               "lighting_key": ["golden_hour", "low_key", "rim_lit", "natural"][i % 4]},
             "required_assets": [{"type": "image", "description": desc, "source": "generate"}]}
            for i, (sid, desc, s0, s1, _narr) in enumerate(scenes)
        ],
    }


def decision_log(pid: str) -> dict:
    return {
        "version": "1.0", "project_id": pid,
        "decisions": [
            {"decision_id": "d-001", "stage": "proposal", "category": "provider_selection",
             "subject": "image generation",
             "options_considered": [
                 {"option_id": "flux_image", "label": "FLUX", "score": 0.9,
                  "reason": "strongest cinematic realism at 16:9"},
                 {"option_id": "openai_image", "label": "gpt-image-1", "score": 0.7,
                  "reason": "solid, slightly flatter light",
                  "rejected_because": "less atmospheric depth for night scenes"}],
             "selected": "flux_image",
             "reason": "Strongest cinematic realism for night exteriors.",
             "user_visible": True, "user_approved": True, "confidence": 0.9},
            {"decision_id": "d-002", "stage": "proposal", "category": "render_runtime_selection",
             "subject": "compose",
             "options_considered": [
                 {"option_id": "remotion", "label": "Remotion", "score": 0.85,
                  "reason": "spring typography for the title cards"},
                 {"option_id": "hyperframes", "label": "HyperFrames", "score": 0.6,
                  "reason": "GSAP-native motion", "rejected_because": "stock React stack fits better"}],
             "selected": "remotion", "reason": "Native title cards with spring physics.",
             "user_visible": True, "user_approved": True, "confidence": 0.85},
        ],
    }


def stage_project(pid: str, title: str, palette: str, scenes: list, *,
                  state: str, hero: str, takes_scene: str | None = None) -> None:
    """state: 'complete' | 'assets_live' | 'script_gate' | 'early'"""
    top, bottom, glow = PALETTES[palette]
    pdir = STAGE_DIR / pid
    init_project(pid, title=title, pipeline_type="cinematic",
                 pipeline_dir=STAGE_DIR, style_playbook="clean-professional")
    art_dir = pdir / "artifacts"

    def cp(stage, status, artifacts, **kw):
        write_checkpoint(STAGE_DIR, pid, stage, status, artifacts,
                         pipeline_type="cinematic", **kw)
        time.sleep(0.02)  # distinct mtimes/timestamps

    brief = sample_artifact("research_brief")
    brief["topic"] = title
    cp("research", "completed", {"research_brief": brief})

    script = script_artifact(title, scenes)
    plan = scene_plan_artifact(scenes, hero)
    (art_dir / "decision_log.json").write_text(json.dumps(decision_log(pid), indent=2))

    if state == "early":
        cp("script", "in_progress", {})
        return

    (art_dir / "script.json").write_text(json.dumps(script, indent=2))
    if state == "script_gate":
        cp("script", "awaiting_human", {"script": script},
           review={"round": 1, "decision": "pass", "critical": 0,
                   "suggestions": 2, "nitpicks": 1,
                   "summary": "Hook rewritten to a direct claim; s3 tightened."})
        return

    cp("script", "awaiting_human", {"script": script},
       review={"round": 1, "decision": "pass", "critical": 0, "suggestions": 1,
               "nitpicks": 0, "summary": "Strong spine; trimmed s2."})
    cp("script", "completed", {"script": script}, human_approved=True)
    (art_dir / "scene_plan.json").write_text(json.dumps(plan, indent=2))
    cp("scene_plan", "awaiting_human", {"scene_plan": plan})
    cp("scene_plan", "completed", {"scene_plan": plan}, human_approved=True)

    # assets
    cp("assets", "in_progress", {})
    manifest = {"version": "1.0", "assets": [], "total_cost_usd": 0.0}
    n_done = len(scenes) if state == "complete" else max(1, len(scenes) - 2)
    for i, (sid, desc, _s0, _s1, _n) in enumerate(scenes[:n_done]):
        emit_event(pdir, {"tool": "flux_image", "event": "start", "scene_id": sid})
        rel = f"assets/images/{sid}.png"
        n_takes = 3 if sid == takes_scene else 1
        for take in range(n_takes):
            take_rel = rel if take == n_takes - 1 else f"assets/images/{sid}_t{take+1}.png"
            cinematic_frame(pdir / take_rel, top, bottom, glow,
                            seed=i * 97 + take * 31 + 11, label=f"{title} · {sid}")
            manifest["assets"].append({
                "id": f"img_{sid}_{take+1}", "type": "image", "path": take_rel,
                "scene_id": sid, "source_tool": "flux_image", "model": "flux-1.1-pro",
                "cost_usd": 0.04, "prompt": desc,
                "quality_score": round(0.84 + take * 0.04, 2)})
            manifest["total_cost_usd"] = round(manifest["total_cost_usd"] + 0.04, 2)
        emit_event(pdir, {"tool": "flux_image", "event": "finish", "scene_id": sid,
                          "success": True, "cost_usd": 0.04 * n_takes, "duration_s": 18.4,
                          "output_path": rel})
        (art_dir / "asset_manifest.json").write_text(json.dumps(manifest, indent=2))
        write_checkpoint(STAGE_DIR, pid, "assets", "in_progress", {},
                         pipeline_type="cinematic",
                         metadata={"partial_progress": {
                             "completed_scene_ids": [s[0] for s in scenes[:i + 1]]}},
                         cost_snapshot={"total_spent_usd": manifest["total_cost_usd"],
                                        "total_reserved_usd": 0.0,
                                        "budget_remaining_usd": round(4 - manifest["total_cost_usd"], 2)})

    if state == "assets_live":
        # one scene actively generating right now
        gen_sid = scenes[n_done][0]
        emit_event(pdir, {"tool": "flux_image", "event": "start", "scene_id": gen_sid})
        return

    cp("assets", "awaiting_human", {"asset_manifest": manifest},
       cost_snapshot={"total_spent_usd": manifest["total_cost_usd"],
                      "total_reserved_usd": 0.0,
                      "budget_remaining_usd": round(4 - manifest["total_cost_usd"], 2)})
    cp("assets", "completed", {"asset_manifest": manifest}, human_approved=True)

    # edit + compose (render via ffmpeg slideshow from the frames)
    edit = {"version": "1.0", "cuts": [], "metadata": {"note": "demo"}}
    (art_dir / "edit_decisions.json").write_text(json.dumps(edit, indent=2))
    renders = pdir / "renders"
    renders.mkdir(exist_ok=True)
    first_frame = pdir / "assets" / "images" / f"{scenes[0][0]}.png"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1",
                    "-i", str(first_frame), "-t", "4", "-vf", "scale=960:540",
                    "-pix_fmt", "yuv420p", str(renders / "final.mp4")],
                   check=False, timeout=60)


SCENES_LIGHTHOUSE = [
    ("sc1", "Opening — a lighthouse at dusk", 0, 4, "The coast holds its breath."),
    ("sc2", "The beam sweeps the water", 4, 9, "Every night, the same promise."),
    ("sc3", "A storm builds offshore", 9, 15, "Until the night the light went out."),
    ("sc4", "The keeper climbs the stairs", 15, 21, "Someone still has to climb."),
    ("sc5", "The lamp room, hands on glass", 21, 26, "And someone always does."),
]

SCENES_STATIC = [
    ("sc1", "A radio tower against a violet sky", 0, 5, "The signal arrived at 3:14 a.m."),
    ("sc2", "Rows of receivers, one glowing", 5, 10, "Nobody was listening. Except her."),
    ("sc3", "Static resolving into a pattern", 10, 16, "Noise, she realized, was a language."),
    ("sc4", "The pattern projected on a wall", 16, 22, "And it was asking a question."),
]

SCENES_ORCHARD = [
    ("sc1", "An orchard in first light", 0, 5, "The trees keep a slower calendar."),
    ("sc2", "Hands grafting a branch", 5, 11, "A graft is a promise to a future you won't see."),
    ("sc3", "Seasons blurring over one tree", 11, 18, "Forty springs in a single trunk."),
    ("sc4", "Fruit in a child's hand", 18, 24, "Somebody planted this for you."),
]

SCENES_PAPER = [
    ("sc1", "A desk lamp over folded paper", 0, 4, "Every boat starts as a flat sheet."),
    ("sc2", "Creases becoming a hull", 4, 9, "Twelve folds between idea and vessel."),
    ("sc3", "The boat on dark water", 9, 15, "It will not survive the river."),
    ("sc4", "Paper dissolving, ink blooming", 15, 20, "That was never the point."),
]


def build_stage() -> None:
    if STAGE_DIR.exists():
        shutil.rmtree(STAGE_DIR)
    STAGE_DIR.mkdir(parents=True)
    stage_project("the-last-lighthouse", "The Last Lighthouse", "lighthouse",
                  SCENES_LIGHTHOUSE, state="complete", hero="sc3", takes_scene="sc3")
    stage_project("signal-in-the-static", "Signal in the Static", "static",
                  SCENES_STATIC, state="assets_live", hero="sc3")
    stage_project("the-slow-orchard", "The Slow Orchard", "orchard",
                  SCENES_ORCHARD, state="script_gate", hero="sc3")
    stage_project("paper-boats", "Paper Boats", "paper",
                  SCENES_PAPER, state="early", hero="sc3")
    print(f"[stage] built 4 demo projects in {STAGE_DIR}")


# ---------------------------------------------------------------------------
# screenshots
# ---------------------------------------------------------------------------

SHOTS = [
    ("library", "/?static=1", 1560, 500, 4200),
    ("board-live", "/p/signal-in-the-static?static=1", 1560, 1150, 4200),
    ("script-gate", "/p/the-slow-orchard?static=1", 1560, 760, 3200),
    ("storyboard", "/p/the-last-lighthouse?static=1", 1560, 1500, 4200),
]


def shoot() -> None:
    env = dict(os.environ)
    server = subprocess.Popen(
        [sys.executable, "-m", "backlot", "serve", "--port", str(PORT)],
        env=env, cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/health", timeout=1):
                    break
            except Exception:
                time.sleep(0.4)
        SHOTS_DIR.mkdir(parents=True, exist_ok=True)
        for name, path, w, h, wait_ms in SHOTS:
            out = SHOTS_DIR / f"{name}.png"
            subprocess.run(
                ["npx", "playwright", "screenshot",
                 "--viewport-size", f"{w},{h}",
                 "--wait-for-timeout", str(wait_ms),
                 f"http://127.0.0.1:{PORT}{path}", str(out)],
                check=True, timeout=120, shell=(os.name == "nt"))
            print(f"[shot] {out}")
    finally:
        server.terminate()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-only", action="store_true")
    parser.add_argument("--shoot-only", action="store_true")
    args = parser.parse_args()
    if not args.shoot_only:
        build_stage()
    if not args.stage_only:
        shoot()
