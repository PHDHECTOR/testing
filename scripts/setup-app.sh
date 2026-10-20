#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
if [[ ! -x .app-runtime/bin/python ]]; then
  python3 -m venv .app-runtime
fi
.app-runtime/bin/python -m pip install --cache-dir .tools/pip-cache -r requirements.txt -r requirements-dev.txt
