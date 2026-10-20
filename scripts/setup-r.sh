#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
python3 - <<'PY'
from pathlib import Path
import hashlib
import platform
import tarfile
import urllib.request

if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
    raise SystemExit('Este instalador es para Linux x86_64. En otros sistemas instala las dependencias de environment.yml con conda/mamba o R y CRAN.')
root = Path('.tools')
binary = root / 'bin/micromamba'
archive = root / 'micromamba-2.9.0-0.tar.bz2'
expected = '8761c382127e6363bd9e0a2451aa3ef90d071a79133f736e2f759a3bf13040dd'
root.mkdir(exist_ok=True)
if not archive.exists():
    urllib.request.urlretrieve('https://conda.anaconda.org/conda-forge/linux-64/' + archive.name, archive)
if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
    raise SystemExit('La suma SHA-256 de micromamba no coincide. No se ejecutó el archivo.')
with tarfile.open(archive) as package:
    package.extract('bin/micromamba', root, filter='data')
print('Micromamba: SHA-256 verificado.')
PY
export MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$project_dir/.tools/mamba}"
export CONDA_PKGS_DIRS="${CONDA_PKGS_DIRS:-$project_dir/.tools/pkgs}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$project_dir/.tools/cache}"
if [[ -f "$project_dir/.runtime/conda-meta/history" ]]; then
  .tools/bin/micromamba install --yes --safety-checks enabled --prefix "$project_dir/.runtime" --file environment.yml
else
  .tools/bin/micromamba create --yes --safety-checks enabled --prefix "$project_dir/.runtime" --file environment.yml
fi
export PROJ_DATA="$project_dir/.runtime/share/proj"
export GDAL_DATA="$project_dir/.runtime/share/gdal"
.runtime/bin/Rscript -e 'pkgs <- c("rmarkdown", "DBI", "RSQLite", "jsonlite", "readxl", "dplyr", "stringr", "lubridate", "purrr", "sf", "leaflet", "htmlwidgets", "tidyr"); stopifnot(all(vapply(pkgs, requireNamespace, logical(1), quietly=TRUE))); stopifnot(!is.na(sf::st_crs(4326))); cat("R Markdown, Excel y cartografía listos\n")'
