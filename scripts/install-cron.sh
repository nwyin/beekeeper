#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_BIN="${PROJECT_DIR}/.venv/bin"
STATE_DIR="${HOME}/.beekeeper"
LOG_DIR="${STATE_DIR}/logs"
ENV_FILE="${STATE_DIR}/.env"
CRON_ENTRY="0 1 * * * . ${ENV_FILE} && ${VENV_BIN}/beekeeper run >> ${LOG_DIR}/cron.log 2>&1"

mkdir -p "$LOG_DIR"

# Check if entry already exists
if crontab -l 2>/dev/null | grep -qF "beekeeper run"; then
    echo "Cron entry already exists:"
    crontab -l | grep "beekeeper run"
    echo ""
    echo "To remove it: crontab -e"
    exit 0
fi

# Append to existing crontab
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo "Installed cron entry:"
echo "  $CRON_ENTRY"
echo ""
echo "Verify with: crontab -l"
