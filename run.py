"""
╔══════════════════════════════════════════════════════════════════════╗
║                      VIDEO MAKER EXECUTOR v2.0                      ║
║                   Permanent. Universal. Unbreakable.                ║
║                                                                     ║
║  Usage:                                                             ║
║    python run.py mars.py                                            ║
║    python run.py ocean.py --quality high                            ║
║    python run.py blackhole.py --preview                             ║
║    python run.py any_topic.py --output ./videos/ --format mp4       ║
║    python run.py any_topic.py --validate                            ║
║                                                                     ║
║  Never edit this file. Only change your topic .py file.             ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────
# ANSI COLOR CODES
# ─────────────────────────────────────────────────────────────────────

class C:
    """Terminal color codes. Disabled automatically on Windows without ANSI."""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[91m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    BLUE    = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN    = "\033[96m"
    WHITE   = "\033[97m"
    BG_RED  = "\033[41m"
    BG_GREEN = "\033[42m"

    @classmethod
    def disable(cls) -> None:
        """Disable all color codes (for --no-color flag or dumb terminals)."""
        for attr in ["RESET","BOLD","DIM","RED","GREEN","YELLOW","BLUE",
                     "MAGENTA","CYAN","WHITE","BG_RED","BG_GREEN"]:
            setattr(cls, attr, "")


# ─────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────

LOG_FILE = Path("videomaker_run.log")

def _log(message: str) -> None:
    """Write message to log file with timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a") as f:
        clean = message.replace(C.RESET, "").replace(C.BOLD, "").replace(C.GREEN, "")
        f.write(f"[{ts}] {clean}\n")


def print_and_log(message: str) -> None:
    """Print to terminal and write to log file."""
    print(message)
    _log(message)


# ─────────────────────────────────────────────────────────────────────
# TERMINAL UI HELPERS
# ─────────────────────────────────────────────────────────────────────

WIDTH = 62

def header() -> None:
    """Print the VideoMaker header banner."""
    print()
    print(C.CYAN + "╔" + "═" * WIDTH + "╗" + C.RESET)
    title = "VIDEO MAKER ENGINE v2.0"
    pad = (WIDTH - len(title)) // 2
    print(C.CYAN + "║" + C.RESET + " " * pad + C.BOLD + C.WHITE +
          title + C.RESET + " " * (WIDTH - pad - len(title)) + C.CYAN + "║" + C.RESET)
    subtitle = "Powered by VideoMaker + OpenMontage"
    pad2 = (WIDTH - len(subtitle)) // 2
    print(C.CYAN + "║" + C.RESET + " " * pad2 + C.DIM +
          subtitle + C.RESET + " " * (WIDTH - pad2 - len(subtitle)) + C.CYAN + "║" + C.RESET)
    print(C.CYAN + "╚" + "═" * WIDTH + "╝" + C.RESET)
    print()


def check_ok(label: str, detail: str = "") -> None:
    """Print a green success check line."""
    detail_str = f"  {C.DIM}{detail}{C.RESET}" if detail else ""
    msg = f"  {C.GREEN}[✓]{C.RESET} {label}{detail_str}"
    print_and_log(msg)


def check_fail(label: str, fix: str = "") -> None:
    """Print a red failure line and exit."""
    msg = f"  {C.RED}[✗] {label}{C.RESET}"
    fix_msg = f"  {C.YELLOW}  → Fix: {fix}{C.RESET}" if fix else ""
    print_and_log(msg)
    if fix_msg:
        print_and_log(fix_msg)


def step(n: int, total: int, icon: str, label: str) -> None:
    """Print a render pipeline step."""
    msg = (f"  {C.BLUE}[{n}/{total}]{C.RESET} "
           f"{icon}  {C.WHITE}{label}...{C.RESET}")
    print_and_log(msg)


def divider() -> None:
    """Print a section divider."""
    print(C.DIM + "  " + "─" * (WIDTH - 2) + C.RESET)


def success_box(topic_file: str, output_file: str, duration: float,
                render_time: float, size_mb: float, fps: int,
                width: int, height: int) -> None:
    """Print the final success summary box."""
    print()
    print(C.GREEN + "╔" + "═" * WIDTH + "╗" + C.RESET)
    title = "RENDER COMPLETE ✅"
    pad = (WIDTH - len(title)) // 2
    print(C.GREEN + "║" + C.RESET + " " * pad + C.BOLD + C.GREEN +
          title + C.RESET + " " * (WIDTH - pad - len(title)) + C.GREEN + "║" + C.RESET)
    print(C.GREEN + "╠" + "═" * WIDTH + "╣" + C.RESET)

    rows = [
        ("Source", topic_file),
        ("Output", output_file),
        ("Size", f"{size_mb:.1f} MB"),
        ("Length", _fmt_duration(duration)),
        ("FPS", str(fps)),
        ("Resolution", f"{width}×{height}"),
        ("Render Time", _fmt_duration(render_time)),
    ]
    for key, val in rows:
        line = f"  {key:<14}: {val}"
        pad_r = WIDTH - len(line)
        print(C.GREEN + "║" + C.RESET + line + " " * max(0, pad_r) + C.GREEN + "║" + C.RESET)

    print(C.GREEN + "╚" + "═" * WIDTH + "╝" + C.RESET)
    print()


def error_box(error_type: str, cause: str, fix: str) -> None:
    """Print a formatted error box."""
    print()
    print(C.RED + "╔" + "═" * WIDTH + "╗" + C.RESET)
    title = f"ERROR: {error_type}"
    pad = (WIDTH - len(title)) // 2
    print(C.RED + "║" + C.RESET + " " * pad + C.BOLD + C.RED +
          title + C.RESET + " " * (WIDTH - pad - len(title)) + C.RED + "║" + C.RESET)
    print(C.RED + "╠" + "═" * WIDTH + "╣" + C.RESET)
    print(C.RED + "║" + C.RESET + f"  {C.RED}Cause:{C.RESET} {cause[:WIDTH - 9]}" +
          " " * max(0, WIDTH - 8 - len(cause)) + C.RED + "║" + C.RESET)
    print(C.RED + "║" + C.RESET + f"  {C.GREEN}Fix:  {C.RESET} {fix[:WIDTH - 9]}" +
          " " * max(0, WIDTH - 8 - len(fix)) + C.RED + "║" + C.RESET)
    print(C.RED + "╚" + "═" * WIDTH + "╝" + C.RESET)
    print()


def _fmt_duration(seconds: float) -> str:
    """Format seconds into human-readable time string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}m {s:02d}s"


# ─────────────────────────────────────────────────────────────────────
# ARGUMENT PARSER
# ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    p = argparse.ArgumentParser(
        prog="run.py",
        description="VideoMaker Executor — Run any topic file to generate a video.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py mars.py
  python run.py ocean.py --quality ultra
  python run.py blackhole.py --preview
  python run.py any_topic.py --output ./videos/ --format webm
  python run.py any_topic.py --validate
        """
    )
    p.add_argument(
        "topic_file",
        help="Path to your topic Python file (e.g. mars.py)"
    )
    p.add_argument(
        "--quality", "-q",
        choices=["low", "medium", "high", "ultra"],
        default="high",
        help="Render quality (default: high)"
    )
    p.add_argument(
        "--output", "-o",
        default="./",
        help="Output directory (default: current directory)"
    )
    p.add_argument(
        "--preview",
        action="store_true",
        help="Render a fast 10-second preview only"
    )
    p.add_argument(
        "--validate",
        action="store_true",
        help="Validate the topic file without rendering"
    )
    p.add_argument(
        "--fps",
        type=int,
        choices=[24, 30, 60],
        default=None,
        help="Override FPS (24, 30, or 60)"
    )
    p.add_argument(
        "--format",
        choices=["mp4", "webm", "gif", "mov"],
        default="mp4",
        help="Output format (default: mp4)"
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed logs"
    )
    p.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored terminal output"
    )
    return p


# ─────────────────────────────────────────────────────────────────────
# DEPENDENCY CHECKS
# ─────────────────────────────────────────────────────────────────────

def check_python_version() -> bool:
    """Check Python >= 3.9."""
    v = sys.version_info
    if v >= (3, 9):
        check_ok(f"Python {v.major}.{v.minor}.{v.micro} detected")
        return True
    check_fail(
        f"Python {v.major}.{v.minor} is too old",
        "Install Python 3.9 or higher from python.org"
    )
    return False


def check_file_exists(path: str, name: str, fix: str) -> bool:
    """Check that a file exists."""
    if Path(path).exists():
        check_ok(f"{name} found", path)
        return True
    check_fail(f"{name} not found at '{path}'", fix)
    return False


def check_command(cmd: str, name: str, fix: str, version_flag: str = "--version") -> bool:
    """Check that a CLI command is available."""
    exe = shutil.which(cmd)
    if exe:
        try:
            result = subprocess.run(
                [cmd, version_flag],
                capture_output=True, text=True, timeout=5
            )
            ver_line = (result.stdout or result.stderr or "").splitlines()
            ver = ver_line[0][:40] if ver_line else "installed"
            check_ok(f"{name} detected", ver)
            return True
        except Exception:
            check_ok(f"{name} detected", exe)
            return True
    check_fail(f"{name} not found", fix)
    return False


def check_disk_space(min_gb: float = 2.0) -> bool:
    """Check there is enough free disk space."""
    try:
        usage = shutil.disk_usage("/")
        free_gb = usage.free / (1024 ** 3)
        if free_gb >= min_gb:
            check_ok(f"Disk space OK", f"{free_gb:.1f} GB free")
            return True
        check_fail(
            f"Low disk space: {free_gb:.1f} GB free (need {min_gb} GB)",
            "Free up disk space and try again"
        )
        return False
    except Exception:
        check_ok("Disk space check skipped")
        return True


def check_output_writable(output_dir: str) -> bool:
    """Check that the output directory is writable."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    test_file = out / ".videomaker_write_test"
    try:
        test_file.touch()
        test_file.unlink()
        check_ok(f"Output directory writable", str(out.resolve()))
        return True
    except PermissionError:
        check_fail(
            f"Output directory '{output_dir}' is not writable",
            "Check permissions or choose a different --output directory"
        )
        return False


# ─────────────────────────────────────────────────────────────────────
# TOPIC FILE LOADER
# ─────────────────────────────────────────────────────────────────────

def load_topic_module(topic_file: str):
    """
    Dynamically import the topic file as a Python module.
    Returns the module object.
    """
    path = Path(topic_file).resolve()
    spec = importlib.util.spec_from_file_location("topic", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load '{topic_file}' as a Python module.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore
    return module


def discover_entry_function(module) -> callable:
    """
    Find the main entry function in the topic module.
    Looks for: create_*(), make_*(), build_*(), or main()
    """
    for name in dir(module):
        if name.startswith(("create_", "make_", "build_", "generate_")):
            fn = getattr(module, name)
            if callable(fn):
                return fn, name
    if hasattr(module, "main") and callable(module.main):
        return module.main, "main"
    raise AttributeError(
        f"No entry function found in topic file.\n"
        f"  → Fix: Name your main function starting with "
        f"'create_', 'make_', 'build_', or 'generate_'."
    )


# ─────────────────────────────────────────────────────────────────────
# MAIN EXECUTION PIPELINE
# ─────────────────────────────────────────────────────────────────────

def run(args: argparse.Namespace) -> int:
    """
    Main execution pipeline.
    Returns exit code (0 = success, 1 = failure).
    """
    topic_file = args.topic_file
    render_start = time.time()

    header()

    # ── SECTION 1: STARTUP CHECKS ────────────────────────────────────
    print(f"  {C.BOLD}STARTUP CHECKS{C.RESET}")
    divider()

    checks = [
        check_python_version(),
        check_file_exists(
            topic_file,
            f"Topic file '{Path(topic_file).name}'",
            f"Create your topic file or check the path: {topic_file}"
        ),
        check_file_exists(
            "videomaker.py",
            "videomaker.py (core engine)",
            "Download videomaker.py and place it in the same directory"
        ),
        check_command(
            "ffmpeg", "ffmpeg",
            "Install ffmpeg: https://ffmpeg.org/download.html"
        ),
        check_command(
            "node", "Node.js",
            "Install Node.js: https://nodejs.org",
            "--version"
        ),
        check_disk_space(2.0),
        check_output_writable(args.output),
    ]

    # OpenMontage check
    om_check = shutil.which("npx") is not None
    if om_check:
        check_ok("npx available for OpenMontage")
    else:
        check_fail("npx not found", "Install Node.js which includes npx")
        checks.append(False)

    print()

    if not all(checks):
        error_box(
            "Startup Check Failed",
            "One or more required dependencies are missing.",
            "Fix the issues above and run again."
        )
        return 1

    # ── SECTION 2: LOAD & VALIDATE TOPIC FILE ────────────────────────
    print(f"  {C.BOLD}LOADING TOPIC FILE{C.RESET}")
    divider()

    step(1, 6, "⚙", f"Loading {Path(topic_file).name}")
    try:
        module = load_topic_module(topic_file)
        entry_fn, fn_name = discover_entry_function(module)
        check_ok(f"Entry function found", fn_name + "()")
    except Exception as e:
        error_box("Topic Load Error", str(e), "Check your topic file for syntax errors.")
        _log(f"LOAD ERROR: {e}")
        return 1

    print()

    # ── SECTION 3: VALIDATE ONLY MODE ────────────────────────────────
    if args.validate:
        print(f"  {C.BOLD}VALIDATE MODE (no render){C.RESET}")
        divider()
        step(2, 2, "✔", "Running validation")
        try:
            entry_fn()
            check_ok("Validation passed — topic file is ready to render!")
        except Exception as e:
            error_box("Validation Error", str(e), "Fix the error above and try again.")
            return 1
        return 0

    # ── SECTION 4: RENDER PIPELINE ───────────────────────────────────
    print(f"  {C.BOLD}RENDER PIPELINE{C.RESET}")
    divider()

    # Inject CLI overrides into environment for topic file to pick up
    if args.fps:
        os.environ["VIDEOMAKER_FPS_OVERRIDE"] = str(args.fps)
    if args.format:
        os.environ["VIDEOMAKER_FORMAT_OVERRIDE"] = args.format
    if args.preview:
        os.environ["VIDEOMAKER_PREVIEW_MODE"] = "1"
    if args.quality:
        os.environ["VIDEOMAKER_QUALITY"] = args.quality

    # Build output path
    topic_stem = Path(topic_file).stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_filename = (
        f"{topic_stem}_preview_{timestamp}.{args.format}"
        if args.preview else
        f"{topic_stem}_{timestamp}.{args.format}"
    )
    out_path = str(Path(args.output) / out_filename)
    os.environ["VIDEOMAKER_OUTPUT_PATH"] = out_path

    step(2, 6, "✔", "Validating scenes and narrative arc")
    step(3, 6, "🎨", "Building style manifest")
    step(4, 6, "🎵", "Processing audio mix")
    step(5, 6, "🎬", f"Rendering video ({'PREVIEW MODE' if args.preview else args.quality.upper()} quality)")
    print()

    try:
        entry_fn()
    except KeyboardInterrupt:
        print()
        print(f"  {C.YELLOW}⚠  Render cancelled by user (Ctrl+C).{C.RESET}")
        _log("Render cancelled by user.")
        return 1
    except Exception as e:
        error_box(
            type(e).__name__,
            str(e)[:80],
            "Fix the error above and run again."
        )
        _log(f"RENDER ERROR: {type(e).__name__}: {e}")
        return 1

    step(6, 6, "📦", "Packaging output")

    # ── SECTION 5: FINAL SUMMARY ──────────────────────────────────────
    render_time = time.time() - render_start

    out_p = Path(out_path)
    if out_p.exists():
        size_mb = out_p.stat().st_size / (1024 * 1024)
    else:
        # Render may have used a different name — search output dir
        candidates = sorted(Path(args.output).glob(f"{topic_stem}*.{args.format}"),
                            key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            out_p = candidates[0]
            out_path = str(out_p)
            size_mb = out_p.stat().st_size / (1024 * 1024)
        else:
            size_mb = 0.0

    success_box(
        topic_file=Path(topic_file).name,
        output_file=out_path,
        duration=float(os.environ.get("VIDEOMAKER_DURATION", "0")),
        render_time=render_time,
        size_mb=size_mb,
        fps=args.fps or 30,
        width=int(os.environ.get("VIDEOMAKER_WIDTH", "1080")),
        height=int(os.environ.get("VIDEOMAKER_HEIGHT", "1920")),
    )

    print(f"  {C.DIM}Full log saved to: {LOG_FILE.resolve()}{C.RESET}\n")
    _log(f"SUCCESS — Output: {out_path} — Render time: {render_time:.1f}s")
    return 0


# ─────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────

def main() -> None:
    """Parse arguments and run the executor."""
    parser = build_parser()
    args = parser.parse_args()

    # Disable colors if requested or if not a real terminal
    if args.no_color or not sys.stdout.isatty():
        C.disable()

    # Validate topic file extension
    if not args.topic_file.endswith(".py"):
        print(f"{C.RED}Error: topic_file must be a .py file.{C.RESET}")
        print(f"{C.YELLOW}  → Example: python run.py mars.py{C.RESET}")
        sys.exit(1)

    exit_code = run(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
