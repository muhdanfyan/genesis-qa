#!/usr/bin/env bash
# =============================================================================
# run-qa.sh — Genesis QA Pipeline Wrapper
# =============================================================================
# Helper script that sets environment variables before invoking run.py.
#
# Usage:
#   export QA_SYSTEM=pisantri
#   export QA_MODE=execute
#   export QA_OUTPUT=json
#   ./run-qa.sh
#
# Environment variables (with defaults):
#   QA_SYSTEM    - System name in config/systems/ (default: pisantri)
#   QA_MODE      - Pipeline mode: explore | generate | execute | full (default: execute)
#   QA_OUTPUT    - Report format: console | json | html | all (default: json)
#   QA_EXTRA     - Additional arguments passed through to run.py (optional)
#
# Secrets injected via GitHub Actions or .env:
#   PISANTRI_USER_PASSWORD
#   PISANTRI_DB_URL
# =============================================================================

set -euo pipefail

# ---- Resolve project root ------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${PROJECT_ROOT}"

# ---- Defaults ------------------------------------------------------------
QA_SYSTEM="${QA_SYSTEM:-pisantri}"
QA_MODE="${QA_MODE:-execute}"
QA_OUTPUT="${QA_OUTPUT:-json}"
QA_EXTRA="${QA_EXTRA:-}"

# ---- Print banner --------------------------------------------------------
echo "=============================================================================="
echo "  Genesis QA Pipeline"
echo "=============================================================================="
echo "  System:   ${QA_SYSTEM}"
echo "  Mode:     ${QA_MODE}"
echo "  Output:   ${QA_OUTPUT}"
echo "  Workdir:  ${PROJECT_ROOT}"
echo "=============================================================================="

# ---- Validate config file exists -----------------------------------------
CONFIG_FILE="config/systems/${QA_SYSTEM}.yaml"
if [ ! -f "${CONFIG_FILE}" ]; then
  echo "ERROR: Configuration file not found: ${CONFIG_FILE}"
  echo "Available systems:"
  ls -1 config/systems/*.yaml 2>/dev/null || echo "  (none)"
  exit 1
fi

# ---- Create reports directory --------------------------------------------
mkdir -p reports

# ---- Run the pipeline ----------------------------------------------------
echo ""
echo ">>> Running: python run.py --system ${QA_SYSTEM} --mode ${QA_MODE} --output ${QA_OUTPUT} ${QA_EXTRA}"
echo ""

python run.py \
  --system "${QA_SYSTEM}" \
  --mode "${QA_MODE}" \
  --output "${QA_OUTPUT}" \
  ${QA_EXTRA}

EXIT_CODE=$?

echo ""
echo "=============================================================================="
if [ ${EXIT_CODE} -eq 0 ]; then
  echo "  RESULT: PASSED (exit code ${EXIT_CODE})"
else
  echo "  RESULT: FAILED (exit code ${EXIT_CODE})"
fi
echo "=============================================================================="

exit ${EXIT_CODE}
