"""Run a media job on GitHub Actions with OpenMontage's own tools.

A job is a JSON file in jobs/. Each step names an OpenMontage tool and its inputs;
outputs are written under renders/<job>/ and committed back by the workflow.

  {"name": "bmd-agent-promo",
   "steps": [
     {"tool": "elevenlabs_tts", "out": "vo/01.mp3", "inputs": {"text": "...", "voice_id": "..."}},
     {"tool": "pixabay_music", "out": "music/bed.mp3", "inputs": {"query": "luxury spa ambient"}}
   ]}

Steps whose output already exists are skipped, so re-running a job only redoes what changed.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.audio.elevenlabs_tts import ElevenLabsTTS  # noqa: E402
from tools.audio.pixabay_music import PixabayMusic  # noqa: E402
from tools.video.pixabay_video import PixabayVideo  # noqa: E402

TOOLS = {"elevenlabs_tts": ElevenLabsTTS, "pixabay_music": PixabayMusic, "pixabay_video": PixabayVideo}


def main(job_path):
    job = json.loads(Path(job_path).read_text())
    out_dir = ROOT / "renders" / job["name"]
    out_dir.mkdir(parents=True, exist_ok=True)
    report, failed = [], 0
    for step in job["steps"]:
        out = out_dir / step["out"]
        if out.exists():
            report.append({"out": step["out"], "status": "kept"})
            continue
        tool = TOOLS[step["tool"]]()
        inputs = dict(step.get("inputs", {}), output_path=str(out))
        res = tool.execute(inputs)
        ok = res.success and out.exists()
        failed += 0 if ok else 1
        report.append({"out": step["out"], "status": "ok" if ok else "failed", "error": res.error,
                       "data": {k: v for k, v in (res.data or {}).items() if isinstance(v, (str, int, float, bool))}})
        print(step["tool"], step["out"], "ok" if ok else f"FAILED: {res.error}")
    (out_dir / "report.json").write_text(json.dumps(report, indent=1))
    return 1 if failed == len(job["steps"]) else 0


if __name__ == "__main__":
    rc = 0
    for p in sys.argv[1:]:
        rc |= main(p)
    sys.exit(rc)
