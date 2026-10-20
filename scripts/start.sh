#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
if [[ ! -x .app-runtime/bin/python ]]; then
  echo 'Ejecuta npm run setup:app para preparar el servidor.' >&2
  exit 1
fi
exec .app-runtime/bin/python -m app.dev "$@"
