#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
if [[ -x .runtime/bin/Rscript ]]; then
  export PATH="$project_dir/.runtime/bin:$PATH"
  export PROJ_DATA="$project_dir/.runtime/share/proj"
  export GDAL_DATA="$project_dir/.runtime/share/gdal"
fi
if ! command -v Rscript >/dev/null; then
  echo 'Falta R. Ejecuta npm run setup:r o instala las dependencias de environment.yml.' >&2
  exit 1
fi
python3 scripts/prepare_report.py
Rscript scripts/render.R
python3 scripts/build_public.py
