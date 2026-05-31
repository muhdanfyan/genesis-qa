#!/usr/bin/env bash
# =============================================================================
# Genesis QA - Cron Runner
# =============================================================================
# Bash script intended to be run as a cron job. It executes the full QA
# pipeline and outputs JSON + HTML reports, then sends a notification.
#
# Usage in crontab (every 6 hours):
#   0 */6 * * * /home/pondokinformatika/genesis-qa/scheduler/cron_runner.sh
#
# Environment variables (set in crontab or .env):
#   GENESIS_QA_DIR    — Path to genesis-qa directory (default: ~/genesis-qa)
#   PISANTRI_ADMIN_PASSWORD — Admin password for PISANTRI API
#   PISANTRI_USER_PASSWORD  — User password for PISANTRI API
#   WA_API_URL        — WhatsApp Business API endpoint (optional)
#   WA_API_KEY        — WhatsApp API key (optional)
#   WA_TO_NUMBER      — Recipient phone number (optional)
# =============================================================================

set -euo pipefail

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GENESIS_QA_DIR="${GENESIS_QA_DIR:-${SCRIPT_DIR}/..}"
SYSTEM="${1:-pisantri}"
MODE="${2:-full}"
OUTPUT="${3:-json}"
NOTIFY="${4:-true}"

REPORT_DIR="${GENESIS_QA_DIR}/report"
LOG_DIR="${GENESIS_QA_DIR}/report/logs"
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
LOGFILE="${LOG_DIR}/cron_${SYSTEM}_${TIMESTAMP}.log"

# ------------------------------------------------------------------
# Bootstrap
# ------------------------------------------------------------------

mkdir -p "${LOG_DIR}"

# Redirect all output to log file (and optionally to terminal)
exec > "${LOGFILE}" 2>&1

echo "============================================"
echo " Genesis QA Cron Run"
echo " Timestamp: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo " System:    ${SYSTEM}"
echo " Mode:      ${MODE}"
echo " Output:    ${OUTPUT}"
echo " Notify:    ${NOTIFY}"
echo " Directory: ${GENESIS_QA_DIR}"
echo "============================================"
echo ""

# ------------------------------------------------------------------
# Environment Check
# ------------------------------------------------------------------

if [ ! -d "${GENESIS_QA_DIR}" ]; then
    echo "ERROR: Genesis QA directory not found: ${GENESIS_QA_DIR}"
    exit 1
fi

if [ ! -f "${GENESIS_QA_DIR}/run.py" ]; then
    echo "ERROR: run.py not found in ${GENESIS_QA_DIR}"
    exit 1
fi

# ------------------------------------------------------------------
# Dependencies Check
# ------------------------------------------------------------------

echo "Checking Python dependencies..."

python3 -c "import requests, yaml" 2>/dev/null || {
    echo "Installing missing dependencies..."
    pip3 install --quiet requests pyyaml 2>&1
}

echo "All dependencies available."
echo ""

# ------------------------------------------------------------------
# Run Tests
# ------------------------------------------------------------------

cd "${GENESIS_QA_DIR}"

CMD="python3 run.py --system ${SYSTEM} --mode ${MODE} --output ${OUTPUT}"

if [ "${NOTIFY}" = "true" ]; then
    CMD="${CMD} --notify"
fi

echo "Running: ${CMD}"
echo ""

${CMD}
EXIT_CODE=$?

echo ""
echo "============================================"
echo " Run completed with exit code: ${EXIT_CODE}"
echo " Log file: ${LOGFILE}"
echo "============================================"

exit ${EXIT_CODE}
