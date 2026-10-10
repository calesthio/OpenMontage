"""Resolve Circuit-video MCP settings from env, tutorial.config.json, then defaults.

AWS credentials are never read from circuit-kubernetes/tmp/secret.yml — export
them into the environment (see env.example). That file also holds unrelated
tokens and must not be parsed.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
TUTORIAL_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
RENDER_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,80}$")

DEFAULTS = {
    "narration_url": "http://127.0.0.1:5557",
    "base_url": "",
    "client_dir": str(REPO_ROOT.parent / "circuitauction-backoffice" / "client"),
    "render_runtime": "ffmpeg",
    "projects_dir": "",
    "lang": "en",
    "s3_bucket": "circuit-kubernetes",
    "s3_prefix": "openmontage/tutorials/",
    "s3_region": "eu-central-1",
    "render_api_url": "",
    "render_timeout_sec": "1800",
    "browser": "",
    "narration_backend": "",   # "" = let render_tutorial.py resolve (recipe/env/ttsd)
    "voice_id": "",
    "narration_cache_dir": "",
}

_ENV = {
    "narration_url": "TUTORIAL_NARRATION_URL",
    "base_url": "TUTORIAL_BASE_URL",
    "client_dir": "TUTORIAL_CLIENT_DIR",
    "render_runtime": "TUTORIAL_RENDER_RUNTIME",
    "projects_dir": "TUTORIAL_PROJECTS_DIR",
    "lang": "TUTORIAL_LANG",
    "s3_bucket": "CIRCUIT_VIDEO_S3_BUCKET",
    "s3_prefix": "CIRCUIT_VIDEO_S3_PREFIX",
    "s3_region": "CIRCUIT_VIDEO_S3_REGION",
    "render_api_url": "CIRCUIT_VIDEO_RENDER_API_URL",
    "render_timeout_sec": "CIRCUIT_VIDEO_RENDER_TIMEOUT_SEC",
    "browser": "TUTORIAL_BROWSER",
    "narration_backend": "TUTORIAL_NARRATION_BACKEND",
    "voice_id": "TUTORIAL_VOICE_ID",
    "narration_cache_dir": "TUTORIAL_NARRATION_CACHE_DIR",
}


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    try:
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if val[:1] in ("'", '"') and len(val) >= 2 and val[-1] == val[0]:
                val = val[1:-1]
            else:
                val = re.split(r"\s+#", val, maxsplit=1)[0].rstrip()  # "VAL   # comment"
            if key:
                out[key] = val
    except OSError:
        pass
    return out


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    tutorial_cfg = REPO_ROOT / "tutorial.config.json"
    if tutorial_cfg.exists():
        try:
            data = json.loads(tutorial_cfg.read_text())
            for key in ("narration_url", "base_url", "client_dir", "render_runtime",
                        "projects_dir", "lang", "browser", "narration_backend", "voice_id"):
                val = data.get(key)
                if val not in (None, ""):
                    cfg[key] = val
        except (OSError, json.JSONDecodeError):
            pass

    env_file = REPO_ROOT / ".env"
    file_vals = _parse_env_file(env_file) if env_file.exists() else {}

    def env(name: str) -> str:
        return os.environ.get(name) or file_vals.get(name) or ""

    for key, env_name in _ENV.items():
        val = env(env_name)
        if val:
            cfg[key] = val
    if not cfg["projects_dir"]:
        cfg["projects_dir"] = env("OPENMONTAGE_PROJECTS_DIR") or str(REPO_ROOT / "projects")
    if not cfg["s3_region"]:
        cfg["s3_region"] = env("AWS_DEFAULT_REGION") or env("AWS_REGION") or DEFAULTS["s3_region"]
    prefix = cfg["s3_prefix"].strip()
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    cfg["s3_prefix"] = prefix.lstrip("/")
    cfg["client_dir"] = str(Path(cfg["client_dir"]).expanduser())
    if not Path(cfg["client_dir"]).is_absolute():
        cfg["client_dir"] = str((REPO_ROOT / cfg["client_dir"]).resolve())
    cfg["aws_access_key_id"] = env("AWS_ACCESS_KEY_ID") or env("CIRCUIT_VIDEO_AWS_ACCESS_KEY_ID")
    cfg["aws_secret_access_key"] = env("AWS_SECRET_ACCESS_KEY") or env("CIRCUIT_VIDEO_AWS_SECRET_ACCESS_KEY")
    cfg["s3_public_base"] = env("CIRCUIT_VIDEO_S3_PUBLIC_BASE").rstrip("/")
    cfg["elevenlabs_api_key"] = env("ELEVENLABS_API_KEY")
    cfg["elevenlabs_voice_ids"] = env("ELEVENLABS_VOICE_IDS")
    cfg["elevenlabs_model_id"] = env("ELEVENLABS_MODEL_ID")
    cfg["render_timeout_sec"] = int(cfg["render_timeout_sec"] or 1800)
    return cfg


def aws_ready(cfg: dict) -> bool:
    return bool(cfg.get("aws_access_key_id") and cfg.get("aws_secret_access_key") and cfg.get("s3_bucket"))


def validate_tutorial_name(name: str) -> str:
    name = (name or "").strip()
    if not TUTORIAL_NAME_RE.match(name):
        raise ValueError("tutorial must be 1-64 letters, digits, underscores, or hyphens")
    return name


def validate_base_url(url: str) -> str:
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("base_url must be an http(s) URL for the demo app Cypress records against")
    return url.rstrip("/")


def validate_render_id(render_id: str) -> str:
    render_id = (render_id or "").strip()
    if not RENDER_ID_RE.match(render_id):
        raise ValueError("render_id must be 1-81 letters, digits, dots, underscores, or hyphens")
    return render_id


NARRATION_BACKENDS = ("ttsd", "elevenlabs")
VOICE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def validate_narration_backend(value: str) -> str:
    value = (value or "").strip()
    if value and value not in NARRATION_BACKENDS:
        raise ValueError(f"narration_backend must be one of {', '.join(NARRATION_BACKENDS)}")
    return value


def validate_voice_id(value: str) -> str:
    value = (value or "").strip()
    if value and not VOICE_ID_RE.match(value):
        raise ValueError("voice_id must be 1-64 letters, digits, underscores, or hyphens")
    return value
