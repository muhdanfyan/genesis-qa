"""
Genesis QA - WhatsApp Notifier
================================
Formats test results into a concise WhatsApp message. If a real WhatsApp
API is not available, the message is saved to a local file.

Usage:
    notifier = WaNotifier()
    notifier.send(summary, failures)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from test.base_engine import TestResult

logger = logging.getLogger(__name__)


class WaNotifier:
    """Formats and dispatches test results as a WhatsApp-compatible message.

    The message is designed to be compact — no markdown, no tables,
    just a clean summary followed by a bullet list of failures.

    Attributes:
        output_dir: Directory where notification files are written when
                    no real API endpoint is configured.
    """

    MAX_FAILURES_IN_MESSAGE: int = 10

    def __init__(
        self,
        output_dir: str = "./notify",
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        """Initialize the notifier.

        Args:
            output_dir: Directory for fallback notification files.
            api_url:    Optional WhatsApp Business API endpoint.
            api_key:    Optional API key for the WhatsApp service.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.api_url = api_url or os.environ.get("WA_API_URL", "")
        self.api_key = api_key or os.environ.get("WA_API_KEY", "")

    def send(
        self,
        summary: dict[str, Any],
        failures: list[TestResult],
        *,
        system_name: str = "Unknown",
        to_number: Optional[str] = None,
    ) -> str:
        """Format and send/dispatch a WhatsApp notification.

        Args:
            summary:     Dict with keys: total, passed, failed, warnings, duration.
            failures:    List of failed ``TestResult`` objects.
            system_name: Name of the system that was tested.
            to_number:   Recipient phone number (optional).

        Returns:
            A string indicating the outcome (file path or API response note).
        """
        message = self._format_message(summary, failures, system_name)

        if self.api_url and self.api_key:
            return self._send_via_api(message, to_number)
        else:
            return self._save_to_file(message)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _format_message(
        self,
        summary: dict[str, Any],
        failures: list[TestResult],
        system_name: str,
    ) -> str:
        """Build a concise WhatsApp message from test results.

        The message is plain text (no markdown) as required by WhatsApp.
        """
        total = summary.get("total", 0)
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        warnings = summary.get("warnings", 0)
        duration = summary.get("duration", 0.0)

        lines: list[str] = []

        # Header
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines.append(f"GENESIS QA REPORT")
        lines.append(f"System: {system_name}")
        lines.append(f"Time:   {timestamp}")
        lines.append("")

        # Summary
        lines.append(f"Results: {total} total | PASS {passed} | FAIL {failed} | WARN {warnings}")
        lines.append(f"Duration: {duration:.2f}s")
        pass_rate = round((passed / total * 100), 1) if total > 0 else 0
        lines.append(f"Pass rate: {pass_rate}%")
        lines.append("")

        # Status icon
        if failed > 0:
            lines.append("STATUS: FAILED - Some tests did not pass")
        elif warnings > 0:
            lines.append("STATUS: PASSED WITH WARNINGS")
        else:
            lines.append("STATUS: ALL PASSED")
        lines.append("")

        # Failure list
        if failures:
            lines.append("FAILURES:")
            for i, failure in enumerate(failures[: self.MAX_FAILURES_IN_MESSAGE], start=1):
                error_snippet = (failure.error[:100] + "...") if len(failure.error) > 100 else failure.error
                lines.append(f"{i}. {failure.name}")
                lines.append(f"   {failure.method} {failure.endpoint}")
                lines.append(f"   Status: {failure.status_code} | Error: {error_snippet}")
                lines.append("")

            if len(failures) > self.MAX_FAILURES_IN_MESSAGE:
                remaining = len(failures) - self.MAX_FAILURES_IN_MESSAGE
                lines.append(f"... and {remaining} more failure(s)")
                lines.append("")

        # Footer
        lines.append("Full report: Check the output directory for JSON/HTML reports.")

        return "\n".join(lines)

    def _save_to_file(self, message: str) -> str:
        """Save the notification message to a local file.

        Returns:
            The path to the saved file.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"wa_notification_{timestamp}.txt"
        out_path = self.output_dir / filename

        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            out_path.write_text(message, encoding="utf-8")
            logger.info("WhatsApp notification saved to %s", out_path.resolve())
        except OSError as exc:
            logger.error("Failed to save notification: %s", exc)
            raise

        return str(out_path.resolve())

    def _send_via_api(self, message: str, to_number: Optional[str] = None) -> str:
        """Send the message via a WhatsApp Business API.

        This is a placeholder for when a real API endpoint is configured.
        Currently just logs and returns a note.

        Args:
            message:    The formatted message text.
            to_number:  Recipient phone number.

        Returns:
            A status string.
        """
        logger.info(
            "WhatsApp API call would be made to %s (to=%s) — message length: %d chars",
            self.api_url,
            to_number or "default",
            len(message),
        )

        # Placeholder: in production this would use requests.post()
        # import requests
        # resp = requests.post(
        #     self.api_url,
        #     json={"to": to_number, "text": message},
        #     headers={"Authorization": f"Bearer {self.api_key}"},
        # )

        # For now, save to file as fallback
        saved_path = self._save_to_file(message)
        return f"API call simulated — message saved to {saved_path}"
