"""Mathematical animation tool via ManimCE.

Generates animated math/science/explainer videos from Python scene code
using the Manim Community Edition engine. Free, local, no API key required.
"""

from __future__ import annotations

import ast
import importlib
import os
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import time
import types
from pathlib import Path
from typing import Any, Optional

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


# --- Safety: caller-supplied scene_code is a local code-execution boundary ---
# math_animate runs Manim on Python supplied by the caller (often an LLM or
# prompt-influenced reference material). That is arbitrary local code execution
# (see issue #219). The static scan below is defense-in-depth: it blocks the
# constructs an attack needs — reading secrets/SSH material, opening network
# connections, spawning subprocesses — while leaving genuine math/animation
# scenes untouched. It is NOT a security sandbox: a determined attacker can
# evade a static denylist, so it is paired with an explicit `allow_unsafe_code`
# opt-out and a tool contract that names the boundary. A passing scan is not
# proof that code is safe to run.
_BLOCKED_IMPORTS = frozenset({
    "os", "sys", "subprocess", "socket", "shutil", "requests", "urllib",
    "http", "ftplib", "smtplib", "telnetlib", "ctypes", "pickle", "marshal",
    "importlib", "builtins", "multiprocessing", "threading", "pty", "glob",
    "resource", "signal", "tempfile", "webbrowser", "pathlib",
})
# Dangerous identifiers blocked wherever they appear as a bare name — not just
# as a direct call. This catches indirection like `__builtins__['open']`,
# `f = open`, or `getattr(x, '__class__')` that a call-target-only or
# attribute-only check would miss.
_BLOCKED_NAMES = frozenset({
    "eval", "exec", "compile", "__import__", "open", "input", "breakpoint",
    "__builtins__", "__loader__", "globals", "locals", "vars",
    "getattr", "setattr", "delattr",
})
# Reflection via dunder attributes is the general escape hatch: `().__class__`,
# `print.__self__` (the builtins module), `x.__globals__`, `f.__reduce__`, etc.
# Enumerating dangerous dunders one by one is whack-a-mole, so block ALL dunder
# *attribute access* and allow only a tiny set that legitimate scenes use
# (`super().__init__(...)`, occasional `Type.__name__`). A dunder is any name
# that starts and ends with double underscores.
_ALLOWED_DUNDER_ATTRS = frozenset({"__init__", "__name__"})


def _is_blocked_dunder(attr: str) -> bool:
    return (
        attr.startswith("__")
        and attr.endswith("__")
        and attr not in _ALLOWED_DUNDER_ATTRS
    )


def _attr_root_name(node: ast.Attribute) -> Optional[str]:
    """Root Name of an attribute chain (`zipfile` for `zipfile.os`, and for
    longer chains like `a.b.os`), or None when the chain does not start with
    a bare Name (e.g. `self.add(...)` or `super().__init__()`)."""
    cur: ast.AST = node.value
    while isinstance(cur, ast.Attribute):
        cur = cur.value
    return cur.id if isinstance(cur, ast.Name) else None


# --- Re-export resolution (issue #864 follow-up) ---
# The first fix for #864 matched the blocked module's literal attribute
# spelling (`zipfile.os`) and only tracked plain Name rebinding. That left
# renamed re-exports (`random._os` is the real `os` module) and alias forms
# (`self.z = zipfile`, tuple unpacking, containers) open. A sweep of the
# standard library finds ~260 attributes that are blocked modules under some
# name, so spelling can never close this class: the scan resolves attribute
# chains against the real modules instead, and flags any access whose value
# IS a blocked module, whatever it is called.
_MODULE_CACHE: dict[str, Optional[types.ModuleType]] = {}


def _is_stdlib_module(name: str) -> bool:
    """True when `name` is a standard-library module, judged by where its
    file lives, so resolving a re-export never imports third-party or local
    code the scene happens to name."""
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, ValueError, AttributeError):
        return False
    if spec is None or spec.origin is None:
        return False
    if spec.origin in ("built-in", "frozen"):
        return True
    try:
        stdlib_dir = sysconfig.get_path("stdlib")
    except Exception:
        return False
    return os.path.abspath(spec.origin).startswith(os.path.abspath(stdlib_dir))


def _import_module(name: str) -> Optional[types.ModuleType]:
    """Import `name` for re-export resolution, or None.

    Only standard-library modules are imported (plus modules already loaded
    in this process, where importing executes nothing new). A blocked module
    is never imported: it is already rejected at its import node, and
    resolving through it would add nothing.
    """
    if name in _MODULE_CACHE:
        return _MODULE_CACHE[name]
    mod: Optional[types.ModuleType] = sys.modules.get(name)
    if mod is None and name.split(".")[0] not in _BLOCKED_IMPORTS:
        if _is_stdlib_module(name):
            try:
                mod = importlib.import_module(name)
            except Exception:
                mod = None
    _MODULE_CACHE[name] = mod
    return mod


def _resolve_imported_name(module: str, name: str) -> Optional[str]:
    """Real module name of `module.name` (e.g. `random._os` -> `os`), or None
    when it is not a module or cannot be resolved."""
    mod = _import_module(module)
    if mod is None:
        return None
    try:
        value = getattr(mod, name)
    except Exception:
        return None
    return value.__name__ if isinstance(value, types.ModuleType) else None


def _binding_key(node: ast.AST) -> Optional[str]:
    """Dotted name for a Name/Attribute chain (`self.z`, `a.b.c`), or None."""
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def _resolve_modules(node: ast.AST, taint: dict[str, set[str]]) -> set[str]:
    """Module names `node` may evaluate to, from taint plus live resolution.

    A name or attribute bound to an imported module resolves to that module;
    an attribute on a resolved module resolves through the real module
    object, so a renamed re-export (`random._os` -> `os`) is seen for what
    it is, not for how it is spelled. Anything else resolves to the empty
    set (unknown, not a module).
    """
    if isinstance(node, ast.Name):
        return set(taint.get(node.id, ()))
    if isinstance(node, ast.Attribute):
        key = _binding_key(node)
        if key is not None and key in taint:
            return set(taint[key])
        out: set[str] = set()
        for base in _resolve_modules(node.value, taint):
            mod = _import_module(base)
            if mod is None:
                continue
            try:
                value = getattr(mod, node.attr)
            except Exception:
                continue
            if isinstance(value, types.ModuleType):
                out.add(value.__name__)
        return out
    if isinstance(node, ast.Subscript):
        # A container holding modules: indexing it yields a module.
        return _resolve_modules(node.value, taint)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        out = set()
        for elt in node.elts:
            out |= _resolve_modules(elt, taint)
        return out
    if isinstance(node, ast.Dict):
        out = set()
        for value in node.values:
            if value is not None:
                out |= _resolve_modules(value, taint)
        return out
    if isinstance(node, ast.Starred):
        return _resolve_modules(node.value, taint)
    if isinstance(node, ast.IfExp):
        return _resolve_modules(node.body, taint) | _resolve_modules(
            node.orelse, taint
        )
    if isinstance(node, ast.NamedExpr):
        return _resolve_modules(node.value, taint)
    return set()


def _collect_tainted_bindings(tree: ast.AST) -> dict[str, set[str]]:
    """Bindings (names and dotted attribute paths) that may alias a module.

    Covers the alias forms in issue #864 and its review: plain imports and
    aliases, `from` imports (resolved to the real module name, so
    `from random import _os` binds `os`), rebinding through plain
    assignments, attribute assignments (`self.z = zipfile`), tuple
    unpacking, containers (`z = [zipfile]`, `z = {'k': zipfile}`), for-loop
    targets, walrus assignments, and function-parameter defaults. Computed
    to a fixpoint so order in the file does not matter (`y = x` before
    `x = zipfile` still taints `y`). Values are module names; a binding may
    alias several modules at once.
    """
    taint: dict[str, set[str]] = {}

    def _add(key: str, mods: set[str]) -> bool:
        if not key or not mods:
            return False
        cur = taint.setdefault(key, set())
        new = mods - cur
        if new:
            cur |= new
            return True
        return False

    def _bind_mods(target: ast.AST, mods: set[str]) -> bool:
        if isinstance(target, ast.Name):
            return _add(target.id, mods)
        if isinstance(target, ast.Attribute):
            key = _binding_key(target)
            return bool(key) and _add(key, mods)
        if isinstance(target, ast.Starred):
            return _bind_mods(target.value, mods)
        if isinstance(target, (ast.Tuple, ast.List)):
            changed = False
            for elt in target.elts:
                changed |= _bind_mods(elt, mods)
            return changed
        if isinstance(target, ast.Subscript):
            # `z[0] = zipfile` adds the module to the container's contents.
            key = _binding_key(target.value)
            return bool(key) and _add(key, mods)
        return False

    def _bind(target: ast.AST, value: ast.AST) -> bool:
        if (
            isinstance(target, (ast.Tuple, ast.List))
            and isinstance(value, (ast.Tuple, ast.List))
            and len(target.elts) == len(value.elts)
        ):
            changed = False
            for elt_target, elt_value in zip(target.elts, value.elts):
                changed |= _bind(elt_target, elt_value)
            return changed
        return _bind_mods(target, _resolve_modules(value, taint))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                _add(alias.asname or root, {root})
        elif isinstance(node, ast.ImportFrom):
            if not node.module:
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                resolved = _resolve_imported_name(node.module, alias.name)
                _add(
                    alias.asname or alias.name,
                    {resolved}
                    if resolved
                    else {f"{node.module}.{alias.name}"},
                )

    statements: list[tuple[ast.AST, ast.AST]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                statements.append((target, node.value))
        elif isinstance(node, ast.AnnAssign):
            if node.value is not None:
                statements.append((node.target, node.value))
        elif isinstance(node, ast.For):
            statements.append((node.target, node.iter))
        elif isinstance(node, ast.NamedExpr):
            statements.append((node.target, node.value))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            defaults = list(node.args.defaults)
            posargs = node.args.posonlyargs + node.args.args
            paired = (
                list(zip(posargs[-len(defaults):], defaults)) if defaults else []
            )
            for arg, default in paired:
                statements.append((ast.Name(id=arg.arg, ctx=ast.Store()), default))
            for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults):
                if default is not None:
                    statements.append(
                        (ast.Name(id=arg.arg, ctx=ast.Store()), default)
                    )

    changed = True
    rounds = 0
    while changed and rounds < 100:
        changed = False
        rounds += 1
        for target, value in statements:
            changed |= _bind(target, value)
    return taint


# Quality presets mapping to Manim CLI flags
QUALITY_PRESETS = {
    "low": {"flag": "-ql", "resolution": "854x480", "fps": 15},
    "medium": {"flag": "-qm", "resolution": "1280x720", "fps": 30},
    "high": {"flag": "-qh", "resolution": "1920x1080", "fps": 60},
    "4k": {"flag": "-qk", "resolution": "3840x2160", "fps": 60},
    "preview": {"flag": "-ql --format gif", "resolution": "854x480", "fps": 15},
}


class MathAnimate(BaseTool):
    name = "math_animate"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "graphics"
    provider = "manim"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["cmd:manim"]
    install_instructions = (
        "Install ManimCE:\n"
        "  pip install manim\n"
        "  manim checkhealth\n"
        "Requires: Python 3.8+, FFmpeg, LaTeX (optional, for math formulas)\n"
        "  Windows: choco install miktex ffmpeg\n"
        "  macOS: brew install mactex ffmpeg\n"
        "  Linux: sudo apt install texlive-full ffmpeg"
    )
    agent_skills = ["manimce-best-practices", "manim-composer"]

    capabilities = [
        "render_scene",
        "render_from_code",
        "render_from_template",
    ]

    input_schema = {
        "type": "object",
        "required": ["scene_code"],
        "properties": {
            "scene_code": {
                "type": "string",
                "description": (
                    "Python code defining a Manim scene. Must contain a class "
                    "inheriting from Scene with a construct() method. "
                    "Import 'from manim import *' is auto-added if missing. "
                    "SECURITY: this code is EXECUTED on the host by Manim. It is "
                    "scanned for dangerous constructs (system/network/subprocess "
                    "access) and rejected by default; treat scene_code as trusted "
                    "input only."
                ),
            },
            "allow_unsafe_code": {
                "type": "boolean",
                "default": False,
                "description": (
                    "Bypass the scene_code safety scan. Only set this for code "
                    "you fully trust — it permits arbitrary local code execution "
                    "(filesystem, network, subprocess). See issue #219."
                ),
            },
            "scene_name": {
                "type": "string",
                "description": "Name of the Scene class to render. Auto-detected if only one scene.",
            },
            "quality": {
                "type": "string",
                "enum": list(QUALITY_PRESETS.keys()),
                "default": "medium",
                "description": "Render quality preset",
            },
            "format": {
                "type": "string",
                "enum": ["mp4", "gif", "png", "webm"],
                "default": "mp4",
            },
            "output_path": {"type": "string"},
            "transparent": {
                "type": "boolean",
                "default": False,
                "description": "Render with transparent background (PNG sequence or WebM)",
            },
            "background_color": {
                "type": "string",
                "description": "Background hex color (e.g., '#1a1a2e'). Default: Manim default (black).",
            },
            "extra_args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Additional Manim CLI arguments",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=500, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout"])
    idempotency_key_fields = ["scene_code", "scene_name", "quality"]
    side_effects = [
        "EXECUTES caller-supplied Python (Manim scene_code) on the host — this "
        "is a local code-execution boundary; scene_code is scanned and rejected "
        "by default unless allow_unsafe_code=true (see issue #219)",
        "writes video/image file to output_path",
        "creates temp files",
    ]
    user_visible_verification = [
        "Watch the animation for correctness and visual quality",
        "Verify math formulas render correctly (requires LaTeX)",
    ]

    def get_status(self) -> ToolStatus:
        if shutil.which("manim"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # local, free

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        quality = inputs.get("quality", "medium")
        # Rough estimates based on scene complexity (assuming ~10s scene)
        estimates = {
            "low": 5.0,
            "medium": 15.0,
            "high": 45.0,
            "4k": 120.0,
            "preview": 3.0,
        }
        return estimates.get(quality, 15.0)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not shutil.which("manim"):
            return ToolResult(
                success=False,
                error="Manim not found. " + self.install_instructions,
            )

        start = time.time()

        try:
            result = self._render(inputs)
        except Exception as e:
            return ToolResult(success=False, error=f"Manim render failed: {e}")

        result.duration_seconds = round(time.time() - start, 2)
        return result

    @staticmethod
    @staticmethod
    def _scan_scene_code(code: str) -> list[str]:
        """Static safety scan of caller-supplied Manim scene code (issue #219).

        Returns a de-duplicated list of disallowed constructs (dangerous
        imports, builtins, and sandbox-escape dunders). Empty list means the
        scan found nothing to block — which is NOT a guarantee the code is safe.
        A syntax error is left for Manim to report, so it returns no violations.

        Also blocks reaching a blocked module through an imported module
        (issue #864): the denylist alone cannot see `zipfile.os`, because
        `zipfile` is not blocked and `.os` is not a dunder. The scan
        therefore resolves attribute chains against the real modules: any
        attribute access whose value IS a blocked module is a violation,
        whatever the attribute is called (`random._os` is the real `os`),
        as is any attribute use on a binding known to be a blocked module
        (`o = zipfile.os; o.system(...)`), and any attribute literally
        named after a blocked module, on any base. Taint follows modules
        through rebinding, attribute assignments, tuple unpacking,
        containers, for-loop targets, walrus assignments and function
        defaults. Importing a blocked name from any module
        (`from zipfile import os`, `from random import _os`) or
        star-importing from a module other than `manim` is likewise a
        violation. Residual limit: an attribute on an object the scan
        cannot resolve (e.g. a parameter with no default) is only caught
        when its name is a blocked module's name; the scan remains
        defense-in-depth, not a sandbox.
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        # Bindings that may alias a module, including through rebinding,
        # attribute assignments, tuple unpacking, containers, for-loop
        # targets, walrus assignments and function defaults (see
        # _collect_tainted_bindings). A binding's value is the set of module
        # names it may hold.
        taint = _collect_tainted_bindings(tree)

        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in _BLOCKED_IMPORTS:
                        violations.append(f"import '{alias.name}'")
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root in _BLOCKED_IMPORTS:
                    violations.append(f"from '{node.module}' import ...")
                else:
                    dangerous = sorted(
                        {a.name for a in node.names if a.name in _BLOCKED_IMPORTS}
                    )
                    if dangerous:
                        violations.append(
                            f"from '{node.module}' import dangerous name(s): "
                            + ", ".join(dangerous)
                        )
                    elif any(a.name == "*" for a in node.names) and root != "manim":
                        violations.append(f"from '{node.module}' import *")
                    elif node.module:
                        # Renamed re-export: `from random import _os` binds
                        # the real `os` module under a harmless-looking name.
                        for alias in node.names:
                            if alias.name == "*":
                                continue
                            resolved = _resolve_imported_name(
                                node.module, alias.name
                            )
                            if (
                                resolved is not None
                                and resolved.split(".")[0] in _BLOCKED_IMPORTS
                            ):
                                violations.append(
                                    f"from '{node.module}' import re-exported "
                                    f"blocked module '{alias.name}' ({resolved})"
                                )
            elif isinstance(node, ast.Name):
                # Blocks direct calls (eval(...)) and indirection alike:
                # `__builtins__['open']`, `f = open`, `getattr(o, '__class__')`.
                if node.id in _BLOCKED_NAMES:
                    violations.append(f"use of '{node.id}'")
            elif isinstance(node, ast.Attribute):
                if _is_blocked_dunder(node.attr):
                    violations.append(f"dunder attribute access '.{node.attr}'")
                else:
                    # A blocked module's name as an attribute, on any base:
                    # `self.z.os`, `z[0].os` and friends are violations even
                    # when the alias form itself was not tracked.
                    if node.attr in _BLOCKED_IMPORTS:
                        violations.append(
                            f"imported module attribute '.{node.attr}'"
                        )
                    base_mods = _resolve_modules(node.value, taint)
                    # Attribute use on a binding that IS a blocked module
                    # (`o = zipfile.os; o.system(...)`).
                    blocked_bases = sorted(
                        m
                        for m in base_mods
                        if m.split(".")[0] in _BLOCKED_IMPORTS
                    )
                    if blocked_bases:
                        violations.append(
                            f"blocked module '{blocked_bases[0]}' attribute "
                            f"'.{node.attr}'"
                        )
                    # Renamed re-export: the attribute's value is a blocked
                    # module, whatever it is called (`random._os` is `os`).
                    yielded = _resolve_modules(node, taint)
                    blocked_yielded = sorted(
                        m
                        for m in yielded
                        if m.split(".")[0] in _BLOCKED_IMPORTS
                    )
                    if blocked_yielded and node.attr not in _BLOCKED_IMPORTS:
                        violations.append(
                            f"imported module attribute '.{node.attr}' "
                            f"re-exports blocked module '{blocked_yielded[0]}'"
                        )
                    # Underscore-renamed blocked name on a module or tainted
                    # base (`random._os` again): covers the case where the
                    # module could not be imported in the scan environment
                    # and live resolution above had nothing to resolve.
                    stripped = node.attr.lstrip("_")
                    if (
                        stripped in _BLOCKED_IMPORTS
                        and stripped != node.attr
                        and (base_mods or _attr_root_name(node) in taint)
                    ):
                        violations.append(
                            f"imported module attribute '.{node.attr}' "
                            f"re-exports blocked module '{stripped}'"
                        )

        seen: set[str] = set()
        deduped: list[str] = []
        for v in violations:
            if v not in seen:
                seen.add(v)
                deduped.append(v)
        return deduped
    def _render(self, inputs: dict[str, Any]) -> ToolResult:
        scene_code = inputs["scene_code"]
        scene_name = inputs.get("scene_name")
        quality = inputs.get("quality", "medium")
        output_format = inputs.get("format", "mp4")
        output_path = inputs.get("output_path")
        transparent = inputs.get("transparent", False)
        bg_color = inputs.get("background_color")
        extra_args = inputs.get("extra_args", [])

        # Ensure import statement
        if "from manim import" not in scene_code:
            scene_code = "from manim import *\n\n" + scene_code

        # Safety gate: scene_code is executed on the host by Manim. Reject
        # dangerous constructs unless the caller explicitly opts out. (issue #219)
        if not inputs.get("allow_unsafe_code", False):
            violations = self._scan_scene_code(scene_code)
            if violations:
                return ToolResult(
                    success=False,
                    error=(
                        "scene_code blocked by the math_animate safety scan. This "
                        "tool executes caller-supplied Python on the host; the "
                        "following constructs are disallowed by default:\n  - "
                        + "\n  - ".join(violations)
                        + "\nIf you fully trust this code and require them, pass "
                        "allow_unsafe_code=true. See issue #219."
                    ),
                )

        # Auto-detect scene name if not provided
        if not scene_name:
            scene_name = self._detect_scene_name(scene_code)
            if not scene_name:
                return ToolResult(
                    success=False,
                    error="Could not detect Scene class name. Provide scene_name explicitly.",
                )

        # Write scene code to temp file
        work_dir = Path(tempfile.mkdtemp(prefix="manim_"))
        scene_file = work_dir / "scene.py"
        scene_file.write_text(scene_code, encoding="utf-8")

        # Build Manim CLI command
        cmd = ["manim"]

        # Quality flag
        preset = QUALITY_PRESETS.get(quality, QUALITY_PRESETS["medium"])
        for flag_part in preset["flag"].split():
            cmd.append(flag_part)

        # Format
        if output_format == "gif":
            cmd.append("--format")
            cmd.append("gif")
        elif output_format == "webm":
            cmd.append("--format")
            cmd.append("webm")
        elif output_format == "png":
            cmd.append("-s")  # save last frame as PNG

        # Transparent background
        if transparent:
            cmd.append("--transparent")

        # Background color
        if bg_color:
            cmd.extend(["--background_color", bg_color])

        # Disable window preview (headless rendering)
        cmd.append("--disable_caching")

        # Extra args
        cmd.extend(extra_args)

        # Scene file and class name
        cmd.append(str(scene_file))
        cmd.append(scene_name)

        # Execute Manim
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 min timeout
                cwd=str(work_dir),
            )
        except subprocess.TimeoutExpired:
            self._cleanup(work_dir)
            return ToolResult(
                success=False,
                error=f"Manim render timed out after 300s. Try 'low' or 'preview' quality.",
            )

        if proc.returncode != 0:
            error_msg = proc.stderr or proc.stdout or "Unknown error"
            # Extract the most useful part of the error
            lines = error_msg.strip().split("\n")
            # Look for the actual error (skip Manim header/progress)
            error_lines = [l for l in lines if "Error" in l or "error" in l or "Traceback" in l]
            if error_lines:
                error_msg = "\n".join(lines[lines.index(error_lines[0]):])
            self._cleanup(work_dir)
            return ToolResult(
                success=False,
                error=f"Manim render failed:\n{error_msg}",
                data={"full_stderr": proc.stderr, "full_stdout": proc.stdout},
            )

        # Find the output file
        rendered_file = self._find_output(work_dir, scene_name, output_format)
        if not rendered_file:
            self._cleanup(work_dir)
            return ToolResult(
                success=False,
                error=f"Render succeeded but output file not found. Manim output:\n{proc.stdout}",
            )

        # Move to desired output path
        if output_path:
            final_path = Path(output_path)
        else:
            ext = rendered_file.suffix
            final_path = Path(f"manim_{scene_name}{ext}")

        final_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(rendered_file), str(final_path))

        # Get video info
        video_info = self._probe_output(final_path)

        # Cleanup temp directory
        self._cleanup(work_dir)

        return ToolResult(
            success=True,
            data={
                "scene_name": scene_name,
                "quality": quality,
                "format": output_format,
                "output": str(final_path),
                "resolution": preset["resolution"],
                "fps": preset["fps"],
                **video_info,
            },
            artifacts=[str(final_path)],
        )

    def _detect_scene_name(self, code: str) -> Optional[str]:
        """Extract Scene subclass name from code."""
        import re

        # Match class definitions that inherit from Scene or its variants
        pattern = r"class\s+(\w+)\s*\(\s*(?:Scene|ThreeDScene|MovingCameraScene|ZoomedScene)\s*\)"
        matches = re.findall(pattern, code)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            # Return the last one (convention: main scene is last)
            return matches[-1]
        return None

    def _find_output(self, work_dir: Path, scene_name: str, fmt: str) -> Optional[Path]:
        """Find Manim's output file in the media directory."""
        media_dir = work_dir / "media"
        if not media_dir.exists():
            return None

        # Manim outputs to media/videos/<scene_file>/<quality>/<SceneName>.<ext>
        # or media/images/<scene_file>/<SceneName>.<ext> for -s flag
        ext_map = {"mp4": ".mp4", "gif": ".gif", "webm": ".webm", "png": ".png"}
        target_ext = ext_map.get(fmt, ".mp4")

        # Search recursively for the output file
        for path in media_dir.rglob(f"{scene_name}{target_ext}"):
            return path

        # Fallback: any file with the right extension
        for path in media_dir.rglob(f"*{target_ext}"):
            return path

        return None

    def _probe_output(self, path: Path) -> dict[str, Any]:
        """Get basic info about the rendered file."""
        info: dict[str, Any] = {"file_size_bytes": path.stat().st_size}

        if not shutil.which("ffprobe"):
            return info

        try:
            proc = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-print_format", "json",
                    "-show_format", "-show_streams",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode == 0:
                import json
                probe = json.loads(proc.stdout)
                fmt = probe.get("format", {})
                info["duration_seconds"] = float(fmt.get("duration", 0))
                info["file_size_mb"] = round(path.stat().st_size / (1024 * 1024), 2)
                for stream in probe.get("streams", []):
                    if stream.get("codec_type") == "video":
                        info["video_width"] = int(stream.get("width", 0))
                        info["video_height"] = int(stream.get("height", 0))
                        info["video_codec"] = stream.get("codec_name", "")
                        break
        except Exception:
            pass

        return info

    def _cleanup(self, work_dir: Path) -> None:
        """Remove temp working directory."""
        try:
            shutil.rmtree(str(work_dir), ignore_errors=True)
        except Exception:
            pass
