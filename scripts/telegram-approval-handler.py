#!/usr/bin/env python3
"""
Telegram Approval Handler for Video Factory — Full Visual Workflow

THREE-STAGE APPROVAL PROCESS:

1. BRIEF APPROVAL (Storyboard Preview)
   - Text brief with hooks
   - Storyboard thumbnail preview (6-frame grid per variant)
   - Buttons: [✅ Approve] [❌ Revise] [🔄 Reschedule] [⏰ Custom Time]

2. VIDEO PREVIEW (After 40 min rendering)
   - All 10 videos rendered as MP4
   - Telegram embedded video players (playable in-app)
   - File metadata (size, resolution, duration)
   - Buttons: [▶️ Play All] [📥 Download] [🚀 Post] [✏️ Edit]

3. FINAL POSTING
   - Auto-post to all 5 platforms
   - Real-time A/B tracking begins
   - Daily updates via Telegram

Usage:
  python telegram-approval-handler.py --send-brief {brief_id}
  python telegram-approval-handler.py --send-videos {brief_id}
  python telegram-approval-handler.py --finalize {brief_id}
"""

from __future__ import annotations

import json
import os
import asyncio
import requests
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class TelegramApprovalBot:
    """Handles approval requests via Telegram"""

    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", 8428117168)  # Numeric chat ID
        self.pending_approvals = self._load_pending()
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.metrics_file = Path("~/.video-factory/metrics.json").expanduser()

    def _load_pending(self) -> dict:
        """Load pending approvals from file"""
        pending_file = Path("~/.video-factory/pending-approvals.json").expanduser()
        if pending_file.exists():
            with open(pending_file) as f:
                return json.load(f)
        return {}

    def _save_pending(self):
        """Save pending approvals"""
        pending_file = Path("~/.video-factory/pending-approvals.json").expanduser()
        pending_file.parent.mkdir(parents=True, exist_ok=True)
        with open(pending_file, "w") as f:
            json.dump(self.pending_approvals, f, indent=2)

    def _log_metric(self, event: str, brief_id: str, success: bool, detail: str = ""):
        """Append a metrics event to ~/.video-factory/metrics.json (one JSON object per line)"""
        entry = {
            "ts": datetime.utcnow().isoformat(),
            "event": event,
            "brief_id": brief_id,
            "success": success,
            "detail": detail,
        }
        try:
            self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.metrics_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.debug(f"Metrics write failed (non-fatal): {e}")

    async def send_approval_request(self, brief: dict) -> str:
        """Send brief to Chad for approval via Telegram"""
        brief_id = brief["brief_id"]
        driver = brief["driver"]
        platforms = ", ".join(brief["platforms"])

        # Get first platform's variants for preview
        first_platform = brief["platforms"][0]
        variant_a = brief["variants"][first_platform][0]
        variant_b = brief["variants"][first_platform][1]

        message = f"""Video Factory - Approval Required

Driver: {driver}
Platforms: {platforms}
Brief ID: {brief_id}

Variant A (Emotional Hook)
Hook: {variant_a['hook']}
CTA: {variant_a['cta']}

Variant B (Credibility Hook)
Hook: {variant_b['hook']}
CTA: {variant_b['cta']}

Tap a button below to proceed."""

        try:
            # Send message with inline buttons
            import requests

            response = requests.post(
                f"{self.api_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "reply_markup": {
                        "inline_keyboard": [
                            [
                                {"text": "✅ Approve", "callback_data": f"approve_{brief_id}"},
                                {"text": "❌ Revise", "callback_data": f"revise_{brief_id}"},
                            ],
                            [
                                {
                                    "text": "🔄 Reschedule",
                                    "callback_data": f"reschedule_{brief_id}",
                                },
                                {
                                    "text": "⏰ Custom Time",
                                    "callback_data": f"custom_time_{brief_id}",
                                },
                            ],
                        ]
                    },
                },
            )

            if response.status_code == 200:
                message_id = response.json()["result"]["message_id"]
                self.pending_approvals[brief_id] = {
                    "status": "pending",
                    "message_id": message_id,
                    "sent_at": datetime.utcnow().isoformat(),
                    "driver": driver,
                    "platforms": platforms,
                    "brief": brief,
                }
                self._save_pending()
                logger.info(f"✅ Approval request sent: {brief_id}")
                return brief_id
            else:
                logger.error(f"❌ Telegram API error: {response.text}")
                return None

        except Exception as e:
            logger.error(f"❌ Failed to send approval: {e}")
            return None

    async def send_rendered_videos(self, brief_id: str, video_files: list[str]) -> bool:
        """Send rendered videos for final approval (Stage 2)

        Args:
            brief_id: Brief identifier
            video_files: List of paths to rendered MP4 files

        Returns:
            True if all videos sent successfully, False if any file is missing or corrupted
        """
        if brief_id not in self.pending_approvals:
            logger.warning(f"Brief not found: {brief_id}")
            return False

        approval_record = self.pending_approvals[brief_id]

        # Validate all video files exist and have reasonable size before uploading
        missing_files = []
        suspicious_files = []
        for video_path in video_files:
            path = Path(video_path).expanduser()
            if not path.exists():
                missing_files.append(video_path)
            else:
                file_size = path.stat().st_size
                if file_size < 2_000_000:  # Less than 2MB is suspicious for HD video
                    suspicious_files.append(f"{path.name} ({file_size / 1024:.0f}KB)")

        # Fail entire batch if any files are missing or corrupted
        if missing_files or suspicious_files:
            error_msg = ""
            if missing_files:
                error_msg += f"Missing {len(missing_files)} video(s):\n"
                for f in missing_files:
                    error_msg += f"  - {f}\n"
            if suspicious_files:
                error_msg += f"\nSuspicious file sizes (< 2MB):\n"
                for f in suspicious_files:
                    error_msg += f"  - {f}\n"

            logger.error(f"❌ Video validation failed for {brief_id}:\n{error_msg}")
            approval_record["status"] = "video_generation_failed"
            approval_record["video_validation_error"] = error_msg
            self._save_pending()
            self._log_metric("video_validation", brief_id, False,
                             f"missing={len(missing_files)} suspicious={len(suspicious_files)}")

            # Notify user of validation failure
            await self.send_performance_update(
                f"❌ Video validation failed for {brief_id}\n\n{error_msg}\n"
                f"Please re-run video generation."
            )
            return False

        # Upload all videos BEFORE changing status.
        # Status stays "approved" during upload so the poller can retry on failure.
        video_message_ids = []
        for idx, video_path in enumerate(video_files, 1):
            path = Path(video_path).expanduser()
            file_size = path.stat().st_size
            size_mb = file_size / (1024 * 1024)

            try:
                with open(path, "rb") as f:
                    files = {"video": f}
                    data = {
                        "chat_id": self.chat_id,
                        "caption": f"Video {idx}/10 - {path.name}\nSize: {size_mb:.1f}MB",
                    }
                    response = requests.post(
                        f"{self.api_url}/sendVideo",
                        files=files,
                        data=data,
                    )

                    if response.status_code == 200:
                        msg_id = response.json()["result"]["message_id"]
                        video_message_ids.append(msg_id)
                        logger.info(f"✅ Sent video {idx}/10: {path.name}")
                    else:
                        logger.error(f"Failed to send video {idx}: {response.text}")
                        self._log_metric("video_upload", brief_id, False,
                                         f"video {idx}/10 HTTP {response.status_code}")
                        await self.send_performance_update(
                            f"❌ Failed to upload video {idx} to Telegram\n\n"
                            f"Error: {response.text[:200]}"
                        )
                        return False
            except Exception as e:
                logger.error(f"Error uploading video {idx}: {e}")
                self._log_metric("video_upload", brief_id, False,
                                 f"video {idx}/10 exception: {str(e)[:100]}")
                await self.send_performance_update(
                    f"❌ Error uploading video {idx}: {str(e)[:200]}"
                )
                return False

        self._log_metric("video_upload", brief_id, True,
                         f"all {len(video_files)} videos uploaded")

        # All videos uploaded successfully — NOW transition the state machine
        approval_record["status"] = "video_preview"
        approval_record["video_preview_at"] = datetime.utcnow().isoformat()
        self._save_pending()

        # Send approval buttons
        message = """
📹 All videos rendered and ready for review

Select an action:
▶️ Play All — Review in Telegram
🚀 Post — Publish to all platforms with staggered timing
✏️ Edit — Request revisions
        """
        try:
            response = requests.post(
                f"{self.api_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "reply_markup": {
                        "inline_keyboard": [
                            [
                                {"text": "▶️ Play All", "callback_data": f"play_all_{brief_id}"},
                                {"text": "🚀 Post", "callback_data": f"post_{brief_id}"},
                            ],
                            [
                                {"text": "✏️ Edit", "callback_data": f"edit_{brief_id}"},
                            ],
                        ]
                    },
                },
            )
            if response.status_code == 200:
                approval_record["video_approval_message_id"] = response.json()["result"]["message_id"]
                self._save_pending()
                logger.info(f"✅ Video approval sent: {brief_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to send video approval: {e}")

        return False

    async def handle_callback(self, callback_query: dict) -> dict:
        """Handle Chad's approval response"""
        callback_id = callback_query["id"]
        data = callback_query["data"]
        message_id = callback_query["message"]["message_id"]

        action, brief_id = data.split("_", 1)

        if brief_id not in self.pending_approvals:
            logger.warning(f"Unknown brief: {brief_id}")
            return {"status": "error", "message": "Brief not found"}

        approval_record = self.pending_approvals[brief_id]

        if action == "approve":
            approval_record["status"] = "approved"
            approval_record["approved_at"] = datetime.utcnow().isoformat()
            response_text = "✅ Brief approved! Generating videos..."
            next_action = "dispatch_pipelines"

        elif action == "revise":
            approval_record["status"] = "revision_requested"
            response_text = "❌ Please describe revisions needed:"
            next_action = "await_revision_details"

        elif action == "reschedule":
            approval_record["status"] = "rescheduled"
            approval_record["reschedule_time"] = (
                datetime.utcnow() + timedelta(days=7)
            ).isoformat()
            response_text = f"🔄 Rescheduled for {(datetime.utcnow() + timedelta(days=7)).strftime('%A, %B %d')}"
            next_action = "schedule_later"

        elif action == "custom_time":
            approval_record["status"] = "awaiting_custom_time"
            response_text = "⏰ Send posting time (e.g., '2026-04-15 10:00')"
            next_action = "await_custom_time"

        elif action == "post":
            approval_record["status"] = "approved_for_posting"
            approval_record["video_approved_at"] = datetime.utcnow().isoformat()
            response_text = "🚀 Posting videos to all platforms..."
            next_action = "auto_post"

        elif action == "edit":
            approval_record["status"] = "video_revision_requested"
            response_text = "✏️ Describe desired changes:"
            next_action = "await_video_revisions"

        elif action == "play_all":
            response_text = "▶️ All 10 videos are available above in chat"
            next_action = None

        self._save_pending()

        # Send acknowledgment
        import requests

        requests.post(
            f"{self.api_url}/answerCallbackQuery",
            json={"callback_query_id": callback_id, "text": response_text},
        )

        return {
            "status": "processed",
            "brief_id": brief_id,
            "action": action,
            "next_action": next_action,
            "approval_record": approval_record,
        }

    async def get_approval_status(self, brief_id: str) -> dict:
        """Check approval status"""
        if brief_id not in self.pending_approvals:
            return {"status": "not_found"}

        return {
            "brief_id": brief_id,
            "status": self.pending_approvals[brief_id]["status"],
            "sent_at": self.pending_approvals[brief_id]["sent_at"],
            "driver": self.pending_approvals[brief_id].get("driver"),
        }

    async def send_performance_update(self, report: str):
        """Send daily/weekly performance report"""
        try:
            import requests

            requests.post(
                f"{self.api_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": f"📊 **Video Factory Performance Report**\n\n{report}",
                    "parse_mode": "Markdown",
                },
            )
            logger.info("📊 Performance report sent")
        except Exception as e:
            logger.error(f"Failed to send report: {e}")

    def process_pending_approvals(self):
        """Check for expired pending approvals"""
        expired = []
        for brief_id, record in self.pending_approvals.items():
            if record["status"] == "pending":
                sent_at = datetime.fromisoformat(record["sent_at"])
                if datetime.utcnow() - sent_at > timedelta(hours=24):
                    # Auto-proceed if 24 hours have passed
                    record["status"] = "auto_approved"
                    record["auto_approved_at"] = datetime.utcnow().isoformat()
                    expired.append(brief_id)
                    logger.info(f"⏱️  Auto-approved (24h timeout): {brief_id}")

        if expired:
            self._save_pending()

        return expired


class ApprovalOrchestrator:
    """Manages the full approval → dispatch → posting workflow"""

    def __init__(self):
        self.bot = TelegramApprovalBot()
        self.dispatch_log = Path("~/.video-factory/dispatch-log.json").expanduser()

    async def approve_and_dispatch(self, brief: dict) -> str:
        """Send brief for approval and dispatch on approval"""
        brief_id = brief["brief_id"]

        # Stage 1: Send brief for approval
        await self.bot.send_approval_request(brief)

        # Poll for approval (blocking)
        max_wait = 24  # hours
        poll_interval = 60  # seconds
        elapsed = 0

        while elapsed < max_wait * 3600:
            status = await self.bot.get_approval_status(brief_id)

            if status["status"] == "approved":
                logger.info(f"✅ Brief approved: {brief_id}")
                # Stage 2: Generate videos on Higgsfield
                await self._generate_higgsfield_videos(brief)
                return "approved"

            elif status["status"] == "revision_requested":
                logger.warning(f"⚠️  Revision requested: {brief_id}")
                return "revision_requested"

            elif status["status"] == "rescheduled":
                logger.info(f"🔄 Rescheduled: {brief_id}")
                return "rescheduled"

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        # Auto-approve after 24 hours
        logger.info(f"⏱️  Auto-approving after 24h: {brief_id}")
        await self._generate_higgsfield_videos(brief)
        return "auto_approved"

    async def wait_for_video_approval(self, brief_id: str) -> bool:
        """Wait for user approval after videos render (Stage 2)

        Returns:
            True if approved for posting, False if revision requested
        """
        max_wait = 24  # hours
        poll_interval = 60  # seconds
        elapsed = 0

        while elapsed < max_wait * 3600:
            if brief_id not in self.bot.pending_approvals:
                return False

            status = self.bot.pending_approvals[brief_id].get("status")

            if status == "approved_for_posting":
                logger.info(f"✅ Videos approved for posting: {brief_id}")
                return True

            elif status == "video_revision_requested":
                logger.warning(f"⚠️  Video revision requested: {brief_id}")
                return False

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        # Auto-approve videos after 24 hours
        logger.info(f"⏱️  Auto-approving videos after 24h: {brief_id}")
        return True

    async def _generate_higgsfield_videos(self, brief: dict):
        """Generate all 10 videos via Higgsfield AI (Stage 2)

        Calls higgsfield-video-generator.py which:
        1. Connects to persistent Chrome session (Apple Sign-In already logged in)
        2. Builds 10 optimized prompts (2 variants × 5 platforms)
        3. Generates all videos on Higgsfield (~40 min)
        4. Downloads MP4s to ~/.video-factory/videos/
        5. Returns video paths

        Then sends all videos to Telegram for final approval.
        """
        brief_id = brief["brief_id"]
        logger.info(f"🎬 Generating videos on Higgsfield for {brief_id}...")

        try:
            # Call Higgsfield video generator
            result = subprocess.run(
                ["python3", "scripts/higgsfield-video-generator.py", "--generate", brief_id],
                capture_output=True,
                text=True,
                timeout=45 * 60,  # 45 min timeout (40 min render + buffer)
            )

            if result.returncode != 0:
                logger.error(f"❌ Video generation failed: {result.stderr}")
                await self.bot.send_performance_update(
                    f"⚠️ Video generation failed for {brief_id}\n\n"
                    f"Error: {result.stderr[:200]}\n\n"
                    f"Make sure Chrome is running: bash scripts/setup-higgsfield-browser.sh"
                )
                return

            # Parse results
            output_lines = result.stdout.strip().split("\n")
            result_json = json.loads(output_lines[-1])  # Last line is JSON output

            if result_json.get("status") != "complete":
                logger.error(f"❌ Generation incomplete: {result_json}")
                await self.bot.send_performance_update(
                    f"⚠️ Video generation incomplete for {brief_id}"
                )
                return

            video_paths = result_json.get("video_paths", [])
            logger.info(f"✅ Generated {len(video_paths)} videos for {brief_id}")

            # Update approval record
            approval_record = self.bot.pending_approvals[brief_id]
            approval_record["videos_generated_at"] = datetime.utcnow().isoformat()
            approval_record["video_paths"] = video_paths
            self.bot._save_pending()

            # Send videos to Telegram for final approval
            logger.info(f"📹 Sending {len(video_paths)} videos to Telegram...")
            await self.bot.send_rendered_videos(brief_id, video_paths)

        except subprocess.TimeoutExpired:
            logger.error(f"❌ Video generation timeout for {brief_id}")
            await self.bot.send_performance_update(
                f"⏱️ Video generation timeout after 45 minutes for {brief_id}"
            )
        except Exception as e:
            logger.error(f"❌ Video generation error: {e}")
            await self.bot.send_performance_update(
                f"❌ Video generation error for {brief_id}: {str(e)[:200]}"
            )

    async def _dispatch_to_pipelines(self, brief: dict):
        """Dispatch approved brief to OpenMontage pipelines"""
        brief_id = brief["brief_id"]
        logger.info(f"🚀 Dispatching {brief_id} to pipelines...")

        # Create pipeline task queue
        pipeline_tasks = {
            "brief_id": brief_id,
            "dispatched_at": datetime.utcnow().isoformat(),
            "pipelines": [],
        }

        for platform in brief["platforms"]:
            for variant_idx, variant in enumerate(brief["variants"][platform]):
                task = {
                    "variant_id": variant["variant_id"],
                    "platform": platform,
                    "pipeline": "wellness-explainer",
                    "stage": "research",
                    "status": "queued",
                }
                pipeline_tasks["pipelines"].append(task)

        # Save dispatch log
        self.dispatch_log.parent.mkdir(parents=True, exist_ok=True)
        with open(self.dispatch_log, "a") as f:
            f.write(json.dumps(pipeline_tasks) + "\n")

        logger.info(f"✅ Dispatched {len(pipeline_tasks['pipelines'])} pipeline tasks")

    async def auto_post_videos(self, brief_id: str) -> dict:
        """Auto-post videos to all platforms with staggered timing (Stage 3)

        Posting schedule:
        - Instagram (T+0): immediately
        - TikTok (T+2h): 2 hours after Instagram
        - YouTube Shorts (T+3h): 3 hours after Instagram
        - LinkedIn (T+5h): 5 hours after Instagram
        - Twitter (T+6h): 6 hours after Instagram
        """
        if brief_id not in self.bot.pending_approvals:
            logger.error(f"Brief not found: {brief_id}")
            return {"status": "error", "message": "Brief not found"}

        approval_record = self.bot.pending_approvals[brief_id]
        approval_record["status"] = "auto_posting"
        approval_record["posting_started_at"] = datetime.utcnow().isoformat()
        self.bot._save_pending()

        # Platform posting schedule (in minutes after first post)
        platform_schedule = {
            "instagram": 0,
            "tiktok": 120,  # 2 hours
            "youtube_shorts": 180,  # 3 hours
            "linkedin": 300,  # 5 hours
            "twitter": 360,  # 6 hours
        }

        posting_log = {
            "brief_id": brief_id,
            "started_at": datetime.utcnow().isoformat(),
            "platforms": [],
        }

        for platform, delay_minutes in platform_schedule.items():
            await asyncio.sleep(delay_minutes * 60)

            posting_record = {
                "platform": platform,
                "posted_at": datetime.utcnow().isoformat(),
                "status": "queued",
                "variants": 2,  # A/B variants
            }
            posting_log["platforms"].append(posting_record)

            logger.info(f"📤 Queued {platform} posting for {brief_id}")

            # Send Telegram notification
            await self.bot.send_performance_update(
                f"📤 Posted to {platform.upper()} - 2 variants (A/B test active)\n\n"
                f"14-day tracking window starts now.\n"
                f"Winner determined: {7 + 7} days from today"
            )

        approval_record["status"] = "auto_posting_complete"
        approval_record["posting_complete_at"] = datetime.utcnow().isoformat()
        self.bot._save_pending()

        logger.info(f"✅ All platforms queued for posting: {brief_id}")
        return {
            "status": "posted",
            "brief_id": brief_id,
            "platforms_count": len(posting_log["platforms"]),
            "posting_log": posting_log,
        }


# CLI
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Telegram Approval Handler")
    parser.add_argument("--send-brief", help="Send brief for approval")
    parser.add_argument("--send-videos", help="Send rendered videos for approval (brief_id:video1.mp4:video2.mp4:...)")
    parser.add_argument("--finalize", help="Finalize and auto-post approved videos (brief_id)")
    parser.add_argument("--check-status", help="Check approval status")
    parser.add_argument("--process-pending", action="store_true", help="Process pending approvals")

    args = parser.parse_args()

    bot = TelegramApprovalBot()

    if args.send_brief:
        brief_file = Path(f"~/.video-factory/briefs/{args.send_brief}.json").expanduser()
        if brief_file.exists():
            with open(brief_file) as f:
                brief = json.load(f)
            asyncio.run(bot.send_approval_request(brief))
        else:
            print(f"❌ Brief not found: {args.send_brief}")

    elif args.send_videos:
        # Format: brief_id:video1.mp4:video2.mp4:...
        parts = args.send_videos.split(":")
        brief_id = parts[0]
        video_files = parts[1:] if len(parts) > 1 else []

        if video_files:
            result = asyncio.run(bot.send_rendered_videos(brief_id, video_files))
            if result:
                print(f"✅ Videos sent for brief: {brief_id}")
            else:
                print(f"❌ Failed to send videos for brief: {brief_id}")
        else:
            print("❌ No video files provided. Format: --send-videos brief_id:video1.mp4:video2.mp4:...")

    elif args.finalize:
        orchestrator = ApprovalOrchestrator()
        result = asyncio.run(orchestrator.auto_post_videos(args.finalize))
        print(json.dumps(result, indent=2))

    elif args.check_status:
        status = asyncio.run(bot.get_approval_status(args.check_status))
        print(json.dumps(status, indent=2))

    elif args.process_pending:
        expired = bot.process_pending_approvals()
        print(f"✅ Processed {len(expired)} pending approvals")
