"""
Genesis QA - JSON Reporter
============================
Outputs test results to a JSON file with a structured summary and
individual result details.

Usage:
    reporter = JsonReporter(output_dir="./report")
    reporter.report(results, system={"name": "Pisantri API"})
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from test.base_engine import TestResult

logger = logging.getLogger(__name__)


class JsonReporter:
    """Serializes test results to a JSON file.

    Output structure::

        {
            "summary": {
                "total": ...,
                "passed": ...,
                "failed": ...,
                "warnings": ...,
                "duration": ...,
                "timestamp": "..."
            },
            "results": [ ... ],
            "system": {
                "name": "...",
                "base_url": "...",
                "type": "..."
            }
        }
    """

    def __init__(self, output_dir: str = "./report") -> None:
        """Initialize the JSON reporter.

        Args:
            output_dir: Directory where JSON reports will be written.
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def report(
        self,
        results: list[TestResult],
        system: Optional[dict[str, str]] = None,
        duration: float = 0.0,
        filename: Optional[str] = None,
    ) -> str:
        """Write test results to a JSON file.

        Args:
            results:  List of test results.
            system:   Dict with keys ``name``, ``base_url``, ``type``.
            duration: Total execution duration in seconds.
            filename: Output filename (auto-generated if not provided).

        Returns:
            The absolute path to the written JSON file.
        """
        system = system or {}
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        warnings = sum(
            1 for r in results if not r.passed and "warning" in r.error.lower()
        )

        report_data: dict[str, Any] = {
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "warnings": warnings,
                "duration": round(duration, 3),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "results": [self._serialize_result(r) for r in results],
            "system": {
                "name": system.get("name", "unknown"),
                "base_url": system.get("base_url", ""),
                "type": system.get("type", "api"),
            },
        }

        if not filename:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            system_slug = system.get("name", "unknown").lower().replace(" ", "_")
            filename = f"report_{system_slug}_{timestamp}.json"

        out_path = self.output_dir / filename
        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            out_path.write_text(
                json.dumps(report_data, indent=2, default=str),
                encoding="utf-8",
            )
            logger.info("JSON report written to %s", out_path.resolve())
        except OSError as exc:
            logger.error("Failed to write JSON report: %s", exc)
            raise

        return str(out_path.resolve())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_result(result: TestResult) -> dict[str, Any]:
        """Convert a ``TestResult`` to a JSON-safe dictionary."""
        return {
            "name": result.name,
            "passed": result.passed,
            "status_code": result.status_code,
            "expected_status": result.expected_status,
            "endpoint": result.endpoint,
            "method": result.method,
            "timing_ms": result.timing_ms,
            "error": result.error,
            "response_body_preview": result.response_body_preview,
            "timestamp": result.timestamp,
            "details": result.details,
        }
