#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="/apps/svr/python3/bin/python3"

if [ ! -x "${PYTHON_BIN}" ]; then
  echo "[ERROR] Python not found: ${PYTHON_BIN}"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# Prefer project backend requirements, fallback to packaged dist requirements.
REQ_FILE=""
if [ -f "${PROJECT_ROOT}/backend/requirements.txt" ]; then
  REQ_FILE="${PROJECT_ROOT}/backend/requirements.txt"
elif [ -f "${PROJECT_ROOT}/requirements.txt" ]; then
  REQ_FILE="${PROJECT_ROOT}/requirements.txt"
fi

if [ -z "${REQ_FILE}" ]; then
  echo "[ERROR] requirements.txt not found."
  echo "Checked:"
  echo "  - ${PROJECT_ROOT}/backend/requirements.txt"
  echo "  - ${PROJECT_ROOT}/requirements.txt"
  exit 1
fi

echo "[INFO] Installing dependencies from: ${REQ_FILE}"
"${PYTHON_BIN}" -m pip install --upgrade pip
"${PYTHON_BIN}" -m pip install -r "${REQ_FILE}"

echo "[INFO] Dependency installation completed."
