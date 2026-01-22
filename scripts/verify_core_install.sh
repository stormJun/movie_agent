#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.tmp/core_install_venv"

rm -rf "${VENV_DIR}"
python3 -m venv "${VENV_DIR}"

"${VENV_DIR}/bin/python" -m pip install -U pip setuptools wheel

# Install the core package from the current checkout.
"${VENV_DIR}/bin/python" -m pip install "${ROOT_DIR}"

CHECK_DIR="${ROOT_DIR}/.tmp/core_install_check_cwd"
mkdir -p "${CHECK_DIR}"

(
  cd "${CHECK_DIR}"
  "${VENV_DIR}/bin/python" -c "import graphrag_agent as core; print('OK:', core.__version__)"
  "${VENV_DIR}/bin/python" "${ROOT_DIR}/scripts/verify_core_import.py"
)
