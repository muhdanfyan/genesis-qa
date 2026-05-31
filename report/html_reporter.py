"""
Genesis QA - HTML Reporter
============================
Outputs test results to a self-contained HTML file with inline CSS.
Includes summary cards, a filterable table, and expandable detail rows.

Usage:
    reporter = HtmlReporter(output_dir="./report")
    reporter.report(results, system={"name": "Pisantri API"})
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from test.base_engine import TestResult

logger = logging.getLogger(__name__)


class HtmlReporter:
    """Generates a self-contained HTML report from test results.

    Features:
    - Summary cards: total, passed (green), failed (red), warnings (yellow).
    - Table with filter-by-status buttons.
    - Expandable detail sections for each test.
    - Responsive layout with inline CSS.
    """

    PAGE_TITLE = "Genesis QA Test Report"

    def __init__(self, output_dir: str = "./report") -> None:
        """Initialize the HTML reporter.

        Args:
            output_dir: Directory where HTML reports will be written.
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
        """Generate and write the HTML report.

        Args:
            results:  List of test results.
            system:   Dict with keys ``name``, ``base_url``, ``type``.
            duration: Total execution duration in seconds.
            filename: Output filename (auto-generated if not provided).

        Returns:
            The absolute path to the written HTML file.
        """
        system = system or {}
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        warnings = sum(
            1 for r in results if not r.passed and "warning" in r.error.lower()
        )

        html = self._build_html(
            results=results,
            system=system,
            total=total,
            passed=passed,
            failed=failed,
            warnings=warnings,
            duration=duration,
        )

        if not filename:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            system_slug = system.get("name", "unknown").lower().replace(" ", "_")
            filename = f"report_{system_slug}_{timestamp}.html"

        out_path = self.output_dir / filename
        self.output_dir.mkdir(parents=True, exist_ok=True)

        try:
            out_path.write_text(html, encoding="utf-8")
            logger.info("HTML report written to %s", out_path.resolve())
        except OSError as exc:
            logger.error("Failed to write HTML report: %s", exc)
            raise

        return str(out_path.resolve())

    # ------------------------------------------------------------------
    # HTML builder
    # ------------------------------------------------------------------

    def _build_html(
        self,
        results: list[TestResult],
        system: dict[str, str],
        total: int,
        passed: int,
        failed: int,
        warnings: int,
        duration: float,
    ) -> str:
        """Build the complete HTML document."""

        pass_rate = round((passed / total * 100) if total > 0 else 0, 1)
        system_name = system.get("name", "Unknown System")
        system_url = system.get("base_url", "")

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{self.PAGE_TITLE} — {system_name}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif;
    background: #f5f7fa; color: #1a1a2e; line-height: 1.6; padding: 20px;
}}
.header {{ max-width: 1200px; margin: 0 auto 24px; }}
.header h1 {{ font-size: 1.8em; color: #16213e; }}
.header .subtitle {{ color: #666; font-size: 0.95em; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px; max-width: 1200px; margin: 0 auto 24px; }}
.card {{ background: #fff; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    text-align: center; }}
.card .number {{ font-size: 2.2em; font-weight: 700; }}
.card .label {{ font-size: 0.85em; color: #666; margin-top: 4px; }}
.card.green .number {{ color: #16a34a; }}
.card.red .number {{ color: #dc2626; }}
.card.yellow .number {{ color: #ca8a04; }}
.card.blue .number {{ color: #2563eb; }}
.card.gray .number {{ color: #6b7280; }}
.filters {{ max-width: 1200px; margin: 0 auto 16px; display: flex; gap: 8px; flex-wrap: wrap; }}
.filter-btn {{ padding: 8px 16px; border: 1px solid #d1d5db; border-radius: 6px;
    background: #fff; cursor: pointer; font-size: 0.85em; transition: all 0.15s; }}
.filter-btn:hover {{ background: #f3f4f6; }}
.filter-btn.active {{ background: #2563eb; color: #fff; border-color: #2563eb; }}
.table-container {{ max-width: 1200px; margin: 0 auto; background: #fff;
    border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.85em; }}
thead {{ background: #f8fafc; }}
th {{ padding: 12px 16px; text-align: left; font-weight: 600; color: #475569;
    border-bottom: 2px solid #e2e8f0; white-space: nowrap; }}
td {{ padding: 10px 16px; border-bottom: 1px solid #f1f5f9; }}
tr:hover {{ background: #f8fafc; }}
tr.failed {{ background: #fef2f2; }}
tr.warning {{ background: #fefce8; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 10px;
    font-size: 0.8em; font-weight: 600; }}
.badge-pass {{ background: #dcfce7; color: #166534; }}
.badge-fail {{ background: #fecaca; color: #991b1b; }}
.badge-warn {{ background: #fef9c3; color: #854d0e; }}
.status-header {{ display: flex; align-items: center; gap: 4px; cursor: pointer;
    color: #2563eb; font-size: 0.85em; }}
.detail {{ display: none; padding: 16px; background: #f8fafc; border-radius: 8px;
    margin: 8px 0; font-family: 'SFMono-Regular', Consolas, monospace; font-size: 0.8em;
    white-space: pre-wrap; word-break: break-all; }}
.detail.open {{ display: block; }}
.preview {{ max-height: 100px; overflow-y: auto; background: #f1f5f9;
    padding: 8px; border-radius: 4px; font-family: monospace; font-size: 0.8em;
    white-space: pre-wrap; word-break: break-all; }}
.timing {{ white-space: nowrap; }}
.footer {{ max-width: 1200px; margin: 24px auto; text-align: center; color: #94a3b8;
    font-size: 0.8em; }}
.success-rate {{ display: inline-block; width: 100px; height: 6px; background: #e2e8f0;
    border-radius: 3px; vertical-align: middle; margin-left: 8px; }}
.success-rate-fill {{ height: 100%; border-radius: 3px;
    background: linear-gradient(90deg, #16a34a, #22c55e); }}
@media (max-width: 768px) {{
    .cards {{ grid-template-columns: repeat(2, 1fr); }}
    th, td {{ padding: 8px 10px; font-size: 0.8em; }}
}}
</style>
</head>
<body>

<div class="header">
    <h1>🔍 {self.PAGE_TITLE}</h1>
    <div class="subtitle">
        <strong>{system_name}</strong>
        {f' — <a href="{system_url}" target="_blank">{system_url}</a>' if system_url else ''}
        &middot; {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
    </div>
</div>

<div class="cards">
    <div class="card blue">
        <div class="number">{total}</div>
        <div class="label">Total Tests</div>
    </div>
    <div class="card green">
        <div class="number">{passed}</div>
        <div class="label">Passed</div>
    </div>
    <div class="card red">
        <div class="number">{failed}</div>
        <div class="label">Failed</div>
    </div>
    <div class="card yellow">
        <div class="number">{warnings}</div>
        <div class="label">Warnings</div>
    </div>
    <div class="card gray">
        <div class="number">{duration:.2f}s</div>
        <div class="label">Duration</div>
    </div>
    <div class="card gray">
        <div class="number">{pass_rate}%<span class="success-rate"><span class="success-rate-fill" style="width:{pass_rate}%"></span></span></div>
        <div class="label">Pass Rate</div>
    </div>
</div>

<div class="filters">
    <button class="filter-btn active" onclick="filterTable('all')">All</button>
    <button class="filter-btn" onclick="filterTable('pass')">Passed</button>
    <button class="filter-btn" onclick="filterTable('fail')">Failed</button>
    <button class="filter-btn" onclick="filterTable('warn')">Warnings</button>
</div>

<div class="table-container">
<table id="results-table">
<thead>
<tr>
    <th>#</th>
    <th>Name</th>
    <th>Endpoint</th>
    <th>Method</th>
    <th>Status</th>
    <th>Timing</th>
    <th>Details</th>
</tr>
</thead>
<tbody>
{self._build_rows(results)}
</tbody>
</table>
</div>

<div class="footer">
    Generated by Genesis QA &middot; Report timestamp: {datetime.now(timezone.utc).isoformat()}
</div>

<script>
function filterTable(filter) {{
    const rows = document.querySelectorAll('#results-table tbody tr');
    const btns = document.querySelectorAll('.filter-btn');
    btns.forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    rows.forEach(row => {{
        if (filter === 'all') {{ row.style.display = ''; }}
        else if (filter === 'pass' && !row.classList.contains('failed') && !row.classList.contains('warning')) {{
            row.style.display = '';
        }} else if (filter === 'fail' && row.classList.contains('failed')) {{
            row.style.display = '';
        }} else if (filter === 'warn' && row.classList.contains('warning')) {{
            row.style.display = '';
        }} else {{
            row.style.display = 'none';
        }}
    }});
}}
function toggleDetail(id) {{
    const el = document.getElementById(id);
    el.classList.toggle('open');
}}
</script>
</body>
</html>"""

    def _build_rows(self, results: list[TestResult]) -> str:
        """Build the HTML table rows from test results."""
        rows = []
        for i, r in enumerate(results, start=1):
            row_class = ""
            badge_class = "badge-pass"
            badge_text = "PASS"

            if not r.passed:
                if "warning" in r.error.lower():
                    row_class = ' class="warning"'
                    badge_class = "badge-warn"
                    badge_text = "WARN"
                else:
                    row_class = ' class="failed"'
                    badge_class = "badge-fail"
                    badge_text = "FAIL"

            detail_id = f"detail-{i}"
            endpoint_display = r.endpoint[:60] + "..." if len(r.endpoint) > 60 else r.endpoint
            preview = (r.response_body_preview[:300].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                       if r.response_body_preview else "")
            error_display = r.error.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") if r.error else ""

            # Build details content
            detail_lines = []
            if error_display:
                detail_lines.append(f"<strong>Error:</strong> {error_display}")
            if preview:
                detail_lines.append(f"<strong>Response Preview:</strong><div class='preview'>{preview}</div>")
            if r.details:
                import json
                detail_lines.append(f"<strong>Details:</strong><br>{json.dumps(r.details, indent=2, default=str)}")

            detail_content = "<br>".join(detail_lines) if detail_lines else "No additional details."

            rows.append(f"""<tr{row_class}>
    <td>{i}</td>
    <td>{r.name[:40] + '...' if len(r.name) > 40 else r.name}</td>
    <td title="{r.endpoint}">{endpoint_display}</td>
    <td>{r.method}</td>
    <td><span class="badge {badge_class}">{badge_text}</span></td>
    <td class="timing">{r.timing_ms:.0f}ms</td>
    <td><span class="status-header" onclick="toggleDetail('{detail_id}')">&#9654; Expand</span></td>
</tr>
<tr id="{detail_id}" class="detail-row">
    <td colspan="7"><div class="detail open">{detail_content}</div></td>
</tr>""")

        return "\n".join(rows)
