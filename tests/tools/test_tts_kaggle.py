#!/usr/bin/env python3
"""TDD tests for tools/audio/tts_kaggle.py.

Fake bridge via monkeypatch of KaggleBridgeTool.execute (no network, no Kaggle).
Scenarios: bridge success -> route=bridge; bridge BLOCKED -> local Kokoro fallback;
license unknown (piper) -> refuse/REJECT; token never in result JSON.
Stdlib only; subprocess not used directly here.
"""

from __future__ import annotations

import json, os, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.audio.tts_kaggle import KokoroTTSTool  # noqa: E402
import tools.audio.tts_kaggle as tts_mod  # noqa: E402
from tools.kaggle_bridge.kaggle_bridge import KaggleBridgeTool  # noqa: E402

SCRIPT = "On December first, 1984, NASA crashed a Boeing 720 airliner on purpose."

def make_tool():
    return KokoroTTSTool()

def _fake_bridge_execute(self, inputs):
    """Monkeypatch replacement: return controlled bridge results."""
    cmd = inputs.get("command")
    if cmd == "run_job":
        dest = inputs.get("fetch_dest", "/tmp/tts_fake_dest")
        mode = inputs.get("job", {}).get("_bridge_mode", "blocked")
        if mode == "success":
            os.makedirs(dest, exist_ok=True)
            wav = os.path.join(dest, "job.wav")
            if not os.path.exists(wav):
                # write a tiny valid wav (silence)
                import wave
                with wave.open(wav, "wb") as w:
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
                    w.writeframes(b"\x00\x00" * 2400)
            return type("R", (), {"success": True, "error": None,
                                  "data": {"verdict": "PASS"}})()
        return type("R", (), {"success": False, "error": "BLOCKED: queue",
                              "data": {"verdict": "BLOCKED"}})()
    return type("R", (), {"success": True, "error": None, "data": {}})()

def test_license_refuse_piper():
    tool = make_tool()
    res = tool.execute({"text": SCRIPT, "job_id": "j1",
                        "output_path": "/tmp/tts_test_piper.wav",
                        "engine": "piper_en_US-lessac-medium"})
    assert res["success"] is True
    assert res["data"]["verdict"] == "REJECT"
    assert "blocked" in res["data"]["reason"] or "license" in res["data"]["reason"].lower()
    payload = json.dumps(res["data"])
    assert "KAGGLE_API_TOKEN" not in payload

def test_bridge_blocked_falls_back_to_local_kokoro(tmp_path, monkeypatch):
    tool = make_tool()
    out = tmp_path / "out.wav"
    orig = KaggleBridgeTool.execute
    KaggleBridgeTool.execute = _fake_bridge_execute

    # Mock local Kokoro pipeline to avoid network (huggingface.co) during tests
    import tools.audio.tts_kaggle as tts_mod
    orig_local = tts_mod.KokoroTTSTool._local_kokoro

    def fake_local(self, text, output_path, voice="af_heart", speed=1.0):
        # Write a small valid silent wav
        import wave
        with wave.open(output_path, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
            w.writeframes(b"\x00\x00" * 2400)

    tts_mod.KokoroTTSTool._local_kokoro = fake_local
    try:
        res = tool.execute({"text": SCRIPT, "job_id": "j2",
                            "output_path": str(out),
                            "engine": "kokoro_82m"})
    finally:
        KaggleBridgeTool.execute = orig
        tts_mod.KokoroTTSTool._local_kokoro = orig_local
    assert res["success"] is True, res.get("error")
    assert res["data"]["verdict"] in ("PASS", "REVIEW")
    assert res["data"]["route"] == "local_kokoro_cpu"
    assert os.path.exists(res["data"]["wav"])
    assert os.path.getsize(res["data"]["wav"]) > 0
    payload = json.dumps(res["data"])
    assert "KAGGLE_API_TOKEN" not in payload

def test_bridge_success_route_bridge(tmp_path):
    tool = make_tool()
    out = tmp_path / "out.wav"
    dest = tmp_path / "fetch"
    orig = KaggleBridgeTool.execute
    def fake(self, inputs):
        if inputs.get("command") == "run_job":
            os.makedirs(inputs.get("fetch_dest", dest), exist_ok=True)
            wav = os.path.join(inputs.get("fetch_dest", dest), "job.wav")
            if not os.path.exists(wav):
                import wave
                with wave.open(wav, "wb") as w:
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
                    w.writeframes(b"\x00\x00" * 2400)
            return type("R", (), {"success": True, "error": None,
                                  "data": {"verdict": "PASS"}})()
        return type("R", (), {"success": True, "error": None, "data": {}})()
    KaggleBridgeTool.execute = fake
    try:
        res = tool.execute({"text": SCRIPT, "job_id": "j3",
                            "output_path": str(out),
                            "engine": "kokoro_82m",
                            "job": {"_bridge_mode": "success"}})
    finally:
        KaggleBridgeTool.execute = orig
    assert res["success"] is True, res.get("error")
    assert res["data"]["route"] == "bridge"
    payload = json.dumps(res["data"])
    assert "KAGGLE_API_TOKEN" not in payload

def test_kokoro_license_ok():
    tool = make_tool()
    ok, reason = tool._license_ok("kokoro_82m")
    assert ok is True
    assert reason is None

def test_missing_inputs_blocked():
    tool = make_tool()
    res = tool.execute({"text": SCRIPT, "job_id": "j4"})
    assert res["success"] is False
    assert res["data"]["verdict"] == "BLOCKED"
