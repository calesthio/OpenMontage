"""gpt-image-2 generation billed to a local Codex ChatGPT subscription.

The only image provider in the registry that needs no API key. It shells out to
the locally-installed `codex` CLI, which carries the user's ChatGPT OAuth session
and exposes an `image_generation` tool internally. Generations consume the
subscription's rolling quota, not API credit.

Deliberately does NOT read the OAuth token out of auth.json or call the Codex
backend directly: the official client owns token refresh and endpoint shape, and
both are undocumented moving targets.
"""

from __future__ import annotations

import json
import os
import shutil
import time
import uuid
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

# Codex writes each generation to $CODEX_HOME/generated_images/<session_id>/*.png
# (filename prefix varies: ig_* interactively, exec-* from `codex exec`). Undocumented,
# hence the primary path is the structured response and this is only the fallback.
_GENERATED_DIR = "generated_images"

# The final-message contract we force on the agent turn, so the result is parsed
# from JSON rather than scraped out of prose.
_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["images"],
    "properties": {
        "images": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Absolute paths of every image file generated",
        }
    },
    "additionalProperties": False,
}

_PROMPT_TEMPLATE = """\
Generate {n} image(s) using your image generation tool.

Aspect: {size}

{ref_block}Image description, render exactly this and nothing else:
{prompt}

When every image is generated, reply with ONLY this JSON object:
{{"images": ["<absolute path to each generated image file>"]}}
"""


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))


class CodexImage(BaseTool):
    name = "codex_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "codex"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    # The binary is local even though it reaches the network on our behalf —
    # what matters to the agent is that no key or endpoint is ours to configure.
    runtime = ToolRuntime.LOCAL

    dependencies = []  # checked dynamically: PATH + auth mode, see get_status()
    install_instructions = (
        "Install the Codex CLI and sign in with a paid ChatGPT plan:\n"
        "  https://developers.openai.com/codex/cli\n"
        "  codex login\n"
        "Verify with: codex features list  (image_generation must be true)\n"
        "No API key is needed — generations bill to the ChatGPT subscription.\n"
        "Free-tier ChatGPT accounts do not have image generation."
    )
    agent_skills = ["codex-image"]

    capabilities = ["generate_image", "generate_illustration", "text_to_image"]
    supports = {
        "complex_instructions": True,
        "text_in_image": True,
        "multiple_outputs": True,
        "offline": False,
        "no_api_key": True,
    }
    best_for = [
        "image generation with zero cash cost when a Codex/ChatGPT subscription exists",
        "machines with no image provider API key and no GPU",
        "complex multi-element compositions and images containing text",
    ]
    not_good_for = [
        "large batches — each image costs 30-60s and burns subscription quota fast",
        "exact non-standard dimensions (only square/portrait/landscape near 1024)",
        "pipelines that need a stable provider contract (Codex internals can change)",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "model": {
                "type": "string",
                "enum": ["gpt-image-2"],
                "default": "gpt-image-2",
                "description": "Fixed — the model is chosen by Codex, not by us.",
            },
            "size": {
                "type": "string",
                "enum": ["1024x1024", "1536x1024", "1024x1536"],
                "default": "1024x1024",
                "description": (
                    "Aspect hint, not an exact size. Codex picks the final pixel "
                    "dimensions (a 1024x1024 request came back 1254x1254). Crop with "
                    "auto_reframe when exact dimensions matter."
                ),
            },
            "n": {"type": "integer", "default": 1, "minimum": 1, "maximum": 4},
            "output_path": {"type": "string"},
            "reference_images": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Local image paths attached to the prompt via `codex exec -i`. "
                    "The agent passes them to gpt-image-2 as style/character references."
                ),
            },
            "codex_model": {
                "type": "string",
                "description": "Codex agent model driving the turn (not the image model).",
            },
            "timeout_seconds": {
                "type": "integer",
                "default": 900,
                "minimum": 60,
                "maximum": 3600,
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    # No retry: a failed turn has usually already spent quota, and a silent
    # second attempt doubles that spend without telling the user.
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = ["prompt", "size", "n"]
    side_effects = [
        "writes image files to output_path",
        "consumes Codex/ChatGPT subscription quota (rolling 5-hour and weekly limits)",
        "creates a Codex session under $CODEX_HOME/sessions",
    ]
    user_visible_verification = [
        "Inspect the generated image for relevance and quality",
        "Check remaining Codex quota if you plan to keep coding after a batch",
    ]

    # ---------------------------------------------------------------- status

    def get_status(self) -> ToolStatus:
        if shutil.which("codex") is None:
            return ToolStatus.UNAVAILABLE
        try:
            auth = json.loads(
                (_codex_home() / "auth.json").read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            return ToolStatus.UNAVAILABLE
        # Never read or log the token itself — only which mode it represents.
        if auth.get("auth_mode") == "chatgpt":
            return ToolStatus.AVAILABLE
        # Signed in with an API key instead: generation may still work, but it
        # bills API credit rather than the subscription. That is a different
        # cost model than this tool advertises, so it is not a clean AVAILABLE.
        return ToolStatus.DEGRADED

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["setup_offer"] = {
            "kind": "local_cli",
            "tool": self.name,
            "command": "codex login",
            "binary": "codex",
            "health_check": "codex features list  # image_generation must be true",
            "requires_api_key": False,
            "what_it_unlocks": [
                "image generation with no API key, billed to a ChatGPT subscription",
            ],
            "notes": "Requires a paid ChatGPT plan. Free tier has no image generation.",
        }
        return info

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Zero dollars — but not zero cost. Each image draws on the ChatGPT
        # subscription's rolling quota roughly 3-5x faster than a normal turn.
        # The scheduler must not treat this as free capacity.
        return 0.0

    # ------------------------------------------------------------- internals

    @staticmethod
    def _output_paths(output_path: str | None, count: int, extension: str) -> list[Path]:
        """Derive one output path per generated image.

        Mirrors openai_image._output_paths so both providers behave identically
        from the caller's side: one image honors the requested path as-is, several
        get `_1`, `_2`, ... so no image overwrites another.
        """
        ext = extension if extension.startswith(".") else f".{extension}"
        if not output_path:
            return [Path(f"generated_image_{idx + 1}{ext}") for idx in range(count)]

        path = Path(output_path)
        suffix = path.suffix or ext
        if count == 1:
            return [path if path.suffix else path.with_suffix(suffix)]

        base = path.with_suffix("") if path.suffix else path
        return [base.parent / f"{base.name}_{idx + 1}{suffix}" for idx in range(count)]

    @staticmethod
    def _collect_images(last_message: Path, started_at: float) -> list[Path]:
        """Locate the generated files. Structured response first, session dir second."""
        try:
            payload = json.loads(last_message.read_text(encoding="utf-8"))
            existing = [Path(p) for p in payload.get("images", []) if Path(p).is_file()]
            if existing:
                return existing
        except (OSError, ValueError, AttributeError):
            pass

        # Fallback for when the agent answers off-contract: Codex still wrote the
        # files under its own generated_images/<session_id>/. Take the session
        # directory created during this run.
        root = _codex_home() / _GENERATED_DIR
        if not root.is_dir():
            return []
        fresh = [d for d in root.iterdir() if d.is_dir() and d.stat().st_mtime >= started_at]
        if not fresh:
            return []
        newest = max(fresh, key=lambda d: d.stat().st_mtime)
        return sorted(newest.glob("*.png"))

    def _lock_path(self) -> Path:
        # Codex keeps global state on disk; concurrent turns corrupt it.
        return _codex_home() / ".openmontage-codex-image.lock"

    # --------------------------------------------------------------- execute

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        status = self.get_status()
        if status is ToolStatus.UNAVAILABLE:
            return ToolResult(
                success=False,
                error="Codex CLI not available or not signed in. " + self.install_instructions,
            )

        prompt = inputs["prompt"]
        size = inputs.get("size", "1024x1024")
        n = int(inputs.get("n", 1))
        timeout = int(inputs.get("timeout_seconds", 900))

        start = time.time()
        workdir = Path(os.environ.get("TEMP") or "/tmp") / f"codex_image_{uuid.uuid4().hex[:12]}"
        workdir.mkdir(parents=True, exist_ok=True)

        schema_file = workdir / "schema.json"
        last_message = workdir / "last.json"
        schema_file.write_text(json.dumps(_OUTPUT_SCHEMA), encoding="utf-8")

        # `-s read-only`: the image tool is internal to Codex, so the agent needs no
        # shell access. workspace-write additionally tries to launch the Windows
        # sandbox helper, which fails on machines where that helper isn't present.
        cmd = [
            "codex", "exec",
            "-C", str(workdir),
            "-s", "read-only",
            "--skip-git-repo-check",
            "--output-schema", str(schema_file),
            "-o", str(last_message),
        ]
        if inputs.get("codex_model"):
            cmd += ["-m", str(inputs["codex_model"])]
        refs = [Path(r).resolve() for r in inputs.get("reference_images", [])]
        missing = [str(r) for r in refs if not r.is_file()]
        if missing:
            return ToolResult(success=False, error=f"reference_images not found: {missing}")
        for r in refs:
            cmd += ["-i", str(r)]
        ref_block = (
            "The attached image(s) are STYLE AND CHARACTER REFERENCES. Pass them to the "
            "image generation tool as input/reference images and keep their art style, "
            "color palette, lighting and materials exactly. Only change what the "
            "description below asks for.\n\n"
        ) if refs else ""

        # An OPENAI_API_KEY in the environment can flip Codex onto API billing —
        # the exact thing this provider exists to avoid. Strip it for the child.
        child_env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}

        lock = self._lock_path()
        try:
            try:
                lock.parent.mkdir(parents=True, exist_ok=True)
                # ponytail: O_EXCL lockfile, not a real mutex. Enough to stop this
                # tool racing itself; swap for a proper lock if other tools drive codex.
                fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
            except FileExistsError:
                return ToolResult(
                    success=False,
                    error=(
                        f"Another Codex image run is in progress ({lock}). Codex keeps "
                        f"global state, so runs are serialized. Delete the lock file if "
                        f"a previous run crashed."
                    ),
                )

            # The prompt goes over stdin, not argv: `codex exec` reads stdin regardless
            # and blocks forever waiting for EOF if nothing closes it, and piping also
            # sidesteps Windows argv quoting on multi-line user prompts.
            try:
                proc = self.run_command(
                    cmd,
                    timeout=timeout,
                    cwd=workdir,
                    env=child_env,
                    input=_PROMPT_TEMPLATE.format(n=n, size=size, prompt=prompt, ref_block=ref_block),
                )
            except Exception as e:
                return ToolResult(success=False, error=f"Codex image generation failed: {e}")

            images = self._collect_images(last_message, start)
            if not images:
                return ToolResult(
                    success=False,
                    error=(
                        "Codex produced no image files. This usually means the quota is "
                        "exhausted or the account has no image generation. Run "
                        "`codex features list` and check image_generation."
                    ),
                )

            session_id = images[0].parent.name
            outputs: list[str] = []
            for src, dest in zip(images, self._output_paths(inputs.get("output_path"), len(images), "png")):
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dest)
                outputs.append(str(dest))
        finally:
            lock.unlink(missing_ok=True)
            shutil.rmtree(workdir, ignore_errors=True)

        return ToolResult(
            success=True,
            data={
                "provider": "codex",
                "model": "gpt-image-2",
                "prompt": prompt,
                "output": outputs[0],
                "outputs": outputs,
                "images_generated": len(outputs),
                "session_id": session_id,
                "billing": "chatgpt_subscription" if status is ToolStatus.AVAILABLE else "openai_api_key",
            },
            artifacts=outputs,
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            model="gpt-image-2",
        )
