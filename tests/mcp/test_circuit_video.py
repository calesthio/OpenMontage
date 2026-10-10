"""Unit tests for the Circuit-video MCP helpers (no live Cypress / S3)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "mcp_servers"))

from circuit_video import s3 as s3mod  # noqa: E402
from circuit_video.config import (  # noqa: E402
    validate_base_url,
    validate_render_id,
    validate_tutorial_name,
)
from circuit_video.server import TOOLS, _call, _handle  # noqa: E402
from circuit_video.service import list_tutorials, render_argv  # noqa: E402


def test_validate_inputs():
    assert validate_tutorial_name("sales-tour") == "sales-tour"
    with pytest.raises(ValueError):
        validate_tutorial_name("../etc/passwd")
    assert validate_base_url("https://demo.example.com/app/") == "https://demo.example.com/app"
    with pytest.raises(ValueError):
        validate_base_url("file:///tmp")
    assert validate_render_id("sales-tour-ab12cd34") == "sales-tour-ab12cd34"
    with pytest.raises(ValueError):
        validate_render_id("bad id")


def test_list_tutorials_from_temp_client(tmp_path):
    spec_dir = tmp_path / "cypress" / "e2e-tutorials" / "sales"
    spec_dir.mkdir(parents=True)
    spec = spec_dir / "sales-tour.tutorial.cy.js"
    spec.write_text("describe('sales', () => {});")
    (spec_dir / "sales-tour.tutorial.json").write_text('{"title":"Sales"}')
    out = list_tutorials({"client_dir": str(tmp_path)})
    assert out["tutorials"] == [{
        "name": "sales-tour",
        "spec": "cypress/e2e-tutorials/sales/sales-tour.tutorial.cy.js",
        "has_recipe": True,
        "has_timings": False,
        "source_lang": "en",
        "languages": {},
    }]


def test_render_argv_includes_base_url():
    cfg = {
        "client_dir": "/tmp/client",
        "narration_url": "http://127.0.0.1:5557",
        "render_runtime": "ffmpeg",
    }
    argv = render_argv(
        cfg, tutorial="sales-tour", project_id="sales-tour-test",
        base_url="https://demo.example.com", offline=True, music="bed.mp3",
    )
    assert "--tutorial" in argv and "sales-tour" in argv
    assert argv[argv.index("--base-url") + 1] == "https://demo.example.com"
    assert "--offline-narration" in argv
    assert argv[argv.index("--music") + 1] == "bed.mp3"
    assert argv[0].endswith("python3") or "python" in Path(argv[0]).name
    assert argv[1].endswith("render_tutorial.py")


def test_s3_key_and_public_url():
    key = s3mod.object_key("openmontage/tutorials/", "sales-tour-ab12", "final.mp4")
    assert key == "openmontage/tutorials/sales-tour-ab12/final.mp4"
    url = s3mod.public_url("circuit-kubernetes", "eu-central-1", key)
    assert url.startswith("https://circuit-kubernetes.s3.eu-central-1.amazonaws.com/")
    assert url.endswith("/openmontage/tutorials/sales-tour-ab12/final.mp4")
    cdn = s3mod.public_url("circuit-kubernetes", "eu-central-1", key, "https://cdn.example.com")
    assert cdn == "https://cdn.example.com/openmontage/tutorials/sales-tour-ab12/final.mp4"


def test_presign_get_is_stable_for_frozen_time():
    now = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)
    url = s3mod.presign_get(
        bucket="circuit-kubernetes",
        key="openmontage/tutorials/demo/final.mp4",
        region="eu-central-1",
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        expires=3600,
        now=now,
    )
    again = s3mod.presign_get(
        bucket="circuit-kubernetes",
        key="openmontage/tutorials/demo/final.mp4",
        region="eu-central-1",
        access_key="AKIAIOSFODNN7EXAMPLE",
        secret_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        expires=3600,
        now=now,
    )
    assert url == again
    assert "X-Amz-Algorithm=AWS4-HMAC-SHA256" in url
    assert "X-Amz-Date=20260830T120000Z" in url
    assert "X-Amz-Expires=3600" in url
    sig = url.split("X-Amz-Signature=")[1]
    assert len(sig) == 64 and all(c in "0123456789abcdef" for c in sig)


def test_mcp_initialize_and_tools_list():
    init = _handle({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0"},
        },
    })
    assert init["result"]["serverInfo"]["name"] == "circuit-video"
    assert "tools" in init["result"]["capabilities"]
    listed = _handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    names = {t["name"] for t in listed["result"]["tools"]}
    assert names == {t["name"] for t in TOOLS}
    assert names == {"list_tutorials", "doctor", "render_tutorial", "get_render", "upload_video",
                     "get_tutorial_text", "save_tutorial_translation", "author_tutorial"}
    render = next(t for t in listed["result"]["tools"] if t["name"] == "render_tutorial")
    assert "base_url" in render["inputSchema"]["required"]


def test_render_tutorial_rejects_bad_url():
    result = _call("render_tutorial", {"base_url": "not-a-url", "tutorial": "sales-tour"})
    assert result.get("isError") is True
    assert "http" in result["content"][0]["text"].lower()


def test_unknown_method():
    reply = _handle({"jsonrpc": "2.0", "id": 9, "method": "nope", "params": {}})
    assert reply["error"]["code"] == -32601


# --- narration backend / ElevenLabs options ---------------------------------

from circuit_video.config import (  # noqa: E402
    load_config,
    validate_narration_backend,
    validate_voice_id,
)
from circuit_video.service import doctor, elevenlabs_env  # noqa: E402


def test_validate_narration_inputs():
    assert validate_narration_backend("") == ""
    assert validate_narration_backend("elevenlabs") == "elevenlabs"
    with pytest.raises(ValueError):
        validate_narration_backend("piper")
    assert validate_voice_id("") == ""
    assert validate_voice_id("21m00Tcm4TlvDq8ikWAM") == "21m00Tcm4TlvDq8ikWAM"
    with pytest.raises(ValueError):
        validate_voice_id("../x")


def test_render_argv_narration_flags_only_when_set():
    cfg = {"client_dir": "/tmp/client", "narration_url": "http://127.0.0.1:5557",
           "render_runtime": "ffmpeg", "narration_backend": "", "voice_id": ""}
    argv = render_argv(cfg, tutorial="t", project_id="p", base_url="https://d.example.com")
    assert "--narration-backend" not in argv and "--voice-id" not in argv
    argv = render_argv(cfg, tutorial="t", project_id="p", base_url="https://d.example.com",
                       narration_backend="elevenlabs", voice_id="VX")
    assert argv[argv.index("--narration-backend") + 1] == "elevenlabs"
    assert argv[argv.index("--voice-id") + 1] == "VX"
    # Config/env-level values are NOT promoted to CLI flags (that would beat the
    # recipe); they reach render_tutorial.py as environment variables instead.
    cfg2 = {**cfg, "narration_backend": "elevenlabs", "voice_id": "CFGV"}
    argv = render_argv(cfg2, tutorial="t", project_id="p", base_url="https://d.example.com")
    assert "--narration-backend" not in argv and "--voice-id" not in argv
    assert elevenlabs_env(cfg2)["TUTORIAL_NARRATION_BACKEND"] == "elevenlabs"
    assert elevenlabs_env(cfg2)["TUTORIAL_VOICE_ID"] == "CFGV"


def test_load_config_reads_narration_env(monkeypatch):
    monkeypatch.setenv("TUTORIAL_NARRATION_BACKEND", "elevenlabs")
    monkeypatch.setenv("TUTORIAL_VOICE_ID", "VX")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk_test")
    monkeypatch.setenv("ELEVENLABS_VOICE_IDS", "en:V1")
    monkeypatch.setenv("ELEVENLABS_MODEL_ID", "ELEVENLABS_MODEL_ID:-eleven_multilingual_v2")
    monkeypatch.delenv("TUTORIAL_NARRATION_CACHE_DIR", raising=False)
    monkeypatch.setattr("circuit_video.config._parse_env_file", lambda path: {})  # ignore the real .env
    cfg = load_config()
    assert cfg["narration_backend"] == "elevenlabs" and cfg["voice_id"] == "VX"
    assert cfg["elevenlabs_api_key"] == "sk_test"
    assert elevenlabs_env(cfg) == {
        "ELEVENLABS_API_KEY": "sk_test",
        "ELEVENLABS_VOICE_IDS": "en:V1",
        "ELEVENLABS_MODEL_ID": "ELEVENLABS_MODEL_ID:-eleven_multilingual_v2",
        "TUTORIAL_NARRATION_BACKEND": "elevenlabs",
        "TUTORIAL_VOICE_ID": "VX",
    }


def test_tools_list_exposes_narration_params():
    tool = next(t for t in TOOLS if t["name"] == "render_tutorial")
    props = tool["inputSchema"]["properties"]
    assert props["narration_backend"]["enum"] == ["ttsd", "elevenlabs"]
    assert props["voice_id"]["type"] == "string"


def test_render_tutorial_elevenlabs_without_key_fails_early(monkeypatch, tmp_path):
    for k in ("ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_IDS", "TUTORIAL_NARRATION_BACKEND"):
        monkeypatch.delenv(k, raising=False)
    spec_dir = tmp_path / "cypress" / "e2e-tutorials"
    spec_dir.mkdir(parents=True)
    (spec_dir / "t.tutorial.cy.js").write_text("")
    cfg = {**load_config(), "client_dir": str(tmp_path), "elevenlabs_api_key": "",
           "elevenlabs_voice_ids": "", "render_api_url": "", "projects_dir": str(tmp_path / "p")}
    monkeypatch.setattr("circuit_video.service.load_config", lambda: cfg)
    out = _call("render_tutorial", {"base_url": "https://d.example.com", "tutorial": "t",
                                    "narration_backend": "elevenlabs"})
    assert out.get("isError") is True
    assert "ELEVENLABS_API_KEY" in out["content"][0]["text"]
    assert not (tmp_path / "p").exists()  # nothing was launched


def test_doctor_reports_elevenlabs_backend(monkeypatch, tmp_path):
    cfg = {**load_config(), "client_dir": str(tmp_path), "base_url": "",
           "narration_backend": "elevenlabs", "voice_id": "",
           "elevenlabs_api_key": "sk", "elevenlabs_voice_ids": "en:V1",
           "elevenlabs_model_id": "", "render_api_url": ""}
    rep = doctor(cfg)
    assert rep["narration_backend"] == "elevenlabs"
    check = next(c for c in rep["checks"] if c["label"] == "elevenlabs narration")
    assert check["status"] == "ok" and "en" in check["detail"]
    assert not any(c["label"] == "ttsd narration" for c in rep["checks"])
    bad = doctor({**cfg, "elevenlabs_api_key": ""})
    check = next(c for c in bad["checks"] if c["label"] == "elevenlabs narration")
    assert check["status"] == "fail" and "ELEVENLABS_API_KEY" in check["detail"]


def test_doctor_tool_accepts_backend_override(monkeypatch, tmp_path):
    tool = next(t for t in TOOLS if t["name"] == "doctor")
    assert tool["inputSchema"]["properties"]["narration_backend"]["enum"] == ["ttsd", "elevenlabs"]
    cfg = {**load_config(), "client_dir": str(tmp_path), "base_url": "", "narration_backend": "",
           "elevenlabs_api_key": "sk", "elevenlabs_voice_ids": "en:V1", "elevenlabs_model_id": "",
           "render_api_url": ""}
    rep = doctor(cfg, narration_backend="elevenlabs", voice_id="VX")
    assert rep["narration_backend"] == "elevenlabs"
    check = next(c for c in rep["checks"] if c["label"] == "elevenlabs narration")
    assert check["status"] == "ok" and "override=VX" in check["detail"]
    with pytest.raises(ValueError):
        doctor(cfg, narration_backend="piper")


from circuit_video.service import caption_font_installed  # noqa: E402


def test_caption_font_check(monkeypatch):
    import subprocess as sp

    class R:
        returncode = 0
        stdout = "Noto Sans\nDejaVu Sans\n"

    monkeypatch.setattr(sp, "run", lambda *a, **k: R())
    assert caption_font_installed("Noto Sans") is True
    assert caption_font_installed("Inter") is False
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert caption_font_installed("Noto Sans") is None


# --- multilingual: lang option, translation + authoring tools ----------------

from circuit_video.service import author_tutorial, save_translation, tutorial_text  # noqa: E402


def _client_with_de(tmp_path):
    d = tmp_path / "cypress" / "e2e-tutorials" / "s"
    d.mkdir(parents=True)
    (d / "tour.tutorial.cy.js").write_text("")
    (d / "tour.tutorial.json").write_text(json.dumps({"title": "Tour", "lang": "en"}))
    (d / "tour.timings.json").write_text(json.dumps({"lang": "en", "steps": [
        {"index": 0, "narration": "Hello.", "duration_ms": 1}]}))
    return tmp_path


def test_list_tutorials_reports_languages(tmp_path):
    client = _client_with_de(tmp_path)
    d = client / "cypress" / "e2e-tutorials" / "s"
    (d / "tour.i18n.de.json").write_text("{}")
    (d / "tour.timings.fr.json").write_text("{}")
    out = list_tutorials({"client_dir": str(client)})["tutorials"][0]
    assert out["source_lang"] == "en"
    assert out["languages"] == {"de": {"translated": True, "timed": False},
                                "fr": {"translated": False, "timed": True}}


def test_tutorial_text_and_save_translation(tmp_path):
    cfg = {"client_dir": str(_client_with_de(tmp_path))}
    tpl = tutorial_text("tour", "de", cfg=cfg)
    assert tpl["steps"] == [{"index": 0, "source": "Hello.", "narration": "", "stale": False}]
    tpl["steps"][0]["narration"] = "Hallo."
    tpl["recipe"]["title"] = "Rundgang"
    res = save_translation("tour", "de", tpl, cfg=cfg)
    assert res["path"].endswith("tour.i18n.de.json") and res["steps"] == 1
    assert json.loads(Path(res["path"]).read_text(encoding="utf-8"))["recipe"]["title"] == "Rundgang"


def test_save_translation_rejects_bad_payload(tmp_path):
    cfg = {"client_dir": str(_client_with_de(tmp_path))}
    with pytest.raises(ValueError, match="step 0"):
        save_translation("tour", "de", {"lang": "de", "steps": [{"index": 0, "narration": ""}]}, cfg=cfg)
    with pytest.raises(ValueError, match="lang"):
        tutorial_text("tour", "German", cfg=cfg)


def test_render_argv_lang():
    cfg = {"client_dir": "/c", "narration_url": "http://127.0.0.1:5557", "render_runtime": "ffmpeg"}
    argv = render_argv(cfg, tutorial="t", project_id="p", base_url="https://d.example.com", lang="de")
    assert argv[argv.index("--lang") + 1] == "de"
    argv = render_argv(cfg, tutorial="t", project_id="p", base_url="https://d.example.com")
    assert "--lang" not in argv


def test_author_tutorial_runs_cli(tmp_path, monkeypatch):
    import subprocess as sp
    cfg = {**load_config(), "client_dir": str(_client_with_de(tmp_path)), "projects_dir": str(tmp_path / "p")}
    seen = {}

    class P:
        returncode = 0
        stdout = "OK wrote x (1 steps, lang=de)\n"
        stderr = ""

    def fake_run(argv, **kw):
        seen["argv"] = argv
        return P()

    monkeypatch.setattr(sp, "run", fake_run)
    out = author_tutorial("tour", "de", narration_backend="elevenlabs", voice_id="VX", cfg=cfg)
    a = seen["argv"]
    assert a[1].endswith("author_tutorial.py") and "--from-timings" in a
    assert a[a.index("--lang") + 1] == "de" and a[a.index("--voice-id") + 1] == "VX"
    assert a[a.index("--narration-backend") + 1] == "elevenlabs"
    assert out["status"] == "succeeded" and out["timings_path"].endswith("tour.timings.de.json")


def test_render_tutorial_lang_requires_translation_before_capture(monkeypatch, tmp_path):
    cfg = {**load_config(), "client_dir": str(_client_with_de(tmp_path)), "render_api_url": "",
           "narration_backend": "", "projects_dir": str(tmp_path / "p")}
    monkeypatch.setattr("circuit_video.service.load_config", lambda: cfg)
    out = _call("render_tutorial", {"base_url": "https://d.example.com", "tutorial": "tour", "lang": "de"})
    assert out.get("isError") is True
    assert "translat" in out["content"][0]["text"]
    assert not (tmp_path / "p").exists()


def test_tools_list_has_i18n_tools():
    names = {t["name"] for t in TOOLS}
    assert {"get_tutorial_text", "save_tutorial_translation", "author_tutorial"} <= names
    rt = next(t for t in TOOLS if t["name"] == "render_tutorial")
    assert rt["inputSchema"]["properties"]["lang"]["type"] == "string"


def test_render_tutorial_lang_rejected_in_remote_mode(monkeypatch, tmp_path):
    """The k8s render-api does not take lang yet: refuse rather than return an English video."""
    cfg = {**load_config(), "client_dir": str(_client_with_de(tmp_path)),
           "render_api_url": "http://render.example.com", "projects_dir": str(tmp_path / "p")}
    monkeypatch.setattr("circuit_video.service.load_config", lambda: cfg)
    out = _call("render_tutorial", {"base_url": "https://d.example.com", "tutorial": "tour", "lang": "de"})
    assert out.get("isError") is True and "remote" in out["content"][0]["text"]


def test_server_prints_startup_banner_to_stderr_only():
    import subprocess as sp
    r = sp.run([sys.executable, str(REPO / "mcp_servers" / "circuit_video" / "server.py")],
               input="", capture_output=True, text=True, timeout=30)
    assert r.returncode == 0
    assert r.stdout == ""  # the JSON-RPC channel must stay clean
    assert "circuit-video MCP server running" in r.stderr
    assert "stdin" in r.stderr and "tools:" in r.stderr
    assert "render_tutorial" in r.stderr and "narration:" in r.stderr and "client_dir:" in r.stderr
