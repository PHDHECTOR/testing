#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
mkdir -p build
.app-runtime/bin/python -m unittest discover -s tests -v 2>&1 | tee build/dual-tests-final.log
