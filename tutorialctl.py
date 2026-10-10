#!/usr/bin/env python3
"""tutorialctl — spin up and drive a local tutorial-video test environment.

Assumes the Go narrator (ttsd) image is already running somewhere reachable; you
just configure its address. tutorialctl ties together the pieces so you can go
from "is my environment ready?" to a rendered tutorial in a couple of commands.

  tutorialctl init                 # write tutorial.config.json you can edit
  tutorialctl up                   # start the ttsd narration container locally
  tutorialctl doctor               # verify the env (ffmpeg, ttsd, demo app, node, specs)
  tutorialctl list                 # list available tutorials
  tutorialctl author <name>        # generate <name>.timings.json via ttsd
  tutorialctl render <name>        # capture + render a tutorial video
  tutorialctl run <name>           # author + render in one shot
  tutorialctl down                 # stop/remove the ttsd container

The narration service (ttsd, from circuit-bid/redis-bridge) reuses the ElevenLabs
narration core over HTTP. `up` builds+runs it locally, forwarding ELEVENLABS_API_KEY
/ ELEVENLABS_VOICE_IDS from your shell. (It needs no Redis — that's only for the
live-stream narrator, which tutorials don't use.)

Config precedence: CLI flags > env (TUTORIAL_*) > config file > defaults. Keys:
narration_url, base_url, client_dir, render_runtime, projects_dir, lang, ttsd_image,
narration_repo, env_file. `up` reads ELEVENLABS_* from your shell or env_file.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent
TTSD_CONTAINER = "tutorial-ttsd"
TTSD_CLIPS_VOLUME = "tutorial-ttsd-clips"

DEFAULTS = {
    "narration_url": "http://127.0.0.1:5557",
    "base_url": "https://backoffice.ddev.site:9010",
    "client_dir": str(REPO_ROOT.parent / "circuitauction-backoffice" / "client"),
    "render_runtime": "ffmpeg",
    "projects_dir": "",  # blank -> OpenMontage default (repo/projects)
    "lang": "en",
    "ttsd_image": "circuit-ttsd:local",
    "narration_repo": str(REPO_ROOT.parent / "circuit-bid" / "redis-bridge"),
    "env_file": "",  # blank -> OpenMontage/.env; source of ELEVENLABS_* for `up`
    "narration_backend": "",  # "" -> script default (recipe/env/ttsd); or ttsd|elevenlabs
    "voice_id": "",  # ElevenLabs voice override (elevenlabs backend)
}
ENV_MAP = {
    "narration_url": "TUTORIAL_NARRATION_URL",
    "base_url": "TUTORIAL_BASE_URL",
    "client_dir": "TUTORIAL_CLIENT_DIR",
    "render_runtime": "TUTORIAL_RENDER_RUNTIME",
    "projects_dir": "TUTORIAL_PROJECTS_DIR",
    "lang": "TUTORIAL_LANG",
    "ttsd_image": "TUTORIAL_TTSD_IMAGE",
    "narration_repo": "TUTORIAL_NARRATION_REPO",
    "env_file": "TUTORIAL_ENV_FILE",
    "narration_backend": "TUTORIAL_NARRATION_BACKEND",
    "voice_id": "TUTORIAL_VOICE_ID",
}
NARRATION_KEYS = ("ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_IDS", "ELEVENLABS_MODEL_ID")

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
if not sys.stdout.isatty():
    GREEN = RED = YELLOW = DIM = RESET = ""


# --- config -----------------------------------------------------------------

def load_config(args) -> dict:
    cfg = dict(DEFAULTS)
    config_arg = getattr(args, "config", None)
    cfg_path = Path(config_arg) if config_arg else (Path.cwd() / "tutorial.config.json")
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text())
            cfg.update({k: v for k, v in data.items() if k in DEFAULTS and v not in (None, "")})
        except Exception as e:  # noqa: BLE001
            print(f"{YELLOW}warn:{RESET} bad config {cfg_path}: {e}", file=sys.stderr)
    for key, env in ENV_MAP.items():
        if os.environ.get(env):
            cfg[key] = os.environ[env]
    if not cfg["projects_dir"] and os.environ.get("OPENMONTAGE_PROJECTS_DIR"):
        cfg["projects_dir"] = os.environ["OPENMONTAGE_PROJECTS_DIR"]
    for key in DEFAULTS:
        val = getattr(args, key, None)
        if val:
            cfg[key] = val
    return cfg


def _env_for(cfg: dict) -> dict:
    env = os.environ.copy()
    if cfg["projects_dir"]:
        env["OPENMONTAGE_PROJECTS_DIR"] = cfg["projects_dir"]
    # Config-level narration choice travels as env (below the recipe, above the
    # script default); explicit tutorialctl flags become CLI flags (see _narration_argv).
    if cfg.get("narration_backend"):
        env["TUTORIAL_NARRATION_BACKEND"] = cfg["narration_backend"]
    if cfg.get("voice_id"):
        env["TUTORIAL_VOICE_ID"] = cfg["voice_id"]
    # ELEVENLABS_* from --env-file (shell env already wins inside _narration_env),
    # only when the child may need them: backend elevenlabs, or unset (a recipe
    # may pin elevenlabs). An explicit ttsd backend never sees the key.
    if cfg.get("narration_backend") != "ttsd":
        nenv, _src = _narration_env(cfg)
        env.update(nenv)
    return env


# Run a subprocess from a pre-built argv list (never a shell string), so there is
# no shell interpolation / injection surface.
def _run_cmd(argv: list[str], cfg: dict, dry: bool) -> int:
    print(f"{DIM}+ {' '.join(argv)}{RESET}")
    if dry:
        return 0
    return subprocess.run(argv, cwd=str(REPO_ROOT), env=_env_for(cfg)).returncode


def tutorial_specs(client_dir: str) -> list[Path]:
    root = Path(client_dir) / "cypress" / "e2e-tutorials"
    return sorted(root.rglob("*.tutorial.cy.js")) if root.exists() else []


# --- commands ---------------------------------------------------------------

def cmd_init(args, cfg) -> int:
    config_arg = getattr(args, "config", None)
    dest = Path(config_arg) if config_arg else (Path.cwd() / "tutorial.config.json")
    if dest.exists() and not args.force:
        print(f"{YELLOW}{dest} already exists{RESET} (use --force to overwrite)")
        return 1
    dest.write_text(json.dumps({k: cfg[k] for k in DEFAULTS}, indent=2) + "\n")
    print(f"{GREEN}wrote{RESET} {dest}")
    print("Edit narration_url / base_url / client_dir to match your setup.")
    return 0


def cmd_doctor(args, cfg) -> int:
    checks: list[tuple[str, str, str]] = []  # (label, status, detail); status ok|warn|fail

    def add(label, status, detail=""):
        checks.append((label, status, detail))

    for b in ("ffmpeg", "ffprobe"):
        add(b, "ok" if shutil.which(b) else "fail", shutil.which(b) or "not on PATH")
    for b in ("node", "npx"):
        add(b, "ok" if shutil.which(b) else "warn", shutil.which(b) or "not on PATH (needed for Cypress/Remotion)")

    # Caption font (lib/captions.py defaults to Noto Sans; libass falls back silently).
    try:
        r = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, timeout=10)
        families = {part.strip() for line in r.stdout.splitlines() for part in line.split(",")}
        have = "Noto Sans" in families
        add("caption font", "ok" if have else "warn",
            "'Noto Sans' installed" if have else "'Noto Sans' missing — install fonts-noto-core")
    except (OSError, subprocess.SubprocessError):
        add("caption font", "warn", "fc-list not available; cannot verify 'Noto Sans'")

    backend = cfg.get("narration_backend") or "ttsd"
    if backend == "elevenlabs":
        # Direct ElevenLabs: offline readiness check (key + voice map from shell/.env).
        nenv, _src = _narration_env(cfg)
        try:
            sys.path.insert(0, str(REPO_ROOT))
            from tools.audio.elevenlabs_narrator import ElevenLabsNarrator

            h = ElevenLabsNarrator.from_env(nenv, voice_id=cfg.get("voice_id") or None).health()
            detail = f"model={h['model_id']} voices: {','.join(h['languages']) or 'none'}"
            if h["voice_override"]:
                detail += f" override={h['voice_override']}"
            add("elevenlabs narration", "ok", detail)
        except Exception as e:  # noqa: BLE001
            add("elevenlabs narration", "fail", str(e))
    else:
        # ttsd narration sidecar (assumed already running — we only check it's reachable)
        try:
            import requests

            r = requests.get(f"{cfg['narration_url'].rstrip('/')}/health", timeout=5)
            if r.status_code == 200:
                body = r.json()
                langs = ",".join(body.get("languages", [])) or "none configured"
                status = "ok" if body.get("voices_configured") else "warn"
                add("ttsd narration", status, f"{cfg['narration_url']} — voices: {langs}")
            else:
                add("ttsd narration", "fail", f"{cfg['narration_url']} -> HTTP {r.status_code}")
        except Exception as e:  # noqa: BLE001
            add("ttsd narration", "fail", f"{cfg['narration_url']} unreachable: {e}")

    # demo app
    try:
        import requests

        try:
            import urllib3

            urllib3.disable_warnings()
        except Exception:  # noqa: BLE001
            pass
        r = requests.get(cfg["base_url"], timeout=8, verify=False)
        add("demo app", "ok" if r.status_code < 500 else "warn",
            f"{cfg['base_url']} -> HTTP {r.status_code}")
    except Exception as e:  # noqa: BLE001
        add("demo app", "warn", f"{cfg['base_url']} unreachable: {e}")

    tconf = Path(cfg["client_dir"]) / "cypress.tutorial.config.js"
    add("client tutorial config", "ok" if tconf.exists() else "fail",
        str(tconf) if tconf.exists() else f"missing {tconf}")
    specs = tutorial_specs(cfg["client_dir"])
    add("tutorial specs", "ok" if specs else "warn",
        f"{len(specs)} found" if specs else "none under cypress/e2e-tutorials/")

    nm = REPO_ROOT / "remotion-composer" / "node_modules"
    if cfg["render_runtime"] == "remotion":
        add("remotion node_modules", "ok" if nm.exists() else "fail",
            str(nm) if nm.exists() else "run `npm install` in remotion-composer/")
    else:
        add("remotion node_modules", "ok" if nm.exists() else "warn",
            "present" if nm.exists() else "not needed for ffmpeg runtime")

    sym = {"ok": f"{GREEN}[ok]{RESET}", "warn": f"{YELLOW}[! ]{RESET}", "fail": f"{RED}[x ]{RESET}"}
    print(f"\n{DIM}environment (runtime={cfg['render_runtime']}){RESET}")
    for label, status, detail in checks:
        print(f"  {sym[status]} {label:<24} {DIM}{detail}{RESET}")
    fails = [c for c in checks if c[1] == "fail"]
    warns = [c for c in checks if c[1] == "warn"]
    print()
    if any(c[0] == "ttsd narration" and c[1] == "fail" for c in checks):
        print(f"{DIM}hint: run `tutorialctl up` to start the ttsd narration container locally, "
              f"or use --narration-backend elevenlabs.{RESET}")
    if fails:
        print(f"{RED}{len(fails)} blocking issue(s).{RESET} Fix these before rendering.")
        return 1
    print(f"{GREEN}environment ready{RESET}" + (f" ({len(warns)} warning(s))" if warns else "") + ".")
    return 0


def cmd_list(args, cfg) -> int:
    specs = tutorial_specs(cfg["client_dir"])
    if not specs:
        print(f"{YELLOW}no tutorials found under {cfg['client_dir']}/cypress/e2e-tutorials/{RESET}")
        return 1
    print(f"{DIM}tutorials in {cfg['client_dir']}:{RESET}")
    for spec in specs:
        name = spec.name[: -len(".tutorial.cy.js")]
        recipe = "recipe" if spec.with_name(f"{name}.tutorial.json").exists() else f"{YELLOW}no-recipe{RESET}"
        timings = "timings" if spec.with_name(f"{name}.timings.json").exists() else f"{DIM}no-timings{RESET}"
        print(f"  {name:<24} {DIM}{recipe} - {timings}{RESET}")
    return 0


def _parse_env_file(path: Path) -> dict:
    """Minimal .env parser (KEY=VALUE), tolerant of `export`, quotes, comments."""
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
            val = val.strip().strip('"').strip("'")
            if key:
                out[key] = val
    except OSError:
        pass
    return out


def _clean_value(key: str, val: str) -> str:
    """Resolve a self-referential shell default for `key`, e.g.
    `${ELEVENLABS_MODEL_ID:-eleven_multilingual_v2}` (or the mangled brace-less
    `ELEVENLABS_MODEL_ID:-eleven_multilingual_v2`) -> the real env value or the
    default. Only matches when the template references `key` itself, so real data
    containing ':' (like `en:VID,fr:VID`) is never altered."""
    m = re.fullmatch(r"\$?\{?" + re.escape(key) + r"(?::-?(.*?))?\}?", val)
    if m:
        return os.environ.get(key) or (m.group(1) or "")
    return val


def _narration_env(cfg: dict) -> tuple[dict, str | None]:
    """Resolve ELEVENLABS_* for the ttsd container: shell env wins, then the
    configured .env file (default OpenMontage/.env)."""
    env_file = Path(cfg.get("env_file") or (REPO_ROOT / ".env"))
    file_vals = _parse_env_file(env_file) if env_file.exists() else {}
    vals = {}
    for k in NARRATION_KEYS:
        raw = os.environ.get(k) or file_vals.get(k)
        if raw:
            v = _clean_value(k, raw)
            if v:
                vals[k] = v
    return vals, (str(env_file) if env_file.exists() else None)


def _mask(argv: list[str]) -> str:
    """Redact secret values (KEY=..., SECRET=..., TOKEN=...) for display."""
    shown = []
    for a in argv:
        if "=" in a and any(s in a.split("=", 1)[0].upper() for s in ("KEY", "SECRET", "TOKEN", "PASSWORD")):
            shown.append(a.split("=", 1)[0] + "=***")
        else:
            shown.append(a)
    return " ".join(shown)


def _docker_state(name: str) -> str:
    """'running' | 'stopped' | 'absent' for a container."""
    r = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", name],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return "absent"
    return "running" if r.stdout.strip() == "true" else "stopped"


def _wait_health(url: str, tries: int = 25) -> bool:
    try:
        import requests
    except Exception:  # noqa: BLE001
        return False
    base = url.rstrip("/")
    for _ in range(tries):
        try:
            r = requests.get(f"{base}/health", timeout=3)
            if r.status_code == 200:
                langs = ",".join(r.json().get("languages", [])) or "none configured"
                print(f"{GREEN}ttsd healthy{RESET} {DIM}({url}) — voices: {langs}{RESET}")
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1)
    print(f"{YELLOW}ttsd not healthy yet{RESET} at {url} — check `docker logs {TTSD_CONTAINER}`")
    return False


def cmd_up(args, cfg) -> int:
    if not shutil.which("docker"):
        print(f"{RED}docker not found on PATH{RESET}")
        return 1
    dry = getattr(args, "dry_run", False)
    port = urlparse(cfg["narration_url"]).port or 5557
    image = cfg["ttsd_image"]

    def sh(argv, capture=False):
        print(f"{DIM}+ {' '.join(argv)}{RESET}")
        if dry:
            return 0
        r = subprocess.run(argv, capture_output=True, text=True) if capture else subprocess.run(argv)
        return r.returncode

    # Build the image if requested or missing.
    have = subprocess.run(["docker", "image", "inspect", image],
                          capture_output=True, text=True).returncode == 0
    if getattr(args, "build", False) or (not have and not dry):
        dockerfile = Path(cfg["narration_repo"]) / "Dockerfile.ttsd"
        if not dockerfile.exists():
            print(f"{RED}cannot build:{RESET} {dockerfile} not found. "
                  f"Set narration_repo, or pre-pull ttsd_image ({image}).")
            return 1
        if sh(["docker", "build", "-f", str(dockerfile), "-t", image, str(cfg["narration_repo"])]) != 0:
            return 1

    # Narration keys: shell env wins, else the .env file (default OpenMontage/.env).
    nenv, env_src = _narration_env(cfg)
    have_synth = bool(nenv.get("ELEVENLABS_API_KEY") and nenv.get("ELEVENLABS_VOICE_IDS"))

    # Start / create the container (idempotent). --recreate removes it first so a
    # changed key/env actually takes effect (docker bakes env at run time).
    state = "absent" if dry else _docker_state(TTSD_CONTAINER)
    if getattr(args, "recreate", False) and state != "absent":
        sh(["docker", "rm", "-f", TTSD_CONTAINER])
        state = "absent"

    if state == "running":
        print(f"{YELLOW}{TTSD_CONTAINER} already running{RESET} "
              f"{DIM}(run `up --recreate` to apply changed keys/env){RESET}")
    elif state == "stopped":
        if sh(["docker", "start", TTSD_CONTAINER]) != 0:
            return 1
        print(f"{GREEN}started{RESET} existing {TTSD_CONTAINER}")
    else:
        run_argv = ["docker", "run", "-d", "--name", TTSD_CONTAINER,
                    "-p", f"127.0.0.1:{port}:5557"]
        for k, v in nenv.items():
            run_argv += ["-e", f"{k}={v}"]
        run_argv += ["-v", f"{TTSD_CLIPS_VOLUME}:/clips", image]
        print(f"{DIM}+ {_mask(run_argv)}{RESET}")
        if not dry and subprocess.run(run_argv).returncode != 0:
            return 1
        print(f"{GREEN}started{RESET} {TTSD_CONTAINER} on 127.0.0.1:{port}")

    if have_synth:
        print(f"{GREEN}synthesis enabled{RESET} {DIM}(ELEVENLABS_* "
              f"{'from ' + env_src if env_src and not os.environ.get('ELEVENLABS_API_KEY') else 'from shell'}){RESET}")
    else:
        where = f"{env_src} or your shell" if env_src else "your shell or OpenMontage/.env"
        print(f"{YELLOW}note:{RESET} ELEVENLABS_API_KEY / ELEVENLABS_VOICE_IDS not found ({where}) — "
              f"ttsd will only serve cached clips.")
    if not dry:
        _wait_health(cfg["narration_url"])
    return 0


def cmd_down(args, cfg) -> int:
    if not shutil.which("docker"):
        print(f"{RED}docker not found on PATH{RESET}")
        return 1
    argv = ["docker", "rm", "-f", TTSD_CONTAINER]
    print(f"{DIM}+ {' '.join(argv)}{RESET}")
    if getattr(args, "dry_run", False):
        return 0
    r = subprocess.run(argv, capture_output=True, text=True)
    if r.returncode == 0:
        print(f"{GREEN}removed{RESET} {TTSD_CONTAINER}")
    else:
        print(f"{YELLOW}{(r.stderr or 'nothing to remove').strip()}{RESET}")
    return 0


def cmd_author(args, cfg) -> int:
    argv = [sys.executable, str(REPO_ROOT / "author_tutorial.py"),
            "--tutorial", args.name, "--client-dir", cfg["client_dir"],
            "--narration-url", cfg["narration_url"], "--lang", cfg["lang"]]
    argv += _narration_argv(args)
    if cfg["base_url"]:
        argv += ["--base-url", cfg["base_url"]]
    if getattr(args, "manifest", None):
        argv += ["--manifest", args.manifest]
    return _run_cmd(argv, cfg, getattr(args, "dry_run", False))


def _narration_argv(args) -> list[str]:
    """--narration-backend / --voice-id only when given on the tutorialctl command
    line (argparse SUPPRESS: absent attribute = not given). Config/env values go
    through _env_for instead so a recipe-pinned choice still wins over them."""
    out: list[str] = []
    if getattr(args, "narration_backend", None):
        out += ["--narration-backend", args.narration_backend]
    if getattr(args, "voice_id", None):
        out += ["--voice-id", args.voice_id]
    return out


def cmd_render(args, cfg) -> int:
    argv = [sys.executable, str(REPO_ROOT / "render_tutorial.py"),
            "--tutorial", args.name, "--client-dir", cfg["client_dir"],
            "--project-id", args.project_id or args.name,
            "--narration-url", cfg["narration_url"],
            "--render-runtime", cfg["render_runtime"]]
    argv += _narration_argv(args)
    if cfg["base_url"]:
        argv += ["--base-url", cfg["base_url"]]
    if args.offline:
        argv += ["--offline-narration"]
    if args.music:
        argv += ["--music", args.music]
    if args.capture:
        argv += ["--capture", args.capture]
    if args.manifest:
        argv += ["--manifest", args.manifest]
    if args.intro_seconds is not None:
        argv += ["--intro-seconds", str(args.intro_seconds)]
    if args.outro_seconds is not None:
        argv += ["--outro-seconds", str(args.outro_seconds)]
    return _run_cmd(argv, cfg, getattr(args, "dry_run", False))


def cmd_run(args, cfg) -> int:
    # Skip authoring when offline (author needs ttsd) or when a --capture render
    # supplies its own manifest.
    if not args.capture and not args.offline:
        rc = cmd_author(args, cfg)
        if rc != 0:
            return rc
    return cmd_render(args, cfg)


# --- parser -----------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    # Common flags are accepted BOTH before and after the subcommand. default=SUPPRESS
    # means an omitted flag contributes nothing to the namespace, so the two copies
    # (top-level parser + subparser) never clobber each other.
    S = argparse.SUPPRESS
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default=S, help="path to tutorial.config.json (default: ./tutorial.config.json)")
    common.add_argument("--narration-url", dest="narration_url", default=S, help="ttsd sidecar URL")
    common.add_argument("--base-url", dest="base_url", default=S, help="demo app URL to record against")
    common.add_argument("--client-dir", dest="client_dir", default=S, help="circuitauction-backoffice/client path")
    common.add_argument("--render-runtime", dest="render_runtime", default=S, choices=["ffmpeg", "remotion"])
    common.add_argument("--projects-dir", dest="projects_dir", default=S, help="OPENMONTAGE_PROJECTS_DIR override")
    common.add_argument("--lang", dest="lang", default=S, help="narration language code")
    common.add_argument("--narration-backend", dest="narration_backend", default=S,
                        choices=["ttsd", "elevenlabs"], help="ttsd sidecar or direct ElevenLabs")
    common.add_argument("--voice-id", dest="voice_id", default=S, help="ElevenLabs voice id override")
    common.add_argument("--ttsd-image", dest="ttsd_image", default=S, help="ttsd docker image (for `up`)")
    common.add_argument("--narration-repo", dest="narration_repo", default=S,
                        help="circuit-bid/redis-bridge path (to build ttsd)")
    common.add_argument("--env-file", dest="env_file", default=S,
                        help="path to .env with ELEVENLABS_* (default OpenMontage/.env)")
    common.add_argument("--dry-run", action="store_true", default=S, help="print commands without running them")

    p = argparse.ArgumentParser(prog="tutorialctl", description=__doc__, parents=[common],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", parents=[common], help="write a config file")
    sp.add_argument("--force", action="store_true")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("up", parents=[common], help="start the ttsd narration container locally")
    sp.add_argument("--build", action="store_true", help="build the ttsd image first")
    sp.add_argument("--recreate", action="store_true", help="remove + recreate to apply changed keys/env")
    sp.set_defaults(func=cmd_up)
    sub.add_parser("down", parents=[common], help="stop/remove the ttsd container").set_defaults(func=cmd_down)

    sub.add_parser("doctor", parents=[common], help="verify the environment").set_defaults(func=cmd_doctor)
    sub.add_parser("list", parents=[common], help="list tutorials").set_defaults(func=cmd_list)

    sp = sub.add_parser("author", parents=[common], help="generate timings.json via ttsd")
    sp.add_argument("name")
    sp.add_argument("--manifest", help="reuse an existing collect manifest")
    sp.set_defaults(func=cmd_author)

    def add_render_args(rp):
        rp.add_argument("name")
        rp.add_argument("--project-id")
        rp.add_argument("--offline", action="store_true", help="silent placeholder narration (no ttsd)")
        rp.add_argument("--music")
        rp.add_argument("--capture", help="use an existing raw capture mp4 (skip Cypress)")
        rp.add_argument("--manifest", help="manifest json for --capture")
        rp.add_argument("--intro-seconds", type=float)
        rp.add_argument("--outro-seconds", type=float)

    sp = sub.add_parser("render", parents=[common], help="capture + render a tutorial")
    add_render_args(sp)
    sp.set_defaults(func=cmd_render)

    sp = sub.add_parser("run", parents=[common], help="author + render")
    add_render_args(sp)
    sp.set_defaults(func=cmd_run)

    return p


def main() -> int:
    args = build_parser().parse_args()
    cfg = load_config(args)
    return args.func(args, cfg)


if __name__ == "__main__":
    raise SystemExit(main())
