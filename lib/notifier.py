"""
notifier.py
Multi-channel notification dispatcher for OpenMontage (Discord Webhook & Telegram Bot).
"""

import os
import json
import urllib.request
import urllib.parse
from typing import Optional, Dict, Any


class NotificationDispatcher:
    def __init__(
        self,
        discord_webhook_url: Optional[str] = None,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
    ):
        self.discord_webhook_url = discord_webhook_url or os.environ.get("DISCORD_WEBHOOK_URL")
        self.telegram_bot_token = telegram_bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = telegram_chat_id or os.environ.get("TELEGRAM_CHAT_ID")

    def send_discord_notification(
        self,
        title: str,
        description: str,
        video_url: Optional[str] = None,
        thumbnail_url: Optional[str] = None,
        fields: Optional[list[Dict[str, Any]]] = None,
        color: int = 0xFFCC00,  # Gold/Yellow
    ) -> bool:
        if not self.discord_webhook_url:
            print("[NOTIFIER] Discord webhook URL not configured.")
            return False

        embed = {
            "title": title,
            "description": description,
            "color": color,
        }
        if video_url:
            embed["url"] = video_url
        if thumbnail_url:
            embed["thumbnail"] = {"url": thumbnail_url}
        if fields:
            embed["fields"] = fields

        payload = {
            "username": "Wild Mechanics Bot 🐾",
            "avatar_url": "https://raw.githubusercontent.com/calesthio/OpenMontage/main/assets/brand/icon.png",
            "embeds": [embed],
        }

        try:
            req = urllib.request.Request(
                self.discord_webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "OpenMontage/1.0"},
            )
            with urllib.request.urlopen(req) as resp:
                success = 200 <= resp.status < 300
                if success:
                    print("[NOTIFIER] Discord notification sent successfully.")
                return success
        except Exception as e:
            print(f"[NOTIFIER] Discord notification error: {e}")
            return False

    def send_telegram_notification(
        self,
        message: str,
        parse_mode: str = "Markdown",
    ) -> bool:
        if not self.telegram_bot_token or not self.telegram_chat_id:
            print("[NOTIFIER] Telegram bot token or chat ID not configured.")
            return False

        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": self.telegram_chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": False,
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "OpenMontage/1.0"},
            )
            with urllib.request.urlopen(req) as resp:
                success = 200 <= resp.status < 300
                if success:
                    print("[NOTIFIER] Telegram notification sent successfully.")
                return success
        except Exception as e:
            print(f"[NOTIFIER] Telegram notification error: {e}")
            return False

    def notify_video_published(
        self,
        title: str,
        animal: str,
        duration_s: float,
        video_url: Optional[str] = None,
        views_target: str = "10k - 50k",
    ):
        """Dispatches rich notification across both Discord and Telegram."""
        dur_str = f"{int(duration_s // 60)}m {int(duration_s % 60)}s" if duration_s >= 60 else f"{int(duration_s)}s"
        
        # 1. Discord Embed
        discord_fields = [
            {"name": "🐾 Animal Story", "value": animal.title(), "inline": True},
            {"name": "⏱️ Duration", "value": dur_str, "inline": True},
            {"name": "📐 Framing", "value": "4:5 Ghost Blur Fill", "inline": True},
        ]
        if video_url:
            discord_fields.append({"name": "🔗 YouTube Link", "value": f"[Watch Short]({video_url})", "inline": False})
        
        self.send_discord_notification(
            title=f"🎬 New Short Uploaded: {title}",
            description="Autonomous wildlife production completed and published to **Wild Mechanics**!",
            video_url=video_url,
            fields=discord_fields,
            color=0x00E6FF,
        )

        # 2. Telegram Message
        tg_text = (
            f"🎬 *New Short Published!* 🐾\n\n"
            f"*Title:* {title}\n"
            f"*Subject:* {animal.title()}\n"
            f"*Duration:* {dur_str} (4:5 Ghost Blur)\n"
        )
        if video_url:
            tg_text += f"\n👉 [Watch on YouTube]({video_url})"
        
        self.send_telegram_notification(tg_text)
