#!/usr/bin/env python3
"""
Genesis QA — Main Entry Point
===============================
Runs the QA test pipeline against a configured system.

Usage:
    python run.py --system pisantri --mode execute
    python run.py --system pisantri --mode full --output json --notify
    python run.py --system pondokinformatika --mode explore --output html

Modes:
    explore   - Crawl the system and discover endpoints
    generate  - Generate test scenarios from discovered endpoints
    execute   - Run configured test scenarios against the system
    full      - Run all three phases sequentially (default)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

from test import (
    HttpEngine,
    CorsEngine,
    AuthEngine,
    RedirectEngine,
    SecurityEngine,
    DbEngine,
    PerformanceEngine,
    BaseEngine,
    TestResult,
    PerformanceResult,
    ScenarioConfig,
)

# ------------------------------------------------------------------
# Logging setup
# ------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("genesis-qa")

# Try to import YAML support
try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


# ------------------------------------------------------------------
# Config loading
# ------------------------------------------------------------------

def load_config(system_name: str) -> dict[str, Any]:
    """Load system configuration from a YAML file.

    Args:
        system_name: Name of the system (matches filename in config/systems/).

    Returns:
        A dictionary of configuration values.

    Raises:
        FileNotFoundError: If the config file does not exist.
        RuntimeError:      If PyYAML is not installed.
    """
    if yaml is None:
        raise RuntimeError(
            "PyYAML is required to load configuration files. "
            "Install it with: pip install pyyaml"
        )

    config_dir = Path(__file__).resolve().parent / "config" / "systems"
    config_path = config_dir / f"{system_name}.yaml"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}\n"
            f"Available systems: {list(config_dir.glob('*.yaml'))}"
        )

    with open(config_path, "r", encoding="utf-8") as f:
        config: dict[str, Any] = yaml.safe_load(f)

    logger.info("Loaded config for '%s' from %s", system_name, config_path)
    return config


# ------------------------------------------------------------------
# Scanner — mode implementations
# ------------------------------------------------------------------

def run_explore(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Explore mode: crawl and discover endpoints.

    Uses the config's endpoint definitions as a starting point.

    Args:
        config: System configuration dict.

    Returns:
        A list of discovered endpoint descriptions.
    """
    system = config.get("system", {})
    base_url = system.get("base_url", "")
    endpoints = config.get("endpoints", {})
    system_name = system.get("name", "Unknown")

    logger.info("=== EXPLORE MODE ===")
    logger.info("System: %s (%s)", system_name, base_url)
    logger.info("Endpoints defined in config: %d", len(endpoints))

    discovered: list[dict[str, Any]] = []
    engine = HttpEngine(base_url)

    # Test each configured endpoint
    for category, ep_config in endpoints.items():
        if isinstance(ep_config, dict):
            if "path" in ep_config:
                # Single endpoint entry
                discovered.append(
                    _test_endpoint(engine, category, ep_config)
                )
            else:
                # Nested endpoints (list, create, get, etc.)
                for sub_name, sub_config in ep_config.items():
                    discovered.append(
                        _test_endpoint(engine, f"{category}.{sub_name}", sub_config)
                    )

    passed = sum(1 for d in discovered if d.get("status_code", 0) in d.get("expected_status", []))
    logger.info(
        "Explore complete: %d/%d endpoints responding as expected",
        passed,
        len(discovered),
    )

    return discovered


def _test_endpoint(
    engine: HttpEngine,
    name: str,
    ep_config: dict[str, Any],
) -> dict[str, Any]:
    """Test a single endpoint and return its status.

    Args:
        engine:    HTTP engine instance.
        name:      Endpoint name/label.
        ep_config: Dict with path, method, expected_status keys.

    Returns:
        A dict with the probe result.
    """
    path = ep_config.get("path", "/")
    method = ep_config.get("method", "GET")
    expected_status = ep_config.get("expected_status", [200])

    scenario = ScenarioConfig(
        name=f"Explore: {name}",
        method=method,
        endpoint=path,
        expected_status=expected_status,
        follow_redirects=True,
    )

    result = engine.run(scenario)

    return {
        "name": name,
        "path": path,
        "method": method,
        "status_code": result.status_code,
        "expected_status": expected_status,
        "passed": result.passed,
        "timing_ms": result.timing_ms,
        "error": result.error,
    }


def run_generate(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate mode: produce test scenarios from config.

    Args:
        config: System configuration dict.

    Returns:
        A list of scenario descriptions.
    """
    system = config.get("system", {})
    endpoints = config.get("endpoints", {})

    logger.info("=== GENERATE MODE ===")
    logger.info("Generating test scenarios from endpoint definitions...")

    scenarios: list[dict[str, Any]] = []

    for category, ep_config in endpoints.items():
        if isinstance(ep_config, dict):
            if "path" in ep_config:
                scenarios.append(_build_scenario(category, ep_config))
            else:
                for sub_name, sub_config in ep_config.items():
                    scenarios.append(
                        _build_scenario(f"{category}.{sub_name}", sub_config)
                    )

    logger.info("Generated %d scenarios", len(scenarios))
    return scenarios


def _build_scenario(name: str, ep_config: dict[str, Any]) -> dict[str, Any]:
    """Build a scenario dict from endpoint config."""
    return {
        "name": f"Test {name}",
        "method": ep_config.get("method", "GET"),
        "endpoint": ep_config.get("path", "/"),
        "expected_status": ep_config.get("expected_status", [200]),
        "follow_redirects": True,
        "retries": 1,
    }


def run_execute(config: dict[str, Any]) -> list[TestResult]:
    """Execute mode: run test scenarios against the system.

    Instantiates the appropriate engines based on config and runs all
    configured test scenarios.

    Args:
        config: System configuration dict.

    Returns:
        A list of ``TestResult`` instances.
    """
    system = config.get("system", {})
    base_url = system.get("base_url", "")
    system_name = system.get("name", "Unknown")
    auth_config = config.get("auth", {})
    security_config = config.get("security", {})
    db_config = config.get("database", {})
    cors_config = config.get("cors", {})

    logger.info("=== EXECUTE MODE ===")
    logger.info("System: %s (%s)", system_name, base_url)

    results: list[TestResult] = []

    # --- 1. HTTP Engine — test all endpoints ---
    http_engine = HttpEngine(base_url)
    endpoints = config.get("endpoints", {})

    for category, ep_config in endpoints.items():
        if isinstance(ep_config, dict):
            if "path" in ep_config:
                scenario = ScenarioConfig(
                    name=f"{category}",
                    method=ep_config.get("method", "GET"),
                    endpoint=ep_config.get("path", "/"),
                    expected_status=ep_config.get("expected_status", [200]),
                    follow_redirects=True,
                )
                result = http_engine.run(scenario)
                results.append(result)
            else:
                for sub_name, sub_config in ep_config.items():
                    scenario = ScenarioConfig(
                        name=f"{category}.{sub_name}",
                        method=sub_config.get("method", "GET"),
                        endpoint=sub_config.get("path", "/"),
                        expected_status=sub_config.get("expected_status", [200]),
                        follow_redirects=True,
                    )
                    result = http_engine.run(scenario)
                    results.append(result)

    # --- 2. Auth Engine — if credentials are configured ---
    if auth_config:
        credentials: dict[str, dict[str, str]] = {}
        for role, creds in auth_config.get("credentials", {}).items():
            username = creds.get("username", "")
            password = creds.get("password", "")
            # Resolve environment variable references
            if password.startswith("${") and password.endswith("}"):
                env_var = password[2:-1]
                password = os.environ.get(env_var, "")
            credentials[role] = {"username": username, "password": password}

        auth_engine = AuthEngine(base_url, credentials=credentials)
        login_endpoint = auth_config.get("login_endpoint", "/auth/login")

        for role, creds in credentials.items():
            if creds["username"] and creds["password"]:
                result = auth_engine.test_login(
                    username=creds["username"],
                    password=creds["password"],
                    endpoint=login_endpoint,
                )
                results.append(result)

    # --- 3. Security Engine ---
    if security_config.get("test_headers", True):
        sec_engine = SecurityEngine(base_url)
        result = sec_engine.test_security_headers()
        results.append(result)

    if security_config.get("test_disclosure", True):
        sec_engine = SecurityEngine(base_url)
        result = sec_engine.test_sensitive_info()
        results.append(result)

    if security_config.get("test_directory_listing", False):
        sec_engine = SecurityEngine(base_url)
        result = sec_engine.test_directory_listing()
        results.append(result)

    # --- 4. Redirect Engine ---
    if security_config.get("test_redirects", True):
        redirect_engine = RedirectEngine(base_url)
        # Test the base URL for redirect behavior
        result = redirect_engine.test_redirect_chain(
            endpoint="/",
            method="GET",
            expected_final_status=[200, 301, 302],
        )
        results.append(result)

    # --- 5. CORS Engine ---
    if security_config.get("test_cors", False) and cors_config.get("allowed_origins"):
        cors_engine = CorsEngine(base_url)
        for endpoint_path in ["/", "/api"]:
            result = cors_engine.test_cors(endpoint=endpoint_path)
            results.append(result)

    # --- 6. DB Engine (optional) ---
    if db_config.get("enabled", False):
        conn_string = db_config.get("connection_string", "")
        if conn_string.startswith("${") and conn_string.endswith("}"):
            conn_string = os.environ.get(conn_string[2:-1], "")

        if conn_string:
            schema_tables = db_config.get("schema_tables", [])
            db_engine = DbEngine(conn_string, schema_tables=schema_tables)
            result = db_engine.test_connection()
            results.append(result)
            if schema_tables:
                result = db_engine.test_schema_validation()
                results.append(result)

    logger.info("Execute complete: %d tests run", len(results))
    return results


def run_performance(config: dict[str, Any]) -> list[PerformanceResult]:
    """Performance mode: run load / performance tests against endpoints.

    Reads ``performance`` section from the config::

        performance:
          enabled: true
          tests:
            - name: "Homepage response time"
              endpoint: /
              method: GET
              type: response_time         # or concurrent / stress / endurance
            - name: "Concurrent API load"
              endpoint: /api/users
              method: GET
              type: concurrent
              num_requests: 20
              concurrency: 5
            - name: "Stress test"
              endpoint: /api/search
              method: GET
              type: stress
              num_requests: 50
              ramp_up: 5
            - name: "Endurance soak"
              endpoint: /health
              method: GET
              type: endurance
              duration_sec: 30
              interval_ms: 1000

    Args:
        config: System configuration dict.

    Returns:
        A list of ``PerformanceResult`` instances.
    """
    system = config.get("system", {})
    base_url = system.get("base_url", "")
    perf_config = config.get("performance", {})

    if not perf_config.get("enabled", False):
        logger.info("Performance testing is disabled in config.")
        return []

    logger.info("=== PERFORMANCE MODE ===")
    logger.info("System: %s (%s)", system.get("name", "Unknown"), base_url)

    engine = PerformanceEngine(base_url)
    test_defs = perf_config.get("tests", [])
    results: list[PerformanceResult] = []

    for test_def in test_defs:
        test_type = test_def.get("type", "response_time")
        endpoint = test_def.get("endpoint", "/")
        method = test_def.get("method", "GET")
        threshold_ms = float(test_def.get("threshold_ms", 2000))
        name = test_def.get("name", f"{method} {endpoint}")

        logger.info("[PERF] Starting '%s' (%s) …", name, test_type)

        if test_type == "response_time":
            result = engine.test_response_time(
                endpoint=endpoint,
                method=method,
                headers=test_def.get("headers"),
                body=test_def.get("body"),
                threshold_ms=threshold_ms,
            )
        elif test_type == "concurrent":
            result = engine.test_concurrent(
                endpoint=endpoint,
                method=method,
                headers=test_def.get("headers"),
                body=test_def.get("body"),
                num_requests=int(test_def.get("num_requests", 10)),
                concurrency=int(test_def.get("concurrency", 5)),
                threshold_ms=threshold_ms,
            )
        elif test_type == "stress":
            result = engine.test_stress(
                endpoint=endpoint,
                method=method,
                headers=test_def.get("headers"),
                body=test_def.get("body"),
                num_requests=int(test_def.get("num_requests", 50)),
                ramp_up=int(test_def.get("ramp_up", 5)),
                threshold_ms=threshold_ms,
            )
        elif test_type == "endurance":
            result = engine.test_endurance(
                endpoint=endpoint,
                method=method,
                headers=test_def.get("headers"),
                body=test_def.get("body"),
                duration_sec=int(test_def.get("duration_sec", 30)),
                interval_ms=int(test_def.get("interval_ms", 1000)),
                threshold_ms=threshold_ms,
            )
        else:
            logger.warning("Unknown performance test type '%s' — skipping", test_type)
            continue

        logger.info(
            "[PERF] '%s' done — avg=%.0fms  p95=%.0fms  "
            "throughput=%.1f req/s  failed=%d/%d",
            name,
            result.avg_ms,
            result.p95_ms,
            result.throughput_req_per_sec,
            result.failed_requests,
            result.total_requests,
        )
        results.append(result)

    return results


# ------------------------------------------------------------------
# Reporting
# ------------------------------------------------------------------

def run_report(
    results: list[TestResult],
    config: dict[str, Any],
    duration: float,
    output_format: str = "console",
) -> list[str]:
    """Generate reports in the specified format(s).

    Args:
        results:       List of test results.
        config:        System configuration.
        duration:      Total execution time in seconds.
        output_format: One of ``console``, ``json``, ``html``, or
                       ``all`` (generates all formats).

    Returns:
        A list of report output paths (empty for console).
    """
    system = config.get("system", {})
    system_info = {
        "name": system.get("name", "Unknown"),
        "base_url": system.get("base_url", ""),
        "type": system.get("type", "api"),
    }

    outputs: list[str] = []
    formats = ["console", "json", "html"] if output_format == "all" else [output_format]

    for fmt in formats:
        if fmt == "console":
            from report.console_reporter import ConsoleReporter
            reporter = ConsoleReporter()
            reporter.report(results, system_name=system_info["name"], duration=duration)
            outputs.append("console")

        elif fmt == "json":
            from report.json_reporter import JsonReporter
            reporter = JsonReporter()
            path = reporter.report(results, system=system_info, duration=duration)
            outputs.append(path)
            logger.info("JSON report: %s", path)

        elif fmt == "html":
            from report.html_reporter import HtmlReporter
            reporter = HtmlReporter()
            path = reporter.report(results, system=system_info, duration=duration)
            outputs.append(path)
            logger.info("HTML report: %s", path)

    return outputs


def run_notify(
    results: list[TestResult],
    config: dict[str, Any],
    duration: float,
) -> str:
    """Send notification via WhatsApp notifier.

    Args:
        results: List of test results.
        config:  System configuration.
        duration: Total execution time in seconds.

    Returns:
        Notification status string.
    """
    system = config.get("system", {})
    system_name = system.get("name", "Unknown")

    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    warnings = sum(1 for r in results if not r.passed and "warning" in r.error.lower())
    failures = [r for r in results if not r.passed]

    summary = {
        "total": total,
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "duration": round(duration, 2),
    }

    from notify.whatsapp import WaNotifier
    notifier = WaNotifier()
    result = notifier.send(
        summary=summary,
        failures=failures,
        system_name=system_name,
    )
    logger.info("Notification: %s", result)
    return result


# ------------------------------------------------------------------
# Main CLI
# ------------------------------------------------------------------

def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Genesis QA — Automated Quality Assurance Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py --system pisantri --mode execute
  python run.py --system pisantri --mode full --output json --notify
  python run.py --system pondokinformatika --mode explore
        """,
    )

    parser.add_argument(
        "--system",
        required=True,
        help="System name (matches config file in config/systems/). "
        "Example: pisantri, pondokinformatika",
    )

    parser.add_argument(
        "--mode",
        choices=["explore", "generate", "execute", "full", "performance"],
        default="full",
        help="Pipeline mode (default: full). 'performance' runs load/performance tests",
    )

    parser.add_argument(
        "--output",
        choices=["console", "json", "html", "all"],
        default="console",
        help="Report output format (default: console)",
    )

    parser.add_argument(
        "--notify",
        action="store_true",
        default=False,
        help="Send notification via WhatsApp notifier after run",
    )

    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:]).

    Returns:
        Exit code (0 = success, 1 = failure).
    """
    args = parse_args(argv)

    start = time.monotonic()

    try:
        # Load configuration
        config = load_config(args.system)
    except (FileNotFoundError, RuntimeError) as exc:
        logger.error("Configuration error: %s", exc)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    all_results: list[TestResult] = []
    all_perf_results: list[PerformanceResult] = []

    # --- Run pipeline ---
    if args.mode in ("explore", "full"):
        discovered = run_explore(config)
        # Convert explore results to TestResult
        for d in discovered:
            all_results.append(
                TestResult(
                    name=f"Explore: {d['name']}",
                    passed=d.get("passed", False),
                    status_code=d.get("status_code", 0),
                    expected_status=d.get("expected_status", [200]),
                    endpoint=d.get("path", ""),
                    method=d.get("method", "GET"),
                    timing_ms=d.get("timing_ms", 0.0),
                    error=d.get("error", ""),
                )
            )

    if args.mode in ("generate", "full"):
        scenarios = run_generate(config)
        logger.info("Generated %d scenarios for testing", len(scenarios))

    if args.mode in ("execute", "full") or (args.mode == "full" and scenarios):
        results = run_execute(config)
        all_results.extend(results)

    if args.mode == "performance":
        all_perf_results = run_performance(config)

    duration = time.monotonic() - start

    # --- Performance mode summary ---
    if all_perf_results:
        print("─" * 60)
        print(f"  System:    {config.get('system', {}).get('name', args.system)}")
        print(f"  Mode:      {args.mode}")
        print(f"  Tests:     {len(all_perf_results)} performance test(s)")
        for pr in all_perf_results:
            status = "PASS" if pr.failed_requests == 0 and pr.avg_ms <= 2000 else "WARN"
            print(
                f"    [{status}] {pr.method} {pr.endpoint}  "
                f"avg={pr.avg_ms:.0f}ms  p95={pr.p95_ms:.0f}ms  "
                f"throughput={pr.throughput_req_per_sec:.1f} req/s  "
                f"failed={pr.failed_requests}/{pr.total_requests}"
            )
        print(f"  Duration:  {duration:.2f}s")
        print("─" * 60)
        return 0

    # --- No tests? Warn ---
    if not all_results:
        logger.warning("No tests were executed — nothing to report.")
        return 0

    # --- Report ---
    report_paths = run_report(all_results, config, duration, args.output)

    # --- Notify ---
    if args.notify:
        notify_result = run_notify(all_results, config, duration)
        logger.info("Notification: %s", notify_result)

    # --- Summary to stdout ---
    passed = sum(1 for r in all_results if r.passed)
    failed = len(all_results) - passed
    print("─" * 60)
    print(f"  System:    {config.get('system', {}).get('name', args.system)}")
    print(f"  Mode:      {args.mode}")
    print(f"  Tests:     {len(all_results)} total, {passed} passed, {failed} failed")
    print(f"  Duration:  {duration:.2f}s")
    if report_paths and report_paths != ["console"]:
        print(f"  Reports:   {', '.join(report_paths)}")
    print("─" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
