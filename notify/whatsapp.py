"""Genesis QA - WhatsApp Notifier
================================
Sends test results to WhatsApp via wa-reporter API.

Two modes:
  1. API mode — kirim langsung via wa-reporter (http://localhost:3005/api/send)
  2. File mode — simpan ke file pending kalo API gak tersedia
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# WA Reporter API endpoint
WA_API_URL = os.getenv("WA_API_URL", "http://localhost:3005/api/send")
WA_TARGET = os.getenv("WA_TARGET", "6283134086899")


class WaNotifier:
    """Send test results to WhatsApp.

    Args:
        api_url: wa-reporter endpoint URL (default: http://localhost:3005/api/send)
        target: Nomor tujuan (default: Bang Dadan)
        report_dir: Directory untuk pending notifications
    """

    def __init__(
        self,
        api_url: str = WA_API_URL,
        target: str = WA_TARGET,
        report_dir: str = "",
    ) -> None:
        self.api_url = api_url
        self.target = target
        self.report_dir = report_dir or str(
            Path(__file__).resolve().parent.parent / "reports"
        )
        self._api_available: bool | None = None

    def send(
        self,
        summary: dict[str, Any],
        failures: list[dict[str, Any]],
    ) -> bool:
        """Send test result notification.

        Args:
            summary: Dict dengan total, passed, failed, warnings, duration
            failures: List of failed test details

        Returns:
            True jika terkirim (API atau file)
        """
        message = self._format_message(summary, failures)

        # Coba kirim via API
        if self._check_api():
            try:
                result = self._send_via_api(message)
                if result:
                    logger.info("WA notification sent via API")
                    return True
            except Exception as e:
                logger.warning("WA API failed: %s", e)

        # Fallback: simpan ke file
        return self._save_to_file(message)

    def _check_api(self) -> bool:
        """Check if wa-reporter API is reachable."""
        if self._api_available is not None:
            return self._api_available

        try:
            import urllib.request

            req = urllib.request.Request(
                f"{self.api_url.replace('/api/send', '/health')}",
                method="GET",
            )
            urllib.request.urlopen(req, timeout=2)
            self._api_available = True
        except Exception:
            self._api_available = False

        return self._api_available

    def _send_via_api(self, message: str) -> bool:
        """Send message via wa-reporter API."""
        import urllib.request

        payload = json.dumps({
            "target": self.target,
            "message": message,
        }).encode("utf-8")

        req = urllib.request.Request(
            self.api_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            return result.get("success", False)

    def _format_message(
        self,
        summary: dict[str, Any],
        failures: list[dict[str, Any]],
    ) -> str:
        """Format pesan WhatsApp yang ringkas."""
        lines = [
            f"🧪 GENESIS-QA REPORT",
            f"",
            f"✅ PASS: {summary.get('passed', 0)}",
            f"❌ FAIL: {summary.get('failed', 0)}",
            f"⚠️ WARN: {summary.get('warnings', 0)}",
            f"⏱ {summary.get('duration', 0):.2f}s",
            f"",
        ]

        if failures:
            lines.append("━━━ FAIL DETAIL ━━━")
            for f in failures[:5]:  # Max 5 detail
                name = f.get("name", f.get("endpoint", "?"))
                err = f.get("error", "?")
                lines.append(f"• {name}: {err[:100]}")

            if len(failures) > 5:
                lines.append(f"… dan {len(failures) - 5} failure lainnya")

        lines.append("")
        lines.append(f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}")

        return "\n".join(lines)

    def _save_to_file(self, message: str) -> bool:
        """Save notification to pending file."""
        try:
            Path(self.report_dir).mkdir(parents=True, exist_ok=True)
            filepath = Path(self.report_dir) / "notif_pending.txt"
            timestamp = datetime.now().isoformat()
            entry = f"=== {timestamp} ===\n{message}\n\n"

            with open(filepath, "a") as f:
                f.write(entry)

            logger.info("WA notification saved to %s", filepath)
            return True
        except Exception as e:
            logger.error("Failed to save notification: %s", e)
            return False
