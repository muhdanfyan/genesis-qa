"""
Genesis QA - Scan Module
=========================
Package initializer for the scan subpackage, which provides web crawling,
endpoint discovery, and security scanning functionality.

Exports:
    Crawler        - Async web crawler that discovers reachable pages
    EndpointScanner - Scans a web application for hidden or exposed endpoints
    SecurityScanner - Runs security checks (headers, injection, CSRF, etc.)
"""

from scan.crawler import Crawler
from scan.endpoint_scanner import EndpointScanner
from scan.security_scanner import SecurityScanner

__all__ = [
    "Crawler",
    "EndpointScanner",
    "SecurityScanner",
]

__version__ = "0.1.0"
