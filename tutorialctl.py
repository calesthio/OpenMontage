#!/usr/bin/env python3
"""tutorialctl — spin up and drive a local tutorial-video test environment.

Assumes the Go narrator (ttsd) image is already running somewhere reachable; you
just configure its address. tutorialctl ties together the pieces so you can go
from "is my environment ready?" to a rendered tutorial in a couple of commands.

  tutorialctl init                 # write tutorial.config.json you can edit
  tutorialctl doctor               # verify the env (ffmpeg, ttsd, demo app, node, specs)
  tutorialctl list                 # list available tutorials
  tutorialctl author <name>        # generate <name>.timings.json via ttsd
  tutorialctl render <name>        # capture + render a tutorial video
  tutorialctl run <name>           # author + render in one shot

Config precedence: CLI flags > env (TUTORIAL_*) > config file > defaults.
Keys: narration_url, base_url, client_dir, render_runtime, projects_dir, lang.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

DEFAULTS = {
    "narration_url": "http://127.0.0.1:5557",
    "base_url": "https://backoffice.ddev.site:9010",
    "client_dir": str(REPO_ROOT.parent / "circuitauction-backoffice" / "client"),
    "render_runtime": "ffmpeg",
    "projects_dir": "",  # blank -> OpenMontage default (repo/projects)
    "lang": "en",
}
ENV_MAP = {
    "narration_url": "TUTORIAL_NARRATION_URL",
    "base_url": "TUTORIAL_BASE_URL",
    "client_dir": "TUTORIAL_CLIENT_DIR",
    "render_runtime": "TUTORIAL_RENDER_RUNTIME",
    "projects_dir": "TUTORIAL_PROJECTS_DIR",
    "lang": "TUTORIAL_LANG",
}

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


def cmd_author(args, cfg) -> int:
    argv = [sys.executable, str(REPO_ROOT / "author_tutorial.py"),
            "--tutorial", args.name, "--client-dir", cfg["client_dir"],
            "--narration-url", cfg["narration_url"], "--lang", cfg["lang"]]
    if cfg["base_url"]:
        argv += ["--base-url", cfg["base_url"]]
    if getattr(args, "manifest", None):
        argv += ["--manifest", args.manifest]
    return _run_cmd(argv, cfg, getattr(args, "dry_run", False))


def cmd_render(args, cfg) -> int:
    argv = [sys.executable, str(REPO_ROOT / "render_tutorial.py"),
            "--tutorial", args.name, "--client-dir", cfg["client_dir"],
            "--project-id", args.project_id or args.name,
            "--narration-url", cfg["narration_url"],
            "--render-runtime", cfg["render_runtime"]]
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
    if not args.capture:  # a --capture render supplies its own manifest; skip authoring
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
    common.add_argument("--dry-run", action="store_true", default=S, help="print commands without running them")

    p = argparse.ArgumentParser(prog="tutorialctl", description=__doc__, parents=[common],
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", parents=[common], help="write a config file")
    sp.add_argument("--force", action="store_true")
    sp.set_defaults(func=cmd_init)

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
