# Genesis QA — Automated Quality Assurance Pipeline

A modular, extensible QA pipeline for web APIs and websites. Built for the Pondok Informatika ecosystem — tests the PISANTRI API, the main website, and any other configured system.

## Features

- **Modular test engines**: HTTP, CORS, Auth, Redirect, Security, Database
- **Three pipeline modes**: Explore (discover endpoints), Generate (create scenarios), Execute (run tests)
- **Multiple report formats**: Console (color-coded terminal table), JSON (structured), HTML (filterable, responsive)
- **WhatsApp notifications**: Concise failure reports, saved locally when no API is configured
- **Cron-ready**: Shell script for scheduled runs
- **Extensible**: Add new engines, systems, and reporters easily

## Requirements

- Python 3.10+
- `pip install requests pyyaml` (or `pip install -r requirements.txt`)

Optional:
- `pip install sqlalchemy` — for database engine tests
- `pip install aiohttp` — for the scan module (endpoint scanner, security scanner, crawler)

## Installation

```bash
# Clone the repository
git clone <repo-url> genesis-qa
cd genesis-qa

# Install dependencies
pip install requests pyyaml

# Optional: database testing
pip install sqlalchemy

# Optional: async scanning modules
pip install aiohttp
```

## Usage

### Basic commands

```bash
# Run all tests against PISANTRI API (default mode: full)
python run.py --system pisantri

# Run only the execute phase
python run.py --system pisantri --mode execute

# Explore endpoints from config
python run.py --system pondokinformatika --mode explore

# Generate test scenarios
python run.py --system pisantri --mode generate

# Run full pipeline, output JSON + HTML, send notification
python run.py --system pisantri --mode full --output all --notify

# Run and save HTML report
python run.py --system pisantri --mode execute --output html
```

### Pipeline modes

| Mode      | Description |
|-----------|-------------|
| `explore` | Crawl the system and discover endpoints based on configuration |
| `generate` | Create structured test scenarios from endpoint definitions |
| `execute` | Run test scenarios against the system (HTTP, auth, CORS, security, redirects, DB) |
| `full` | Run all three phases sequentially (default) |

### Output formats

| Format    | Description |
|-----------|-------------|
| `console` | Tabular output to terminal with ANSI color coding (default) |
| `json`    | Structured JSON file in `report/` directory |
| `html`    | Self-contained HTML report with inline CSS, cards, filterable table |
| `all`     | Generate all formats |

## Project Structure

```
genesis-qa/
├── run.py                         # Main entry point
├── README.md                      # This file
├── __init__.py
│
├── test/                          # Test engines
│   ├── __init__.py                # Package exports
│   ├── base_engine.py             # BaseEngine, TestResult, ScenarioConfig
│   ├── http_engine.py             # HTTP request engine with retry & timing
│   ├── cors_engine.py             # CORS configuration tester
│   ├── auth_engine.py             # Authentication & RBAC tester
│   ├── redirect_engine.py         # Redirect chain & loop detector
│   ├── security_engine.py         # Security headers & info disclosure
│   └── db_engine.py               # Database connection & schema tester
│
├── report/                        # Report generators
│   ├── console_reporter.py        # Terminal table output
│   ├── json_reporter.py           # Structured JSON output
│   └── html_reporter.py           # Self-contained HTML report
│
├── config/
│   └── systems/                   # System configurations (YAML)
│       ├── pisantri.yaml          # PISANTRI API config
│       └── pondokinformatika.yaml # Website landing page config
│
├── notify/
│   └── whatsapp.py                # WhatsApp notification formatter
│
├── scheduler/
│   └── cron_runner.sh             # Bash script for cron jobs
│
├── scan/                          # Scanning modules (async, uses aiohttp)
│   ├── crawler.py                 # Web crawler
│   ├── endpoint_scanner.py        # Endpoint discovery
│   └── security_scanner.py        # Security vulnerability scanning
│
└── generate/                      # Scenario generation (uses random)
    ├── scenario_generator.py      # Test scenario generator
    └── edge_case_factory.py       # Edge case creator
```

## Adding a New System

1. Create `config/systems/<name>.yaml` with the following structure:

```yaml
system:
  name: "My System"
  type: "api"  # or "website"
  base_url: "https://api.example.com"

endpoints:
  health:
    path: "/health"
    method: "GET"
    expected_status: [200]
  users:
    list: { path: "/users", method: "GET", expected_status: [200] }
    create: { path: "/users", method: "POST", expected_status: [201] }

security:
  test_cors: false
  test_headers: true
  test_redirects: true
  test_disclosure: true
  test_directory_listing: false

database:
  enabled: false
```

2. Run it:

```bash
python run.py --system my-system --mode execute
```

## Setting Up a Cron Job

Edit your crontab (`crontab -e`) and add:

```cron
# Run every 6 hours
0 */6 * * * /home/pondokinformatika/genesis-qa/scheduler/cron_runner.sh pisantri full json true

# Run website tests daily at 8 AM
0 8 * * * /home/pondokinformatika/genesis-qa/scheduler/cron_runner.sh pondokinformatika execute html false
```

The cron script creates logs in `report/logs/` and auto-installs missing Python dependencies.

### Environment variables for cron

Set these in your crontab or a `.env` file:

```
GENESIS_QA_DIR=/home/pondokinformatika/genesis-qa
PISANTRI_ADMIN_PASSWORD=<your-admin-password>
PISANTRI_USER_PASSWORD=<your-user-password>
WA_API_URL=https://api.whatsapp.com/v1/messages
WA_API_KEY=<your-api-key>
WA_TO_NUMBER=+6281234567890
```

## Extending

### Adding a new test engine

1. Create `test/my_engine.py` with a class that inherits from `BaseEngine`.
2. Implement the `run(scenario: ScenarioConfig) -> TestResult` method.
3. Add the import to `test/__init__.py`.
4. Instantiate and use it in `run.py`'s `run_execute()` function.

### Adding a new reporter

1. Create `report/my_reporter.py` with a class that has a `report()` method.
2. Add the reporter import and call in `run.py`'s `run_report()` function.

## License

Internal use — Pondok Informatika
