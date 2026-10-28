#!/usr/bin/env python3
"""
Telegram Webhook Handler for Video Factory

Receives Telegram callbacks (button taps) and triggers automatic video generation.
Listens for: ✅ Approve, ❌ Revise, 🔄 Reschedule, ⏰ Custom Time
Then: Generates videos → sends to Telegram → waits for 🚀 Post approval
Then: Auto-posts to all platforms
"""

from __future__ import annotations

import json
import os
import asyncio
import logging
from pathlib import Path
from flask import Flask, request
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Import our handlers
import sys
sys.path.insert(0, str(Path(__file__).parent))

from telegram_approval_handler import TelegramApprovalBot, ApprovalOrchestrator
from higgsfield_video_generator import HighgsfieldOrchestrator as HighgsfieldGen

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", 8428117168)


@app.route("/telegram/callback", methods=["POST"])
async def handle_telegram_callback():
    """Receive Telegram callback queries (button taps)"""
    try:
        update = request.get_json()

        if "callback_query" not in update:
            return {"ok": True}, 200

        callback_query = update["callback_query"]
        callback_id = callback_query["id"]
        data = callback_query["data"]
        message_id = callback_query["message"]["message_id"]

        action, brief_id = data.split("_", 1)
        logger.info(f"📲 Received callback: {action} for {brief_id}")

        # Load the brief
        brief_path = Path(f"~/.video-factory/briefs/{brief_id}.json").expanduser()
        if not brief_path.exists():
            logger.error(f"Brief not found: {brief_id}")
            return {"ok": True}, 200

        with open(brief_path) as f:
            brief = json.load(f)

        bot = TelegramApprovalBot()

        if action == "approve":
            # Answer the callback with loading message
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
                json={
                    "callback_query_id": callback_id,
                    "text": "🎬 Generating videos... (40 min rendering)",
                },
            )

            # Send notification that video generation started
            await bot.send_performance_update(
                f"🎬 Starting Higgsfield video generation for {brief_id}...\n\n"
                f"Driver: {brief['driver']}\n"
                f"Platforms: {', '.join(brief['platforms'])}\n\n"
                f"Estimated time: 40 minutes"
            )

            # ASYNC: Generate videos in background
            asyncio.create_task(_generate_and_send_videos(brief, bot))

        elif action == "post":
            # Answer the callback
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
                json={
                    "callback_query_id": callback_id,
                    "text": "🚀 Publishing to all platforms...",
                },
            )

            # Auto-post videos
            orchestrator = ApprovalOrchestrator()
            await orchestrator.auto_post_videos(brief_id)

        elif action == "revise":
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
                json={
                    "callback_query_id": callback_id,
                    "text": "❌ Brief sent back for revision",
                },
            )

        elif action == "reschedule":
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
                json={
                    "callback_query_id": callback_id,
                    "text": "🔄 Rescheduled for next week",
                },
            )

        elif action == "custom_time":
            requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
                json={
                    "callback_query_id": callback_id,
                    "text": "⏰ Custom time set",
                },
            )

        return {"ok": True}, 200

    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return {"ok": False, "error": str(e)}, 500


async def _generate_and_send_videos(brief: dict, bot: TelegramApprovalBot):
    """Background task: Generate videos and send to Telegram"""
    brief_id = brief["brief_id"]

    try:
        # Generate videos on Higgsfield
        logger.info(f"🎬 Generating videos for {brief_id}...")
        higgsfield = HighgsfieldGen()
        result = await higgsfield.generate_all_videos(brief)

        if result.get("status") != "complete":
            logger.error(f"Video generation failed: {result}")
            await bot.send_performance_update(
                f"❌ Video generation failed for {brief_id}\n\n{result.get('message', 'Unknown error')}"
            )
            return

        video_paths = result.get("video_paths", [])
        logger.info(f"✅ Generated {len(video_paths)} videos")

        # Send videos to Telegram
        logger.info(f"📹 Sending {len(video_paths)} videos to Telegram...")
        await bot.send_rendered_videos(brief_id, video_paths)

        logger.info(f"✅ Videos sent to Telegram for {brief_id}")

    except Exception as e:
        logger.error(f"❌ Video generation error: {e}")
        await bot.send_performance_update(
            f"❌ Video generation error for {brief_id}: {str(e)[:200]}"
        )


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return {"status": "ok"}, 200


if __name__ == "__main__":
    port = int(os.getenv("WEBHOOK_PORT", 5000))
    logger.info(f"🚀 Starting Telegram webhook server on port {port}")
    logger.info(f"📍 Telegram will POST to: https://your-domain.com/telegram/callback")
    app.run(host="0.0.0.0", port=port, debug=False)
