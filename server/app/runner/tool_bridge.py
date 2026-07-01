"""Tool Bridge: exposes OpenMontage BaseTool registry to the headless agent.

The agent is given three capabilities:
  read_file         — read any file under the OpenMontage root
  write_artifact    — persist an artifact JSON to the project dir
  run_openmontage_tool — call any registered BaseTool by name

Tool schemas are returned in OpenAI function-call format so they work with
both the OpenAI SDK (pointing at MaaS) and Anthropic SDK.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# Add OpenMontage root to path so we can import tools/lib
OM_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(OM_ROOT))

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a file from the OpenMontage filesystem. "
                "Use for skills (skills/), pipeline manifests (pipeline_defs/), "
                "schemas (schemas/), and project artifacts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relative to OpenMontage root"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_artifact",
            "description": (
                "Write a pipeline artifact JSON to the project artifacts directory. "
                "IMPORTANT: Keep 'content' compact — each field value under 300 chars, "
                "use arrays of short strings rather than long prose. "
                "Large content causes token truncation and will fail."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "artifact_name": {
                        "type": "string",
                        "description": "e.g. 'research', 'proposal_packet', 'script', 'scene_plan'"
                    },
                    "content": {
                        "type": "object",
                        "description": "Compact JSON artifact. Keep each string value under 300 chars."
                    }
                },
                "required": ["artifact_name", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_openmontage_tool",
            "description": (
                "Run a tool from the OpenMontage tool registry. "
                "Available capabilities: video_generation, image_generation, tts, "
                "music_search, subtitle, enhancement, analysis."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "Registered tool name, e.g. 'maas_video', 'maas_image', 'maas_tts'"
                    },
                    "inputs": {
                        "type": "object",
                        "description": "Tool inputs per the tool's input_schema"
                    }
                },
                "required": ["tool_name", "inputs"]
            }
        }
    }
]


def execute_tool(
    name: str,
    args: dict[str, Any],
    project_dir: Path,
    emit_event: Any = None,   # callable(event_dict) for SSE
    cost_accumulator: list | None = None,  # mutable list[float] for cost accumulation
    cost_tracker: Any = None,  # optional tools.cost_tracker.CostTracker ledger
) -> str:
    """Execute a tool call and return a string result for the agent."""

    if name == "read_file":
        path = OM_ROOT / args["path"]
        if not path.exists():
            return f"ERROR: File not found: {args['path']}"
        content = path.read_text(encoding="utf-8")
        if len(content) > 12000:
            content = content[:12000] + f"\n\n[truncated — {len(content)} total chars]"
        return content

    elif name == "write_artifact":
        artifact_name = args.get("artifact_name")
        content = args.get("content")
        if not artifact_name:
            return "ERROR: write_artifact requires 'artifact_name' parameter"
        if content is None:
            return "ERROR: write_artifact requires 'content' parameter"
        artifacts_dir = project_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        out = artifacts_dir / f"{artifact_name}.json"
        out.write_text(json.dumps(content, ensure_ascii=False, indent=2))
        if emit_event:
            emit_event({
                "type": "artifact_written",
                "artifact": artifact_name,
                "path": str(out.relative_to(OM_ROOT)),
            })
        return f"Written to {out}"

    elif name == "run_openmontage_tool":
        tool_name = args["tool_name"]
        inputs = args.get("inputs", {})

        if emit_event:
            emit_event({
                "type": "tool_call",
                "tool": tool_name,
                "summary": f"调用工具 {tool_name}",
                "inputs_preview": {k: str(v)[:80] for k, v in inputs.items()},
            })

        from tools.tool_registry import registry
        registry.discover()
        tool = registry.get(tool_name)
        if not tool:
            return f"ERROR: Tool '{tool_name}' not found in registry"

        # Set output path if not specified.
        if "output_path" not in inputs:
            ext_map = {
                "video_generation": "mp4",
                "image_generation": "png",
                "tts": "mp3",
                "music_generation": "mp3",
                "audio_processing": "mp3",
                "video_post": "mp4",
            }
            ext = ext_map.get(tool.capability, "bin")

            # The final composed video is the pipeline deliverable — it must land
            # in renders/ so the runner and /media serving can find and play it.
            # Any other video_post op (trim, stitch) stays in assets/.
            is_final_compose = (
                tool.capability == "video_post"
                and inputs.get("operation", "compose") == "compose"
            )
            if is_final_compose:
                renders_dir = project_dir / "renders"
                renders_dir.mkdir(parents=True, exist_ok=True)
                inputs = {**inputs, "output_path": str(renders_dir / "final.mp4")}
            else:
                out_dir = project_dir / "assets" / tool.capability
                out_dir.mkdir(parents=True, exist_ok=True)
                inputs = {**inputs, "output_path": str(out_dir / f"{tool_name}_output.{ext}")}

        # Ledger: estimate before, reconcile after (real CostTracker usage →
        # persists an itemized cost_log.json for budget governance/audit).
        entry_id = None
        if cost_tracker is not None:
            try:
                entry_id = cost_tracker.estimate(
                    tool_name,
                    inputs.get("operation", "run"),
                    float(tool.estimate_cost(inputs) or 0.0),
                )
                cost_tracker.approve_tool(tool_name)
                cost_tracker.reserve(entry_id)   # OBSERVE mode never raises
            except Exception:
                entry_id = None

        result = tool.execute(inputs)

        if cost_tracker is not None and entry_id is not None:
            try:
                cost_tracker.reconcile(
                    entry_id, float(result.cost_usd or 0.0), success=result.success
                )
            except Exception:
                pass

        if result.success:
            # Record every completed paid call (append even 0.0 so the tally
            # reflects call count; the sum is what drives the CNY display).
            if cost_accumulator is not None and result.cost_usd is not None:
                cost_accumulator.append(float(result.cost_usd))
            if emit_event and result.artifacts:
                for artifact_path in result.artifacts:
                    emit_event({
                        "type": "asset_ready",
                        "tool": tool_name,
                        "path": artifact_path,
                        "kind": tool.capability,
                    })
            return json.dumps({
                "success": True,
                "data": result.data,
                "artifacts": result.artifacts,
                "cost_usd": result.cost_usd,
            })
        else:
            return json.dumps({"success": False, "error": result.error})

    return f"ERROR: Unknown tool: {name}"
