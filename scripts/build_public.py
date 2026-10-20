"""Ensambla exclusivamente los datos ya agregados y las bibliotecas públicas."""
from pathlib import Path
import json
import os
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    payload = json.loads((ROOT / 'build/public-payload.json').read_text(encoding='utf-8'))
    allowed = {'schema_version', 'territory', 'min_year', 'max_year', 'threshold', 'rounding', 'period_years', 'census_agebs', 'positive_population_agebs', 'periods', 'metrics', 'geometry', 'cells'}
    if set(payload) != allowed:
        raise ValueError('La estructura del archivo público contiene campos inesperados.')
    for feature in payload['geometry']['features']:
        if set(feature['properties']) - {'code', 'ageb', 'municipality', 'locality', 'population'}:
            raise ValueError('Se encontraron atributos no autorizados en la geometría pública.')
    for metric in payload['cells'].values():
        for cells in metric.values():
            for cell in cells:
                if set(cell) != {'code', 'count', 'rate', 'suppressed'}:
                    raise ValueError('Se encontraron datos no autorizados en una celda pública.')
                if cell['suppressed'] and (cell['count'] is not None or cell['rate'] is not None):
                    raise ValueError('Una celda suprimida conserva su valor.')
                if not cell['suppressed'] and (cell['count'] < 5 or cell['count'] % 5 != 0):
                    raise ValueError('Un conteo publicado no cumple la política de redondeo.')
    leaflet = ROOT / 'node_modules/leaflet/dist'
    replacements = {
        '__LEAFLET_CSS__': (leaflet / 'leaflet.css').read_text(),
        '__LEAFLET_JS__': (leaflet / 'leaflet.js').read_text().replace('//# sourceMappingURL=leaflet.js.map', ''),
        '__PUBLIC_CSS__': (ROOT / 'web/public.css').read_text(),
        '__PUBLIC_JS__': (ROOT / 'web/public.js').read_text(),
        '__PUBLIC_DATA__': json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c'),
    }
    html = (ROOT / 'web/public.html').read_text()
    for key, value in replacements.items():
        if html.count(key) != 1:
            raise ValueError('La plantilla pública cambió: ' + key)
        html = html.replace(key, value)
    directory = ROOT / 'dist/public'
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=directory, suffix='.html')
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        handle.write(html)
    os.replace(temporary, directory / 'index.html')
    print('Versión pública generada: solo polígonos y celdas agregadas con supresión y redondeo.')


if __name__ == '__main__':
    main()
