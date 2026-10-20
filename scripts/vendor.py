"""Prepara dependencias verificadas para construir Docker sin descargar paquetes."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request

from packaging.utils import parse_wheel_filename

ROOT = Path(__file__).resolve().parents[1]


def main():
    tools = ROOT / '.tools'
    tools.mkdir(exist_ok=True)
    target = ROOT / 'vendor/wheels'
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=tools) as temporary:
        subprocess.run([sys.executable, '-m', 'pip', 'download', '--only-binary=:all:', '--cache-dir', str(tools/'pip-cache'), '--dest', temporary, '-r', str(ROOT/'requirements.txt')], check=True)
        lock = []
        for wheel in sorted(Path(temporary).glob('*.whl')):
            name, version, _, _ = parse_wheel_filename(wheel.name)
            with urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json', timeout=30) as response:
                release = json.load(response)
            expected = next(item['digests']['sha256'] for item in release['urls'] if item['filename'] == wheel.name)
            digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
            if digest != expected:
                raise RuntimeError('La suma SHA-256 no coincide; no se utilizará el paquete.')
            shutil.copyfile(wheel, target/wheel.name)
            lock.append(f'{name}=={version} --hash=sha256:{digest}')
        (target/'requirements.lock').write_text('\n'.join(lock)+'\n')
    print('Dependencias para Docker verificadas contra las sumas SHA-256 publicadas por PyPI.')


if __name__ == '__main__':
    main()
