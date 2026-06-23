"""Code snippet renderer for overlay images.

Generates styled code screenshots using Pygments for syntax
highlighting and Pillow for rendering. No external services required.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolStability,
    ToolStatus,
    ToolTier,
)


# Theme presets mapping to Pygments styles and background colors
THEMES = {
    "monokai": {
        "pygments_style": "monokai",
        "bg_color": "#272822",
        "text_color": "#f8f8f2",
        "border_color": "#3e3d32",
    },
    "github_dark": {
        "pygments_style": "github-dark",
        "bg_color": "#0d1117",
        "text_color": "#c9d1d9",
        "border_color": "#30363d",
    },
    "dracula": {
        "pygments_style": "dracula",
        "bg_color": "#282a36",
        "text_color": "#f8f8f2",
        "border_color": "#44475a",
    },
    "one_dark": {
        "pygments_style": "one-dark",
        "bg_color": "#282c34",
        "text_color": "#abb2bf",
        "border_color": "#3e4452",
    },
    "solarized_dark": {
        "pygments_style": "solarized-dark",
        "bg_color": "#002b36",
        "text_color": "#839496",
        "border_color": "#073642",
    },
    "light": {
        "pygments_style": "default",
        "bg_color": "#ffffff",
        "text_color": "#333333",
        "border_color": "#e1e4e8",
    },
}


class CodeSnippet(BaseTool):
    name = "code_snippet"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "graphics"
    provider = "pygments"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["python:pygments", "python:PIL"]
    install_instructions = "pip install Pygments Pillow"
    agent_skills = []

    capabilities = [
        "render_code_image",
        "syntax_highlight",
        "themed_code_card",
    ]

    input_schema = {
        "type": "object",
        "required": ["code"],
        "properties": {
            "code": {"type": "string"},
            "language": {"type": "string", "default": "python"},
            "theme": {
                "type": "string",
                "enum": list(THEMES.keys()),
                "default": "monokai",
            },
            "font_size": {"type": "integer", "default": 20},
            "padding": {"type": "integer", "default": 40},
            "border_radius": {"type": "integer", "default": 12},
            "line_numbers": {"type": "boolean", "default": True},
            "title": {"type": "string", "description": "Optional title bar text"},
            "output_path": {"type": "string"},
            "width": {"type": "integer", "description": "Force specific width"},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50)
    idempotency_key_fields = ["code", "language", "theme", "font_size"]
    side_effects = ["writes image to output_path"]
    user_visible_verification = [
        "Verify code is readable and syntax highlighting is correct",
    ]

    def get_status(self) -> ToolStatus:
        try:
            import pygments  # noqa: F401
            from PIL import Image  # noqa: F401
            return ToolStatus.AVAILABLE
        except ImportError:
            return ToolStatus.UNAVAILABLE

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            from PIL import Image, ImageDraw, ImageFont  # noqa: F401
            from pygments import highlight
            from pygments.lexers import get_lexer_by_name, guess_lexer
            from pygments.formatters import ImageFormatter
        except ImportError:
            return ToolResult(
                success=False,
                error="Pygments and Pillow required. Run: pip install Pygments Pillow",
            )

        start = time.time()

        code = inputs["code"]
        language = inputs.get("language", "python")
        theme_name = inputs.get("theme", "monokai")
        font_size = inputs.get("font_size", 20)
        padding = inputs.get("padding", 40)
        line_numbers = inputs.get("line_numbers", True)
        title = inputs.get("title")
        output_path = Path(inputs.get("output_path", "code_snippet.png"))

        theme = THEMES.get(theme_name, THEMES["monokai"])

        try:
            lexer = get_lexer_by_name(language)
        except Exception:
            lexer = guess_lexer(code)

        # Use Pygments ImageFormatter for rendering
        formatter = ImageFormatter(
            style=theme["pygments_style"],
            font_size=font_size,
            line_numbers=line_numbers,
            image_pad=padding,
            line_number_bg=theme["bg_color"],
            line_number_fg="#6272a4",
        )

        # Render to bytes
        image_bytes = highlight(code, lexer, formatter)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_bytes)

        # Add title bar if requested
        if title:
            self._add_title_bar(output_path, title, theme, font_size)

        elapsed = time.time() - start
        img = Image.open(output_path)

        return ToolResult(
            success=True,
            data={
                "output": str(output_path),
                "language": language,
                "theme": theme_name,
                "width": img.width,
                "height": img.height,
                "line_count": code.count("\n") + 1,
            },
            artifacts=[str(output_path)],
            duration_seconds=round(elapsed, 2),
        )

    def _add_title_bar(
        self, image_path: Path, title: str, theme: dict, font_size: int
    ) -> None:
        """Add a title bar to the top of the code image."""
        from PIL import Image, ImageDraw, ImageFont

        img = Image.open(image_path)
        bar_height = font_size + 20

        new_img = Image.new("RGB", (img.width, img.height + bar_height), theme["bg_color"])

        # Draw title bar
        draw = ImageDraw.Draw(new_img)
        draw.rectangle(
            [(0, 0), (img.width, bar_height)],
            fill=theme["border_color"],
        )

        # Draw window dots
        dot_y = bar_height // 2
        for i, color in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
            draw.ellipse(
                [(15 + i * 22, dot_y - 6), (15 + i * 22 + 12, dot_y + 6)],
                fill=color,
            )

        # Draw title text
        try:
            font = ImageFont.truetype("arial.ttf", font_size - 4)
        except (IOError, OSError):
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), title, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (img.width - text_width) // 2
        draw.text((text_x, 8), title, fill=theme["text_color"], font=font)

        # Paste original image below title bar
        new_img.paste(img, (0, bar_height))
        new_img.save(image_path)

    @staticmethod
    def list_themes() -> dict[str, str]:
        return {name: f"Background: {t['bg_color']}" for name, t in THEMES.items()}
