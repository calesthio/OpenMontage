"""
Spike: Headless Agent Runner for OpenMontage Web Platform

验证命题:
  能否用 MaaS (OpenAI-compatible, anthropic/claude-sonnet-4.6) 驱动一个无头 agent,
  让它读取 OpenMontage 的 skill/manifest,并通过 Tool Bridge 调用现有 BaseTool?

测试场景: cinematic pipeline 的 script 阶段
  - agent 读取 script-director.md skill
  - agent 读取已有 proposal_packet.json
  - agent 调用 write_artifact 产出 script.json
  - agent 【不】实际生成视频(保证 spike 运行快速和免费)

运行:
  python spike_agent_runner.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# ── 路径设置 ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# ── OpenAI-compat 客户端指向 MaaS ─────────────────────────────────────────────
from openai import OpenAI

MAAS_KEY  = os.environ.get("MAAS_API_KEY", "")
MAAS_BASE = os.environ.get("MAAS_API_BASE", "https://api.aiapbot.com")
LLM_MODEL = "anthropic/claude-sonnet-4.6"   # 1000k ctx, tool-capable, on MaaS

client = OpenAI(api_key=MAAS_KEY, base_url=f"{MAAS_BASE}/v1")

# ── 测试项目路径 ───────────────────────────────────────────────────────────────
PROJECT_DIR = ROOT / "projects" / "spike-test"
PROJECT_DIR.mkdir(parents=True, exist_ok=True)
(PROJECT_DIR / "artifacts").mkdir(exist_ok=True)

# 使用已有的 puppy-coffee-machine proposal 作为输入上下文
PROPOSAL_SRC = ROOT / "projects" / "puppy-coffee-machine" / "artifacts" / "proposal_packet.json"

# ── Tool 定义 ─────────────────────────────────────────────────────────────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a file from the OpenMontage project filesystem. "
                "Use for reading skills (skills/), pipeline manifests (pipeline_defs/), "
                "schemas (schemas/), and project artifacts (projects/)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path relative to OpenMontage root, e.g. 'skills/pipelines/cinematic/script-director.md'"
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
                "The content must conform to the artifact schema. "
                "Returns the path where it was written."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "artifact_name": {
                        "type": "string",
                        "description": "Artifact name, e.g. 'script', 'proposal_packet', 'scene_plan'"
                    },
                    "content": {
                        "type": "object",
                        "description": "The artifact content as a JSON object"
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
                "Run any tool from the OpenMontage tool registry by name. "
                "For the spike, only safe/free tools are allowed (no video generation). "
                "Available for spike: list_tools"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_name": {
                        "type": "string",
                        "description": "Tool name from registry, e.g. 'maas_image', 'maas_tts', 'maas_video'"
                    },
                    "inputs": {
                        "type": "object",
                        "description": "Tool input parameters per tool's input_schema"
                    }
                },
                "required": ["tool_name", "inputs"]
            }
        }
    }
]

# ── Tool 执行实现 ──────────────────────────────────────────────────────────────
def execute_tool(name: str, args: dict) -> str:
    """执行 tool call, 返回字符串结果"""

    if name == "read_file":
        path = ROOT / args["path"]
        if not path.exists():
            return f"ERROR: File not found: {args['path']}"
        content = path.read_text(encoding="utf-8")
        # 限制返回长度避免 context 爆
        if len(content) > 8000:
            content = content[:8000] + f"\n\n... [truncated, total {len(path.read_text())} chars]"
        return content

    elif name == "write_artifact":
        artifact_name = args["artifact_name"]
        content = args["content"]
        out_path = PROJECT_DIR / "artifacts" / f"{artifact_name}.json"
        out_path.write_text(json.dumps(content, ensure_ascii=False, indent=2))
        print(f"\n  📄 写入 artifact: {out_path.relative_to(ROOT)}")
        return f"Written to {out_path}"

    elif name == "run_openmontage_tool":
        tool_name = args["tool_name"]
        inputs = args.get("inputs", {})

        # Spike 阶段: 只允许安全工具,不实际调用生成类工具
        ALLOWED_TOOLS = {"list_tools"}
        if tool_name == "list_tools":
            from tools.tool_registry import registry
            registry.discover()
            tools_info = []
            for t in list(registry._tools.values())[:20]:
                tools_info.append(f"{t.name} (capability={t.capability}, provider={t.provider})")
            return "Available tools (first 20):\n" + "\n".join(tools_info)

        # 实际 tool 调用在 spike 中模拟返回
        print(f"\n  🔧 [SIMULATED] tool call: {tool_name}({json.dumps(inputs, ensure_ascii=False)[:120]})")
        return json.dumps({
            "success": True,
            "simulated": True,
            "note": f"Spike mode: {tool_name} call simulated, not actually executed",
            "tool_name": tool_name,
            "inputs_received": inputs
        })

    return f"ERROR: Unknown tool: {name}"

# ── Agent 循环 ────────────────────────────────────────────────────────────────
def run_agent(task: str, max_turns: int = 12) -> str:
    """
    核心 agent 循环:
      1. 发送 task + tools
      2. 若 LLM 返回 tool_calls → 执行 → 追加 tool results → 继续
      3. 直到 LLM 返回纯文本(任务完成)或 max_turns
    """
    print(f"\n{'='*60}")
    print(f"🤖 Agent 启动")
    print(f"   模型: {LLM_MODEL} via MaaS")
    print(f"   任务: {task[:80]}...")
    print(f"{'='*60}\n")

    messages = [{"role": "user", "content": task}]
    turn = 0

    while turn < max_turns:
        turn += 1
        print(f"\n── Turn {turn} ────────────────────────────────")

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=4096,
            temperature=0.7,
        )

        msg = response.choices[0].message
        finish = response.choices[0].finish_reason

        print(f"   finish_reason: {finish}")

        # 纯文本回复 → agent 完成
        if msg.content and not msg.tool_calls:
            print(f"\n✅ Agent 完成 (turn {turn})")
            print(f"\n── Agent 最终回复 ─────────────────────────────")
            print(msg.content)
            return msg.content

        # 有工具调用
        if msg.tool_calls:
            # 先把 assistant 消息追加
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                    }
                    for tc in msg.tool_calls
                ]
            })

            # 执行每个 tool call
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                tool_args = json.loads(tc.function.arguments)
                print(f"\n  → tool_call: {tool_name}({list(tool_args.keys())})")

                result = execute_tool(tool_name, tool_args)
                print(f"    result: {result[:200]}{'...' if len(result)>200 else ''}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result
                })

        elif finish == "stop":
            # stop without content or tool_calls
            break

    return "[Agent reached max_turns without completing]"


# ── Spike 主流程 ──────────────────────────────────────────────────────────────
def main():
    print("\n" + "="*60)
    print("  OpenMontage Web Platform — Agent Runner SPIKE")
    print("  目标: 验证无头 agent 能读 skill + 调 tool + 产出 artifact")
    print("="*60)

    # 读入 proposal 作为上下文
    proposal = json.loads(PROPOSAL_SRC.read_text()) if PROPOSAL_SRC.exists() else {}

    task = f"""
You are the script-director for OpenMontage's cinematic pipeline.

## Your task
1. Read the file `skills/pipelines/cinematic/script-director.md` to understand your role and constraints.
2. Read the proposal artifact below (already approved by the user).
3. Based on the proposal, produce a cinematic script artifact for a 30-second marketing film.
4. Write the artifact using the `write_artifact` tool with artifact_name="script_spike".

## Approved Proposal
```json
{json.dumps(proposal, ensure_ascii=False, indent=2)}
```

## Instructions
- Write a script with 4 beats: hook / escalation / reveal / landing
- Each beat should have: start_time, end_time, label, description, title_card (optional), narration (optional)
- Keep it concise — this is a spike test, not production
- After writing the artifact, confirm what you produced in 2-3 sentences.

Begin now.
"""

    t0 = time.time()
    result = run_agent(task)
    elapsed = round(time.time() - t0, 1)

    print(f"\n{'='*60}")
    print(f"  Spike 完成  |  耗时: {elapsed}s")

    # 检查产出
    out = PROJECT_DIR / "artifacts" / "script_spike.json"
    if out.exists():
        data = json.loads(out.read_text())
        print(f"  ✅ artifact 产出: {out.relative_to(ROOT)}")
        print(f"     beats: {len(data.get('beat_map', data.get('beats', [])))} 个")
        print(f"\n  【SPIKE 验证通过】Agent 成功读 skill + 产出 artifact")
    else:
        print(f"  ⚠️  artifact 未产出 — 检查 agent 输出")

    print("="*60)


if __name__ == "__main__":
    main()
