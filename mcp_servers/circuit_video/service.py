"""Circuit-video operations used by the MCP tools (no protocol code here)."""

from __future__ import annotations

import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen

from . import s3 as s3mod
from .config import (
    REPO_ROOT,
    aws_ready,
    load_config,
    validate_base_url,
    validate_narration_backend,
    validate_render_id,
    validate_tutorial_name,
    validate_voice_id,
)

_SLUG = re.compile(r"[^a-z0-9-]+")
_UNVERIFIED = ssl._create_unverified_context()


def _http_json(url: str, method: str = "GET", body: Optional[dict] = None, timeout: int = 30) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = Request(url, data=data, method=method)
    if body is not None:
        req.add_header("content-type", "application/json")
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", "replace")
        return json.loads(raw) if raw else {}


def _http_status(url: str, timeout: int = 8, verify: bool = True) -> tuple[int, str]:
    ctx = None if verify else _UNVERIFIED
    try:
        req = Request(url, method="GET")
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.status, ""
    except Exception as e:  # noqa: BLE001
        status = getattr(e, "code", None)
        if status:
            return int(status), str(e)
        return 0, str(e)


def caption_font_installed(family: str) -> Optional[bool]:
    """True/False via fontconfig; None when fc-list is not available."""
    if not shutil.which("fc-list"):
        return None
    try:
        r = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    families = {part.strip() for line in r.stdout.splitlines() for part in line.split(",")}
    return family in families


def tutorial_specs(client_dir: str) -> list[Path]:
    root = Path(client_dir) / "cypress" / "e2e-tutorials"
    return sorted(root.rglob("*.tutorial.cy.js")) if root.exists() else []


def list_tutorials(cfg: Optional[dict] = None) -> dict:
    cfg = cfg or load_config()
    client_dir = cfg["client_dir"]
    specs = tutorial_specs(client_dir)
    items = []
    for spec in specs:
        name = spec.name[: -len(".tutorial.cy.js")]
        try:
            rel = spec.relative_to(Path(client_dir)).as_posix()
        except ValueError:
            rel = str(spec)
        items.append({
            "name": name,
            "spec": rel,
            "has_recipe": spec.with_name(f"{name}.tutorial.json").exists(),
            "has_timings": spec.with_name(f"{name}.timings.json").exists(),
        })
    return {"client_dir": client_dir, "tutorials": items}


def doctor(cfg: Optional[dict] = None, base_url: Optional[str] = None,
           narration_backend: Optional[str] = None, voice_id: Optional[str] = None) -> dict:
    cfg = dict(cfg or load_config())
    if base_url:
        cfg["base_url"] = validate_base_url(base_url)
    if narration_backend:
        cfg["narration_backend"] = validate_narration_backend(narration_backend)
    if voice_id:
        cfg["voice_id"] = validate_voice_id(voice_id)
    checks: list[dict] = []

    def add(label: str, status: str, detail: str = ""):
        checks.append({"label": label, "status": status, "detail": detail})

    for b in ("ffmpeg", "ffprobe"):
        path = shutil.which(b)
        add(b, "ok" if path else "fail", path or "not on PATH")
    for b in ("node", "npx"):
        path = shutil.which(b)
        add(b, "ok" if path else "warn", path or "not on PATH (needed for Cypress/Remotion)")

    font = "Noto Sans"
    have_font = caption_font_installed(font)
    if have_font is None:
        add("caption font", "warn", f"fc-list not available; cannot verify {font!r}")
    else:
        add("caption font", "ok" if have_font else "warn",
            f"{font!r} {'installed' if have_font else 'missing — captions fall back to the default sans (install fonts-noto-core)'}")

    backend = cfg.get("narration_backend") or "ttsd"
    if backend == "elevenlabs":
        try:
            h = _elevenlabs_narrator(cfg).health()
            langs = ",".join(h["languages"]) or "none"
            detail = f"model={h['model_id']} voices: {langs}"
            if h["voice_override"]:
                detail += f" override={h['voice_override']}"
            add("elevenlabs narration", "ok", detail)
        except Exception as e:  # noqa: BLE001
            add("elevenlabs narration", "fail", f"{e} — see mcp_servers/circuit_video/env.example")
    else:
        narr = cfg["narration_url"].rstrip("/")
        try:
            body = _http_json(f"{narr}/health", timeout=5)
            langs = ",".join(body.get("languages", [])) or "none configured"
            status = "ok" if body.get("voices_configured") else "warn"
            add("ttsd narration", status, f"{narr} — voices: {langs}")
        except Exception as e:  # noqa: BLE001
            add("ttsd narration", "fail",
                f"{narr} unreachable: {e} (run `tutorialctl up`, or set "
                "narration_backend=elevenlabs)")

    if cfg.get("base_url"):
        status_code, err = _http_status(cfg["base_url"], timeout=8, verify=False)
        if 1 <= status_code < 500:
            add("demo app", "ok", f"{cfg['base_url']} -> HTTP {status_code}")
        elif status_code:
            add("demo app", "warn", f"{cfg['base_url']} -> HTTP {status_code}")
        else:
            add("demo app", "warn", f"{cfg['base_url']} unreachable: {err}")
    else:
        add("demo app", "warn", "no base_url configured — pass one to render_tutorial")

    tconf = Path(cfg["client_dir"]) / "cypress.tutorial.config.js"
    add("client tutorial config", "ok" if tconf.exists() else "fail",
        str(tconf) if tconf.exists() else f"missing {tconf}")
    specs = tutorial_specs(cfg["client_dir"])
    add("tutorial specs", "ok" if specs else "warn",
        f"{len(specs)} found" if specs else f"none under {cfg['client_dir']}/cypress/e2e-tutorials/")

    nm = REPO_ROOT / "remotion-composer" / "node_modules"
    if cfg["render_runtime"] == "remotion":
        add("remotion node_modules", "ok" if nm.exists() else "fail",
            str(nm) if nm.exists() else "run `npm install` in remotion-composer/")
    else:
        add("remotion node_modules", "ok" if nm.exists() else "warn",
            "present" if nm.exists() else "not needed for ffmpeg runtime")

    if aws_ready(cfg):
        add("aws s3", "ok", f"bucket={cfg['s3_bucket']} region={cfg['s3_region']}")
    else:
        add("aws s3", "warn",
            "AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / CIRCUIT_VIDEO_S3_BUCKET not set — "
            "renders will stay local")

    if cfg.get("render_api_url"):
        url = cfg["render_api_url"].rstrip("/") + "/healthz"
        try:
            body = _http_json(url, timeout=5)
            add("render api", "ok", f"{url} {body}")
        except Exception as e:  # noqa: BLE001
            add("render api", "fail", f"{url} unreachable: {e}")

    fails = [c for c in checks if c["status"] == "fail"]
    return {
        "ready": not fails,
        "runtime": cfg["render_runtime"],
        "narration_backend": backend,
        "mode": "remote" if cfg.get("render_api_url") else "local",
        "checks": checks,
    }


def _slug(s: str) -> str:
    return _SLUG.sub("-", s.lower()).strip("-")[:24] or "tutorial"


def _project_dir(cfg: dict, project_id: str) -> Path:
    return Path(cfg["projects_dir"]) / project_id


def _final_mp4(cfg: dict, project_id: str) -> Path:
    return _project_dir(cfg, project_id) / "renders" / "final.mp4"


def _job_path(cfg: dict, project_id: str) -> Path:
    return _project_dir(cfg, project_id) / "mcp_job.json"


def _write_job(cfg: dict, project_id: str, payload: dict) -> None:
    path = _job_path(cfg, project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(payload)
    payload["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _read_job(cfg: dict, project_id: str) -> Optional[dict]:
    path = _job_path(cfg, project_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def render_argv(cfg: dict, *, tutorial: str, project_id: str, base_url: str,
                offline: bool = False, music: Optional[str] = None,
                render_runtime: Optional[str] = None,
                narration_backend: Optional[str] = None,
                voice_id: Optional[str] = None) -> list[str]:
    argv = [
        sys.executable, str(REPO_ROOT / "render_tutorial.py"),
        "--tutorial", tutorial,
        "--client-dir", cfg["client_dir"],
        "--project-id", project_id,
        "--narration-url", cfg["narration_url"],
        "--render-runtime", render_runtime or cfg["render_runtime"],
        "--base-url", base_url,
    ]
    if offline:
        argv.append("--offline-narration")
    if music:
        argv += ["--music", music]
    # Only explicit tool-call values become CLI flags (CLI beats the recipe).
    # Config/env-level values reach render_tutorial.py via elevenlabs_env() as
    # TUTORIAL_NARRATION_BACKEND / TUTORIAL_VOICE_ID, i.e. below the recipe.
    if narration_backend:
        argv += ["--narration-backend", narration_backend]
    if voice_id:
        argv += ["--voice-id", voice_id]
    return argv


def _truncate(text: str, limit: int = 8000) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[:2000] + "\n…\n" + text[-limit + 2200:]


_ELEVENLABS_KEYS = (
    ("elevenlabs_api_key", "ELEVENLABS_API_KEY"),
    ("elevenlabs_voice_ids", "ELEVENLABS_VOICE_IDS"),
    ("elevenlabs_model_id", "ELEVENLABS_MODEL_ID"),
    ("narration_cache_dir", "TUTORIAL_NARRATION_CACHE_DIR"),
    ("narration_backend", "TUTORIAL_NARRATION_BACKEND"),
    ("voice_id", "TUTORIAL_VOICE_ID"),
)


def elevenlabs_env(cfg: dict) -> dict[str, str]:
    """ELEVENLABS_* (+ cache dir) to hand to the render subprocess, from MCP config."""
    return {env_name: cfg[key] for key, env_name in _ELEVENLABS_KEYS if cfg.get(key)}


def _elevenlabs_narrator(cfg: dict, voice_id: str = ""):
    """Build (offline) the ElevenLabs narrator from MCP config; raises NarrationError."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from tools.audio.elevenlabs_narrator import ElevenLabsNarrator

    return ElevenLabsNarrator.from_env(
        elevenlabs_env(cfg), voice_id=voice_id or cfg.get("voice_id") or None,
    )


def _maybe_upload(cfg: dict, project_id: str, upload: bool) -> dict:
    final = _final_mp4(cfg, project_id)
    out: dict = {"local_path": str(final)}
    if not final.exists():
        out["upload_error"] = f"render missing: {final}"
        return out
    if not upload:
        return out
    if not aws_ready(cfg):
        out["upload_skipped"] = (
            "AWS credentials not set. Export AWS_ACCESS_KEY_ID and "
            "AWS_SECRET_ACCESS_KEY (see mcp_servers/circuit_video/env.example)."
        )
        return out
    try:
        out.update(s3mod.upload_render(cfg, project_id, final))
    except Exception as e:  # noqa: BLE001
        out["upload_error"] = str(e)
    return out


def _run_local(cfg: dict, job: dict) -> dict:
    project_id = job["render_id"]
    argv = render_argv(
        cfg,
        tutorial=job["tutorial"],
        project_id=project_id,
        base_url=job["base_url"],
        offline=job.get("offline", False),
        music=job.get("music"),
        render_runtime=job.get("render_runtime"),
        narration_backend=job.get("narration_backend"),
        voice_id=job.get("voice_id"),
    )
    env = os.environ.copy()
    env["OPENMONTAGE_PROJECTS_DIR"] = cfg["projects_dir"]
    env.update(elevenlabs_env(cfg))
    if cfg.get("browser"):
        env["TUTORIAL_BROWSER"] = cfg["browser"]
    log_path = _project_dir(cfg, project_id) / "mcp_job.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _write_job(cfg, project_id, {**job, "status": "running", "log": str(log_path)})
    with log_path.open("w") as log:
        log.write("+ " + " ".join(argv) + "\n")
        log.flush()
        proc = subprocess.run(
            argv, cwd=str(REPO_ROOT), env=env,
            stdout=log, stderr=subprocess.STDOUT,
            timeout=job.get("timeout_sec") or cfg["render_timeout_sec"],
        )
    payload = {**job, "status": "succeeded" if proc.returncode == 0 else "failed",
               "returncode": proc.returncode, "log": str(log_path)}
    if proc.returncode == 0:
        payload.update(_maybe_upload(cfg, project_id, job.get("upload", True)))
    else:
        payload["error"] = f"render_tutorial.py exited {proc.returncode}"
        payload["log_tail"] = _truncate(log_path.read_text() if log_path.exists() else "")
    _write_job(cfg, project_id, payload)
    return payload


def _run_remote(cfg: dict, job: dict) -> dict:
    api = cfg["render_api_url"].rstrip("/")
    body = {
        "tutorial": job["tutorial"],
        "base_url": job["base_url"],
        "offline": bool(job.get("offline")),
    }
    if job.get("music"):
        body["music"] = job["music"]
    if job.get("render_runtime"):
        body["render_runtime"] = job["render_runtime"]
    for key in ("narration_backend", "voice_id"):
        if job.get(key):
            body[key] = job[key]  # forwarded; the k8s worker keeps ttsd today
    created = _http_json(f"{api}/renders", method="POST", body=body, timeout=30)
    render_id = created.get("render_id") or job["render_id"]
    payload = {**job, "render_id": render_id, "status": created.get("status", "queued"),
               "remote": True, "render_api": api}
    _write_job(cfg, render_id, payload)
    if job.get("wait", True):
        return get_render(render_id, cfg=cfg, wait=True)
    return payload


def render_tutorial(
    *,
    base_url: str,
    tutorial: Optional[str] = None,
    project_id: Optional[str] = None,
    offline: bool = False,
    music: Optional[str] = None,
    render_runtime: Optional[str] = None,
    upload: bool = True,
    wait: bool = True,
    narration_backend: Optional[str] = None,
    voice_id: Optional[str] = None,
    cfg: Optional[dict] = None,
) -> dict:
    cfg = dict(cfg or load_config())
    base_url = validate_base_url(base_url)
    available = list_tutorials(cfg)["tutorials"]
    if not tutorial:
        if len(available) == 1:
            tutorial = available[0]["name"]
        else:
            names = ", ".join(t["name"] for t in available) or "(none found)"
            raise ValueError(f"tutorial is required. Available: {names}")
    tutorial = validate_tutorial_name(tutorial)
    names = {t["name"] for t in available}
    if names and tutorial not in names:
        raise ValueError(f"unknown tutorial {tutorial!r}. Available: {', '.join(sorted(names))}")
    if render_runtime and render_runtime not in ("ffmpeg", "remotion"):
        raise ValueError("render_runtime must be ffmpeg or remotion")
    narration_backend = validate_narration_backend(narration_backend or "")
    voice_id = validate_voice_id(voice_id or "")
    effective_backend = narration_backend or cfg.get("narration_backend") or ""
    if effective_backend == "elevenlabs" and not offline and not cfg.get("render_api_url"):
        # Fail before a 5–20 minute Cypress capture when the key/voice is missing.
        try:
            _elevenlabs_narrator(cfg, voice_id).health()
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"ElevenLabs narration not ready: {e}") from e
    project_id = project_id or f"{_slug(tutorial)}-{uuid.uuid4().hex[:8]}"
    job = {
        "render_id": project_id,
        "tutorial": tutorial,
        "base_url": base_url,
        "offline": offline,
        "music": music,
        "render_runtime": render_runtime or cfg["render_runtime"],
        "narration_backend": narration_backend,
        "voice_id": voice_id,
        "upload": upload,
        "wait": wait,
        "status": "queued",
        "mode": "remote" if cfg.get("render_api_url") else "local",
    }
    if cfg.get("render_api_url"):
        return _run_remote(cfg, job)
    if wait:
        return _run_local(cfg, job)

    job_file = _project_dir(cfg, project_id) / "mcp_job.request.json"
    job_file.parent.mkdir(parents=True, exist_ok=True)
    job_file.write_text(json.dumps(job, indent=2) + "\n")
    log_path = _project_dir(cfg, project_id) / "mcp_job.log"
    env = os.environ.copy()
    env["OPENMONTAGE_PROJECTS_DIR"] = cfg["projects_dir"]
    env.update(elevenlabs_env(cfg))
    with log_path.open("w") as log:
        proc = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve().parent / "server.py"),
             "--job", str(job_file)],
            cwd=str(REPO_ROOT), env=env,
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
    payload = {**job, "status": "running", "pid": proc.pid, "log": str(log_path)}
    _write_job(cfg, project_id, payload)
    return payload


def get_render(render_id: str, cfg: Optional[dict] = None, wait: bool = False) -> dict:
    cfg = cfg or load_config()
    render_id = validate_render_id(render_id)

    if cfg.get("render_api_url"):
        api = cfg["render_api_url"].rstrip("/")
        deadline = time.time() + (cfg["render_timeout_sec"] if wait else 0)
        while True:
            try:
                remote = _http_json(f"{api}/renders/{render_id}", timeout=15)
            except Exception as e:  # noqa: BLE001
                job = _read_job(cfg, render_id) or {"render_id": render_id}
                job["status"] = "unknown"
                job["error"] = str(e)
                return job
            if remote.get("status") in ("succeeded", "failed") or not wait:
                _write_job(cfg, render_id, {**(_read_job(cfg, render_id) or {}), **remote})
                return remote
            if time.time() >= deadline:
                remote["status"] = remote.get("status", "running")
                remote["error"] = "timed out waiting for remote render"
                return remote
            time.sleep(5)

    job = _read_job(cfg, render_id) or {"render_id": render_id}
    final = _final_mp4(cfg, render_id)
    pid = job.get("pid")
    if pid and job.get("status") == "running":
        running = True
        try:
            os.kill(int(pid), 0)
        except OSError:
            running = False
        if not running and final.exists():
            job["status"] = "succeeded"
            job.update({k: v for k, v in (_read_job(cfg, render_id) or {}).items()})
        elif not running:
            latest = _read_job(cfg, render_id) or job
            if latest.get("status") == "running":
                latest["status"] = "failed"
                latest["error"] = "worker process exited before writing final.mp4"
            job = latest
    if final.exists() and job.get("status") not in ("failed",):
        job.setdefault("local_path", str(final))
        if job.get("status") in (None, "queued", "running", "unknown"):
            job["status"] = "succeeded"
    job.setdefault("render_id", render_id)
    return job


def upload_video(file_path: str, *, render_id: Optional[str] = None,
                 key: Optional[str] = None, cfg: Optional[dict] = None) -> dict:
    cfg = cfg or load_config()
    path = Path(file_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    if not aws_ready(cfg):
        raise RuntimeError(
            "AWS credentials not set. Export AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY "
            "(from circuit-kubernetes/tmp/secret.yml AWS s3 section — do not commit them)."
        )
    render_id = render_id or path.parent.parent.name or "upload"
    if key:
        s3_uri = s3mod.upload_file(
            path,
            bucket=cfg["s3_bucket"],
            key=key,
            region=cfg["s3_region"],
            access_key=cfg["aws_access_key_id"],
            secret_key=cfg["aws_secret_access_key"],
        )
        download_url = (
            s3mod.public_url(cfg["s3_bucket"], cfg["s3_region"], key, cfg.get("s3_public_base") or "")
            if cfg.get("s3_public_base")
            else s3mod.presign_get(
                bucket=cfg["s3_bucket"], key=key, region=cfg["s3_region"],
                access_key=cfg["aws_access_key_id"], secret_key=cfg["aws_secret_access_key"],
            )
        )
        return {"s3_uri": s3_uri, "s3_key": key, "download_url": download_url, "local_path": str(path)}
    out = s3mod.upload_render(cfg, render_id, path)
    out["local_path"] = str(path)
    return out


def run_job_file(path: str) -> int:
    job = json.loads(Path(path).read_text())
    cfg = load_config()
    result = _run_local(cfg, job)
    return 0 if result.get("status") == "succeeded" else 1
