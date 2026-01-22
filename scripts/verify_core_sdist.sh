#!/usr/bin/env bash
set -euo pipefail

# Phase2.5: ensure the sdist is core-only (doesn't ship the monorepo) and is installable.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/.tmp/core_sdist_dist"
VENV_DIR="${ROOT_DIR}/.tmp/core_sdist_venv"
CHECK_DIR="${ROOT_DIR}/.tmp/core_sdist_check_cwd"

rm -rf "${OUT_DIR}" "${VENV_DIR}" "${CHECK_DIR}"
mkdir -p "${OUT_DIR}" "${CHECK_DIR}"

# Build sdist using setuptools (no extra build tooling).
(cd "${ROOT_DIR}" && python3 setup.py sdist --dist-dir "${OUT_DIR}" >/dev/null)

SDIST_TGZ="$(ls -1 "${OUT_DIR}"/*.tar.gz | head -n 1)"
echo "Built sdist: ${SDIST_TGZ}"

# Validate the archive doesn't include large monorepo folders.
python3 - <<'PY' "${SDIST_TGZ}"
import sys
import tarfile

tgz = sys.argv[1]
bad_prefixes = (
    # Allow `backend/graphrag_agent/**` but reject other backend subpackages.
    "backend/application/",
    "backend/config/",
    "backend/domain/",
    "backend/infrastructure/",
    "backend/server/",
    "backend/cache/",
    "server/",
    "frontend/",
    "frontend-react/",
    "docs/",
    "tools/",
    "datasets/",
    "data/",
    "files/",
    "cache/",
    "logs/",
    "training/",
    "SparrowRecSys-master/",
    "test/",
)

with tarfile.open(tgz, "r:gz") as tf:
    names = tf.getnames()

hits = []
for n in names:
    # Strip top-level project dir inside tarball, e.g. graphrag-agent-0.1.0/...
    parts = n.split("/", 1)
    rel = parts[1] if len(parts) == 2 else parts[0]
    for bp in bad_prefixes:
        if rel.startswith(bp):
            hits.append(rel)
            break

if hits:
    sample = "\\n".join(hits[:20])
    raise SystemExit(f"sdist unexpectedly includes monorepo content (sample):\\n{sample}")

print("OK: sdist content boundary")
PY

# Install from sdist into a clean venv, then run core import verifier.
python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/python" -m pip install -U pip setuptools wheel >/dev/null

(
  cd "${CHECK_DIR}"
  "${VENV_DIR}/bin/python" -m pip install "${SDIST_TGZ}" >/dev/null
  "${VENV_DIR}/bin/python" -c "import graphrag_agent as core; print('OK:', core.__version__)"
  "${VENV_DIR}/bin/python" "${ROOT_DIR}/scripts/verify_core_import.py"
)

echo "OK: sdist install + core imports"
