"""Prepara o comprueba la carpeta exclusiva de GitHub Pages; no lee datos clínicos."""
from html.parser import HTMLParser
from pathlib import Path
import argparse
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = {'index.html', '.nojekyll', 'LEAFLET-LICENSE.txt', 'release.json'}
FIELDS = {'schema_version', 'territory', 'min_year', 'max_year', 'threshold',
          'rounding', 'period_years', 'census_agebs', 'positive_population_agebs',
          'periods', 'metrics', 'geometry', 'cells'}


class PublicData(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.payloads = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'script':
            if attrs.get('src') or attrs.get('data-for'):
                raise ValueError('El sitio público no debe cargar scripts externos ni widgets clínicos.')
            self.capture = attrs.get('id') == 'public-data' and attrs.get('type') == 'application/json'

    def handle_data(self, data):
        if self.capture:
            self.payloads.append(data)

    def handle_endtag(self, tag):
        if tag == 'script':
            self.capture = False


def validate(html):
    parser = PublicData()
    parser.feed(html)
    if len(parser.payloads) != 1:
        raise ValueError('Se esperaba un único bloque público de resultados.')
    data = json.loads(parser.payloads[0])
    if set(data) != FIELDS or data['threshold'] != 5 or data['rounding'] != 5:
        raise ValueError('La estructura o la política de publicación cambió.')
    if set(data['cells']) != {'total', 'incidence', 'active'}:
        raise ValueError('Los indicadores públicos no coinciden.')
    if data['geometry']['type'] != 'FeatureCollection':
        raise ValueError('La geometría pública debe ser una colección de polígonos.')
    for feature in data['geometry']['features']:
        if feature['geometry']['type'] not in ('Polygon', 'MultiPolygon'):
            raise ValueError('Se encontró geometría individual en el sitio público.')
        if set(feature['properties']) != {'code', 'ageb', 'municipality', 'locality', 'population'}:
            raise ValueError('Se encontraron atributos no autorizados en el mapa.')
    for periods in data['cells'].values():
        for cells in periods.values():
            for cell in cells:
                if set(cell) != {'code', 'count', 'rate', 'suppressed'}:
                    raise ValueError('La publicación contiene campos no autorizados.')
                if cell['suppressed']:
                    if cell['count'] is not None or cell['rate'] is not None:
                        raise ValueError('Una celda protegida conserva sus valores.')
                elif not isinstance(cell['count'], int) or cell['count'] < 5 or cell['count'] % 5:
                    raise ValueError('Un conteo no cumple la política pública.')
    if 'https://a.basemaps.cartocdn.com/light_all/' not in html or 'tile.openstreetmap.org' in html:
        raise ValueError('El mapa público debe utilizar CARTO Positron.')
    return data


def main():
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument('--check', action='store_true', help='Solo valida docs/, sin compilar ni copiar.')
    args = arguments.parse_args()
    directory = ROOT / 'docs'
    if not args.check:
        source = ROOT / 'dist/public/index.html'
        data = validate(source.read_text(encoding='utf-8'))
        directory.mkdir(exist_ok=True)
        shutil.copyfile(source, directory / 'index.html')
        shutil.copyfile(ROOT / 'node_modules/leaflet/LICENSE', directory / 'LEAFLET-LICENSE.txt')
        (directory / '.nojekyll').touch()
        metadata = {'variant': 'public', 'basemap': 'CARTO Positron',
                    'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                    'census_agebs': data['census_agebs'], 'threshold': 5, 'rounding': 5}
        (directory / 'release.json').write_text(json.dumps(metadata, indent=2) + '\n')
    if {path.name for path in directory.iterdir()} != PUBLIC_FILES:
        raise ValueError('docs/ contiene archivos ajenos a la entrega pública.')
    if any(path.is_symlink() or not path.is_file() for path in directory.iterdir()):
        raise ValueError('La carpeta pública solo admite archivos regulares.')
    validate((directory / 'index.html').read_text(encoding='utf-8'))
    metadata = json.loads((directory / 'release.json').read_text())
    if metadata['variant'] != 'public' or metadata['sha256'] != hashlib.sha256((directory / 'index.html').read_bytes()).hexdigest():
        raise ValueError('La versión pública no coincide con su manifiesto.')
    print('GitHub Pages: solo HTML público agregado, licencia y manifiesto; CARTO configurado.')


if __name__ == '__main__':
    main()
