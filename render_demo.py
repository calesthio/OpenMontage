from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
COMPOSER_DIR = ROOT_DIR / "remotion-composer"
PROPS_DIR = COMPOSER_DIR / "public" / "demo-props"
OUTPUT_DIR = ROOT_DIR / "projects" / "demos" / "renders"

DEMO_DESCRIPTIONS = {
    "world-in-numbers": "Global scale story with titles, stats, and charts",
    "code-to-screen": "Developer workflow explainer with comparison and KPI cards",
    "focusflow-pitch": "Startup-style pitch built only from Remotion components",
}


def discover_demos() -> dict[str, Path]:
    if not PROPS_DIR.exists():
        return {}
    return {path.stem: path for path in sorted(PROPS_DIR.glob("*.json"))}


def find_command(*names: str) -> str | None:
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            return resolved
    return None


def ensure_demo_environment() -> str:
    if not find_command("node", "node.exe"):
        raise SystemExit("Error: Node.js is required. Install it from https://nodejs.org/")

    npm_cmd = find_command("npm.cmd", "npm", "npm.exe")
    if not npm_cmd:
        raise SystemExit("Error: npm is required but was not found on PATH.")

    npx_cmd = find_command("npx.cmd", "npx", "npx.exe")
    if not npx_cmd:
        raise SystemExit("Error: npx is required but was not found on PATH.")

    if not (COMPOSER_DIR / "node_modules").exists():
        print("Installing Remotion dependencies...")
        subprocess.run([npm_cmd, "install"], cwd=COMPOSER_DIR, check=True)

    return npx_cmd


def validate_props_file(path: Path) -> None:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload.get("cuts"), list) or not payload["cuts"]:
        raise SystemExit(f"Error: {path} must define at least one cut.")


def render_demo(name: str, props_path: Path, npx_cmd: str) -> None:
    validate_props_file(props_path)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"{name}.mp4"

    print()
    print(f"Rendering: {name}")
    print(f"Props:     {props_path}")
    print(f"Output:    {output_path}")
    print()

    subprocess.run(
        [
            npx_cmd,
            "remotion",
            "render",
            "src/index.tsx",
            "Explainer",
            str(output_path),
            "--props",
            str(props_path),
            "--codec",
            "h264",
        ],
        cwd=COMPOSER_DIR,
        check=True,
    )

    if output_path.exists():
        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"Done: {output_path} ({size_mb:.1f} MB)")
    else:
        print("Render finished without creating the expected output file.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Render zero-key OpenMontage demo videos from checked-in Remotion props."
    )
    parser.add_argument("demo", nargs="?", help="Render one named demo instead of all demos.")
    parser.add_argument("--list", action="store_true", help="List available demo fixtures and exit.")
    args = parser.parse_args(argv)

    demos = discover_demos()
    if not demos:
        raise SystemExit(f"Error: No demo prop files were found in {PROPS_DIR}.")

    if args.list:
        print("Available zero-key demos:")
        for name in demos:
            description = DEMO_DESCRIPTIONS.get(name, "Checked-in Remotion demo")
            print(f"  {name:20} {description}")
        return 0

    if args.demo and args.demo not in demos:
        available = ", ".join(demos)
        raise SystemExit(f"Unknown demo '{args.demo}'. Available demos: {available}")

    npx_cmd = ensure_demo_environment()
    selected = {args.demo: demos[args.demo]} if args.demo else demos

    for name, props_path in selected.items():
        render_demo(name, props_path, npx_cmd)

    return 0


if __name__ == "__main__":
    sys.exit(main())
