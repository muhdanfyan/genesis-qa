"""
Genesis QA - Console Reporter
==============================
Outputs test results as a formatted table to the terminal with
color-coded PASS/FAIL/WARNING indicators.

Usage:
    reporter = ConsoleReporter()
    reporter.report(results)
"""

from __future__ import annotations

import logging
import sys
from typing import Any, Optional

from test.base_engine import TestResult

logger = logging.getLogger(__name__)


class ConsoleReporter:
    """Formats and writes test results to the terminal.

    Produces a table with columns: No, Name, Endpoint, Method,
    Status, Timing, Error. Uses ANSI color codes:
    - Green for PASS
    - Red for FAIL
    - Yellow for WARNING
    """

    # ANSI color codes
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    TABLE_WIDTH = 120

    def __init__(self, output_stream: Any = None) -> None:
        """Initialize the console reporter.

        Args:
            output_stream: Stream to write to (default: sys.stdout).
        """
        self.stream = output_stream or sys.stdout
        self._use_colors = self._supports_color()

    def report(
        self,
        results: list[TestResult],
        system_name: str = "",
        duration: float = 0.0,
    ) -> None:
        """Write a formatted test report to the console.

        Args:
            results:     List of test results to display.
            system_name: Name of the system under test.
            duration:    Total execution duration in seconds.
        """
        self._print_header(system_name)
        self._print_table(results)
        self._print_summary(results, duration)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _supports_color(self) -> bool:
        """Check if the output stream supports ANSI color codes."""
        if not hasattr(self.stream, "isatty"):
            return False
        try:
            return self.stream.isatty()
        except (ValueError, OSError):
            return False

    def _colorize(self, color: str, text: str) -> str:
        """Wrap text in ANSI color codes if supported."""
        if self._use_colors:
            return f"{color}{text}{self.RESET}"
        return text

    def _status_str(self, result: TestResult) -> str:
        """Return a colorized status string."""
        if result.passed:
            return self._colorize(self.GREEN, "PASS")
        elif "warning" in result.error.lower():
            return self._colorize(self.YELLOW, "WARN")
        else:
            return self._colorize(self.RED, "FAIL")

    def _print_header(self, system_name: str) -> None:
        """Print the report header."""
        title = f" Genesis QA Test Report "
        if system_name:
            title += f"— {system_name} "
        line = "━" * self.TABLE_WIDTH

        self._writeline("")
        self._writeline(self._colorize(self.BOLD, line))
        self._writeline(self._colorize(self.CYAN + self.BOLD, title))
        self._writeline(self._colorize(self.BOLD, line))
        self._writeline("")

    def _print_table(self, results: list[TestResult]) -> None:
        """Print the results table."""
        if not results:
            self._writeline(self._colorize(self.YELLOW, "  No test results to display."))
            self._writeline("")
            return

        # Column widths
        no_w = 4
        name_w = 35
        endpoint_w = 55
        method_w = 8
        status_w = 8
        timing_w = 10

        # Header
        header = (
            f"{'No':>{no_w}}  "
            f"{'Name':<{name_w}}  "
            f"{'Endpoint':<{endpoint_w}}  "
            f"{'Method':<{method_w}}  "
            f"{'Status':<{status_w}}  "
            f"{'Timing':<{timing_w}}  "
            f"{'Error'}"
        )
        separator = "─" * self.TABLE_WIDTH
        self._writeline(self._colorize(self.BOLD, header))
        self._writeline(separator)

        # Rows
        for i, result in enumerate(results, start=1):
            name = self._truncate(result.name, name_w)
            endpoint = self._truncate(result.endpoint, endpoint_w)
            method = result.method.ljust(method_w)
            status = self._status_str(result)
            timing = f"{result.timing_ms:.0f}ms".rjust(timing_w)
            error = self._truncate(result.error, 30) if result.error else ""

            row = (
                f"{i:>{no_w}}  "
                f"{name:<{name_w}}  "
                f"{endpoint:<{endpoint_w}}  "
                f"{method:<{method_w}}  "
                f"{str(status):<{status_w}}  "
                f"{timing:<{timing_w}}  "
                f"{error}"
            )
            self._writeline(row)

        self._writeline(separator)
        self._writeline("")

    def _print_summary(self, results: list[TestResult], duration: float) -> None:
        """Print a summary section below the table."""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        warnings = sum(
            1 for r in results if not r.passed and "warning" in r.error.lower()
        )

        self._writeline(self._colorize(self.BOLD, "  Summary"))
        self._writeline(f"    Total:      {total}")
        self._writeline(
            f"    Passed:     {self._colorize(self.GREEN, str(passed))}"
        )
        if failed:
            self._writeline(
                f"    Failed:     {self._colorize(self.RED, str(failed))}"
            )
        if warnings:
            self._writeline(
                f"    Warnings:   {self._colorize(self.YELLOW, str(warnings))}"
            )
        self._writeline(f"    Duration:   {duration:.2f}s")
        self._writeline("")

    def _writeline(self, text: str = "") -> None:
        """Write a line to the output stream."""
        try:
            print(text, file=self.stream)
        except OSError:
            pass

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """Truncate text with ellipsis if it exceeds *max_len*."""
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."
