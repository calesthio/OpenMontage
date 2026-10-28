#!/usr/bin/env python3
"""
Telegram Approval Poller for Video Factory

Runs in background, watches for approval status changes, and automatically:
1. Generates videos when brief is approved
2. Sends videos to Telegram for final approval
3. Auto-posts when videos are approved

Run this continuously in the background:
  python3 scripts/approval-poller.py
"""

from __future__ import annotations

import json
import os
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Import our handlers (use importlib for hyphenated filenames)
import sys
import importlib.util
sys.path.insert(0, str(Path(__file__).parent))

# Load telegram_approval_handler
spec = importlib.util.spec_from_file_location(
    "telegram_approval_handler",
    Path(__file__).parent / "telegram-approval-handler.py"
)
telegram_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(telegram_module)
TelegramApprovalBot = telegram_module.TelegramApprovalBot
ApprovalOrchestrator = telegram_module.ApprovalOrchestrator

# Load higgsfield_video_generator
spec = importlib.util.spec_from_file_location(
    "higgsfield_video_generator",
    Path(__file__).parent / "higgsfield-video-generator.py"
)
higgsfield_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(higgsfield_module)
HighgsfieldGen = higgsfield_module.HighgsfieldOrchestrator


class ApprovalPoller:
    """Poll for approval status changes and trigger automation"""

    MAX_RETRIES = 3  # Maximum retry attempts before giving up

    def __init__(self):
        self.bot = TelegramApprovalBot()
        self.processed_briefs = set()  # Track which briefs we've already processed
        self.retry_counts = {}  # Track retry attempts per brief
        self.last_check = {}  # Track last check time for each brief

    async def poll(self, poll_interval: int = 10):
        """Poll for approval changes every N seconds"""
        logger.info("🔄 Starting approval poller...")
        logger.info(f"📍 Checking every {poll_interval} seconds for approval changes")

        while True:
            try:
                await self._check_all_approvals()
                await asyncio.sleep(poll_interval)
            except Exception as e:
                logger.error(f"❌ Poller error: {e}")
                await asyncio.sleep(poll_interval)

    async def _check_all_approvals(self):
        """Check all pending approvals for status changes"""
        pending_approvals = self.bot.pending_approvals

        for brief_id, record in pending_approvals.items():
            status = record.get("status")

            # Stage 1: Brief approved → Generate videos
            if status == "approved" and brief_id not in self.processed_briefs:
                retries = self.retry_counts.get(brief_id, 0)
                if retries >= self.MAX_RETRIES:
                    logger.error(f"❌ Brief {brief_id} failed after {retries} attempts. Giving up.")
                    self.processed_briefs.add(brief_id)
                    await self.bot.send_performance_update(
                        f"❌ Video generation for {brief_id} failed after {retries} attempts.\n\n"
                        f"Manual intervention required. Re-approve the brief to try again."
                    )
                    continue

                attempt = retries + 1
                logger.info(f"✅ Brief approved: {brief_id} (attempt {attempt}/{self.MAX_RETRIES})")

                # Load brief and generate videos
                brief_path = Path(f"~/.video-factory/briefs/{brief_id}.json").expanduser()
                if brief_path.exists():
                    with open(brief_path) as f:
                        brief = json.load(f)

                    # Send notification
                    retry_note = f" (retry {attempt}/{self.MAX_RETRIES})" if retries > 0 else ""
                    await self.bot.send_performance_update(
                        f"🎬 Starting Higgsfield video generation for {brief_id}{retry_note}...\n\n"
                        f"Driver: {brief['driver']}\n"
                        f"Platforms: {', '.join(brief['platforms'])}\n\n"
                        f"Estimated time: 40 minutes"
                    )

                    # Generate videos and wait for success before marking as processed
                    success = await self._generate_videos(brief)
                    if success:
                        self.processed_briefs.add(brief_id)
                        self.retry_counts.pop(brief_id, None)
                        logger.info(f"✅ Brief {brief_id} marked as processed (videos sent to Telegram)")
                    else:
                        self.retry_counts[brief_id] = attempt
                        logger.warning(
                            f"⚠️ Video generation failed for {brief_id}. "
                            f"Attempt {attempt}/{self.MAX_RETRIES}. Will retry on next poll cycle."
                        )

            # Stage 3: Videos approved → Auto-post
            elif status == "approved_for_posting" and brief_id not in self.processed_briefs:
                retries = self.retry_counts.get(f"post_{brief_id}", 0)
                if retries >= self.MAX_RETRIES:
                    logger.error(f"❌ Posting {brief_id} failed after {retries} attempts. Giving up.")
                    self.processed_briefs.add(brief_id)
                    await self.bot.send_performance_update(
                        f"❌ Video posting for {brief_id} failed after {retries} attempts.\n\n"
                        f"Manual intervention required."
                    )
                    continue

                attempt = retries + 1
                logger.info(f"✅ Videos approved for posting: {brief_id} (attempt {attempt}/{self.MAX_RETRIES})")

                # Auto-post to all platforms and wait for success before marking as processed
                orchestrator = ApprovalOrchestrator()
                result = await orchestrator.auto_post_videos(brief_id)
                if result.get("status") == "posted":
                    self.processed_briefs.add(brief_id)
                    self.retry_counts.pop(f"post_{brief_id}", None)
                    logger.info(f"✅ Brief {brief_id} marked as processed (videos posted)")
                else:
                    self.retry_counts[f"post_{brief_id}"] = attempt
                    logger.warning(
                        f"⚠️ Video posting failed for {brief_id}. "
                        f"Attempt {attempt}/{self.MAX_RETRIES}. Will retry on next poll cycle."
                    )

    async def _generate_videos(self, brief: dict) -> bool:
        """Generate videos on Higgsfield and send to Telegram

        Returns:
            True if videos generated and sent to Telegram successfully
            False if any step failed (generation failed or Telegram upload failed)
        """
        brief_id = brief["brief_id"]

        try:
            logger.info(f"🎬 Generating videos for {brief_id}...")
            higgsfield = HighgsfieldGen()
            result = await higgsfield.generate_all_videos(brief)

            if result.get("status") != "complete":
                logger.error(f"Video generation failed: {result}")
                await self.bot.send_performance_update(
                    f"❌ Video generation failed for {brief_id}\n\n"
                    f"{result.get('message', 'Unknown error')}"
                )
                return False

            video_paths = result.get("video_paths", [])
            logger.info(f"✅ Generated {len(video_paths)} videos")

            # Send videos to Telegram
            logger.info(f"📹 Sending {len(video_paths)} videos to Telegram...")
            success = await self.bot.send_rendered_videos(brief_id, video_paths)

            if success:
                logger.info(f"✅ Videos sent to Telegram for {brief_id}")
                return True
            else:
                logger.error(f"Failed to send videos to Telegram for {brief_id}")
                return False

        except Exception as e:
            logger.error(f"❌ Video generation error: {e}")
            await self.bot.send_performance_update(
                f"❌ Video generation error for {brief_id}: {str(e)[:200]}"
            )
            return False


async def main():
    """Start the approval poller"""
    poller = ApprovalPoller()
    await poller.poll(poll_interval=10)  # Check every 10 seconds


if __name__ == "__main__":
    print("")
    print("🚀 Telegram Approval Poller Starting")
    print("=" * 60)
    print("")
    print("This watches for approval status changes and automatically:")
    print("  1. Generates videos when you tap ✅ Approve on a brief")
    print("  2. Sends videos to Telegram for final approval")
    print("  3. Auto-posts when you tap 🚀 Post on videos")
    print("")
    print("Keep this running in the background while using the video factory.")
    print("")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print("")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n✅ Poller stopped")
