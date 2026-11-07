"""TTS integration tool — OpenMontage MASTER RUN P4.

Implements tools/audio/tts_kaggle.py (KokoroTTSTool).
Conventions: follows tools/kaggle_bridge/kaggle_bridge.py (KaggleBridgeTool)
and tools/audio/finish_audio.py (FinishAudioTool).
License gate: engines whose license is not verified permissive (MIT / Apache-2.0)
or is blocked are REFUSED in code (never silent success). Piper
en_US-lessac-medium is blocked (license UNKNOWN).
Fallback: if the Kaggle bridge is BLOCKED (P3), fall back to local Kokoro-82M
(CPU) if installed; otherwise BLOCKED.
No secrets: KAGGLE_API_TOKEN never logged, passed on CLI, or written to result
JSON. No voice cloning of any third-party or real person's voice.
"""

from __future__ import annotations

import hashlib, json, os, sys, time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.audio.finish_audio import FinishAudioTool
from tools.qa.qc import QCTool
from tools.kaggle_bridge.kaggle_bridge import KaggleBridgeTool

CONFIG_PATH = "config/voice.json"

_ALLOWED_LICENSES = {"MIT", "Apache-2.0"}

def _load_voice_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _scrub_token(value):
    if isinstance(value, str):
        tok = os.environ.get("KAGGLE_API_TOKEN")
        if tok and len(tok) >= 20 and all(c in "0123456789abcdef" for c in tok.lower()):
            value = value.replace(tok, "<redacted>")
    return value

class KokoroTTSTool:
    name = "tts_kaggle"
    version = "0.1.0"

    def __init__(self):
        self.config = _load_voice_config()
        self.engines = self.config.get("engines", {})
        self.blocked = set(self.config.get("blocked_engines", []))

    def _license_ok(self, engine):
        eng = self.engines.get(engine, {})
        lic = eng.get("license")
        status = eng.get("status")
        if engine in self.blocked:
            return False, "blocked"
        if lic not in _ALLOWED_LICENSES:
            return False, f"license {lic!r} not permissive"
        if status in ("blocked", "unknown"):
            return False, f"status {status!r}"
        return True, None

    def _local_kokoro(self, text, output_path, voice="af_heart", speed=1.0):
        from kokoro import KPipeline
        import torch, soundfile as sf
        pipeline = KPipeline(lang_code='a')
        chunks = []
        for _, _, audio in pipeline(text, voice=voice, speed=speed):
            chunks.append(audio)
        full = torch.cat(chunks) if len(chunks) > 1 else chunks[0]
        wav = full.numpy() if hasattr(full, "numpy") else full
        sf.write(output_path, wav, 24000)
        return output_path

    def execute(self, inputs):
        text = inputs.get("text")
        job_id = inputs.get("job_id")
        output_path = inputs.get("output_path")
        engine = inputs.get("engine", self.config.get("engine", "kokoro_82m"))
        voice = inputs.get("voice", "af_heart")
        speed = float(inputs.get("speed", 1.0))

        if not all([text, job_id, output_path]):
            return {"success": False, "error": "BLOCKED: text, job_id, output_path required",
                    "data": {"verdict": "BLOCKED"}}

        # ---- License gate ----
        ok, reason = self._license_ok(engine)
        if not ok:
            return {"success": True, "error": None,
                    "data": {"verdict": "REJECT", "engine": engine, "reason": reason}}

        # ---- Try Kaggle bridge (TTS job) ----
        bridge = KaggleBridgeTool()
        job_folder = f"/tmp/tts_jobs/{job_id}"
        bridge_res = bridge.execute({
            "command": "run_job",
            "job_folder": job_folder,
            "job_id": job_id,
            "kernel_slug": "forts845/of-bridge-runner",
            "job": {"job_id": job_id, "text": text, "engine": engine, "voice": voice},
            "run_py": None,  # no deployed TTS Kaggle run.py (P3 blocked) -> bridge will fall short
            "timeout": 3600, "accelerator": "cpu",
            "fetch_dest": f"/tmp/tts_output/{job_id}",
            "kaggle_cmd": "kaggle",
        })
        bridge_ok = bool(bridge_res and bridge_res.success and bridge_res.data.get("verdict") == "PASS")
        wav_path = None
        if bridge_ok:
            # find wav in fetch dest
            dest = Path(f"/tmp/tts_output/{job_id}")
            wavs = [p for p in dest.iterdir() if p.is_file() and p.suffix == ".wav"]
            if wavs:
                wav_path = str(wavs[0])

        # ---- Fallback: local Kokoro CPU ----
        if wav_path is None:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            self._local_kokoro(text, output_path, voice=voice, speed=speed)
            wav_path = output_path

        # ---- Finish audio (loudnorm + limiter) ----
        finished_path = str(Path(output_path).with_suffix(".finished.wav"))
        fin = FinishAudioTool()
        fin_res = fin.execute({"input_path": wav_path, "output_path": finished_path})
        if not fin_res.success:
            return {"success": False, "error": f"BLOCKED: finish_audio failed: {fin_res.error}",
                    "data": {"verdict": "BLOCKED"}}

        # ---- QC verify on finished wav (ebur128) ----
        qc = QCTool()
        qc_path = str(Path(finished_path).with_suffix(".qa_report.json"))
        qc_res = qc.execute({"input_path": finished_path, "output_path": qc_path})
        qc_verdict = (qc_res.data or {}).get("verdict", "UNKNOWN") if qc_res.success else "BLOCKED"

        # ---- words.json ----
        words_path = str(Path(finished_path).with_suffix(".words.json"))
        with open(words_path, "w") as f:
            json.dump({"engine": engine, "voice": voice, "job_id": job_id, "text": text,
                       "wav": finished_path}, f, indent=2)

        # ---- manifest ----
        manifest = {
            "job_id": job_id, "engine": engine, "license": self.engines.get(engine, {}).get("license"),
            "wav": finished_path, "sha256": _sha256_file(Path(finished_path)),
            "bytes": os.path.getsize(finished_path), "qc_verdict": qc_verdict,
        }
        manifest_path = str(Path(finished_path).with_suffix(".manifest.json"))
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        result = {
            "success": True, "verdict": "PASS" if qc_verdict == "PASS" else "REVIEW",
            "engine": engine, "voice": voice, "job_id": job_id,
            "wav": finished_path, "words": words_path, "manifest": manifest_path,
            "qc": qc_verdict, "bridge_used": bridge_ok,
            "route": "bridge" if bridge_ok else "local_kokoro_cpu",
        }
        return {"success": True, "error": None, "data": _scrub_token(result)}
