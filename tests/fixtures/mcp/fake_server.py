"""Static fake MCP server for OpenMontage contract tests (stdio transport).

The tool list and parameter prototypes mirror the real ComfyUI MCP server in
`/opt/AI/comfy_api/my_mcp.py` (Video/Image generation API base on ComfyUI and
VLM). This fixture is a PURE STATIC demo: handlers return canned content blocks
and mutate nothing — no ComfyUI, no VLM, no network requests.
"""

import asyncio
import base64
from enum import Enum
from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.types import BlobResourceContents, EmbeddedResource, ImageContent
from pydantic import Field

mcp = MCPServer("Video/Image generation API base on ComfyUI and VLM (fake, static)")

# Turn any input into a deterministic byte payload for content blocks.
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
_MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 32 + b"FAKEDEMOVIDEO"


def _png_block() -> ImageContent:
    return ImageContent(type="image", data=base64.b64encode(_PNG).decode(), mimeType="image/png")


def _mp4_block(uri: str = "fake://out/video/demo.mp4") -> EmbeddedResource:
    blob = BlobResourceContents(uri=uri, blob=_MP4, mimeType="video/mp4")
    return EmbeddedResource(type="resource", resource=blob)


class AspectRatio(str, Enum):
    SQUARE = "1:1 (Square)"
    PHOTO_V = "2:3 (Portrait Photo)"
    PHOTO_H = "3:2 (Photo)"
    STANDARD_V = "3:4 (Portrait Standard)"
    STANDARD_H = "4:3 (Standard)"
    WIDESCREEN_V = "9:16 (Portrait Widescreen)"
    WIDESCREEN_H = "16:9 (Widescreen)"
    ULTRAWIDE_H = "21:9 (Ultrawide)"


@mcp.tool()
def calculate_resolution(
    aspect_ratio: Annotated[
        AspectRatio,
        Field(description="The aspect ratio for the output dimensions."),
    ] = AspectRatio.SQUARE,
    megapixels: Annotated[
        float,
        Field(ge=0.1, le=16.0, description="Target total megapixels. 1.0 MP ≈ 1024x1024 for square."),
    ] = 1.0,
    multiple: Annotated[
        int,
        Field(ge=8, le=128, multiple_of=4, description="Nearest multiple of the result."),
    ] = 8,
) -> dict:
    """Calculate width and height from aspect ratio and megapixel target."""
    return {"width": 1024, "height": 1024}


@mcp.tool(name="expand_prompt")
def _expand_prompt(
    prompt: str,
    target_model: Literal["zit", "minimax-h3"],
) -> str:
    """Expand simple user prompt to detailed prompt (static demo)."""
    return f"expanded:{target_model}:{prompt}"


@mcp.tool()
async def generate_image_t2i_zit(
    ctx: Context,
    prompt: str,
    width: int,
    height: int,
    steps: int = 8,
    cfg: float = 1.0,
    batch: int = 1,
    seed: int | None = None,
    override_lora_weights: list[tuple[str, float]] | None = None,
) -> ImageContent:
    """t2i = text-to-image, zit = Z-Image Turbo (static demo image)."""
    return _png_block()


async def _static_video() -> EmbeddedResource:
    return _mp4_block()


@mcp.tool()
async def generate_video_fl2va_minimax_h3(
    ctx: Context,
    duration: float,
    prompt: str,
    first_frame_url: str,
    last_frame_url: str,
    width: int = 0,
    height: int = 0,
    seed: int = 0,
    override_lora_weights: list[tuple[str, float]] | None = None,
) -> EmbeddedResource:
    """First-frame and Last-Frame to Video with Audio (static demo mp4)."""
    return await _static_video()


@mcp.tool()
async def generate_video_i2va_minimax_h3(
    ctx: Context,
    duration: float,
    prompt: str,
    image_url: str,
    width: int = 0,
    height: int = 0,
    seed: int = 0,
    override_lora_weights: list[tuple[str, float]] | None = None,
) -> EmbeddedResource:
    """Image to Video with Audio (static demo mp4)."""
    return await _static_video()


@mcp.tool()
async def generate_video_t2va_minimax_h3(
    ctx: Context,
    duration: float,
    prompt: str,
    width: int,
    height: int,
    seed: int = 0,
    override_lora_weights: list[tuple[str, float]] | None = None,
) -> EmbeddedResource:
    """Text to Video with Audio (static demo mp4)."""
    return await _static_video()


@mcp.tool()
async def generate_video_ref2va_minimax_h3(
    ctx: Context,
    duration: float,
    prompt: str,
    width: int,
    height: int,
    ref_image_urls: list[str] = (),
    ref_video_urls: list[str] = (),
    ref_audio_urls: list[str] = (),
    ref_video_audio_urls: list[str] = (),
    seed: int = 0,
    override_lora_weights: list[tuple[str, float]] | None = None,
) -> EmbeddedResource:
    """Multi-modal reference to Video with Audio (static demo mp4)."""
    return await _static_video()


@mcp.tool()
def select_best_image(image_urls: list[str]) -> str:
    """Select the best image — static: always index 0."""
    return "0\nstatic: best anatomical accuracy and composition"


@mcp.tool()
def evaluate_media(prompt: str, urls: list[str]) -> str:
    """AIGC visual quality audit report — static demo."""
    return (
        "1. Image\n    Score: 9/10\n    Detailed Analysis: static demo passes prompt adherence.\n"
        "    Recommendation: usable, no regeneration needed.\n"
    )


@mcp.tool()
def extract_video_last_frame(video_url: str) -> str:
    """Extract the last frame of a video — static demo URL."""
    return "fake://out/frames/last_frame_demo.png"


async def main() -> None:
    await mcp.run_stdio_async()


if __name__ == "__main__":
    asyncio.run(main())
