"""Diagram generation tool using Mermaid CLI, Cairo/Pillow, or Graphviz.

Generates technical diagrams from text descriptions. Supports Mermaid
syntax (flowcharts, sequence diagrams, etc.) and simple box/arrow
diagrams via Pillow as fallback.
"""

from __future__ import annotations

import json
import shutil
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


class DiagramGen(BaseTool):
    name = "diagram_gen"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "graphics"
    provider = "mermaid"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = []  # checked dynamically
    install_instructions = (
        "For Mermaid diagrams:\n"
        "  npm install -g @mermaid-js/mermaid-cli\n"
        "For Pillow-based diagrams (fallback):\n"
        "  pip install Pillow"
    )
    agent_skills = ["beautiful-mermaid", "d3-viz"]

    capabilities = [
        "generate_mermaid",
        "generate_flowchart",
        "generate_box_diagram",
    ]

    input_schema = {
        "type": "object",
        "required": ["diagram_type"],
        "properties": {
            "diagram_type": {
                "type": "string",
                "enum": ["mermaid", "flowchart", "boxes"],
            },
            "definition": {
                "type": "string",
                "description": "Mermaid syntax or diagram description",
            },
            "boxes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "color": {"type": "string"},
                    },
                },
                "description": "Box definitions for box diagram type",
            },
            "connections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "from": {"type": "integer"},
                        "to": {"type": "integer"},
                        "label": {"type": "string"},
                    },
                },
            },
            "title": {"type": "string"},
            "theme": {
                "type": "string",
                "enum": ["dark", "light", "neutral"],
                "default": "dark",
            },
            "width": {"type": "integer", "default": 1200},
            "height": {"type": "integer", "default": 800},
            "output_path": {"type": "string"},
            "allow_text_fallback": {
                "type": "boolean",
                "default": False,
                "description": "Render Mermaid source as a text card when Mermaid CLI is unavailable",
            },
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50)
    idempotency_key_fields = ["diagram_type", "definition", "boxes", "allow_text_fallback"]
    side_effects = ["writes diagram image to output_path"]
    user_visible_verification = [
        "Verify diagram accurately represents the described structure",
    ]

    def get_status(self) -> ToolStatus:
        statuses = self.operation_statuses()
        if all(status == "available" for status in statuses.values()):
            return ToolStatus.AVAILABLE
        if any(status == "available" for status in statuses.values()):
            return ToolStatus.DEGRADED
        return ToolStatus.UNAVAILABLE

    def operation_statuses(self) -> dict[str, str]:
        """Return backend availability for each supported diagram type."""
        return {
            "mermaid": "available" if self._has_mermaid() else "unavailable",
            "flowchart": "available" if self._has_pillow() else "unavailable",
            "boxes": "available" if self._has_pillow() else "unavailable",
        }

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["operation_statuses"] = self.operation_statuses()
        return info

    def idempotency_key(self, inputs: dict[str, Any]) -> str:
        return super().idempotency_key(
            {**inputs, "allow_text_fallback": inputs.get("allow_text_fallback", False)}
        )

    def _has_mermaid(self) -> bool:
        return shutil.which("mmdc") is not None

    def _has_pillow(self) -> bool:
        try:
            from PIL import Image  # noqa: F401
            return True
        except ImportError:
            return False

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        diagram_type = inputs["diagram_type"]
        start = time.time()

        try:
            if diagram_type == "mermaid":
                result = self._render_mermaid(inputs)
            elif diagram_type in ("flowchart", "boxes"):
                result = self._render_boxes(inputs)
            else:
                return ToolResult(success=False, error=f"Unknown diagram type: {diagram_type}")
        except Exception as e:
            return ToolResult(success=False, error=f"Diagram generation failed: {e}")

        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _render_mermaid(self, inputs: dict[str, Any]) -> ToolResult:
        definition = inputs.get("definition", "")
        if not definition:
            return ToolResult(success=False, error="Mermaid definition required")

        output_path = Path(inputs.get("output_path", "diagram.png"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        theme = inputs.get("theme", "dark")

        if self._has_mermaid():
            # Write temp mermaid file
            temp_mmd = output_path.with_suffix(".mmd")
            temp_mmd.write_text(definition, encoding="utf-8")

            mermaid_config = {"theme": theme}
            config_path = output_path.with_suffix(".mermaid.json")
            config_path.write_text(json.dumps(mermaid_config), encoding="utf-8")

            cmd = [
                "mmdc",
                "-i", str(temp_mmd),
                "-o", str(output_path),
                "-c", str(config_path),
                "-b", "transparent",
                "-w", str(inputs.get("width", 1200)),
            ]

            try:
                self.run_command(cmd, timeout=30)
            finally:
                temp_mmd.unlink(missing_ok=True)
                config_path.unlink(missing_ok=True)

            return ToolResult(
                success=True,
                data={
                    "method": "mermaid-cli",
                    "output": str(output_path),
                },
                artifacts=[str(output_path)],
            )
        if inputs.get("allow_text_fallback", False):
            return self._render_text_card(definition, inputs)

        return ToolResult(
            success=False,
            error=(
                "Mermaid CLI (mmdc) is not available. "
                "Install it with: npm install -g @mermaid-js/mermaid-cli"
            ),
        )

    def _render_boxes(self, inputs: dict[str, Any]) -> ToolResult:
        """Render a box-and-arrow diagram using Pillow."""
        if not self._has_pillow():
            return ToolResult(
                success=False,
                error="Pillow required for box diagrams. Run: pip install Pillow",
            )

        from PIL import Image, ImageDraw, ImageFont

        boxes = inputs.get("boxes", [])
        connections = inputs.get("connections", [])
        title = inputs.get("title", "")
        theme = inputs.get("theme", "dark")
        width = inputs.get("width", 1200)
        height = inputs.get("height", 800)
        output_path = Path(inputs.get("output_path", "diagram.png"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Theme colors
        if theme == "dark":
            bg, text_color, box_default, line_color = "#1e1e2e", "#cdd6f4", "#45475a", "#89b4fa"
        elif theme == "light":
            bg, text_color, box_default, line_color = "#ffffff", "#333333", "#e1e4e8", "#0366d6"
        else:
            bg, text_color, box_default, line_color = "#2d2d2d", "#d4d4d4", "#404040", "#569cd6"

        img = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(img)

        try:
            font = ImageFont.truetype("arial.ttf", 18)
            title_font = ImageFont.truetype("arial.ttf", 24)
        except (IOError, OSError):
            font = ImageFont.load_default()
            title_font = font

        # Draw title
        y_offset = 20
        if title:
            bbox = draw.textbbox((0, 0), title, font=title_font)
            tw = bbox[2] - bbox[0]
            draw.text(((width - tw) // 2, y_offset), title, fill=text_color, font=title_font)
            y_offset += 50

        # Layout boxes in a grid
        if not boxes:
            boxes = [{"label": "Empty"}]

        cols = min(len(boxes), 4)
        rows = (len(boxes) + cols - 1) // cols
        box_w = min(200, (width - 80) // cols - 20)
        box_h = 60
        x_gap = (width - cols * box_w) // (cols + 1)
        y_gap = max(40, (height - y_offset - rows * box_h) // (rows + 1))

        box_positions = []
        for i, box in enumerate(boxes):
            col = i % cols
            row = i // cols
            x = x_gap + col * (box_w + x_gap)
            y = y_offset + y_gap + row * (box_h + y_gap)

            fill = box.get("color", box_default)
            draw.rounded_rectangle(
                [(x, y), (x + box_w, y + box_h)],
                radius=8,
                fill=fill,
                outline=line_color,
                width=2,
            )

            label = box.get("label", f"Box {i}")
            bbox = draw.textbbox((0, 0), label, font=font)
            lw = bbox[2] - bbox[0]
            lh = bbox[3] - bbox[1]
            draw.text(
                (x + (box_w - lw) // 2, y + (box_h - lh) // 2),
                label, fill=text_color, font=font,
            )

            box_positions.append((x, y, x + box_w, y + box_h))

        # Draw connections
        for conn in connections:
            fi = conn.get("from", 0)
            ti = conn.get("to", 0)
            if fi >= len(box_positions) or ti >= len(box_positions):
                continue

            fx1, fy1, fx2, fy2 = box_positions[fi]
            tx1, ty1, tx2, ty2 = box_positions[ti]

            start_x = (fx1 + fx2) // 2
            start_y = fy2
            end_x = (tx1 + tx2) // 2
            end_y = ty1

            draw.line([(start_x, start_y), (end_x, end_y)], fill=line_color, width=2)

            # Arrow head
            arrow_size = 8
            draw.polygon(
                [(end_x, end_y), (end_x - arrow_size, end_y - arrow_size * 2), (end_x + arrow_size, end_y - arrow_size * 2)],
                fill=line_color,
            )

            # Connection label
            conn_label = conn.get("label")
            if conn_label:
                mid_x = (start_x + end_x) // 2
                mid_y = (start_y + end_y) // 2
                draw.text((mid_x + 5, mid_y - 10), conn_label, fill=text_color, font=font)

        img.save(output_path)

        return ToolResult(
            success=True,
            data={
                "method": "pillow",
                "output": str(output_path),
                "box_count": len(boxes),
                "connection_count": len(connections),
            },
            artifacts=[str(output_path)],
        )

    def _render_text_card(self, text: str, inputs: dict[str, Any]) -> ToolResult:
        """Fallback: render text as a styled card image."""
        if not self._has_pillow():
            return ToolResult(
                success=False,
                error="Pillow required. Run: pip install Pillow",
            )

        from PIL import Image, ImageDraw, ImageFont

        output_path = Path(inputs.get("output_path", "diagram.png"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        width = inputs.get("width", 800)

        try:
            font = ImageFont.truetype("consola.ttf", 16)
        except (IOError, OSError):
            font = ImageFont.load_default()

        # Calculate needed height
        lines = text.split("\n")
        line_height = 22
        height = max(200, len(lines) * line_height + 80)

        img = Image.new("RGB", (width, height), "#1e1e2e")
        draw = ImageDraw.Draw(img)

        y = 40
        for line in lines:
            draw.text((40, y), line, fill="#cdd6f4", font=font)
            y += line_height

        img.save(output_path)

        return ToolResult(
            success=True,
            data={
                "method": "text_card",
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
        )
