<!-- skills/meta/mcp-tool-classification.md -->
# MCP Tool Classification (Agent Review)

Use whenever a configured MCP server exposes tools whose `capability` is not yet
frozen in `mcp_servers.yaml`. The Agent — not Python — decides capability; Python
only persists the verdict.

## When to run

- When first connecting a configured MCP server (or after its tool set changes)
  and before the first preflight/proposal that might use its tools.
- On tool-set changes: only review the **new or changed** unfrozen tools. The
  disk cache is keyed by config hash, so existing frozen verdicts stay put.

## Procedure

1. Run `mcp_catalog` (`operation: review`). The output lists every tool of every
   configured server: `name` / `title` / `description` / `input_schema` summary /
   `output_hints` / `frozen` / `capability`.
2. For each `frozen: false` tool, decide which OpenMontage capability family it
   belongs to (`tts`, `image_generation`, `video_generation`, `music_generation`,
   `analysis`, `subtitle`, `enhancement`, `graphics`, `avatar`, `publish`, ...) —
   or that it fits **no** family. Evidence ordering: `description` semantics >
   `input_schema` argument shape > tool name. The output shape (image/video/audio/
   text content blocks) is a strong signal. When unsure, leave it unfrozen.
3. Write the verdict back to `mcp_servers.yaml`:

   ```yaml
   tools:
     <remote_tool_name>: { capability: <capability> }   # optionally add cost_usd / agent_skills / model
   ```

   For tools that are uncertain or fit no capability family, write nothing.
4. After writing, call `registry.discover_mcp()` in the same session (or restart)
   to register the newly frozen tools.
5. A user can manually declare/override any verdict at any time — the file is the
   frozen source of truth; a manual declaration has the highest priority.

## Rules

- **Unfrozen ≠ "capability unknown but guessed": never guess.** An unfrozen tool
  is never bridged into a selector's candidate list. It remains reachable only via
  `mcp_call` (raw passthrough) and visible in `mcp_catalog`.
- Different tools on the same server can belong to different capabilities; the
  `provider` name is always that server's slug.
- If a probe is needed to confirm the output shape, call the tool once via
  `mcp_call` and let the actual result inform the verdict.
- The capability value must exactly match one of the strings in
  `registry.capability_catalog()` — no invented family names.
