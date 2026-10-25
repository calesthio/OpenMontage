"""Autopilot upload step — runs in a SEPARATE CI job from the agent.

The agent job produces a render plus `projects/<id>/autopilot/publish_request.json`, but never holds
platform credentials. This job holds the YouTube/TikTok credentials and no LLM, so a prompt-injected
agent can't touch the channel accounts. It treats the hand-off file as untrusted: it re-validates the
video and metadata before calling the `youtube_publish` / `tiktok_publish` tools.

  python scripts/autopilot_publish.py                 # newest publish_request.json under projects/
  python scripts/autopilot_publish.py --dry-run       # validate only, no upload
  python scripts/autopilot_publish.py --request projects/x/autopilot/publish_request.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.publishers import _social  # noqa: E402
from tools.publishers.tiktok_publish import TikTokPublish  # noqa: E402
from tools.publishers.youtube_publish import YouTubePublish  # noqa: E402

CHANNEL = ROOT / "autopilot" / "channel.yaml"
HISTORY = ROOT / "autopilot" / "history.json"
MIN_SECONDS, MAX_SECONDS = 8, 180


def find_request(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    found = sorted((ROOT / "projects").glob("*/autopilot/publish_request.json"), key=lambda p: p.stat().st_mtime)
    if not found:
        blocked = sorted((ROOT / "projects").glob("*/autopilot/blocked.json"))
        if blocked:
            sys.exit(f"Agent reported a blocker, nothing to publish:\n{blocked[-1].read_text()[:3000]}")
        sys.exit("No publish_request.json found under projects/*/autopilot/")
    return found[-1]


def safe_path(rel: str) -> Path:
    """Resolve a path from the hand-off file and refuse anything outside projects/."""
    p = (ROOT / rel).resolve()
    if not str(p).startswith(str((ROOT / "projects").resolve()) + os.sep):
        sys.exit(f"Refusing video_path outside projects/: {rel}")
    return p


def validate(req: dict, video: Path) -> list[str]:
    problems = []
    err = _social.validate_video(video)
    if err:
        return [err]
    info = _social.probe_video(video)
    if not info:
        problems.append("ffprobe could not read the video")
    else:
        if info.get("height", 0) <= info.get("width", 0):
            problems.append(f"not vertical: {info.get('width')}x{info.get('height')}")
        if not MIN_SECONDS <= info.get("duration", 0) <= MAX_SECONDS:
            problems.append(f"duration {info.get('duration')}s outside {MIN_SECONDS}-{MAX_SECONDS}s")
    if not str(req.get("title", "")).strip():
        problems.append("missing title")
    if not str(req.get("topic_key", "")).strip():
        problems.append("missing topic_key")
    return problems


def update_history(req: dict, results: dict) -> None:
    history = json.loads(HISTORY.read_text()) if HISTORY.exists() else {"published": []}
    history["published"].append({
        "topic_key": str(req["topic_key"])[:500],
        "title": _social.clean_text(req.get("title"), 100),
        "project_id": str(req.get("project_id", ""))[:120],
        "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "results": results,
    })
    history["published"] = history["published"][-500:]
    HISTORY.write_text(json.dumps(history, indent=2) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--request")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    channel = yaml.safe_load(CHANNEL.read_text())
    pub = channel.get("publishing", {})
    auto = os.environ.get("AUTO_PUBLISH", str(pub.get("auto_publish", False))).lower() in ("1", "true", "yes")
    platforms = pub.get("platforms", ["youtube", "tiktok"])

    req_path = find_request(args.request)
    req = json.loads(req_path.read_text())
    video = safe_path(req["video_path"])
    problems = validate(req, video)
    if problems:
        print("Validation failed:\n- " + "\n- ".join(problems))
        return 2
    print(f"Validated {video.relative_to(ROOT)} — '{req['title']}' (auto_publish={auto})")

    hashtags = list(req.get("hashtags") or [])
    if not any(h.lower().lstrip("#") == "shorts" for h in hashtags):
        hashtags.insert(0, "#Shorts")

    results, failed, logs = {}, False, []
    for platform in platforms:
        if platform == "youtube":
            yt = pub.get("youtube", {})
            res = YouTubePublish().execute({
                "video_path": str(video), "title": req["title"], "description": req.get("description", ""),
                "tags": req.get("tags", []), "hashtags": hashtags, "privacy": "public" if auto else "private",
                "category_id": str(yt.get("category_id", "28")),
                "contains_synthetic_media": bool(yt.get("contains_synthetic_media", True)),
                "dry_run": args.dry_run,
            })
        elif platform == "tiktok":
            res = TikTokPublish().execute({
                "video_path": str(video), "caption": req.get("tiktok_caption") or req["title"],
                "mode": "direct" if auto else "draft",
                "is_aigc": bool(pub.get("tiktok", {}).get("is_aigc", True)), "dry_run": args.dry_run,
            })
        else:
            print(f"Unknown platform {platform!r}, skipping")
            continue

        if res.data and res.data.get("publish_log"):
            logs.extend(res.data["publish_log"]["entries"])
        if res.success:
            results[platform] = res.data.get("url") or res.data.get("tiktok_status") or "dry-run ok"
            print(f"[{platform}] OK: {results[platform]}")
        else:
            failed = True
            results[platform] = f"FAILED: {res.error}"
            print(f"[{platform}] FAILED: {res.error}")

    if logs:
        out = req_path.parent.parent / "artifacts" / "publish_log_social.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"version": "1.0", "entries": logs}, indent=2))

    if not args.dry_run and any(not str(v).startswith("FAILED") for v in results.values()):
        update_history(req, results)  # record even partial success so the topic isn't redone
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
