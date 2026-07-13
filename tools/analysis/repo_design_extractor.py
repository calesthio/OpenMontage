"""Deterministic design-system scanner for product source repositories.

First half of the product-motion pipeline's repo_analysis stage. This tool is
a *scanner*, not the artifact author: it detects the frontend framework,
classifies candidate design files, parses CSS custom properties and Tailwind
v4 ``@theme`` blocks with file+line provenance, best-effort evaluates JS
tailwind configs (by shelling out to ``node``; degrades to ``null``), and
indexes screen/component source files.

The agent then reads the flagged files directly (guided by the
``repo-design-extraction`` skill) and authors the schema-validated
``design_system`` and ``ui_inventory`` artifacts. Determinism: all directory
walks are sorted; the same repo state always yields the same scan report.

The analyzed repository is only ever read, never written.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

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

# Directories never worth walking for design tokens.
_SKIP_DIRS = {
    "node_modules", ".git", ".next", ".nuxt", ".svelte-kit", "dist", "build",
    "out", "coverage", ".turbo", ".cache", "__pycache__", ".venv", "venv",
    "storybook-static", ".output", "vendor",
}

# CSS custom property declaration, e.g. `--color-primary: #6366f1;`
_CSS_VAR_RE = re.compile(r"(--[\w-]+)\s*:\s*([^;{}]+);")
# Tailwind v4 CSS-first theme block: `@theme { ... }`
_THEME_BLOCK_RE = re.compile(r"@theme\b")
# @font-face family declaration
_FONT_FACE_RE = re.compile(r"font-family\s*:\s*['\"]?([^'\";,}]+)")
# next/font google imports, e.g. `import { Inter } from "next/font/google"`
_NEXT_FONT_RE = re.compile(r"import\s*\{([^}]+)\}\s*from\s*['\"]next/font/google['\"]")

_STYLE_EXTS = {".css", ".scss", ".sass", ".less"}
_SOURCE_EXTS = {".tsx", ".jsx", ".ts", ".js", ".vue", ".svelte"}

# Screen/route roots checked in order; (glob root, kind)
_SCREEN_ROOTS = [
    "app", "src/app", "pages", "src/pages", "src/views", "src/screens",
    "src/routes", "src/features",
]
_COMPONENT_ROOTS = ["components", "src/components", "app/components", "src/ui"]


class RepoDesignExtractor(BaseTool):
    name = "repo_design_extractor"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "analysis"
    provider = "local"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = []  # pure stdlib; node is probed at runtime and optional
    install_instructions = (
        "No installation required. Optional: having `node` on PATH lets the "
        "scanner evaluate JS tailwind configs; without it tailwind_theme "
        "degrades to null and the agent reads the config file directly."
    )
    fallback_tools = []
    agent_skills = ["repo-design-extraction"]

    capabilities = [
        "detect_frontend_framework",
        "scan_design_token_sources",
        "parse_css_custom_properties",
        "index_screens_and_components",
    ]
    supports = {"offline": True, "readonly_on_target": True}
    best_for = [
        "grounding a product-motion run in a repo's real design tokens",
        "finding which files define a web app's design system",
        "indexing screens/components before UI-replica planning",
    ]
    not_good_for = [
        "live-URL extraction (use `npx hyperframes capture` / website-to-video)",
        "non-web repos (backend, mobile) — v1 targets web frontends",
    ]

    input_schema = {
        "type": "object",
        "required": ["repo_path"],
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "Path to the product repository to analyze (read-only)",
            },
            "output_path": {
                "type": "string",
                "description": "Optional path to write the scan_report JSON (should live under projects/<id>/artifacts/)",
            },
            "max_files": {
                "type": "integer",
                "default": 5000,
                "description": "Cap on files walked; larger repos are truncated (reported in the result)",
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "framework": {"type": "string"},
            "styling_systems": {"type": "array"},
            "candidate_files": {"type": "array"},
            "css_custom_properties": {"type": "array"},
            "tailwind_theme": {},
            "fonts": {"type": "array"},
            "screen_candidates": {"type": "array"},
            "components_index": {"type": "array"},
            "truncated": {"type": "boolean"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=10, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=0, retryable_errors=[])
    idempotency_key_fields = ["repo_path", "max_files"]
    side_effects = ["writes scan_report JSON to output_path (never writes to repo_path)"]
    user_visible_verification = [
        "Spot-check a few reported css_custom_properties against the cited file+line",
    ]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 15.0

    # ---- execution ----

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        repo = Path(inputs["repo_path"]).expanduser()
        if not repo.is_dir():
            return ToolResult(
                success=False, error=f"repo_path is not a directory: {repo}"
            )

        start = time.time()
        try:
            report = self._scan(repo, int(inputs.get("max_files", 5000)))
        except Exception as e:
            return ToolResult(success=False, error=f"Repo scan failed: {e}")

        artifacts: list[str] = []
        output_path = inputs.get("output_path")
        if output_path:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(report, indent=2))
            artifacts.append(str(out))

        return ToolResult(
            success=True,
            data=report,
            artifacts=artifacts,
            duration_seconds=round(time.time() - start, 2),
            cost_usd=0.0,
        )

    # ---- scanning ----

    def _scan(self, repo: Path, max_files: int) -> dict[str, Any]:
        files, truncated = self._walk(repo, max_files)

        pkg = self._read_package_json(repo)
        framework = self._detect_framework(pkg)
        candidate_files: list[dict[str, str]] = []
        css_vars: list[dict[str, Any]] = []
        fonts: list[dict[str, Any]] = []
        theme_files: list[Path] = []

        for rel in files:
            path = repo / rel
            name = path.name.lower()
            ext = path.suffix.lower()

            if re.fullmatch(r"tailwind\.config\.(js|cjs|mjs|ts)", name):
                candidate_files.append({"path": rel, "kind": "tailwind_config",
                                        "reason": "Tailwind theme configuration"})
                theme_files.append(path)
                continue

            if ext in _STYLE_EXTS:
                text = self._read_text(path)
                if text is None:
                    continue
                has_root = ":root" in text
                has_theme = bool(_THEME_BLOCK_RE.search(text))
                if has_root or has_theme:
                    candidate_files.append({
                        "path": rel,
                        "kind": "theme_css" if has_theme else "css_variables",
                        "reason": "@theme block (Tailwind v4)" if has_theme
                        else ":root custom properties",
                    })
                    css_vars.extend(self._parse_css_vars(text, rel))
                if "@font-face" in text:
                    for m in _FONT_FACE_RE.finditer(text):
                        family = m.group(1).strip()
                        if family and not family.startswith("var("):
                            fonts.append({"family": family, "source": "font-face",
                                          "file": rel})
                continue

            if ext in _SOURCE_EXTS:
                if "theme" in name or "tokens" in name or "design" in name:
                    candidate_files.append({"path": rel, "kind": "theme_source",
                                            "reason": "theme/token module by name"})
                if framework in ("next", "react") and (
                    name.startswith("layout.") or name.startswith("_app.")
                    or name.startswith("_document.")
                ):
                    text = self._read_text(path)
                    if text:
                        for m in _NEXT_FONT_RE.finditer(text):
                            for f in m.group(1).split(","):
                                f = f.strip()
                                if f:
                                    fonts.append({"family": f, "source": "next/font",
                                                  "file": rel})
                        candidate_files.append({"path": rel, "kind": "app_shell",
                                                "reason": "root layout / app shell"})

        # de-dup fonts deterministically
        seen: set[tuple[str, str]] = set()
        fonts = [f for f in fonts
                 if (key := (f["family"].lower(), f["file"])) not in seen
                 and not seen.add(key)]

        report: dict[str, Any] = {
            "repo_path": str(repo),
            "framework": framework,
            "styling_systems": self._detect_styling_systems(pkg, candidate_files, css_vars, files),
            "candidate_files": candidate_files,
            "css_custom_properties": css_vars,
            "tailwind_theme": self._eval_tailwind_config(theme_files),
            "fonts": fonts,
            "screen_candidates": self._index_screens(repo, files, framework),
            "components_index": self._index_components(files),
            "files_scanned": len(files),
            "truncated": truncated,
        }
        return report

    def _walk(self, repo: Path, max_files: int) -> tuple[list[str], bool]:
        """Sorted, capped, skip-listed walk. Returns repo-relative paths."""
        collected: list[str] = []
        truncated = False
        for root, dirs, filenames in os.walk(repo):
            dirs[:] = sorted(d for d in dirs
                             if d not in _SKIP_DIRS and not d.startswith("."))
            rel_root = Path(root).relative_to(repo)
            for fname in sorted(filenames):
                if len(collected) >= max_files:
                    return collected, True
                rel = str(rel_root / fname) if str(rel_root) != "." else fname
                collected.append(rel)
        return collected, truncated

    @staticmethod
    def _read_text(path: Path, limit: int = 512_000) -> str | None:
        try:
            if path.stat().st_size > limit:
                return None
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None

    def _read_package_json(self, repo: Path) -> dict[str, Any]:
        pkg_path = repo / "package.json"
        text = self._read_text(pkg_path)
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _detect_framework(pkg: dict[str, Any]) -> str:
        deps: dict[str, str] = {}
        for key in ("dependencies", "devDependencies"):
            deps.update(pkg.get(key) or {})
        if "next" in deps:
            return "next"
        if "nuxt" in deps or "nuxt3" in deps:
            return "nuxt"
        if "svelte" in deps or "@sveltejs/kit" in deps:
            return "svelte"
        if "vue" in deps:
            return "vue"
        if "react" in deps:
            return "react"
        return "other"

    @staticmethod
    def _detect_styling_systems(
        pkg: dict[str, Any],
        candidate_files: list[dict[str, str]],
        css_vars: list[dict[str, Any]],
        files: list[str],
    ) -> list[str]:
        deps: dict[str, str] = {}
        for key in ("dependencies", "devDependencies"):
            deps.update(pkg.get(key) or {})
        systems: list[str] = []
        if "tailwindcss" in deps or any(
            c["kind"] in ("tailwind_config", "theme_css") for c in candidate_files
        ):
            systems.append("tailwind")
        if css_vars:
            systems.append("css-variables")
        if "styled-components" in deps:
            systems.append("styled-components")
        if any(d.startswith("@emotion/") for d in deps):
            systems.append("emotion")
        if any(f.endswith((".module.css", ".module.scss")) for f in files):
            systems.append("css-modules")
        if "sass" in deps or "node-sass" in deps or any(
            f.endswith((".scss", ".sass")) for f in files
        ):
            systems.append("sass")
        return systems

    @staticmethod
    def _parse_css_vars(text: str, rel: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for i, line in enumerate(text.splitlines(), start=1):
            for m in _CSS_VAR_RE.finditer(line):
                out.append({
                    "name": m.group(1),
                    "value": m.group(2).strip(),
                    "file": rel,
                    "line": i,
                })
        return out

    @staticmethod
    def _eval_tailwind_config(theme_files: list[Path]) -> Any:
        """Best-effort JS tailwind config evaluation via node. TS configs and
        missing node degrade to None — the agent reads the file directly."""
        node = shutil.which("node")
        if not node:
            return None
        for cfg in theme_files:
            if cfg.suffix == ".ts":
                continue
            expr = (
                f"const c = require({json.dumps(str(cfg))});"
                "JSON.stringify((c && (c.theme || (c.default && c.default.theme))) || null)"
            )
            try:
                proc = subprocess.run(
                    [node, "-p", expr],
                    capture_output=True, text=True, timeout=20,
                    cwd=str(cfg.parent),
                )
                if proc.returncode == 0 and proc.stdout.strip() not in ("", "null"):
                    return json.loads(proc.stdout)
            except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
                continue
        return None

    @staticmethod
    def _index_screens(
        repo: Path, files: list[str], framework: str
    ) -> list[dict[str, str]]:
        screens: list[dict[str, str]] = []
        for rel in files:
            p = Path(rel)
            parts = p.parts
            root = None
            for candidate in _SCREEN_ROOTS:
                croot = tuple(candidate.split("/"))
                if parts[: len(croot)] == croot:
                    root = candidate
                    break
            if root is None or p.suffix.lower() not in _SOURCE_EXTS:
                continue
            stem = p.stem.lower()
            inner = Path(*parts[len(root.split("/")):])
            if root in ("app", "src/app"):
                # Next app router: only page files are screens. Route groups
                # like (auth) organize files without affecting the URL.
                if stem != "page":
                    continue
                segs = [s for s in inner.parent.parts
                        if not (s.startswith("(") and s.endswith(")"))]
                route = "/" + "/".join(segs)
            elif root in ("pages", "src/pages"):
                if stem.startswith("_") or inner.parts[:1] == ("api",):
                    continue
                segs = list(inner.parent.parts) + ([] if stem == "index" else [stem])
                route = "/" + "/".join(segs)
            else:
                route = ""
            screens.append({
                "path": rel,
                "route": route if route else "/" + inner.stem,
                "root": root,
            })
        return screens

    @staticmethod
    def _index_components(files: list[str]) -> list[dict[str, str]]:
        comps: list[dict[str, str]] = []
        for rel in files:
            p = Path(rel)
            parts = p.parts
            for candidate in _COMPONENT_ROOTS:
                croot = tuple(candidate.split("/"))
                if parts[: len(croot)] == croot and p.suffix.lower() in _SOURCE_EXTS:
                    if p.stem.lower() in ("index", "types", "utils"):
                        break
                    comps.append({"name": p.stem, "path": rel})
                    break
        return comps
