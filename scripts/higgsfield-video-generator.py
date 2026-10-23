#!/usr/bin/env python3
"""
Higgsfield AI Video Generator for Video Factory

Generates 10 marketing videos (5 platforms × 2 A/B variants) from a brief using:
- Hormozi-based messaging (transformation → mechanism → result)
- Platform-optimized Higgsfield prompts
- Persistent browser automation with Playwright
- Direct integration with Telegram approval workflow
"""

from __future__ import annotations

import json
import os
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class HighgsfieldPromptBuilder:
    """Build Higgsfield AI prompts using Hormozi framework + marketing best practices"""

    # Platform-specific specs
    PLATFORM_SPECS = {
        "instagram": {
            "resolution": "1080x1350",
            "duration": "30-45s",
            "aspect_ratio": "4:5 vertical",
            "style": "polished, professional, high-engagement hooks",
            "format": "cinematic short-form",
        },
        "tiktok": {
            "resolution": "1080x1920",
            "duration": "15-60s",
            "aspect_ratio": "9:16 vertical",
            "style": "energetic, trending, snappy cuts, trending audio-friendly",
            "format": "UGC-style energetic",
        },
        "youtube_shorts": {
            "resolution": "1080x1920",
            "duration": "15-60s",
            "aspect_ratio": "9:16 vertical",
            "style": "educational, cinematic, high production value",
            "format": "cinematic educational",
        },
        "linkedin": {
            "resolution": "1200x627",
            "duration": "30-60s",
            "aspect_ratio": "16:9 horizontal",
            "style": "professional, credible, executive-focused",
            "format": "professional insights",
        },
        "twitter": {
            "resolution": "1200x675",
            "duration": "15-30s",
            "aspect_ratio": "16:9 horizontal",
            "style": "punchy, direct, data-driven",
            "format": "performance ad",
        },
    }

    def __init__(self):
        pass

    def build_prompt(
        self,
        driver: str,
        hook: str,
        cta: str,
        platform: str,
        variant_type: str,
    ) -> str:
        """Build a Higgsfield prompt for a specific variant

        Args:
            driver: VLC wellness driver (e.g., "HRV", "Sleep Quality")
            hook: Marketing hook (transformation/credibility)
            cta: Call-to-action text
            platform: Target platform (instagram, tiktok, etc.)
            variant_type: "emotional" or "credibility"

        Returns:
            Higgsfield prompt string
        """
        specs = self.PLATFORM_SPECS[platform]

        # Build the prompt structure using Higgsfield best practices
        prompt = f"""
[FORMAT]
Type: {specs['format']}
Resolution: {specs['resolution']}
Duration: {specs['duration']}
Aspect Ratio: {specs['aspect_ratio']}
Style: {specs['style']}

[OPENING HOOK]
Visual: Clean, attention-grabbing scene establishing the wellness topic ({driver})
Camera: Slow push forward building tension
Audio: Minimal ambient sound, no dialogue yet
Text Overlay: "{hook}"
Duration: 5 seconds
Goal: Stop scrolling, trigger curiosity

[PROBLEM STATEMENT]
Visual: Show the relatable problem or pain point related to {driver}
Camera: Medium shot, natural lighting, authentic
Audio: Soft background music building engagement
Narration or Text: Expand on the hook with a relatable statement
Duration: 10 seconds
Tone: Empathetic, understanding

[MECHANISM/INSIGHT]
Visual: Reveal the solution or insight
Camera: Dynamic motion - pull back or cut to new perspective
Audio: Uplifting music, slight increase in pace
Narration or Text: Explain the mechanism or why this works
Duration: 10 seconds
Tone: Educational, credible

[TRANSFORMATION/RESULTS]
Visual: Show the positive outcome or transformation
Camera: Pull forward or zoom, energetic motion
Audio: Triumphant, motivating music crescendo
Narration or Text: Results, benefits, or what's possible
Duration: 8 seconds
Tone: Inspiring, motivating

[CALL-TO-ACTION]
Visual: Clear, simple final frame with CTA
Camera: Static, direct to camera
Background: Branded, clean, professional
Text Overlay: "{cta}"
Audio: Music fades to clear voice saying CTA
Duration: 3 seconds
Tone: Confident, direct

[TECHNICAL SPECS]
- No watermarks or credits
- Optimize for mobile viewing
- Ensure text is readable on small screens
- Keep pacing snappy (cut frequency: 1-2 cuts per 5 seconds)
- Use realistic, natural movements
- Color grading: Consistent, brand-aligned
- No AI artifacts or unrealistic elements
"""
        return prompt.strip()

    def build_batch_prompts(self, brief: dict) -> dict[str, dict]:
        """Build prompts for all 10 variants in a brief

        Args:
            brief: Brief dict with platforms, variants, driver, etc.

        Returns:
            Dict mapping platform:variant_id -> prompt
        """
        prompts = {}

        for platform in brief["platforms"]:
            variants = brief["variants"][platform]

            for variant_idx, variant in enumerate(variants):
                variant_type = "emotional" if variant_idx == 0 else "credibility"
                variant_id = variant["variant_id"]

                prompt = self.build_prompt(
                    driver=brief["driver"],
                    hook=variant["hook"],
                    cta=variant["cta"],
                    platform=platform,
                    variant_type=variant_type,
                )

                prompts[f"{platform}:{variant_id}"] = {
                    "variant_id": variant_id,
                    "platform": platform,
                    "variant_type": variant_type,
                    "prompt": prompt,
                }

        return prompts


class HighgsfieldBrowserAutomation:
    """Browser automation for Higgsfield AI video generation with persistent Apple Sign-In"""

    def __init__(self, cdp_url: str = "http://localhost:9222"):
        self.cdp_url = cdp_url
        self.browser = None
        self.page = None

    async def connect(self) -> bool:
        """Connect to persistent Chrome instance via Chrome DevTools Protocol"""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright")
            return False

        try:
            playwright = await async_playwright().start()
            # Connect to existing Chrome instance running with --remote-debugging-port=9222
            self.browser = await playwright.chromium.connect_over_cdp(self.cdp_url)
            self.page = await self.browser.new_page()

            # Verify we're logged in by checking if we can access create page
            await self.page.goto("https://higgsfield.ai/create", wait_until="networkidle", timeout=10000)
            logger.info("✅ Connected to persistent Higgsfield session (Apple Sign-In)")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Chrome on {self.cdp_url}: {e}")
            logger.error("Make sure Chrome is running with: bash scripts/setup-higgsfield-browser.sh")
            return False

    # Platform-aware minimum file sizes (bytes). HD video at these durations
    # should never be smaller than these values.
    PLATFORM_MIN_SIZES = {
        "instagram": 3_000_000,   # 30-45s @ 1080x1350 ≈ 8-15MB
        "tiktok": 2_000_000,      # 15-60s @ 1080x1920 ≈ 4-20MB
        "youtube_shorts": 2_000_000,  # 15-60s @ 1080x1920 ≈ 4-20MB
        "linkedin": 2_000_000,    # 30-60s @ 1200x627 ≈ 3-10MB
        "twitter": 1_500_000,     # 15-30s @ 1200x675 ≈ 2-6MB
    }
    DEFAULT_MIN_SIZE = 2_000_000

    async def generate_video(self, prompt: str, variant_id: str, platform: str = None) -> Optional[str]:
        """Generate a single video via Higgsfield prompt

        Args:
            prompt: Higgsfield-formatted prompt
            variant_id: Unique variant identifier
            platform: Target platform (for size validation thresholds)

        Returns:
            Path to downloaded MP4, or None if failed
        """
        try:
            # Navigate to create page
            await self.page.goto("https://higgsfield.ai/create", wait_until="networkidle")

            # Find and fill prompt textarea
            prompt_field = await self.page.query_selector('textarea[placeholder*="Describe"]')
            if prompt_field:
                await prompt_field.fill(prompt)
            else:
                logger.error("❌ Could not find prompt input field")
                return None

            # Click generate/create button
            generate_button = await self.page.query_selector('button:has-text("Generate")')
            if not generate_button:
                generate_button = await self.page.query_selector('button:has-text("Create")')

            if generate_button:
                await generate_button.click()
            else:
                logger.error("❌ Could not find generate button")
                return None

            # Wait for video to render (poll for download link or completion)
            max_wait = 45 * 60  # 45 minutes in seconds (40 min render + buffer)
            start_time = datetime.utcnow()

            while (datetime.utcnow() - start_time).total_seconds() < max_wait:
                # Check if download link appeared
                download_link = await self.page.query_selector('a:has-text("Download")')
                if download_link:
                    # Download the video
                    async with self.page.expect_download() as download_info:
                        await download_link.click()
                    download = await download_info.value

                    # Save to ~/.video-factory/videos/
                    output_dir = Path("~/.video-factory/videos").expanduser()
                    output_dir.mkdir(parents=True, exist_ok=True)
                    output_path = output_dir / f"{variant_id}.mp4"

                    await download.save_as(output_path)

                    # Validate file size using platform-aware thresholds
                    min_size = self.PLATFORM_MIN_SIZES.get(platform, self.DEFAULT_MIN_SIZE)
                    min_size_mb = min_size / (1024 * 1024)
                    file_size = output_path.stat().st_size
                    size_mb = file_size / (1024 * 1024)

                    if file_size < min_size:
                        logger.error(
                            f"❌ Video file suspiciously small for {variant_id}: {size_mb:.1f}MB "
                            f"(expected > {min_size_mb:.0f}MB for {platform or 'unknown'} HD video). "
                            f"File may be corrupted or incomplete."
                        )
                        # Delete the corrupted file
                        output_path.unlink()
                        return None

                    # Optional: validate with ffprobe if available
                    probe_ok = await self._ffprobe_validate(output_path, variant_id)
                    if probe_ok is False:  # None means ffprobe unavailable (skip)
                        output_path.unlink()
                        return None

                    logger.info(f"✅ Downloaded {variant_id}: {output_path} ({size_mb:.1f}MB)")
                    return str(output_path)

                # Wait before polling again
                await asyncio.sleep(5)

            logger.error(f"❌ Video generation timeout for {variant_id}")
            return None

        except Exception as e:
            logger.error(f"❌ Video generation failed for {variant_id}: {e}")
            return None

    async def _ffprobe_validate(self, file_path: Path, variant_id: str) -> Optional[bool]:
        """Validate video file using ffprobe.

        Returns:
            True if valid video, False if corrupt/not-a-video, None if ffprobe unavailable.
        """
        import subprocess
        import shutil

        if not shutil.which("ffprobe"):
            logger.debug("ffprobe not found, skipping codec validation")
            return None

        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-select_streams", "v:0",
                    "-show_entries", "stream=codec_name,duration,width,height",
                    "-of", "json",
                    str(file_path),
                ],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode != 0:
                logger.error(
                    f"❌ ffprobe failed for {variant_id}: {result.stderr.strip()}"
                )
                return False

            import json as _json
            probe = _json.loads(result.stdout)
            streams = probe.get("streams", [])
            if not streams:
                logger.error(f"❌ No video stream found in {variant_id}")
                return False

            stream = streams[0]
            codec = stream.get("codec_name", "unknown")
            duration = float(stream.get("duration", 0))
            width = int(stream.get("width", 0))
            height = int(stream.get("height", 0))

            if duration < 5:
                logger.error(
                    f"❌ Video too short for {variant_id}: {duration:.1f}s (expected >= 5s)"
                )
                return False

            logger.info(
                f"   ffprobe OK: {variant_id} — {codec} {width}x{height} {duration:.1f}s"
            )
            return True

        except subprocess.TimeoutExpired:
            logger.warning(f"ffprobe timed out for {variant_id}, skipping validation")
            return None
        except Exception as e:
            logger.warning(f"ffprobe error for {variant_id}: {e}, skipping validation")
            return None

    async def generate_batch(self, prompts: dict) -> dict[str, Optional[str]]:
        """Generate all videos in a batch

        Args:
            prompts: Dict mapping variant_id -> prompt

        Returns:
            Dict mapping variant_id -> video_path
        """
        results = {}

        for key, prompt_data in prompts.items():
            variant_id = prompt_data["variant_id"]
            prompt = prompt_data["prompt"]
            platform = prompt_data.get("platform")

            logger.info(f"🎬 Generating {variant_id} ({platform})...")
            video_path = await self.generate_video(prompt, variant_id, platform=platform)
            results[variant_id] = video_path

        return results

    async def close(self):
        """Close browser connection"""
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        logger.info("✅ Browser closed")


class HighgsfieldOrchestrator:
    """Orchestrate brief → prompts → video generation → Telegram approval"""

    def __init__(self, cdp_url: str = "http://localhost:9222"):
        self.prompt_builder = HighgsfieldPromptBuilder()
        self.browser = HighgsfieldBrowserAutomation(cdp_url=cdp_url)

    async def generate_all_videos(self, brief: dict) -> dict:
        """Full pipeline: build prompts → connect to persistent session → generate all 10 videos

        Args:
            brief: Brief dict with driver, platforms, variants

        Returns:
            Dict with status and video paths
        """
        brief_id = brief["brief_id"]

        # Step 1: Connect to persistent Chrome session (must be running with --remote-debugging-port=9222)
        if not await self.browser.connect():
            return {
                "status": "error",
                "message": "Failed to connect to Higgsfield browser. Run: bash scripts/setup-higgsfield-browser.sh"
            }

        # Step 2: Build all prompts
        logger.info(f"🔨 Building prompts for {brief_id}...")
        prompts = self.prompt_builder.build_batch_prompts(brief)
        logger.info(f"✅ Built {len(prompts)} prompts")

        # Step 3: Generate all videos
        logger.info(f"🎬 Starting video generation for {brief_id}...")
        results = await self.browser.generate_batch(prompts)

        # Step 4: Close browser connection
        await self.browser.close()

        # Step 5: Collect results
        video_paths = [path for path in results.values() if path]
        failed_count = len(results) - len(video_paths)

        return {
            "status": "complete",
            "brief_id": brief_id,
            "total_videos": len(results),
            "successful_videos": len(video_paths),
            "failed_videos": failed_count,
            "video_paths": video_paths,
            "results": results,
        }


# CLI
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Higgsfield AI Video Generator")
    parser.add_argument("--generate", help="Brief ID to generate videos for (uses persistent Apple Sign-In session)")
    parser.add_argument("--test-prompt", action="store_true", help="Generate sample prompt")

    args = parser.parse_args()

    if args.test_prompt:
        builder = HighgsfieldPromptBuilder()
        prompt = builder.build_prompt(
            driver="HRV",
            hook="Why 8 hours of sleep still feels like 4",
            cta="Check your HRV score",
            platform="tiktok",
            variant_type="emotional",
        )
        print(prompt)

    elif args.generate:
        # Load brief
        brief_path = Path(f"~/.video-factory/briefs/{args.generate}.json").expanduser()
        if not brief_path.exists():
            print(f"❌ Brief not found: {args.generate}")
            exit(1)

        with open(brief_path) as f:
            brief = json.load(f)

        print(f"🎬 Generating videos for {args.generate}...")
        print("📍 Make sure Chrome is running with: bash scripts/setup-higgsfield-browser.sh")
        print("")

        orchestrator = HighgsfieldOrchestrator()
        result = asyncio.run(orchestrator.generate_all_videos(brief))
        print(json.dumps(result, indent=2))
    else:
        parser.print_help()
