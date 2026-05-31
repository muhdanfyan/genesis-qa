#!/usr/bin/env python3
"""
Genesis-QA Web Server

Server HTTP mini untuk serve dashboard HTML dan API endpoint
yang membaca reports/latest.json.

Usage:
    python3 server.py                  # Default port 8000
    python3 server.py --port 8080      # Custom port
    python3 server.py --reports /path/to/reports  # Custom report dir

Endpoints:
    GET /                     → dashboard.html
    GET /api/latest-report    → reports/latest.json (sebagai JSON)
    GET /api/health           → health check
"""

import argparse
import json
import os
import sys
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path


class GenesisQAHandler(SimpleHTTPRequestHandler):
    """Custom handler with API endpoints for genesis-qa dashboard."""

    def __init__(self, *args, **kwargs):
        self.reports_dir = kwargs.pop('reports_dir',
                                       Path(__file__).resolve().parent.parent / 'reports')
        # Store reports_dir as class attribute for access in methods
        GenesisQAHandler._reports_dir = self.reports_dir
        super().__init__(*args, directory=str(Path(__file__).resolve().parent), **kwargs)

    def do_GET(self):
        path = self.path.rstrip('/') or '/'

        if path == '/api/latest-report':
            self._serve_latest_report()
        elif path == '/api/health':
            self._serve_health()
        elif path == '/' or path == '':
            # Redirect / to dashboard.html
            self.send_response(302)
            self.send_header('Location', '/dashboard.html')
            self.end_headers()
        else:
            # Serve static files (dashboard.html, etc.)
            super().do_GET()

    def _serve_latest_report(self):
        """Serve reports/latest.json as JSON."""
        latest_path = Path(GenesisQAHandler._reports_dir) / 'latest.json'

        if not latest_path.exists():
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'error': 'latest.json not found',
                'path': str(latest_path),
                'hint': 'Run some tests first to generate a report.'
            }).encode('utf-8'))
            return

        try:
            with open(latest_path, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'error': 'Invalid JSON in latest.json',
                'detail': str(e)
            }).encode('utf-8'))
            return
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'error': 'Failed to read report',
                'detail': str(e)
            }).encode('utf-8'))
            return

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def _serve_health(self):
        """Health check endpoint."""
        latest_path = Path(GenesisQAHandler._reports_dir) / 'latest.json'
        report_exists = latest_path.exists()
        report_age = None
        if report_exists:
            try:
                mtime = os.path.getmtime(latest_path)
                report_age = datetime.now() - datetime.fromtimestamp(mtime)
                report_age = f"{report_age.seconds // 3600}h {(report_age.seconds // 60) % 60}m"
            except Exception:
                report_age = 'unknown'

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({
            'status': 'ok',
            'service': 'genesis-qa-server',
            'timestamp': datetime.now().isoformat(),
            'report': {
                'exists': report_exists,
                'path': str(latest_path),
                'age': report_age
            }
        }).encode('utf-8'))

    def log_message(self, format, *args):
        """Override with timestamped logging."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sys.stderr.write(f'[{timestamp}] {args[0]} {args[1]} {args[2]}\n')


def create_report_sample(reports_dir):
    """Create a sample latest.json so dashboard has data to display."""
    sample = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "system": "genesis-qa",
            "total_tests": 4
        },
        "summary": {
            "total": 4,
            "pass": 2,
            "fail": 1,
            "warn": 1
        },
        "results": [
            {
                "endpoint": "/api/students",
                "method": "GET",
                "status": "PASS",
                "response_time": 145,
                "timestamp": datetime.now().isoformat()
            },
            {
                "endpoint": "/api/auth/login",
                "method": "POST",
                "status": "PASS",
                "response_time": 230,
                "timestamp": datetime.now().isoformat()
            },
            {
                "endpoint": "/api/payments/process",
                "method": "POST",
                "status": "FAIL",
                "response_time": 5200,
                "timestamp": datetime.now().isoformat(),
                "error": "Gateway timeout — upstream server tidak merespon dalam 5 detik"
            },
            {
                "endpoint": "/api/schedule/sync",
                "method": "PUT",
                "status": "WARN",
                "response_time": 1890,
                "timestamp": datetime.now().isoformat(),
                "warning": "Response time mendekati threshold (2s)"
            }
        ]
    }

    reports_dir.mkdir(parents=True, exist_ok=True)
    sample_path = reports_dir / 'latest.json'
    with open(sample_path, 'w') as f:
        json.dump(sample, f, indent=2)
    print(f'[INFO] Sample report created: {sample_path}')
    return sample_path


def main():
    parser = argparse.ArgumentParser(description='Genesis-QA Dashboard Server')
    parser.add_argument('--port', type=int, default=8000,
                        help='Port to listen on (default: 8000)')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                        help='Host to bind (default: 0.0.0.0)')
    parser.add_argument('--reports', type=str, default=None,
                        help='Path to reports directory (default: ../reports)')
    parser.add_argument('--create-sample', action='store_true',
                        help='Create sample latest.json if none exists')
    args = parser.parse_args()

    # Resolve reports directory
    script_dir = Path(__file__).resolve().parent
    if args.reports:
        reports_dir = Path(args.reports).resolve()
    else:
        reports_dir = script_dir.parent / 'reports'

    # Create sample report if requested
    if args.create_sample:
        create_report_sample(reports_dir)

    # Store reports_dir as module-level attribute for handler
    handler = GenesisQAHandler
    handler._reports_dir = reports_dir

    # We need to pass reports_dir to the handler via a factory
    class HandlerFactory(GenesisQAHandler):
        def __init__(self, *args, **kwargs):
            kwargs['reports_dir'] = reports_dir
            super().__init__(*args, **kwargs)

    server = HTTPServer((args.host, args.port), HandlerFactory)

    print(f'')
    print(f'  ╔═════════════════════════════════════════╗')
    print(f'  ║        Genesis-QA Dashboard Server      ║')
    print(f'  ╠═════════════════════════════════════════╣')
    print(f'  ║  URL:  http://{args.host}:{args.port}            ║')
    print(f'  ║  API:  /api/latest-report               ║')
    print(f'  ║  Docs: /api/health                       ║')
    print(f'  ║  Reports: {str(reports_dir):28s} ║')
    print(f'  ╚═════════════════════════════════════════╝')
    print(f'')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[INFO] Server stopped.')
        server.server_close()


if __name__ == '__main__':
    main()
