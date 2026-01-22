#!/usr/bin/env bash
set -euo pipefail

# Verify Phase2.5 "tools packages" can be installed and imported without relying
# on `PYTHONPATH=backend` (i.e., via pip-installable runtime/tools packages).

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.tmp/tools_packages_venv"

rm -rf "${VENV_DIR}"
python3 -m venv "${VENV_DIR}"

"${VENV_DIR}/bin/python" -m pip install -U pip setuptools wheel >/dev/null

# Install packages from local paths (simulates what CI does).
"${VENV_DIR}/bin/python" -m pip install "${ROOT_DIR}" >/dev/null
"${VENV_DIR}/bin/python" -m pip install "${ROOT_DIR}/backend" >/dev/null
"${VENV_DIR}/bin/python" -m pip install "${ROOT_DIR}/tools/graphrag_agent_build" >/dev/null
"${VENV_DIR}/bin/python" -m pip install "${ROOT_DIR}/tools/graphrag_agent_evaluation" >/dev/null

"${VENV_DIR}/bin/python" - <<'PY'
import importlib

import graphrag_agent  # core
import server  # runtime
import infrastructure  # runtime
import application  # runtime
import domain  # runtime
import config  # runtime
import graphrag_agent_build  # tools
import graphrag_agent_evaluation  # tools

# Legacy build path should remain importable when build package is installed.
importlib.import_module("infrastructure.integrations.build.main")

print("OK: core/runtime/tools packages importable without PYTHONPATH")
PY

